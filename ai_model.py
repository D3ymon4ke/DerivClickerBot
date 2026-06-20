import os
import json
import numpy as np

# Tenta importar PyTorch para aceleração por GPU, caso contrário usará NumPy nativo
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ==========================================
# 1. MOTOR DE REDE NEURAL EM NUMPY (CPU FALLBACK)
# ==========================================
class NumpyMLP:
    """
    Uma rede neural de 3 camadas (15 -> 32 -> 16 -> 1) implementada puramente em NumPy
    com ReLU nas camadas ocultas e Sigmoid na saída.
    """
    def __init__(self, input_size=20, hidden1=32, hidden2=16):
        self.input_size = input_size
        self.hidden1 = hidden1
        self.hidden2 = hidden2
        
        # Pesos da camada de Atenção (Gate)
        self.Wa = np.random.randn(input_size, input_size) * np.sqrt(2.0 / input_size)
        self.ba = np.zeros((1, input_size))
        
        # Inicialização He (MSRA) para ReLU
        self.W1 = np.random.randn(input_size, hidden1) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden1))
        
        self.W2 = np.random.randn(hidden1, hidden2) * np.sqrt(2.0 / hidden1)
        self.b2 = np.zeros((1, hidden2))
        
        self.W3 = np.random.randn(hidden2, 1) * np.sqrt(2.0 / hidden2)
        self.b3 = np.zeros((1, 1))
        
        # Variáveis de estado do Otimizador Adam
        self.t = 0
        self.m_Wa = np.zeros_like(self.Wa)
        self.v_Wa = np.zeros_like(self.Wa)
        self.m_ba = np.zeros_like(self.ba)
        self.v_ba = np.zeros_like(self.ba)
        
        self.m_W1 = np.zeros_like(self.W1)
        self.v_W1 = np.zeros_like(self.W1)
        self.m_b1 = np.zeros_like(self.b1)
        self.v_b1 = np.zeros_like(self.b1)
        
        self.m_W2 = np.zeros_like(self.W2)
        self.v_W2 = np.zeros_like(self.W2)
        self.m_b2 = np.zeros_like(self.b2)
        self.v_b2 = np.zeros_like(self.b2)
        
        self.m_W3 = np.zeros_like(self.W3)
        self.v_W3 = np.zeros_like(self.W3)
        self.m_b3 = np.zeros_like(self.b3)
        self.v_b3 = np.zeros_like(self.b3)

    def _relu(self, x):
        return np.maximum(0, x)

    def _relu_deriv(self, x):
        return (x > 0).astype(float)

    def _sigmoid(self, x):
        # Clip para evitar overflow de exp
        x = np.clip(x, -500, 500)
        return 1.0 / (1.0 + np.exp(-x))

    def _adam_update(self, param, grad, m, v, lr, beta1=0.9, beta2=0.999, eps=1e-8):
        m = beta1 * m + (1.0 - beta1) * grad
        v = beta2 * v + (1.0 - beta2) * (grad ** 2)
        m_hat = m / (1.0 - beta1 ** self.t)
        v_hat = v / (1.0 - beta2 ** self.t)
        param -= lr * m_hat / (np.sqrt(v_hat) + eps)
        return m, v

    def forward(self, X):
        # X shape: (batch_size, input_size)
        # Camada de Atenção Gate
        self.z_a = np.dot(X, self.Wa) + self.ba
        self.attn = self._sigmoid(self.z_a)
        self.X_attn = X * self.attn
        
        # Camadas ocultas e saída
        self.z1 = np.dot(self.X_attn, self.W1) + self.b1
        self.a1 = self._relu(self.z1)
        
        self.z2 = np.dot(self.a1, self.W2) + self.b2
        self.a2 = self._relu(self.z2)
        
        self.z3 = np.dot(self.a2, self.W3) + self.b3
        self.a3 = self._sigmoid(self.z3)
        return self.a3

    def backward(self, X, y, lr=0.01):
        # X: (batch_size, input_size)
        # y: (batch_size, 1)
        m = X.shape[0]
        
        # Forward pass para atualizar estados internos
        out = self.forward(X)
        
        # Backpropagation
        # Gradiente da perda BCE em relação à saída (a3)
        dz3 = out - y
        dW3 = np.dot(self.a2.T, dz3) / m
        db3 = np.sum(dz3, axis=0, keepdims=True) / m
        
        # dL/da2
        da2 = np.dot(dz3, self.W3.T)
        dz2 = da2 * self._relu_deriv(self.z2)
        dW2 = np.dot(self.a1.T, dz2) / m
        db2 = np.sum(dz2, axis=0, keepdims=True) / m
        
        # dL/da1
        da1 = np.dot(dz2, self.W2.T)
        dz1 = da1 * self._relu_deriv(self.z1)
        dW1 = np.dot(self.X_attn.T, dz1) / m
        db1 = np.sum(dz1, axis=0, keepdims=True) / m
        
        # Backpropagation até a camada de Auto-Atenção
        dX_attn = np.dot(dz1, self.W1.T)
        d_attn = dX_attn * X
        dz_a = d_attn * self.attn * (1.0 - self.attn)
        dWa = np.dot(X.T, dz_a) / m
        dba = np.sum(dz_a, axis=0, keepdims=True) / m
        
        # Incrementa o passo de tempo do Adam
        self.t += 1
        
        # Atualização dos pesos com o Otimizador Adam
        self.m_Wa, self.v_Wa = self._adam_update(self.Wa, dWa, self.m_Wa, self.v_Wa, lr)
        self.m_ba, self.v_ba = self._adam_update(self.ba, dba, self.m_ba, self.v_ba, lr)
        
        self.m_W1, self.v_W1 = self._adam_update(self.W1, dW1, self.m_W1, self.v_W1, lr)
        self.m_b1, self.v_b1 = self._adam_update(self.b1, db1, self.m_b1, self.v_b1, lr)
        
        self.m_W2, self.v_W2 = self._adam_update(self.W2, dW2, self.m_W2, self.v_W2, lr)
        self.m_b2, self.v_b2 = self._adam_update(self.b2, db2, self.m_b2, self.v_b2, lr)
        
        self.m_W3, self.v_W3 = self._adam_update(self.W3, dW3, self.m_W3, self.v_W3, lr)
        self.m_b3, self.v_b3 = self._adam_update(self.b3, db3, self.m_b3, self.v_b3, lr)
        
        # Retorna a loss BCE média
        loss = -np.mean(y * np.log(np.clip(out, 1e-15, 1.0)) + (1.0 - y) * np.log(np.clip(1.0 - out, 1e-15, 1.0)))
        return loss


# ==========================================
# 2. MOTOR DE REDE NEURAL EM PYTORCH (GPU/CPU)
# ==========================================
if HAS_TORCH:
    class TorchMLP(nn.Module):
        def __init__(self, input_size=20, hidden1=32, hidden2=16):
            super(TorchMLP, self).__init__()
            self.attn_weights = nn.Sequential(
                nn.Linear(input_size, input_size),
                nn.Sigmoid()
            )
            self.net = nn.Sequential(
                nn.Linear(input_size, hidden1),
                nn.ReLU(),
                nn.Linear(hidden1, hidden2),
                nn.ReLU(),
                nn.Linear(hidden2, 1),
                nn.Sigmoid()
            )
            
        def forward(self, x):
            attn = self.attn_weights(x)
            x_attn = x * attn
            return self.net(x_attn)


# ==========================================
# 3. GERENCIADOR DO MODELO UNIFICADO (IA principal)
# ==========================================
class TradingAI:
    def __init__(self, use_gpu=True, lr=0.01):
        self.lr = lr
        self.use_gpu = use_gpu
        self.device = "cpu"
        self.engine = "numpy"
        
        if HAS_TORCH:
            self.engine = "pytorch"
            if use_gpu and torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
            
            self.model = TorchMLP().to(self.device)
            self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
            self.criterion = nn.BCELoss()
        else:
            self.model = NumpyMLP()
            
        self.loss_history = []
        self.accuracy_history = []

    def predict(self, features):
        """
        Recebe um vetor de 15 features do Accumulator e prevê a probabilidade
        de a entrada ser segura (valor entre 0.0 e 1.0).
        """
        X = np.array(features, dtype=np.float32).reshape(1, -1)
        if self.engine == "pytorch":
            self.model.eval()
            with torch.no_grad():
                tensor_X = torch.tensor(X, device=self.device)
                pred = self.model(tensor_X).cpu().numpy()[0][0]
            return float(pred)
        else:
            pred = self.model.forward(X)[0][0]
            return float(pred)

    def train_on_batch(self, X_batch, y_batch):
        """
        Executa um passo de treinamento em lote.
        X_batch: numpy array shape (N, 15)
        y_batch: numpy array shape (N, 1)
        """
        if len(X_batch) == 0:
            return 0.0
            
        X_batch = np.array(X_batch, dtype=np.float32)
        y_batch = np.array(y_batch, dtype=np.float32).reshape(-1, 1)
        
        if self.engine == "pytorch":
            self.model.train()
            self.optimizer.zero_grad()
            tensor_X = torch.tensor(X_batch, device=self.device)
            tensor_y = torch.tensor(y_batch, device=self.device)
            
            out = self.model(tensor_X)
            loss = self.criterion(out, tensor_y)
            loss.backward()
            self.optimizer.step()
            loss_val = float(loss.item())
        else:
            loss_val = self.model.backward(X_batch, y_batch, lr=self.lr)
            
        self.loss_history.append(loss_val)
        if len(self.loss_history) > 100:
            self.loss_history.pop(0)
            
        return loss_val

    def save_weights(self, filepath="capturas/ai_weights.json"):
        """Salva os pesos do modelo em formato JSON para portabilidade."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        weights = {}
        if self.engine == "pytorch":
            # Converte state_dict para listas do numpy e depois listas normais
            state = self.model.state_dict()
            for k, v in state.items():
                weights[k] = v.cpu().numpy().tolist()
        else:
            weights = {
                "Wa": self.model.Wa.tolist(),
                "ba": self.model.ba.tolist(),
                "W1": self.model.W1.tolist(),
                "b1": self.model.b1.tolist(),
                "W2": self.model.W2.tolist(),
                "b2": self.model.b2.tolist(),
                "W3": self.model.W3.tolist(),
                "b3": self.model.b3.tolist()
            }
            
        try:
            with open(filepath, "w") as f:
                json.dump(weights, f)
            return True
        except Exception:
            return False

    def load_weights(self, filepath="capturas/ai_weights.json"):
        """Carrega os pesos do modelo de um arquivo JSON."""
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, "r") as f:
                weights = json.load(f)
                
            if self.engine == "pytorch":
                state = {}
                for k, v in weights.items():
                    state[k] = torch.tensor(v, device=self.device)
                self.model.load_state_dict(state)
            else:
                if "Wa" in weights:
                    self.model.Wa = np.array(weights["Wa"])
                if "ba" in weights:
                    self.model.ba = np.array(weights["ba"])
                self.model.W1 = np.array(weights["W1"])
                self.model.b1 = np.array(weights["b1"])
                self.model.W2 = np.array(weights["W2"])
                self.model.b2 = np.array(weights["b2"])
                self.model.W3 = np.array(weights["W3"])
                self.model.b3 = np.array(weights["b3"])
            return True
        except Exception:
            return False


# ==========================================
# 4. MEMÓRIA DE EXPERIÊNCIA E ENGENHARIA DE FEATURES
# ==========================================
class ExperienceReplay:
    def __init__(self, max_size=5000):
        self.max_size = max_size
        self.memory = []
        
    def add(self, features, label):
        self.memory.append((features, label))
        if len(self.memory) > self.max_size:
            self.memory.pop(0)
            
    def sample_batch(self, batch_size=32):
        if len(self.memory) == 0:
            return [], []
            
        crashes = [item for item in self.memory if item[1] == 0]
        safes = [item for item in self.memory if item[1] == 1]
        
        # Se não tivermos pelo menos uma amostra de cada classe, faz amostragem aleatória comum
        if len(crashes) == 0 or len(safes) == 0:
            indices = np.random.choice(len(self.memory), min(batch_size, len(self.memory)), replace=False)
            X = [self.memory[i][0] for i in indices]
            y = [self.memory[i][1] for i in indices]
            return X, y
            
        half_batch = batch_size // 2
        
        # Determina a quantidade para amostrar de cada classe
        num_crashes = min(half_batch, len(crashes))
        num_safes = batch_size - num_crashes
        
        if num_safes > len(safes):
            num_safes = len(safes)
            num_crashes = min(batch_size - num_safes, len(crashes))
            
        crash_indices = np.random.choice(len(crashes), num_crashes, replace=len(crashes) < num_crashes)
        safe_indices = np.random.choice(len(safes), num_safes, replace=len(safes) < num_safes)
        
        batch = [crashes[i] for i in crash_indices] + [safes[i] for i in safe_indices]
        np.random.shuffle(batch)
        
        X = [item[0] for item in batch]
        y = [item[1] for item in batch]
        return X, y

    def get_accuracy(self, model):
        """Calcula a acurácia atual da IA no histórico completo da memória."""
        if len(self.memory) == 0:
            return 0.0
            
        correct = 0
        for features, label in self.memory:
            pred = model.predict(features)
            pred_bin = 1 if pred >= 0.5 else 0
            if pred_bin == label:
                correct += 1
        return (correct / len(self.memory)) * 100.0


def extract_accumulator_features(tick_prices, last_crash_index, current_index, survival_lengths):
    """
    Função de Engenharia de Features específica para o comportamento do Accumulator:
    Recebe um histórico recente de preços e calcula os 20 indicadores matemáticos de estabilidade,
    incluindo as estatísticas dos últimos ciclos de sobrevivência (acumulado).
    """
    # Garante que temos pelo menos 11 preços
    if len(tick_prices) < 11:
        # Preenche com o primeiro preço para estabilizar
        first_val = tick_prices[0] if len(tick_prices) > 0 else 1.0
        tick_prices = [first_val] * (11 - len(tick_prices)) + list(tick_prices)
        
    # Calcula as variações percentuais dos últimos 10 ticks (log returns)
    returns = []
    for i in range(-10, 0):
        prev = tick_prices[i-1]
        curr = tick_prices[i]
        ret = np.log(curr / prev) if prev > 0 else 0.0
        returns.append(ret * 10000.0) # Escala de retorno multiplicada por 10.000 para faixa ideal de IA
        
    # EMA(3) das variações
    ema_3 = returns[-1]
    for r in returns[-3:]:
        ema_3 = 0.5 * r + 0.5 * ema_3
        
    # EMA(8) das variações
    ema_8 = returns[-1]
    for r in returns[-8:]:
        ema_8 = 0.22 * r + 0.78 * ema_8
        
    # Volatilidade recente (Desvio padrão das variações)
    volatility = float(np.std(returns))
    
    # Distância desde o último crash (normalizado para 0.0 - 1.0, assumindo max 60 ticks)
    ticks_since_crash = float(current_index - last_crash_index)
    normalized_crash_dist = min(1.0, ticks_since_crash / 60.0)
    
    # Direção do último tick (1, -1 ou 0)
    last_ret = returns[-1]
    last_dir = 1.0 if last_ret > 1e-3 else (-1.0 if last_ret < -1e-3 else 0.0)
    
    # Garante que temos dados no survival_lengths
    if not survival_lengths:
        survival_lengths = [10] * 10
        
    # Estatísticas dos últimos runs do Accumulator (normalizados para escala de rede neural)
    avg_len = float(np.mean(survival_lengths)) / 50.0
    std_len = float(np.std(survival_lengths)) / 20.0
    min_len = float(np.min(survival_lengths)) / 50.0
    max_len = float(np.max(survival_lengths)) / 50.0
    last_len = float(survival_lengths[-1]) / 50.0
    
    # Consolida as 20 features
    features = returns + [ema_3, ema_8, volatility, normalized_crash_dist, last_dir, avg_len, std_len, min_len, max_len, last_len]
    return features


def extract_rise_fall_features(tick_prices):
    """
    Função de Engenharia de Features específica para Rise/Fall com múltiplos timeframes.
    Extrai exatamente 20 features focadas em tendências, momentum e volatilidade
    de curto, médio e longo prazo (1m e 5m).
    """
    # Garante que temos pelo menos 151 preços (necessários para SMA 150)
    if len(tick_prices) < 151:
        first_val = tick_prices[0] if len(tick_prices) > 0 else 1.0
        tick_prices = [first_val] * (151 - len(tick_prices)) + list(tick_prices)
        
    p_curr = tick_prices[-1]
    
    # 1. Log returns de curto prazo (últimos 5 ticks) -> 5 features
    returns_5 = []
    for i in range(-5, 0):
        prev = tick_prices[i-1]
        curr = tick_prices[i]
        ret = np.log(curr / prev) if prev > 0 else 0.0
        returns_5.append(ret * 10000.0)
        
    # 2. Retornos acumulados multi-escala -> 5 features
    ret_10 = (np.log(p_curr / tick_prices[-11]) * 10000.0) if tick_prices[-11] > 0 else 0.0
    ret_30 = (np.log(p_curr / tick_prices[-31]) * 10000.0) if tick_prices[-31] > 0 else 0.0
    ret_60 = (np.log(p_curr / tick_prices[-61]) * 10000.0) if tick_prices[-61] > 0 else 0.0
    ret_100 = (np.log(p_curr / tick_prices[-101]) * 10000.0) if tick_prices[-101] > 0 else 0.0
    ret_150 = (np.log(p_curr / tick_prices[-151]) * 10000.0) if tick_prices[-151] > 0 else 0.0
    
    # 3. Cruzamento de Médias Móveis (SMA / Preço Atual) -> 4 features
    sma_10_ratio = (sum(tick_prices[-10:]) / 10.0) / p_curr - 1.0
    sma_30_ratio = (sum(tick_prices[-30:]) / 30.0) / p_curr - 1.0
    sma_60_ratio = (sum(tick_prices[-60:]) / 60.0) / p_curr - 1.0
    sma_150_ratio = (sum(tick_prices[-150:]) / 150.0) / p_curr - 1.0
    
    sma_features = [sma_10_ratio * 1000.0, sma_30_ratio * 1000.0, sma_60_ratio * 1000.0, sma_150_ratio * 1000.0]
    
    # 4. Volatilidade multi-escala (std dev de log returns de 1 tick) -> 3 features
    rets_10 = [np.log(tick_prices[i] / tick_prices[i-1]) * 10000.0 for i in range(-10, 0)]
    vol_10 = float(np.std(rets_10))
    
    rets_30 = [np.log(tick_prices[i] / tick_prices[i-1]) * 10000.0 for i in range(-30, 0)]
    vol_30 = float(np.std(rets_30))
    
    rets_150 = [np.log(tick_prices[i] / tick_prices[i-1]) * 10000.0 for i in range(-150, 0)]
    vol_150 = float(np.std(rets_150))
    
    # 5. Momentum e Direção de curtíssimo prazo -> 3 features
    last_dir = 1.0 if returns_5[-1] > 1e-3 else (-1.0 if returns_5[-1] < -1e-3 else 0.0)
    roc_5 = (p_curr - tick_prices[-6]) / (tick_prices[-6] + 1e-9) * 100.0
    roc_15 = (p_curr - tick_prices[-16]) / (tick_prices[-16] + 1e-9) * 100.0
    
    features = (
        returns_5 + 
        [ret_10, ret_30, ret_60, ret_100, ret_150] + 
        sma_features + 
        [vol_10, vol_30, vol_150] + 
        [last_dir, roc_5, roc_15]
    )
    
    return features[:20]


# ==========================================
# 4. MODELO DE CLASSIFICAÇÃO DE DÍGITOS (MATCHES/DIFFERS)
# ==========================================

class TorchDigitMLP(nn.Module):
    def __init__(self, input_size=150, hidden1=64, hidden2=32):
        super(TorchDigitMLP, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, 10),
            nn.Softmax(dim=-1)
        )
        
    def forward(self, x):
        return self.net(x)

class NumpyDigitMLP:
    def __init__(self, input_size=150, hidden1=64, hidden2=32):
        self.input_size = input_size
        self.hidden1 = hidden1
        self.hidden2 = hidden2
        # Inicializa pesos (He initialization)
        self.W1 = np.random.randn(input_size, hidden1) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden1))
        self.W2 = np.random.randn(hidden1, hidden2) * np.sqrt(2.0 / hidden1)
        self.b2 = np.zeros((1, hidden2))
        self.W3 = np.random.randn(hidden2, 10) * np.sqrt(2.0 / hidden2)
        self.b3 = np.zeros((1, 10))

    def forward(self, X):
        self.z1 = np.dot(X, self.W1) + self.b1
        self.a1 = np.maximum(0, self.z1) # ReLU
        self.z2 = np.dot(self.a1, self.W2) + self.b2
        self.a2 = np.maximum(0, self.z2) # ReLU
        self.z3 = np.dot(self.a2, self.W3) + self.b3
        # Softmax estável
        exp_scores = np.exp(self.z3 - np.max(self.z3, axis=1, keepdims=True))
        self.probs = exp_scores / np.sum(exp_scores, axis=1, keepdims=True)
        return self.probs

    def backward(self, X, y_one_hot, lr=0.01):
        N = X.shape[0]
        dscores = (self.probs - y_one_hot) / N
        
        dW3 = np.dot(self.a2.T, dscores)
        db3 = np.sum(dscores, axis=0, keepdims=True)
        
        da2 = np.dot(dscores, self.W3.T)
        dz2 = da2 * (self.z2 > 0)
        dW2 = np.dot(self.a1.T, dz2)
        db2 = np.sum(dz2, axis=0, keepdims=True)
        
        da1 = np.dot(dz2, self.W2.T)
        dz1 = da1 * (self.z1 > 0)
        dW1 = np.dot(X.T, dz1)
        db1 = np.sum(dz1, axis=0, keepdims=True)
        
        # SGD updates
        self.W3 -= lr * dW3
        self.b3 -= lr * db3
        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        self.W1 -= lr * dW1
        self.b1 -= lr * db1

class DigitExperienceReplay:
    def __init__(self, max_size=5000):
        self.max_size = max_size
        self.memory = []
        
    def add(self, features, label):
        self.memory.append((features, label))
        if len(self.memory) > self.max_size:
            self.memory.pop(0)
            
    def sample_batch(self, batch_size=32):
        if len(self.memory) == 0:
            return [], []
        indices = np.random.choice(len(self.memory), min(batch_size, len(self.memory)), replace=False)
        X = [self.memory[i][0] for i in indices]
        y = [self.memory[i][1] for i in indices]
        return X, y

    def get_accuracy(self, model):
        if len(self.memory) == 0:
            return 0.0
        samples = self.memory[-100:]
        correct = 0
        for x, y in samples:
            probs = model.predict(x)
            pred = np.argmax(probs)
            if pred == int(y):
                correct += 1
        return (correct / len(samples)) * 100.0

class DigitAI:
    def __init__(self, use_gpu=True, lr=0.01):
        self.lr = lr
        self.use_gpu = use_gpu
        self.device = "cpu"
        self.engine = "numpy"
        
        if HAS_TORCH:
            self.engine = "pytorch"
            if use_gpu and torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
            
            self.model = TorchDigitMLP().to(self.device)
            self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
            self.criterion = nn.CrossEntropyLoss()
        else:
            self.model = NumpyDigitMLP()
            
        self.loss_history = []
        self.accuracy_history = []

    def predict(self, features):
        X = np.array(features, dtype=np.float32).reshape(1, -1)
        if self.engine == "pytorch":
            self.model.eval()
            with torch.no_grad():
                tensor_X = torch.tensor(X, device=self.device)
                probs = self.model(tensor_X).cpu().numpy()[0]
            return probs
        else:
            probs = self.model.forward(X)[0]
            return probs

    def train_on_batch(self, X_batch, y_batch):
        if len(X_batch) == 0:
            return 0.0
            
        if self.engine == "pytorch":
            self.model.train()
            X_tensor = torch.tensor(X_batch, dtype=torch.float32, device=self.device)
            y_tensor = torch.tensor(y_batch, dtype=torch.long, device=self.device)
            
            self.optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = self.criterion(outputs, y_tensor)
            loss.backward()
            self.optimizer.step()
            return float(loss.item())
        else:
            N = len(y_batch)
            y_one_hot = np.zeros((N, 10))
            y_one_hot[np.arange(N), y_batch.astype(int)] = 1.0
            
            self.model.forward(X_batch)
            self.model.backward(X_batch, y_one_hot, lr=self.lr)
            
            loss = -np.sum(y_one_hot * np.log(self.model.probs + 1e-15)) / N
            return float(loss)

    def save_weights(self, path="digit_ai_weights.pth"):
        if self.engine == "pytorch":
            torch.save(self.model.state_dict(), path)
        else:
            weights = {
                "W1": self.model.W1.tolist(),
                "b1": self.model.b1.tolist(),
                "W2": self.model.W2.tolist(),
                "b2": self.model.b2.tolist(),
                "W3": self.model.W3.tolist(),
                "b3": self.model.b3.tolist()
            }
            with open("digit_ai_weights.json", "w") as f:
                json.dump(weights, f)

    def load_weights(self, path="digit_ai_weights.pth"):
        if self.engine == "pytorch":
            if os.path.exists(path):
                try:
                    self.model.load_state_dict(torch.load(path, map_location=self.device))
                except Exception:
                    # Ignore mismatched weights and start fresh
                    pass
        else:
            if os.path.exists("digit_ai_weights.json"):
                try:
                    with open("digit_ai_weights.json", "r") as f:
                        w = json.load(f)
                    w1_arr = np.array(w["W1"])
                    if w1_arr.shape == self.model.W1.shape:
                        self.model.W1 = w1_arr
                        self.model.b1 = np.array(w["b1"])
                        self.model.W2 = np.array(w["W2"])
                        self.model.b2 = np.array(w["b2"])
                        self.model.W3 = np.array(w["W3"])
                        self.model.b3 = np.array(w["b3"])
                except Exception:
                    pass
