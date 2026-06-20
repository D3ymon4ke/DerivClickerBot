import os
import time
import random
import threading
import datetime
import csv
import json
try:
    import winsound
except ImportError:
    winsound = None
import pygame
import cv2
import numpy as np
import pyautogui
import telegram_sender
import ai_model

# Evita travar o mouse caso ocorra algum loop infinito (arraste para o canto superior esquerdo para abortar)
pyautogui.FAILSAFE = True

def one_hot_encode_digits(digits, num_classes=10):
    encoded = []
    for d in digits:
        vec = [0.0] * num_classes
        try:
            val = int(d)
            if 0 <= val < num_classes:
                vec[val] = 1.0
        except ValueError:
            pass
        encoded.extend(vec)
    return encoded

class BotWorker(threading.Thread):
    def __init__(self, config, on_click_cb, on_win_cb, on_loss_cb, on_log_cb, on_status_cb, on_next_time_cb, on_stop_limit_cb, on_start_execution_cb=None, on_finance_cb=None):
        super().__init__(daemon=True)
        self.config = config
        self.on_click_cb = on_click_cb
        self.on_win_cb = on_win_cb
        self.on_loss_cb = on_loss_cb
        self.on_log_cb = on_log_cb
        self.on_status_cb = on_status_cb
        self.on_next_time_cb = on_next_time_cb
        self.on_stop_limit_cb = on_stop_limit_cb
        self.on_start_execution_cb = on_start_execution_cb
        self.on_finance_cb = on_finance_cb
        
        self.running = False
        self.click_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.current_profit = 0.0
        
        # Atributos de Ciclos de Entradas
        self.cycle_entries_count = 0
        self.in_cycle_cooldown = False
        self.cycle_cooldown_end_time = 0.0
        
        self.win_detected_state = False
        self.last_win_time = 0
        
        self.loss_detected_state = False
        self.last_loss_time = 0
        
        # Atributos de Modo Inteligente (Adaptive Mode)
        self.adaptive_sequence = []
        self.adaptive_phase = "observation"
        self.adaptive_observation_start_time = 0.0
        self.adaptive_relearn_start_time = 0.0
        
        self.adaptive_crashed = False
        self.adaptive_consec_green_ticks = 0
        self.adaptive_consec_red_crashes = 0
        self.adaptive_ready_to_click = True
        
        self.api_client = None
        self.api_connected = False
        self.api_authorized = False
        self.last_api_tick_time = 0.0
        
        self.adaptive_strategy = {
            "type": "none",
            "wait_ticks": 3,
            "wait_reds": 2,
            "text": "Fase de observacao ativa",
            "dominant_pattern": "3 ciclos → repetição",
            "confidence": 0.0,
            "eventos_analisados": 0,
            "probabilidade_repeticao": 0.0,
            "sequencia_mais_comum": 3
        }
        self.adaptive_event_count_since_relearn = 0
        self.adaptive_loss_count_since_relearn = 0
        self.setup_in_progress = False
        
        # --- ATRIBUTOS DO MODO IA ---
        self.ai = ai_model.TradingAI(
            use_gpu=self.config.get("ai_use_gpu", True),
            lr=self.config.get("ai_learning_rate", 0.01)
        )
        self.ai.load_weights()  # carrega pesos salvos se existirem
        self.ai_replay = ai_model.ExperienceReplay(max_size=5000)
        
        self.digit_ai = ai_model.DigitAI(
            use_gpu=self.config.get("ai_use_gpu", True),
            lr=self.config.get("ai_learning_rate", 0.01)
        )
        self.digit_ai.load_weights()
        self.ai_digit_replay = ai_model.DigitExperienceReplay(max_size=5000)
        self.ai_training_iterations = 0
        self.martingale_level = 0
        self.last_dynamic_duration = None
        
        self.ai_tick_prices = []
        self.ai_tick_digits = []
        self.ai_tick_history_max = 500
        self.ai_observations = []
        self.ai_digit_observations = []
        self.ai_current_tick_index = 0
        self.ai_last_crash_index = 0
        self.on_ai_metrics_cb = None
        self.ai_prediction_confidence = 0.0
        self.ai_loss = 0.0
        self.ai_accuracy = 0.0
        self.ai_survival_lengths = [10] * 10
        self.market_trend = "LATERAL ⚖️"
        # Controlo de entrada do Modo IA
        self.ai_entry_cooldown_remaining = 0   # ticks restantes de cooldown pós-entrada
        self.ai_active_contract = False         # True enquanto há contrato aberto via API
        self.ai_selling_contract_id = None      # ID do contrato sendo vendido para evitar repetição
        self.ai_ticks_since_crash = 0           # ticks consecutivos sem crash desde o último
        self.ai_reasoning_status = "Inativo"
        self.ai_reasoning_explanation = "Aguardando inicialização do robô..."
        
        # Cria as pastas de historico se nao existirem
        os.makedirs("capturas/historico", exist_ok=True)
        self.history_file = "wins_history.csv"
        
        self.sounds = {}
        self._load_custom_sounds()
        
        # Inicializa cliente Llama para integracao local/remota
        llama_provider = self.config.get("llama_provider", "ollama")
        if llama_provider == "local":
            from local_llama import LocalLlamaClient
            self.llama = LocalLlamaClient(
                model_name=self.config.get("llama_model", "Qwen/Qwen2.5-0.5B-Instruct"),
                enabled=self.config.get("llama_enabled", False)
            )
        else:
            from llama_client import LlamaClient
            self.llama = LlamaClient(
                url=self.config.get("llama_url", "http://localhost:11434/api/generate"),
                model=self.config.get("llama_model", "llama3"),
                enabled=self.config.get("llama_enabled", False)
            )
        self.recent_ops = []
        
    def _load_custom_sounds(self):
        try:
            # Garante que o mixer está inicializado
            if not pygame.mixer.get_init():
                pygame.mixer.init()
                
            sound_mappings = {
                "click": "songs/entrada.mp3",
                "win": "songs/win.mp3",
                "loss": "songs/loss.mp3",
                "start": "songs/start.mp3",
                "stopwin": "songs/stopwin.mp3",
                "stoploss": "songs/stoploss.mp3",
            }
            
            for key, path in sound_mappings.items():
                if os.path.exists(path):
                    try:
                        self.sounds[key] = pygame.mixer.Sound(path)
                    except Exception as e:
                        print(f"[BotWorker] Erro ao carregar som {path}: {e}")
        except Exception as e:
            print(f"[BotWorker] Erro ao inicializar mixer de áudio: {e}")
        
    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {msg}"
        self.on_log_cb(formatted)
        
        if self.config.get("save_log", True):
            try:
                with open("deriv_bot.log", "a", encoding="utf-8") as f:
                    f.write(formatted + "\n")
            except Exception:
                pass

    def play_sound(self, sound_type):
        if not self.config.get("play_sounds", True):
            return
        
        def _play():
            try:
                use_custom = self.config.get("use_custom_sounds", True)
                sound_key = sound_type
                
                # Tradução de stopwin/stoploss caso não existam
                if sound_key not in self.sounds:
                    if sound_key == "stopwin" and "win" in self.sounds:
                        sound_key = "win"
                    elif sound_key == "stoploss" and "loss" in self.sounds:
                        sound_key = "loss"
                
                if use_custom and sound_key in self.sounds:
                    self.sounds[sound_key].play()
                else:
                    # Fallback para beeps clássicos
                    if winsound:
                        if sound_type == "click":
                            winsound.Beep(1000, 150)
                        elif sound_type in ["win", "stopwin"]:
                            winsound.Beep(1800, 200)
                            winsound.Beep(2200, 300)
                        elif sound_type in ["loss", "stoploss"]:
                            winsound.Beep(800, 250)
                            winsound.Beep(500, 350)
                        elif sound_type == "stop":
                            winsound.Beep(600, 250)
                        elif sound_type == "start":
                            winsound.Beep(1200, 150)
                            winsound.Beep(1500, 150)
                    else:
                        print("\a", end="", flush=True)
            except Exception:
                # Segundo fallback geral caso o pygame.mixer dê algum problema
                try:
                    if winsound:
                        if sound_type == "click":
                            winsound.Beep(1000, 150)
                        elif sound_type in ["win", "stopwin"]:
                            winsound.Beep(1800, 200)
                            winsound.Beep(2200, 300)
                        elif sound_type in ["loss", "stoploss"]:
                            winsound.Beep(800, 250)
                            winsound.Beep(500, 350)
                        elif sound_type == "stop":
                            winsound.Beep(600, 250)
                        elif sound_type == "start":
                            winsound.Beep(1200, 150)
                            winsound.Beep(1500, 150)
                    else:
                        print("\a", end="", flush=True)
                except Exception:
                    pass
        
        threading.Thread(target=_play, daemon=True).start()

    def take_screenshot(self, name_prefix):
        if not self.config.get("auto_screenshot", False):
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capturas/historico/{name_prefix}_{timestamp}.png"
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            self.log(f"Screenshot salvo: {filename}")
        except Exception as e:
            self.log(f"Erro ao salvar screenshot: {e}")

    def save_result_to_history(self, result_type):
        try:
            file_exists = os.path.exists(self.history_file)
            with open(self.history_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Data/Hora", "Resultado", "Wins Totais", "Losses Totais"])
                writer.writerow([
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    result_type,
                    self.win_count,
                    self.loss_count
                ])
        except Exception as e:
            self.log(f"Erro ao salvar historico: {e}")

    def find_image(self, template_path, sensitivity):
        if not os.path.exists(template_path):
            return None, 0.0
        
        try:
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                return None, 0.0
            
            h, w = template.shape[:2]
            
            # Captura de tela inteira
            screenshot = pyautogui.screenshot()
            screenshot_np = np.array(screenshot)
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            # Template matching do OpenCV
            res = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= sensitivity:
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y), max_val
            return None, max_val
        except Exception:
            return None, 0.0

    def start_bot(self):
        self.running = True
        self.cycle_entries_count = 0
        self.in_cycle_cooldown = False
        self.cycle_cooldown_end_time = 0.0
        
        self.ai_selling_contract_id = None
        self.adaptive_sequence = []
        self.adaptive_phase = "observation"
        self.adaptive_observation_start_time = time.time()
        self.adaptive_relearn_start_time = time.time()
        self.adaptive_crashed = False
        self.adaptive_consec_green_ticks = 0
        self.adaptive_consec_red_crashes = 0
        self.adaptive_ready_to_click = True
        
        # Conecta API se token fornecido
        token = self.config.get("deriv_api_token", "").strip()
        if token:
            self.log("Iniciando conexão com a API da Deriv...")
            symbol = self.config.get("deriv_symbol", "R_100")
            growth_rate = self.config.get("deriv_growth_rate", 0.01)
            app_id = str(self.config.get("deriv_app_id", "1098")).strip() or "1098"
            
            from deriv_api_client import DerivApiClient
            self.api_client = DerivApiClient(
                token=token,
                app_id=app_id,
                symbol=symbol,
                growth_rate=growth_rate,
                account_type=self.config.get("deriv_account_type", "demo")
            )
            self.api_client.on_tick_cb = self._on_api_tick
            self.api_client.on_contract_status_cb = self._on_api_contract_status
            self.api_client.on_contract_update_cb = self._on_api_contract_update
            self.api_client.on_history_cb = self._on_api_history
            self.api_client.on_log_cb = self.log
            self.api_client.on_connection_change_cb = self._on_api_connection_change
            self.api_client.connect()
            
        self.adaptive_strategy = {
            "type": "none",
            "wait_ticks": 3,
            "wait_reds": 2,
            "text": "Fase de observacao ativa",
            "dominant_pattern": "3 ciclos → repetição",
            "confidence": 0.0,
            "eventos_analisados": 0,
            "probabilidade_repeticao": 0.0,
            "sequencia_mais_comum": 3
        }
        self.adaptive_event_count_since_relearn = 0
        self.adaptive_loss_count_since_relearn = 0
        
        # Se agendamento estiver ativo, enviamos log e telegram de agendamento.
        # Caso contrário, enviamos log e telegram de início imediato.
        if self.config.get("schedule_enabled", False):
            date_str = self.config.get("schedule_date", "")
            time_str = self.config.get("schedule_time", "")
            self.log(f"Agendamento ativo: aguardando {date_str} às {time_str}...")
            
            tg_msg = (
                "⏰ <b>Deriv Clicker Bot</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🟡 <b>Estado:</b> Agendado para iniciar!\n"
                f"📅 <b>Data:</b> {date_str}\n"
                f"⏰ <b>Horário:</b> {time_str}\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>O bot iniciará as operações automaticamente neste horário.</i>"
            )
            telegram_sender.send_telegram_msg(self.config, tg_msg, self.log)
        else:
            self.play_sound("start")
            self.log("Bot iniciado.")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                "🚀 <b>Deriv Clicker Bot</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🟢 <b>Estado:</b> Operação Iniciada!\n"
                f"⏱️ <b>Horário:</b> {timestamp}\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>Monitorando botão de entrada e resultados...</i>"
            )
            telegram_sender.send_telegram_msg(self.config, msg, self.log)
            
        self.start()

    def stop_bot(self, reason=None):
        if self.running:
            self.running = False
            if self.api_client:
                try:
                    self.api_client.disconnect()
                except Exception:
                    pass
                self.api_client = None
            if reason in ["win", "profit_win"]:
                self.play_sound("stopwin")
            elif reason == "loss":
                self.play_sound("stoploss")
            else:
                self.play_sound("stop")
            self.log("Bot parado.")
            self.on_status_cb(False)

    def _wait_if_in_cycle_cooldown(self):
        if self.config.get("mode") == "ai":
            return
        if not self.config.get("cycle_enabled", False):
            return
            
        if not self.in_cycle_cooldown:
            return
            
        self.log(f"[Ciclos] Ciclo finalizado. Iniciando pausa de {self.config.get('cycle_cooldown_minutes', 60)} minutos...")
        
        if self.cycle_cooldown_end_time <= 0:
            self.cycle_cooldown_end_time = time.time() + self.config.get("cycle_cooldown_minutes", 60) * 60
            
        cooldown_mins = self.config.get("cycle_cooldown_minutes", 60)
        end_time_str = datetime.datetime.fromtimestamp(self.cycle_cooldown_end_time).strftime("%H:%M:%S")
        tg_msg = (
            "🔄 <b>PAUSA POR CICLO ATIVADA!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📥 <b>Entradas no Ciclo:</b> {self.config.get('cycle_max_entries', 4)}/{self.config.get('cycle_max_entries', 4)}\n"
            f"⏱️ <b>Tempo de Pausa:</b> {cooldown_mins} min\n"
            f"⏳ <b>Retorno previsto às:</b> {end_time_str}\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        telegram_sender.send_telegram_msg(self.config, tg_msg, self.log)
        
        while self.running and self.in_cycle_cooldown:
            remaining = self.cycle_cooldown_end_time - time.time()
            if remaining <= 0:
                break
                
            self.on_next_time_cb(-remaining)
            time.sleep(0.5)
            
        if not self.running:
            return
            
        self.in_cycle_cooldown = False
        self.cycle_cooldown_end_time = 0.0
        self.cycle_entries_count = 0
        self.log("[Ciclos] Pausa de ciclo finalizada! Retomando operações...")
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resume_msg = (
            "🚀 <b>Deriv Clicker Bot - Ciclo Retomado</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🟢 <b>Estado:</b> Operação Retomada!\n"
            f"⏱️ <b>Horário:</b> {timestamp}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<i>Iniciando novo ciclo de entradas...</i>"
        )
        telegram_sender.send_telegram_msg(self.config, resume_msg, self.log)

    def run(self):
        # Se a configuração automatizada do clickerbot estiver em andamento, aguarda sua conclusão
        while self.setup_in_progress and self.running:
            time.sleep(0.5)

        # Se agendamento estiver ativo, espera o horário alvo
        if self.config.get("schedule_enabled", False):
            date_str = self.config.get("schedule_date", "")
            time_str = self.config.get("schedule_time", "")
            try:
                target_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
                target_ts = target_dt.timestamp()
                
                # Loop de espera com suporte a cancelamento imediato
                while self.running:
                    now = time.time()
                    if now >= target_ts:
                        break
                    
                    remaining = target_ts - now
                    # Passa tempo restante como negativo para atualizar contagem na GUI
                    self.on_next_time_cb(-remaining)
                    
                    time.sleep(0.5)
                
                if not self.running:
                    return
                
                # Horário atingido! Realiza a transição para execução
                self.log("Horário agendado atingido! Iniciando operações...")
                self.play_sound("start")
                
                # Envia mensagem no Telegram de início de operações
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                msg = (
                    "🚀 <b>Deriv Clicker Bot</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "🟢 <b>Estado:</b> Operação Iniciada (Agendamento)!\n"
                    f"⏱️ <b>Horário:</b> {timestamp}\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "<i>Monitorando botão de entrada e resultados...</i>"
                )
                telegram_sender.send_telegram_msg(self.config, msg, self.log)
                
                # Callback para a GUI transicionar de status AGENDADO para EXECUTANDO
                if self.on_start_execution_cb:
                    self.on_start_execution_cb()
                    
            except Exception as e:
                self.log(f"Erro ao processar agendamento: {e}")
                self.stop_bot()
                return

        # Inicia a thread de escaneamento de resultados (win/loss) em background
        results_thread = threading.Thread(target=self._results_monitor_loop, daemon=True)
        results_thread.start()
        
        mode = self.config.get("mode", "fixed")
        
        try:
            if mode == "fixed":
                self._run_fixed_mode()
            elif mode == "random":
                self._run_random_mode()
            elif mode == "sequence":
                self._run_sequence_mode()
            elif mode == "linered":
                self._run_linered_mode()
            elif mode == "adaptive":
                self._run_adaptive_mode()
            elif mode == "ai":
                self._run_ai_mode()
        except Exception as e:
            self.log(f"Erro de execucao do bot: {e}")
            self.stop_bot()

    def _run_fixed_mode(self):
        fixed_interval = self.config.get("fixed_interval", 5.0)
        self.log(f"Modo Intervalo Fixo ativo: clique a cada {fixed_interval}s.")
        
        while self.running:
            self._wait_if_in_cycle_cooldown()
            if not self.running:
                break
            elapsed = 0.0
            while elapsed < fixed_interval and self.running:
                time.sleep(0.1)
                elapsed += 0.1
                
            if not self.running:
                break
                
            self._attempt_click()

    def _run_random_mode(self):
        min_val = self.config.get("random_min", 2.0)
        max_val = self.config.get("random_max", 10.0)
        self.log(f"Modo Intervalo Aleatorio ativo: [{min_val}s, {max_val}s].")
        
        while self.running:
            self._wait_if_in_cycle_cooldown()
            if not self.running:
                break
            next_wait = round(random.uniform(min_val, max_val), 1)
            self.on_next_time_cb(next_wait)
            self.log(f"Proximo clique sorteado em: {next_wait}s.")
            
            elapsed = 0.0
            while elapsed < next_wait and self.running:
                time.sleep(0.1)
                elapsed += 0.1
                
            if not self.running:
                break
                
            self._attempt_click()

    def _run_sequence_mode(self):
        clicks_per_cycle = self.config.get("seq_clicks", 3)
        click_interval = self.config.get("seq_interval", 2.0)
        cycle_wait = self.config.get("seq_wait", 20.0)
        
        self.log(f"Modo Sequencia ativo: {clicks_per_cycle} cliques, intervalo {click_interval}s, ciclo {cycle_wait}s.")
        
        while self.running:
            self._wait_if_in_cycle_cooldown()
            if not self.running:
                break
            for i in range(clicks_per_cycle):
                if not self.running:
                    break
                
                self.log(f"Clique {i+1}/{clicks_per_cycle} do ciclo.")
                self._attempt_click()
                
                elapsed = 0.0
                while elapsed < click_interval and self.running:
                    time.sleep(0.1)
                    elapsed += 0.1
                    
            if not self.running:
                break
                
            self.log(f"Ciclo finalizado. Aguardando {cycle_wait}s para novo ciclo...")
            self.on_next_time_cb(cycle_wait)
            
            elapsed = 0.0
            while elapsed < cycle_wait and self.running:
                time.sleep(0.1)
                elapsed += 0.1

    def _run_linered_mode(self):
        """
        Modo Número Vermelho (antigo Linha Vermelha):
        - Monitora a tela continuamente (a cada 300ms)
        - Quando number.png é detectada e está vermelho: clica no botão de entrada (1 vez por evento)
        - Aguarda o número deixar de ser vermelho para se rearmar
        - Respeita todos os limites de Stop Win/Stop Loss
        """
        number_path = self.config.get("image_number_path", "capturas/number.png")
        sens        = self.config.get("sensitivity_number", 0.65)
        
        self.log("Modo Número Vermelho ativo: aguardando o número ficar vermelho para entrar...")
        self.on_next_time_cb(0)  # sem contagem regressiva neste modo
        
        # Estado interno
        red_armed     = True   # True = pronto para clicar no proximo vermelho
        last_log_time = 0

        while self.running:
            self._wait_if_in_cycle_cooldown()
            if not self.running:
                break
            try:
                # 1. Configs dinâmicas
                sens = self.config.get("sensitivity_number", 0.65)
                use_region = self.config.get("use_search_region", False)
                search_region = self.config.get("search_region", None) if use_region else None

                # 2. Captura de tela (completa ou região restrita)
                if search_region:
                    # search_region formato: [x, y, w, h]
                    x_r, y_r, w_r, h_r = search_region
                    screenshot = pyautogui.screenshot(region=(x_r, y_r, w_r, h_r))
                else:
                    screenshot = pyautogui.screenshot()
                
                screenshot_np = np.array(screenshot)
                frame_gray    = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

                # 3. Localiza o número usando template matching
                num_pos, num_conf = self._find_image_in_frame(frame_gray, number_path, sens)

                is_red_signal = False
                red_pixel_count = 0

                if num_pos:
                    # Se encontrou, verifica se a região correspondente na tela é vermelha
                    center_x, center_y = num_pos
                    
                    # Lê dimensões do template
                    template = cv2.imread(number_path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        h, w = template.shape[:2]
                        x_start = max(0, center_x - w // 2)
                        y_start = max(0, center_y - h // 2)
                        x_end = min(screenshot_np.shape[1], center_x + w // 2)
                        y_end = min(screenshot_np.shape[0], center_y + h // 2)
                        
                        region_rgb = screenshot_np[y_start:y_end, x_start:x_end]
                        
                        # pixels vermelhos: R > 120 e R > G * 1.3 e R > B * 1.3
                        r = region_rgb[:, :, 0]
                        g = region_rgb[:, :, 1]
                        b = region_rgb[:, :, 2]
                        red_mask = (r > 120) & (r > g * 1.3) & (r > b * 1.3)
                        red_pixel_count = np.sum(red_mask)
                        
                        # Considera vermelho se tiver pelo menos 15 pixels com essa característica
                        if red_pixel_count >= 15:
                            is_red_signal = True

                now = time.time()
                if now - last_log_time > 3.0:
                    status_str = "Vermelho" if is_red_signal else "Não Vermelho"
                    region_str = f"Região {search_region}" if search_region else "Tela Cheia"
                    if num_pos:
                        self.log(f"[Busca Número] Encontrado em {region_str} (conf={num_conf:.2f}, sens={sens:.2f}) | Estado: {status_str} (pixels vermelhos={red_pixel_count})")
                    else:
                        self.log(f"[Busca Número] Não encontrado em {region_str} (conf={num_conf:.2f}, sens={sens:.2f})")
                    last_log_time = now

                if num_pos and is_red_signal:
                    if red_armed:
                        # --- SINAL VERMELHO DETECTADO: ENTRAR ---
                        self.log(f"[Número Vermelho] Sinal vermelho detectado! (conf={num_conf:.2f}, pixels={red_pixel_count}) Entrando...")
                        self._attempt_click()
                        red_armed = False  # desarma até normalizar/mudar cor
                else:
                    # Se o número não for encontrado ou se for encontrado mas NÃO for vermelho, rearma
                    if not red_armed:
                        self.log(f"[Número] Sinal normalizado/ausente. Aguardando próximo sinal vermelho...")
                        red_armed = True

            except Exception:
                pass

            time.sleep(0.3)  # resolução de 300ms para responsividade

    def _run_adaptive_mode(self):
        self.log("Modo Inteligente (Adaptive Mode) ativo: aguardando fase de observação inicial...")
        self.adaptive_phase = "observation"
        self.adaptive_observation_start_time = time.time()
        self.adaptive_relearn_start_time = time.time()
        
        if self.api_client and self.api_client.connected:
            self.log("Solicitando histórico de ticks para pular a observação...")
            self.api_client.request_ticks_history(1000)
            
        number_path = self.config.get("image_number_path", "capturas/number.png")
        sens = self.config.get("sensitivity_number", 0.65)
        
        crashed = False
        last_tick_time = 0.0
        
        consec_green_ticks = 0
        consec_red_crashes = 0
        ready_to_click = True
        
        while self.running:
            self._wait_if_in_cycle_cooldown()
            if not self.running:
                break
                
            try:
                obs_minutes = self.config.get("adaptive_observation_minutes", 30)
                obs_seconds = obs_minutes * 60
                now = time.time()
                
                # --- CASO API DA DERIV CONECTADA ---
                if self.api_client and self.api_client.connected:
                    if self.adaptive_phase == "observation":
                        elapsed_obs = now - self.adaptive_observation_start_time
                        remaining_obs = max(0.0, obs_seconds - elapsed_obs)
                        self.on_next_time_cb(-remaining_obs)
                        
                        if elapsed_obs >= obs_seconds:
                            self.log("Fase de observação concluída! Iniciando análise estatística...")
                            self.relearn_strategy()
                            self.adaptive_phase = "operation"
                            self.play_sound("start")
                    else:
                        conf = self.adaptive_strategy.get("confidence", 0.0)
                        if conf < 50.0:
                            self.log(f"Alerta: Confiança muito baixa ({conf:.1f}% < 50%). Retornando à fase de observação...")
                            self.adaptive_phase = "observation"
                            self.adaptive_observation_start_time = time.time()
                            self.adaptive_sequence = []
                            continue
                        elif conf < 60.0:
                            self.log(f"Alerta: Confiança baixa ({conf:.1f}% < 60%). Pausando o bot automaticamente.")
                            self.play_sound("error")
                            self.stop_bot("Confiança Baixa (<60%)")
                            break
                            
                        strat_type = self.adaptive_strategy.get("type", "none")
                        if self.adaptive_ready_to_click:
                            should_click = False
                            if strat_type == "entrar_apos_ticks":
                                wait_ticks = self.adaptive_strategy.get("wait_ticks", 3)
                                if self.adaptive_consec_green_ticks >= wait_ticks:
                                    should_click = True
                            elif strat_type == "entrar_apos_consecutivos_red":
                                wait_reds = self.adaptive_strategy.get("wait_reds", 2)
                                if self.adaptive_consec_red_crashes >= wait_reds and self.adaptive_consec_green_ticks >= 1:
                                    should_click = True
                            elif strat_type == "entrar_padrao_ciclo":
                                if self.adaptive_consec_green_ticks >= 3:
                                    should_click = True
                                    
                            if should_click:
                                original_win_value = self.config.get("win_value", 1.50)
                                if conf < 70.0:
                                    self.config["win_value"] = original_win_value / 2.0
                                    self.log(f"Confiança moderada ({conf:.1f}% < 70%). Entrada reduzida pela metade.")
                                
                                self._attempt_click()
                                
                                if conf < 70.0:
                                    self.config["win_value"] = original_win_value
                                    
                                self.adaptive_ready_to_click = False
                                
                        self.on_next_time_cb(0)
                        
                    time.sleep(0.3)
                    continue

                # --- CASO SEM API DA DERIV (BACKWARD COMPATIBLE SCREEN OCR) ---
                sens = self.config.get("sensitivity_number", 0.65)
                use_region = self.config.get("use_search_region", False)
                search_region = self.config.get("search_region", None) if use_region else None
                
                if search_region:
                    x_r, y_r, w_r, h_r = search_region
                    screenshot = pyautogui.screenshot(region=(x_r, y_r, w_r, h_r))
                else:
                    screenshot = pyautogui.screenshot()
                
                screenshot_np = np.array(screenshot)
                frame_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
                
                num_pos, num_conf = self._find_image_in_frame(frame_gray, number_path, sens)
                
                is_red_signal = False
                red_pixel_count = 0
                if num_pos:
                    center_x, center_y = num_pos
                    template = cv2.imread(number_path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        h, w = template.shape[:2]
                        x_start = max(0, center_x - w // 2)
                        y_start = max(0, center_y - h // 2)
                        x_end = min(screenshot_np.shape[1], center_x + w // 2)
                        y_end = min(screenshot_np.shape[0], center_y + h // 2)
                        
                        region_rgb = screenshot_np[y_start:y_end, x_start:x_end]
                        r = region_rgb[:, :, 0]
                        g = region_rgb[:, :, 1]
                        b = region_rgb[:, :, 2]
                        red_mask = (r > 120) & (r > g * 1.3) & (r > b * 1.3)
                        red_pixel_count = np.sum(red_mask)
                        if red_pixel_count >= 15:
                            is_red_signal = True
                            
                now = time.time()
                
                if num_pos:
                    if is_red_signal:
                        if not crashed:
                            self.adaptive_sequence.append("V")
                            crashed = True
                            consec_red_crashes += 1
                            consec_green_ticks = 0
                            self.adaptive_event_count_since_relearn += 1
                            self.log(f"Adaptativo: Evento 'V' registrado (Crash). Total no histórico: {len(self.adaptive_sequence)}")
                            self._trigger_relearn_if_needed()
                    else:
                        if crashed:
                            crashed = False
                            ready_to_click = True
                            consec_green_ticks = 0
                            
                        if now - last_tick_time >= 1.0:
                            self.adaptive_sequence.append("G")
                            consec_green_ticks += 1
                            consec_red_crashes = 0
                            self.adaptive_event_count_since_relearn += 1
                            last_tick_time = now
                            self._trigger_relearn_if_needed()
                else:
                    if crashed:
                        crashed = False
                        ready_to_click = True
                        consec_green_ticks = 0
                
                if self.adaptive_phase == "observation":
                    elapsed_obs = now - self.adaptive_observation_start_time
                    remaining_obs = max(0.0, obs_seconds - elapsed_obs)
                    self.on_next_time_cb(-remaining_obs)
                    
                    if elapsed_obs >= obs_seconds:
                        self.log("Fase de observação concluída! Iniciando análise estatística...")
                        self.relearn_strategy()
                        self.adaptive_phase = "operation"
                        self.play_sound("start")
                else:
                    conf = self.adaptive_strategy.get("confidence", 0.0)
                    if conf < 50.0:
                        self.log(f"Alerta: Confiança muito baixa ({conf:.1f}% < 50%). Retornando à fase de observação...")
                        self.adaptive_phase = "observation"
                        self.adaptive_observation_start_time = time.time()
                        self.adaptive_sequence = []
                        continue
                    elif conf < 60.0:
                        self.log(f"Alerta: Confiança baixa ({conf:.1f}% < 60%). Pausando o bot automaticamente.")
                        self.play_sound("error")
                        self.stop_bot("Confiança Baixa (<60%)")
                        break
                        
                    strat_type = self.adaptive_strategy.get("type", "none")
                    if ready_to_click:
                        should_click = False
                        if strat_type == "entrar_apos_ticks":
                            wait_ticks = self.adaptive_strategy.get("wait_ticks", 3)
                            if consec_green_ticks >= wait_ticks:
                                should_click = True
                        elif strat_type == "entrar_apos_consecutivos_red":
                            wait_reds = self.adaptive_strategy.get("wait_reds", 2)
                            if consec_red_crashes >= wait_reds and consec_green_ticks >= 1:
                                should_click = True
                        elif strat_type == "entrar_padrao_ciclo":
                            if consec_green_ticks >= 3:
                                should_click = True
                                
                        if should_click:
                            original_win_value = self.config.get("win_value", 1.50)
                            if conf < 70.0:
                                self.config["win_value"] = original_win_value / 2.0
                                self.log(f"Confiança moderada ({conf:.1f}% < 70%). Entrada reduzida pela metade.")
                            
                            self._attempt_click()
                            
                            if conf < 70.0:
                                self.config["win_value"] = original_win_value
                                
                            ready_to_click = False
                            
                    self.on_next_time_cb(0)
                    
            except Exception as e:
                self.log(f"Erro no loop do modo adaptativo: {e}")
                
            time.sleep(0.3)

    def _process_ai_tick(self, price, is_crash):
        self.ai_current_tick_index += 1

        # Atualiza contador de ticks seguros sem crash
        if is_crash:
            # Calcula a duração do run antes de resetar a referência
            run_length = self.ai_current_tick_index - self.ai_last_crash_index
            self.ai_survival_lengths.append(run_length)
            if len(self.ai_survival_lengths) > 10:
                self.ai_survival_lengths.pop(0)
            self.ai_last_crash_index = self.ai_current_tick_index
            self.ai_ticks_since_crash = 0
            # Se há contrato ativo e houve crash, o contrato foi perdido — API notificará via _on_api_contract_status
            # Reseta o cooldown de entrada em crash (começa contagem de segurança do zero)
            self.ai_entry_cooldown_remaining = 0
        else:
            self.ai_ticks_since_crash += 1
            # Decrementa cooldown pós-entrada
            if self.ai_entry_cooldown_remaining > 0:
                self.ai_entry_cooldown_remaining -= 1

        self.ai_tick_prices.append(price)
        if len(self.ai_tick_prices) > self.ai_tick_history_max:
            self.ai_tick_prices.pop(0)

        # Extrai o último dígito do preço
        price_str = str(price)
        last_digit = 0
        for char in reversed(price_str):
            if char.isdigit():
                last_digit = int(char)
                break
        self.ai_tick_digits.append(last_digit)
        if len(self.ai_tick_digits) > 50:
            self.ai_tick_digits.pop(0)

        # Features para o DigitAI (últimos 15 dígitos com one-hot encoding)
        if len(self.ai_tick_digits) >= 15:
            digit_features_raw = self.ai_tick_digits[-15:]
        else:
            first_val = self.ai_tick_digits[0] if len(self.ai_tick_digits) > 0 else 0
            digit_features_raw = [first_val] * (15 - len(self.ai_tick_digits)) + list(self.ai_tick_digits)
        digit_features = one_hot_encode_digits(digit_features_raw)

        # Calculate market trend based on SMA of recent prices
        if len(self.ai_tick_prices) >= 20:
            recent = self.ai_tick_prices[-8:]
            older = self.ai_tick_prices[-20:-8]
            avg_recent = sum(recent) / len(recent)
            avg_older = sum(older) / len(older)
            diff = avg_recent - avg_older
            trend_threshold = price * 0.00002
            if diff > trend_threshold:
                self.market_trend = "ALTA 🐂"
            elif diff < -trend_threshold:
                self.market_trend = "BAIXA 🐻"
            else:
                self.market_trend = "LATERAL ⚖️"
        else:
            self.market_trend = "LATERAL ⚖️"

        # Média Móvel Rápida e Lenta para Veto de Tendência
        if len(self.ai_tick_prices) >= 30:
            self.sma_10 = sum(self.ai_tick_prices[-10:]) / 10.0
            self.sma_30 = sum(self.ai_tick_prices[-30:]) / 30.0
        else:
            self.sma_10 = None
            self.sma_30 = None

        contract_mode = self.config.get("deriv_contract_mode", "accumulator")

        # Extrai features específicas do modo de contrato
        if contract_mode == "rise_fall":
            features = ai_model.extract_rise_fall_features(self.ai_tick_prices)
        else:
            features = ai_model.extract_accumulator_features(
                self.ai_tick_prices, self.ai_last_crash_index, self.ai_current_tick_index, self.ai_survival_lengths
            )

        # Cria registro de observação pendente de rotulação para a IA principal
        obs = {
            "index": self.ai_current_tick_index,
            "features": features,
            "price": price,
            "is_crash": is_crash,
            "timestamp": time.time(),
            "label": None
        }
        self.ai_observations.append(obs)

        # Rotulagem retroativa da IA principal: se passaram K ticks (padrão 3)
        K = self.config.get("ai_lookahead_ticks", 3)
        if contract_mode == "rise_fall":
            dur_val = self.config.get("deriv_rf_duration_value", 5)
            dur_unit = self.config.get("deriv_rf_duration_unit", "t")
            if dur_unit == "t":
                K = int(dur_val)
            elif dur_unit == "s":
                K = max(1, int(dur_val / 2))
            elif dur_unit == "m":
                K = max(1, int(dur_val * 30))
                
        for old_obs in self.ai_observations:
            if old_obs["label"] is None:
                if self.ai_current_tick_index - old_obs["index"] >= K:
                    if contract_mode == "accumulator":
                        crashed_in_interval = False
                        for check_obs in self.ai_observations:
                            if old_obs["index"] < check_obs["index"] <= self.ai_current_tick_index:
                                if check_obs["is_crash"]:
                                    crashed_in_interval = True
                                    break
                        label = 0 if crashed_in_interval else 1
                    else:  # rise_fall
                        future_price = price
                        for check_obs in self.ai_observations:
                            if check_obs["index"] == old_obs["index"] + K:
                                future_price = check_obs["price"]
                                break
                        label = 1 if future_price > old_obs["price"] else 0
                        
                    self.ai_replay.add(old_obs["features"], label)
                    old_obs["label"] = label

        # Limpa observações já rotuladas e antigas (limite dinâmico para evitar deletar antes de rotular)
        max_keep = max(50, K + 20)
        self.ai_observations = [o for o in self.ai_observations if o["label"] is None or self.ai_current_tick_index - o["index"] < max_keep]

        # Registro e Rotulagem retroativa do DigitAI (1 tick lookahead)
        digit_obs = {
            "index": self.ai_current_tick_index,
            "features": digit_features,
            "label": None
        }
        self.ai_digit_observations.append(digit_obs)

        for old_digit_obs in self.ai_digit_observations:
            if old_digit_obs["label"] is None:
                if self.ai_current_tick_index == old_digit_obs["index"] + 1:
                    self.ai_digit_replay.add(old_digit_obs["features"], last_digit)
                    old_digit_obs["label"] = last_digit

        self.ai_digit_observations = [o for o in self.ai_digit_observations if o["label"] is None or self.ai_current_tick_index - o["index"] < 50]

        # Treinamento periódico online (a cada 10 ticks)
        if self.ai_current_tick_index % 10 == 0:
            # Treina IA principal
            if len(self.ai_replay.memory) >= 32:
                # Executa 5 passos de treino para acelerar o aprendizado online
                for _ in range(5):
                    X_batch, y_batch = self.ai_replay.sample_batch(32)
                    loss_val = self.ai.train_on_batch(X_batch, y_batch)
                    self.ai_training_iterations += 1
                self.ai_loss = loss_val
                acc = self.ai_replay.get_accuracy(self.ai)
                self.ai_accuracy = acc
                if self.ai_current_tick_index % 100 == 0:
                    self.ai.save_weights(filepath=f"capturas/ai_weights_{contract_mode}.json")
            
            # Treina DigitAI
            if len(self.ai_digit_replay.memory) >= 32:
                # Executa 5 passos de treino
                for _ in range(5):
                    X_digit_batch, y_digit_batch = self.ai_digit_replay.sample_batch(32)
                    digit_loss = self.digit_ai.train_on_batch(np.array(X_digit_batch, dtype=np.float32), np.array(y_digit_batch, dtype=np.int64))
                    self.ai_training_iterations += 1
                if self.ai_current_tick_index % 100 == 0:
                    self.digit_ai.save_weights()

            # Se o modo for matches/differs, atualiza as métricas da GUI com os dados da rede de dígitos
            if contract_mode in ["matches", "differs"]:
                acc = self.ai_digit_replay.get_accuracy(self.digit_ai)
                self.ai_accuracy = acc
                if len(self.ai_digit_replay.memory) >= 32:
                    self.ai_loss = digit_loss

            # Atualiza métricas na GUI se callback estiver registrado
            if self.on_ai_metrics_cb:
                device_status = "GPU" if self.ai.device == "cuda" else "CPU"
                samples_count = len(self.ai_digit_replay.memory) if contract_mode in ["matches", "differs"] else len(self.ai_replay.memory)
                self.on_ai_metrics_cb(self.ai_loss, self.ai_accuracy, samples_count, device_status)

        # Prevê a probabilidade do tick atual ser seguro
        self.ai_digit_vetoed = False
        if contract_mode in ["matches", "differs"]:
            digit_probs = self.digit_ai.predict(digit_features)
            if contract_mode == "matches":
                best_digit = int(np.argmax(digit_probs))
                raw_prob = float(digit_probs[best_digit])
                # Calibragem: 10% (aleatório) = 0% confiança; 100% (certo) = 100% confiança
                self.ai_prediction_confidence = max(0.0, (raw_prob - 0.10) / 0.90)
                self.predicted_barrier = best_digit
            else:  # differs
                best_digit = int(np.argmin(digit_probs))
                raw_prob = float(digit_probs[best_digit])
                # Calibragem: 10% (aleatório) = 0% confiança; 0% (impossível) = 100% confiança
                conf = max(0.0, (0.10 - raw_prob) / 0.10)
                
                # Filtro de Segurança Estatístico (Veto micro-trend):
                # Se o dígito escolhido para Differs saiu nos últimos 3 ticks, vetamos para evitar hot streaks (rachas)
                recent_ticks = list(self.ai_tick_digits[-3:]) if len(self.ai_tick_digits) >= 3 else list(self.ai_tick_digits)
                if best_digit in recent_ticks:
                    conf = 0.0
                    self.ai_digit_vetoed = True
                    
                self.ai_prediction_confidence = conf
                self.predicted_barrier = best_digit
        else:
            self.ai_prediction_confidence = self.ai.predict(features)

        # ─── DECISÃO DE ENTRADA (somente no Modo IA, com API e contrato livre) ───
        if self.config.get("mode") != "ai":
            self.ai_reasoning_status = "Inativo"
            self.ai_reasoning_explanation = "O robô não está no Modo IA. Ative o modo 'IA Neural' nas configurações principais para iniciar a análise."
            return
        if not (self.api_client and self.api_client.connected and self.api_client.authorized):
            self.ai_reasoning_status = "Aguardando Conexão"
            self.ai_reasoning_explanation = "A API da Deriv não está conectada ou autorizada. Por favor, conecte a sua conta para permitir que o robô faça operações."
            return
            
        contract_mode = self.config.get("deriv_contract_mode", "accumulator")
        if contract_mode == "accumulator" and is_crash:
            self.ai_reasoning_status = "Bloqueado (Crash)"
            self.ai_reasoning_explanation = "Um crash de ticks foi detectado no mercado. Entrada bloqueada para evitar prejuízos."
            return

        threshold = self.config.get("ai_threshold", 75.0) / 100.0
        min_safe  = self.config.get("ai_min_ticks_safe", 5)
        cooldown  = self.config.get("ai_entry_cooldown", 10)
        
        if self.ai_active_contract:
            self.ai_reasoning_status = "Contrato Ativo"
            self.ai_reasoning_explanation = f"Existe um contrato {contract_mode.upper()} em andamento. Monitorando o mercado para ver se a operação é finalizada com lucro."
            return
            
        if self.ai_entry_cooldown_remaining > 0:
            self.ai_reasoning_status = "Cooldown Ativo"
            self.ai_reasoning_explanation = f"Aguardando a estabilização do preço após a última entrada.\nTempo de cooldown restante: {self.ai_entry_cooldown_remaining} ticks."
            return

        # Precisa de amostras suficientes para confiar na IA
        min_samples = self.config.get("ai_min_samples_start", 500)
        samples_len = len(self.ai_digit_replay.memory) if contract_mode in ["matches", "differs"] else len(self.ai_replay.memory)
        if samples_len < min_samples:
            self.ai_reasoning_status = "Coletando Dados"
            self.ai_reasoning_explanation = f"Coletando amostras de ticks para alimentar o buffer de treinamento da rede neural.\nProgresso: {samples_len} / {min_samples} ticks analisados."
            return

        # Análise neural
        ready = False
        if contract_mode == "accumulator":
            if self.ai_ticks_since_crash < min_safe:
                self.ai_reasoning_status = "Aguardando Margem"
                self.ai_reasoning_explanation = f"O mercado acabou de sofrer um crash. Aguardando margem de segurança de ticks mínimos pós-crash.\nFalta: {min_safe - self.ai_ticks_since_crash} ticks de estabilização."
            elif self.ai_prediction_confidence < threshold:
                self.ai_reasoning_status = "Aguardando Gatilho"
                self.ai_reasoning_explanation = (
                    f"A rede neural considerou a probabilidade de sobrevivência abaixo do limite de segurança.\n"
                    f"Confiança Atual: {self.ai_prediction_confidence*100:.1f}%\n"
                    f"Limiar Exigido: {threshold*100:.1f}%\n\n"
                    f"💡 DICA: Como a rede neural ainda está em fase de aprendizado online, suas previsões tendem a ficar próximas de 50%. "
                    f"Para forçar mais entradas durante o treino, tente diminuir o 'Limiar de Confiança da IA' nas configurações para 60% ou 55%."
                )
            else:
                ready = True
        elif contract_mode in ["matches", "differs"]:
            if getattr(self, "ai_digit_vetoed", False):
                self.ai_reasoning_status = "Veto Estatístico 🛑"
                self.ai_reasoning_explanation = (
                    f"Entrada bloqueada por segurança estatística contra rachas.\n"
                    f"Dígito Alvo: {getattr(self, 'predicted_barrier', 0)}\n"
                    f"Motivo: O dígito {getattr(self, 'predicted_barrier', 0)} saiu nos últimos 3 ticks. Evitando hot streaks."
                )
            elif self.ai_prediction_confidence < threshold:
                self.ai_reasoning_status = "Aguardando Gatilho"
                if contract_mode == "differs":
                    raw_prob_val = 0.10 * (1.0 - self.ai_prediction_confidence)
                    prob_desc = f"Probabilidade prevista: {raw_prob_val*100:.1f}%"
                else:
                    raw_prob_val = 0.10 + 0.90 * self.ai_prediction_confidence
                    prob_desc = f"Probabilidade prevista: {raw_prob_val*100:.1f}%"
                
                self.ai_reasoning_explanation = (
                    f"A rede neural considerou a confiança na previsão de dígitos abaixo do limite.\n"
                    f"Dígito Alvo: {getattr(self, 'predicted_barrier', 0)} ({prob_desc})\n"
                    f"Confiança Atual: {self.ai_prediction_confidence*100:.1f}%\n"
                    f"Limiar Exigido: {threshold*100:.1f}%"
                )
            else:
                ready = True
        else:  # rise_fall
            is_strong_call = self.ai_prediction_confidence >= threshold
            is_strong_put = self.ai_prediction_confidence <= (1.0 - threshold)
            
            # --- FILTRO 1: SMA TREND VETO ---
            self.ai_trend_vetoed = False
            if (is_strong_call or is_strong_put) and getattr(self, "sma_10", None) is not None and getattr(self, "sma_30", None) is not None:
                if is_strong_call and (self.sma_10 < self.sma_30):
                    # Permite apenas se a confiança for ultra-forte
                    if self.ai_prediction_confidence < min(0.95, threshold + 0.15):
                        self.ai_reasoning_status = "Veto de Tendência 🛑"
                        self.ai_reasoning_explanation = (
                            f"Operação CALL (Alta) bloqueada por segurança.\n"
                            f"A tendência macro é de BAIXA (Média Rápida {self.sma_10:.5f} < Lenta {self.sma_30:.5f}).\n"
                            f"Confiança: {self.ai_prediction_confidence*100:.1f}% (Necessário {min(0.95, threshold + 0.15)*100:.0f}% para contra-tendência)"
                        )
                        self.ai_trend_vetoed = True
                elif is_strong_put and (self.sma_10 > self.sma_30):
                    # Permite apenas se a confiança for ultra-forte
                    if self.ai_prediction_confidence > max(0.05, (1.0 - threshold) - 0.15):
                        self.ai_reasoning_status = "Veto de Tendência 🛑"
                        self.ai_reasoning_explanation = (
                            f"Operação PUT (Baixa) bloqueada por segurança.\n"
                            f"A tendência macro é de ALTA (Média Rápida {self.sma_10:.5f} > Lenta {self.sma_30:.5f}).\n"
                            f"Confiança: {(1.0 - self.ai_prediction_confidence)*100:.1f}% (Necessário {min(0.95, threshold + 0.15)*100:.0f}% para contra-tendência)"
                        )
                        self.ai_trend_vetoed = True

            # --- FILTRO 3: SMART CONFIDENCE MARTINGALE VETO ---
            self.ai_martingale_vetoed = False
            if (is_strong_call or is_strong_put) and not self.ai_trend_vetoed:
                if getattr(self, "martingale_level", 0) > 0:
                    martingale_threshold = max(0.70, threshold + 0.10)
                    current_conf = self.ai_prediction_confidence if is_strong_call else (1.0 - self.ai_prediction_confidence)
                    if current_conf < martingale_threshold:
                        self.ai_reasoning_status = "Martingale Veto 🛑"
                        self.ai_reasoning_explanation = (
                            f"Recuperação Martingale pausada (Nível {self.martingale_level}).\n"
                            f"Aguardando sinal com maior confiança para proteger a banca.\n"
                            f"Confiança Atual: {current_conf*100:.1f}% | Exigido para Martingale: {martingale_threshold*100:.0f}%"
                        )
                        self.ai_martingale_vetoed = True

            if not (is_strong_call or is_strong_put):
                self.ai_reasoning_status = "Mercado Indeciso"
                self.ai_reasoning_explanation = (
                    f"Rede neural indicou mercado sem tendência de direção clara (lateralizado).\n"
                    f"Confiança para Alta (CALL): {self.ai_prediction_confidence*100:.1f}%\n"
                    f"Confiança para Baixa (PUT): {(1.0 - self.ai_prediction_confidence)*100:.1f}%\n"
                    f"Limiar Exigido: {threshold*100:.1f}%\n\n"
                    f"💡 DICA: No início do treinamento, a rede neural se mantém neutra (próxima de 50%). "
                    f"Você pode diminuir o 'Limiar de Confiança da IA' nas configurações principais (ex: para 60% ou 55%) "
                    f"para tornar a tomada de decisão mais sensível e permitir mais entradas."
                )
            elif not self.ai_trend_vetoed and not self.ai_martingale_vetoed:
                ready = True

        if ready:
            self.ai_active_contract = True
            self.ai_entry_cooldown_remaining = cooldown
            threading.Thread(
                target=self._query_llama_and_trade,
                args=(contract_mode, threshold, cooldown, self.ai_prediction_confidence),
                daemon=True
            ).start()

    def _query_llama_and_trade(self, contract_mode, threshold, cooldown, confidence):
        try:
            direction = None
            duration = None
            duration_unit = None
            llama_veto = False
            
            # Se Llama estiver habilitado, consulta o Llama
            if self.llama.enabled:
                self.log("🤖 [Modo IA] Consultando Llama para avaliacao de entrada...")
                self.ai_reasoning_status = "Consultando Llama"
                llama_model_name = getattr(self.llama, "model_name", getattr(self.llama, "model", "Llama"))
                self.ai_reasoning_explanation = f"Rede neural confirmou o padrão de entrada. Consultando o modelo Llama ({llama_model_name}) para validação macro..."
                winrate = (self.win_count / (self.win_count + self.loss_count) * 100.0) if (self.win_count + self.loss_count) > 0 else 0.0
                decision = self.llama.get_decision(
                    mode=contract_mode,
                    tick_history=self.ai_tick_digits if contract_mode in ["matches", "differs"] else self.ai_tick_prices,
                    current_profit=self.current_profit,
                    winrate=winrate,
                    recent_ops=self.recent_ops
                )
                if decision:
                    if contract_mode in ["accumulator", "matches", "differs"]:
                        if not decision.get("is_safe", False):
                            self.log("🤖 [Llama] Operacao vetada por motivos de seguranca.")
                            self.ai_reasoning_status = "Veto do Llama 🚫"
                            self.ai_reasoning_explanation = f"A rede neural indicou entrada, mas o modelo Llama ({llama_model_name}) vetou a operação considerando alto risco macro."
                            llama_veto = True
                    else:  # rise_fall
                        direction = decision.get("direction")
                        duration = decision.get("duration")
                        duration_unit = decision.get("duration_unit")
                        llama_conf = decision.get("confidence", 0.0)
                        self.log(f"🤖 [Llama] Decisao: {str(direction).upper()} | Duracao: {duration}{duration_unit} | Confianca: {llama_conf}%")
            
            if llama_veto:
                self.ai_active_contract = False
                return
 
            # Fallback para definicao de direcao no modo rise_fall se o Llama nao respondeu ou esta desligado
            if contract_mode == "rise_fall" and not direction:
                if confidence >= threshold:
                    direction = "rise"
                elif confidence <= (1.0 - threshold):
                    direction = "fall"
                else:
                    # Fallback via EMA de curtissimo prazo
                    if len(self.ai_tick_prices) >= 8:
                        recent = self.ai_tick_prices[-3:]
                        older = self.ai_tick_prices[-8:-3]
                        ema_fast = sum(recent) / len(recent)
                        ema_slow = sum(older) / len(older)
                        direction = "rise" if ema_fast >= ema_slow else "fall"
                    else:
                        direction = "rise"
            
            samples_count = len(self.ai_digit_replay.memory) if contract_mode in ["matches", "differs"] else len(self.ai_replay.memory)
            self.log(
                f"🎯 [Modo IA] ENTRADA ({contract_mode.upper()})! "
                f"Confianca Neural={confidence*100:.1f}% "
                f"(Threshold: {threshold*100:.0f}%) | Amostras={samples_count}"
            )
            self.ai_reasoning_status = "Entrada Confirmada 🚀"
            if contract_mode == "rise_fall":
                self.ai_reasoning_explanation = f"Padrão confirmado! Solicitando entrada Rise/Fall via API:\nDireção: {str(direction).upper()}\nDuração: {duration or 5}{duration_unit or 't'}\nConfiança Neural: {confidence*100:.1f}%"
            elif contract_mode in ["matches", "differs"]:
                barrier = getattr(self, "predicted_barrier", 0)
                self.ai_reasoning_explanation = f"Padrão confirmado em {contract_mode.upper()}! Solicitando entrada via API.\nDígito Previsto: {barrier}\nConfiança Neural: {confidence*100:.1f}%"
            else:
                self.ai_reasoning_explanation = f"Padrão de segurança confirmado no Accumulator! Solicitando compra via API.\nConfiança Neural: {confidence*100:.1f}%"
 
            self._attempt_click(direction=direction, duration=duration, duration_unit=duration_unit)
        except Exception as e:
            self.log(f"❌ [Modo IA] Erro ao processar entrada/Llama: {e}")
            self.ai_active_contract = False
            self.ai_reasoning_status = "Erro na Entrada"
            self.log(f"❌ [Modo IA] Erro ao processar entrada/Llama: {e}")
            self.ai_active_contract = False
            self.ai_reasoning_status = "Erro na Entrada"
            self.ai_reasoning_explanation = f"Ocorreu um erro ao processar a entrada: {e}"



    def _run_ai_mode(self):
        """
        Modo IA puro — 100% orientado a dados da API Deriv em tempo real.
        Sem captura de tela. Ticks vêm de _on_api_tick via WebSocket.
        A lógica de entrada também está em _on_api_tick para reação imediata.
        """
        # Verifica se a API está configurada — obrigatório neste modo
        token = self.config.get("deriv_api_token", "").strip()
        if not token:
            self.log("❌ [Modo IA] Token de API não configurado! Configure o Token PAT e o App ID em Configurações Avançadas.")
            self.stop_bot()
            return

        # Aguarda a API conectar e carregar parâmetros da barreira (máx 15 s)
        self.log("🧠 [Modo IA] Aguardando conexão e parâmetros de barreira da API Deriv...")
        waited = 0
        while self.running and waited < 15:
            if self.api_client and self.api_client.authorized and self.api_client.barrier_distance is not None:
                break
            time.sleep(0.5)
            waited += 0.5

        if not self.running:
            return

        if not (self.api_client and self.api_client.authorized and self.api_client.barrier_distance is not None):
            self.log("❌ [Modo IA] Não foi possível conectar ou obter parâmetros de barreira da API em 15 segundos. Verifique o token, App ID e o mercado.")
            self.stop_bot()
            return

        self.log(f"✅ [Modo IA] API conectada! Conta: {self.config.get('deriv_account_type','demo').upper()} | Saldo: ${self.api_client.balance:.2f}")

        # Executa pesquisa de mercado automática se ativada
        if self.config.get("deriv_scan_market", False):
            self._scan_best_asset_and_timeframe()
            if not self.running:
                return

        # Solicita histórico para pré-alimentar e treinar a IA antes de operar
        self.log("📊 [Modo IA] Solicitando histórico de ticks para pré-treinar a rede neural...")
        self.api_client.request_ticks_history(1000)

        # Carrega pesos específicos para o tipo de contrato ativo para evitar contaminação
        contract_mode = self.config.get("deriv_contract_mode", "accumulator")
        if contract_mode not in ["matches", "differs"]:
            weights_file = f"capturas/ai_weights_{contract_mode}.json"
            self.log(f"🧠 [Modo IA] Carregando pesos específicos para {contract_mode.upper()} de '{weights_file}'...")
            self.ai.load_weights(weights_file)

        # Inicializa estado da IA
        self.ai_ticks_since_crash = 0
        self.ai_entry_cooldown_remaining = 0
        self.ai_active_contract = False
        self.ai_selling_contract_id = None

        threshold = self.config.get("ai_threshold", 75.0)
        min_safe = self.config.get("ai_min_ticks_safe", 5)
        cooldown = self.config.get("ai_entry_cooldown", 10)

        self.log(
            f"🤖 [Modo IA] Parâmetros: Limiar={threshold:.0f}% | "
            f"Ticks mín. seguros={min_safe} | Cooldown pós-entrada={cooldown} ticks"
        )
        self.log("⏳ [Modo IA] Coletando dados e treinando... Primeiras entradas após acumular amostras suficientes.")

        # Contador para log periódico
        last_status_log_tick = 0

        # O loop principal apenas mantém o bot vivo. Todo processamento de ticks
        # e tomada de decisão ocorre em _on_api_tick (chamado pelo WebSocket thread).
        while self.running:
            self._wait_if_in_cycle_cooldown()
            if not self.running:
                break

            # Verifica se a API ainda está conectada
            if not (self.api_client and self.api_client.connected):
                self.log("⚠️ [Modo IA] Conexão com a API perdida. Aguardando reconexão...")
                time.sleep(2)
                continue

            # Log de status periódico (a cada ~60 s)
            if self.ai_current_tick_index - last_status_log_tick >= 120:
                last_status_log_tick = self.ai_current_tick_index
                self.log(
                    f"📈 [Modo IA Status] Tick #{self.ai_current_tick_index} | "
                    f"Amostras: {len(self.ai_replay.memory)} | "
                    f"Acurácia: {self.ai_accuracy:.1f}% | "
                    f"Loss: {self.ai_loss:.4f} | "
                    f"Ticks s/ crash: {self.ai_ticks_since_crash} | "
                    f"Contrato ativo: {'Sim' if self.ai_active_contract else 'Não'} | "
                    f"Cooldown: {self.ai_entry_cooldown_remaining} ticks"
                )

            time.sleep(0.5)


    def _trigger_relearn_if_needed(self):
        now = time.time()
        elapsed_relearn = now - self.adaptive_relearn_start_time
        relearn_min = self.config.get("adaptive_relearn_minutes", 30)
        relearn_events = self.config.get("adaptive_relearn_events", 100)
        
        trigger = False
        if elapsed_relearn >= relearn_min * 60:
            self.log(f"Gatilho de reaprendizado: {relearn_min} minutos decorridos.")
            trigger = True
        elif self.adaptive_event_count_since_relearn >= relearn_events:
            self.log(f"Gatilho de reaprendizado: {relearn_events} eventos coletados.")
            trigger = True
            
        if trigger:
            self.relearn_strategy()

    def relearn_strategy(self):
        self.adaptive_relearn_start_time = time.time()
        self.adaptive_event_count_since_relearn = 0
        self.adaptive_loss_count_since_relearn = 0
        
        seq = self.adaptive_sequence
        if not seq:
            self.log("Adaptativo: Não há eventos suficientes para analisar.")
            return
            
        total_events = len(seq)
        
        v_indices = [i for i, x in enumerate(seq[:-1]) if x == 'V']
        v_followed_by_v = sum(1 for idx in v_indices if seq[idx+1] == 'V')
        p_v_after_v = (v_followed_by_v / len(v_indices) * 100) if v_indices else 0.0
        p_g_after_v = 100.0 - p_v_after_v
        
        v_runs = []
        current_run = 0
        for x in seq:
            if x == 'V':
                current_run += 1
            else:
                if current_run > 0:
                    v_runs.append(current_run)
                    current_run = 0
        if current_run > 0:
            v_runs.append(current_run)
            
        most_common_v_run = 1
        if v_runs:
            most_common_v_run = max(set(v_runs), key=v_runs.count)
            
        rounds = []
        current_g = 0
        for x in seq:
            if x == 'G':
                current_g += 1
            elif x == 'V':
                rounds.append(current_g)
                current_g = 0
                
        avg_g_interval = 2.8
        most_common_g_interval = 3
        if rounds:
            avg_g_interval = round(sum(rounds) / len(rounds), 1)
            most_common_g_interval = max(set(rounds), key=rounds.count)
            if most_common_g_interval < 1:
                most_common_g_interval = 1
                
        best_strategy = "entrar_padrao_ciclo"
        best_confidence = 50.0
        best_params = {}
        
        for t in range(1, 6):
            wins = sum(1 for r in rounds if r >= t + 1)
            total_entries = sum(1 for r in rounds if r >= t)
            win_rate = (wins / total_entries * 100) if total_entries > 0 else 0.0
            
            if total_entries >= 3 and win_rate > best_confidence:
                best_confidence = win_rate
                best_strategy = "entrar_apos_ticks"
                best_params = {"wait_ticks": t}
                
        for r in range(1, 4):
            wins = 0
            total_entries = 0
            for i in range(r, len(rounds)):
                if all(rounds[i-k] <= 1 for k in range(1, r+1)):
                    total_entries += 1
                    if rounds[i] >= 2:
                        wins += 1
            win_rate = (wins / total_entries * 100) if total_entries > 0 else 0.0
            if total_entries >= 3 and win_rate > best_confidence:
                best_confidence = win_rate
                best_strategy = "entrar_apos_consecutivos_red"
                best_params = {"wait_reds": r}
                
        confidence_val = round(best_confidence, 1)
        if best_strategy == "entrar_apos_ticks":
            ticks = best_params["wait_ticks"]
            strategy_text = f"Entrar após {ticks} ticks verdes"
            dominant_pattern = f"{ticks} ciclos → repetição"
        elif best_strategy == "entrar_apos_consecutivos_red":
            reds = best_params["wait_reds"]
            strategy_text = f"Entrar após {reds} vermelhos consecutivos"
            dominant_pattern = f"{reds} red consecutivos"
        else:
            strategy_text = "Entrar após 3 ciclos verdes (padrão)"
            dominant_pattern = "3 ciclos → repetição"
            best_params = {"wait_ticks": 3}
            confidence_val = 65.0
            
        self.adaptive_strategy = {
            "type": best_strategy,
            "wait_ticks": best_params.get("wait_ticks", 3),
            "wait_reds": best_params.get("wait_reds", 2),
            "text": strategy_text,
            "dominant_pattern": dominant_pattern,
            "confidence": confidence_val,
            "eventos_analisados": total_events,
            "probabilidade_repeticao": round(p_v_after_v, 1),
            "sequencia_mais_comum": most_common_g_interval
        }
        
        session_db = {
            "eventos_analisados": total_events,
            "sequencia_mais_comum": most_common_g_interval,
            "probabilidade_repeticao": round(p_v_after_v, 1),
            "confianca": confidence_val,
            "estrategia": best_strategy,
            "detalhes_estrategia": strategy_text
        }
        
        try:
            with open("adaptive_session.json", "w", encoding="utf-8") as f:
                json.dump(session_db, f, indent=4, ensure_ascii=False)
            self.log(f"Adaptativo: Análise estatística concluída! Estratégia: '{strategy_text}' | Confiança: {confidence_val}%")
        except Exception as e:
            self.log(f"Erro ao salvar adaptive_session.json: {e}")

    def _attempt_click(self, direction=None, duration=None, duration_unit=None):
        # --- EXECUÇÃO VIA API DA DERIV ---
        use_api_trading = self.config.get("deriv_use_api_trading", False)
        
        if use_api_trading and self.api_client and self.api_client.connected and self.api_client.authorized:
            base_stake = self.config.get("win_value", 1.50)
            contract_mode = self.config.get("deriv_contract_mode", "accumulator")
            
            # --- MARTINGALE INTELIGENTE (APLICAÇÃO) ---
            if getattr(self, "martingale_level", 0) > 0 and contract_mode == "rise_fall":
                stake = base_stake * (2.0 ** self.martingale_level)
                self.log(f"🔥 [Martingale] Aplicando stake recuperado (Nível {self.martingale_level}): ${stake:.2f}")
            else:
                stake = base_stake
            
            if contract_mode == "accumulator":
                self.api_client.growth_rate = float(self.config.get("deriv_growth_rate", 0.01))
                self.log(f"[API] Enviando ordem de compra Accumulator (Stake: ${stake:.2f})")
                success = self.api_client.buy_accumulator(stake)
            elif contract_mode in ["matches", "differs"]:
                barrier = getattr(self, "predicted_barrier", 0)
                contract_type = "DIGITMATCH" if contract_mode == "matches" else "DIGITDIFF"
                self.log(f"[API] Enviando ordem {contract_mode.upper()} -> Dígito previsto: {barrier} | Stake: ${stake:.2f}")
                success = self.api_client.buy_digits(stake, contract_type, barrier)
            else:  # rise_fall
                if not direction:
                    # Direção padrão baseada em EMAs das features/preços
                    if len(self.ai_tick_prices) >= 8:
                        recent = self.ai_tick_prices[-3:]
                        older = self.ai_tick_prices[-8:-3]
                        ema_fast = sum(recent) / len(recent)
                        ema_slow = sum(older) / len(older)
                        direction = "rise" if ema_fast >= ema_slow else "fall"
                    else:
                        direction = "rise"
                
                # --- EXPIRAÇÃO DINÂMICA (VOLATILIDADE) ---
                if not duration:
                    is_auto = self.config.get("deriv_rf_auto_duration", True)
                    unit = self.config.get("deriv_rf_duration_unit", "t")
                    
                    if is_auto and unit == "t":
                        if len(self.ai_tick_prices) >= 20:
                            recent_diffs = []
                            for i in range(-19, 0):
                                prev = self.ai_tick_prices[i-1]
                                curr = self.ai_tick_prices[i]
                                recent_diffs.append(abs(curr - prev))
                            volatility = sum(recent_diffs) / len(recent_diffs)
                            avg_price = sum(self.ai_tick_prices[-20:]) / 20.0
                            vol_ratio = volatility / (avg_price * 0.0001 + 1e-9)
                            
                            if vol_ratio < 0.3: # volatilidade ultra-baixa
                                duration = 8
                            elif vol_ratio < 0.6: # volatilidade baixa
                                duration = 6
                            elif vol_ratio > 1.5: # volatilidade ultra-alta
                                duration = 3
                            elif vol_ratio > 1.0: # volatilidade alta
                                duration = 4
                            else: # padrão
                                duration = 5
                            self.log(f"⚡ [Expiração Dinâmica] Volatilidade: {vol_ratio:.2f} -> Definindo expiração para {duration} ticks.")
                        else:
                            duration = self.config.get("deriv_rf_duration_value", 5)
                    else:
                        duration = self.config.get("deriv_rf_duration_value", 5)
                
                # Armazena a expiração dinâmica atual para o overlay
                self.last_dynamic_duration = duration
                if not duration_unit:
                    duration_unit = self.config.get("deriv_rf_duration_unit", "t")
                self.log(f"[API] Enviando ordem Rise/Fall -> Direcao: {direction.upper()} | Duracao: {duration}{duration_unit} | Stake: ${stake:.2f}")
                success = self.api_client.buy_rise_fall(stake, direction, duration, duration_unit)
                
            if success:
                self.click_count += 1
                self.on_click_cb(self.click_count)
                if self.on_finance_cb:
                    self.on_finance_cb(self.current_profit, self.click_count)
                self.play_sound("click")
                
                # --- CICLOS DE ENTRADAS ---
                if self.config.get("cycle_enabled", False) and self.config.get("mode") != "ai":
                    self.cycle_entries_count += 1
                    self.log(f"[Ciclos] Entrada registrada ({self.cycle_entries_count}/{self.config.get('cycle_max_entries', 4)} no ciclo atual)")
                    if self.cycle_entries_count >= self.config.get("cycle_max_entries", 4):
                        self.in_cycle_cooldown = True
                        self.cycle_cooldown_end_time = time.time() + self.config.get("cycle_cooldown_minutes", 60) * 60
                
                # Limite Modo Livre (Entradas)
                finance_mode = self.config.get("finance_mode", "target")
                if finance_mode == "free":
                    limit_entries = self.config.get("free_entries", 10)
                    if self.click_count >= limit_entries:
                        self.log(f"Limite de Entradas atingido ({self.click_count}/{limit_entries} em Modo Livre)! Parando bot...")
                        self.on_stop_limit_cb("entries", self.click_count)
                        
                        stop_free_msg = (
                            "🏁 <b>LIMITE DE ENTRADAS ALCANÇADO!</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            f"📊 <b>Total de Entradas:</b> {self.click_count}\n"
                            f"💰 <b>Saldo Final:</b> ${self.current_profit:.2f}\n"
                            f"📈 <b>Assertividade Final:</b> {(self.win_count / (self.win_count + self.loss_count) * 100) if (self.win_count + self.loss_count) > 0 else 0.0:.1f}%\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        telegram_sender.send_telegram_msg(self.config, stop_free_msg, self.log)
                        time.sleep(2)
                        self.stop_bot("entries")
            else:
                self.log("Falha ao efetuar compra via API.")
            return

        # --- CASO CONTRÁRIO, MANTÉM COMPORTAMENTO ANTERIOR (CLIQUE FÍSICO) ---
        image_path = self.config.get("image_button_path", "capturas/botao.png")
        sens = self.config.get("sensitivity", 0.8)
        
        pos, conf = self.find_image(image_path, sens)
        if pos:
            x, y = pos
            orig_x, orig_y = pyautogui.position()
            
            pyautogui.click(x, y)
            pyautogui.moveTo(orig_x, orig_y)
            
            self.click_count += 1
            self.on_click_cb(self.click_count)
            if self.on_finance_cb:
                self.on_finance_cb(self.current_profit, self.click_count)
                
            self.log(f"Botao encontrado (Confianca: {conf:.2f}), clicado em ({x}, {y}).")
            self.play_sound("click")
            
            # --- CICLOS DE ENTRADAS ---
            if self.config.get("cycle_enabled", False) and self.config.get("mode") != "ai":
                self.cycle_entries_count += 1
                self.log(f"[Ciclos] Entrada registrada ({self.cycle_entries_count}/{self.config.get('cycle_max_entries', 4)} no ciclo atual)")
                if self.cycle_entries_count >= self.config.get("cycle_max_entries", 4):
                    self.in_cycle_cooldown = True
                    self.cycle_cooldown_end_time = time.time() + self.config.get("cycle_cooldown_minutes", 60) * 60
            
            # Limite Modo Livre (Entradas)
            finance_mode = self.config.get("finance_mode", "target")
            if finance_mode == "free":
                limit_entries = self.config.get("free_entries", 10)
                if self.click_count >= limit_entries:
                    self.log(f"Limite de Entradas atingido ({self.click_count}/{limit_entries} em Modo Livre)! Parando bot...")
                    self.on_stop_limit_cb("entries", self.click_count)
                    
                    stop_free_msg = (
                        "🏁 <b>LIMITE DE ENTRADAS ALCANÇADO!</b>\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Total de Entradas:</b> {self.click_count}\n"
                        f"💰 <b>Saldo Final:</b> ${self.current_profit:.2f}\n"
                        f"📈 <b>Assertividade Final:</b> {(self.win_count / (self.win_count + self.loss_count) * 100) if (self.win_count + self.loss_count) > 0 else 0.0:.1f}%\n"
                        "━━━━━━━━━━━━━━━━━━"
                    )
                    telegram_sender.send_telegram_msg(self.config, stop_free_msg, self.log)
                    time.sleep(2)
                    self.stop_bot("entries")
        else:
            self.log(f"Botao de clique nao encontrado (Maior confianca: {conf:.2f}).")

    def _find_image_in_frame(self, frame_gray, template_path, sensitivity):
        if not os.path.exists(template_path):
            return None, 0.0
        try:
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                return None, 0.0
            
            h, w = template.shape[:2]
            res = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= sensitivity:
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y), max_val
            return None, max_val
        except Exception:
            return None, 0.0

    def take_screenshot_from_frame(self, screenshot_img, name_prefix):
        if not self.config.get("auto_screenshot", False):
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capturas/historico/{name_prefix}_{timestamp}.png"
            screenshot_img.save(filename)
            self.log(f"Screenshot salvo: {filename}")
        except Exception as e:
            self.log(f"Erro ao salvar screenshot: {e}")

    def _results_monitor_loop(self):
        if self.config.get("deriv_use_api_trading", False):
            self.log("[Monitor] Operações via API ativas: ignorando monitoramento por captura de tela.")
            return
            
        win_image_path = self.config.get("image_win_path", "capturas/win.png")
        win2_image_path = self.config.get("image_win2_path", "capturas/win2.png")
        loss_image_path = self.config.get("image_loss_path", "capturas/loss.png")
        sens = self.config.get("sensitivity", 0.8)
        
        while self.running:
            try:
                screenshot = pyautogui.screenshot()
                screenshot_np = np.array(screenshot)
                screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
                
                now = time.time()
                
                # --- MONITOR DE WIN ---
                win_pos, win_conf = self._find_image_in_frame(screenshot_gray, win_image_path, sens)
                win2_pos, win2_conf = None, 0.0
                if os.path.exists(win2_image_path):
                    win2_pos, win2_conf = self._find_image_in_frame(screenshot_gray, win2_image_path, sens)
                
                # Prioritiza win2 se detectado, senao win comum
                detected_win_pos = win2_pos if win2_pos is not None else win_pos
                detected_win_conf = win2_conf if win2_pos is not None else win_conf
                is_win2 = win2_pos is not None
                
                if detected_win_pos:
                    if not self.win_detected_state and (now - self.last_win_time > 3.0):
                        self.win_count += 1
                        self.martingale_level = 0
                        self.last_win_time = now
                        self.win_detected_state = True
                        
                        self.on_win_cb(self.win_count)
                        self.adaptive_loss_count_since_relearn = 0
                        
                        # Atualiza Saldo Financeiro ($1.00 se for win2, senao win_value)
                        win_val = 1.00 if is_win2 else self.config.get("win_value", 1.50)
                        self.current_profit += win_val
                        self.recent_ops.append(("WIN", win_val, datetime.datetime.now().strftime("%H:%M:%S")))
                        self.recent_ops = self.recent_ops[-10:]
                        if self.on_finance_cb:
                            self.on_finance_cb(self.current_profit, self.click_count)
                        
                        win_type_str = "WIN2" if is_win2 else "WIN"
                        self.log(f"{win_type_str} detectado! (Confianca: {detected_win_conf:.2f}, Retorno: ${win_val:.2f}) - Wins Totais: {self.win_count} | Saldo: ${self.current_profit:.2f}")
                        self.play_sound("win")
                        self.save_result_to_history(win_type_str)
                        self.take_screenshot_from_frame(screenshot, win_type_str.lower())
                        
                        # Notificacao Telegram Win
                        total_conclusion = self.win_count + self.loss_count
                        rate = (self.win_count / total_conclusion * 100) if total_conclusion > 0 else 0.0
                        win_msg = (
                            f"🟢 <b>{win_type_str} DETECTADO!</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            f"🏆 <b>Resultado:</b> VITÓRIA ({win_type_str})!\n"
                            f"🔥 <b>Confiança:</b> {detected_win_conf:.2f}\n"
                            f"💵 <b>Retorno:</b> ${win_val:.2f}\n"
                            f"💰 <b>Saldo Atual:</b> ${self.current_profit:.2f}\n"
                            "📊 <b>Placar Geral:</b>\n"
                            f"├─ Wins: {self.win_count}\n"
                            f"└─ Losses: {self.loss_count}\n"
                            f"📈 <b>Assertividade:</b> {rate:.1f}%\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        telegram_sender.send_telegram_msg(self.config, win_msg, self.log)
                        
                        # Limite Meta de Lucro
                        finance_mode = self.config.get("finance_mode", "target")
                        if finance_mode == "target":
                            target = self.config.get("target_profit", 10.00)
                            if self.current_profit >= target:
                                self.log(f"Meta de Lucro Atingida (${self.current_profit:.2f} >= ${target:.2f})! Parando bot...")
                                self.on_stop_limit_cb("profit_win", self.current_profit)
                                
                                stop_target_msg = (
                                    "💰 <b>META DE LUCRO ALCANÇADA!</b>\n"
                                    "━━━━━━━━━━━━━━━━━━\n"
                                    f"✅ <b>Saldo Final:</b> ${self.current_profit:.2f}\n"
                                    f"🎯 <b>Meta Definida:</b> ${target:.2f}\n"
                                    f"📊 <b>Placar Geral:</b> {self.win_count} Wins - {self.loss_count} Losses\n"
                                    f"📈 <b>Assertividade Final:</b> {rate:.1f}%\n"
                                    "━━━━━━━━━━━━━━━━━━"
                                )
                                telegram_sender.send_telegram_msg(self.config, stop_target_msg, self.log)
                                time.sleep(2)
                                self.stop_bot("profit_win")
                                break
                        
                        if self.config.get("enable_stop_win", False) and self.win_count >= self.config.get("stop_win", 5):
                            self.log(f"Limite Stop Win atingido ({self.win_count} Wins)! Parando bot...")
                            self.on_stop_limit_cb("win", self.win_count)
                            
                            # Notificacao Telegram Stop Win
                            stop_win_msg = (
                                "💰 <b>STOP WIN ALCANÇADO!</b>\n"
                                "━━━━━━━━━━━━━━━━━━\n"
                                f"✅ <b>Meta Batida:</b> {self.win_count} Wins!\n"
                                "🏁 <b>Estado:</b> Bot Finalizado (Meta Concluída)\n"
                                f"📈 <b>Assertividade Final:</b> {rate:.1f}%\n"
                                "━━━━━━━━━━━━━━━━━━\n"
                                "<i>Sessão finalizada com sucesso. Lucro garantido!</i>"
                            )
                            telegram_sender.send_telegram_msg(self.config, stop_win_msg, self.log)
                            time.sleep(2)  # aguarda envio do Telegram antes de parar
                            self.stop_bot("win")
                            break
                else:
                    if win_conf < (sens - 0.05):
                        self.win_detected_state = False
                    
                    # --- MONITOR DE LOSS ---
                    loss_pos, loss_conf = self._find_image_in_frame(screenshot_gray, loss_image_path, sens)
                    if loss_pos:
                        if not self.loss_detected_state and (now - self.last_loss_time > 3.0):
                            self.loss_count += 1
                            if not hasattr(self, "martingale_level"):
                                self.martingale_level = 0
                            self.martingale_level += 1
                            self.last_loss_time = now
                            self.loss_detected_state = True
                            
                            self.on_loss_cb(self.loss_count)
                            
                            # Treina imediatamente pós-loss no modo IA
                            if self.config.get("mode") == "ai":
                                self.force_ai_loss_learning()
                            
                            self.adaptive_loss_count_since_relearn += 1
                            if self.config.get("mode") == "adaptive":
                                relearn_losses = self.config.get("adaptive_relearn_losses", 3)
                                if self.adaptive_loss_count_since_relearn >= relearn_losses:
                                    self.log(f"Gatilho de reaprendizado: {relearn_losses} losses consecutivas atingidas.")
                                    self.relearn_strategy()
                            
                            # Atualiza Saldo Financeiro
                            loss_val = self.config.get("loss_value", 30.00)
                            self.current_profit -= loss_val
                            self.recent_ops.append(("LOSS", -loss_val, datetime.datetime.now().strftime("%H:%M:%S")))
                            self.recent_ops = self.recent_ops[-10:]
                            if self.on_finance_cb:
                                self.on_finance_cb(self.current_profit, self.click_count)
                                
                            self.log(f"LOSS detectado! (Confianca: {loss_conf:.2f}) - Losses Totais: {self.loss_count} | Saldo: ${self.current_profit:.2f}")
                            self.play_sound("loss")
                            self.save_result_to_history("LOSS")
                            self.take_screenshot_from_frame(screenshot, "loss")
                            
                            # Notificacao Telegram Loss
                            total_conclusion = self.win_count + self.loss_count
                            rate = (self.win_count / total_conclusion * 100) if total_conclusion > 0 else 0.0
                            loss_msg = (
                                "🔴 <b>LOSS DETECTADO!</b>\n"
                                "━━━━━━━━━━━━━━━━━━\n"
                                "💔 <b>Resultado:</b> DERROTA!\n"
                                f"🔥 <b>Confiança:</b> {loss_conf:.2f}\n"
                                f"💰 <b>Saldo Atual:</b> ${self.current_profit:.2f}\n"
                                "📊 <b>Placar Geral:</b>\n"
                                f"├─ Wins: {self.win_count}\n"
                                f"└─ Losses: {self.loss_count}\n"
                                f"📈 <b>Assertividade:</b> {rate:.1f}%\n"
                                "━━━━━━━━━━━━━━━━━━"
                            )
                            telegram_sender.send_telegram_msg(self.config, loss_msg, self.log)
                            
                            if self.config.get("enable_stop_loss", False) and self.loss_count >= self.config.get("stop_loss", 3):
                                self.log(f"Limite Stop Loss atingido ({self.loss_count} Losses)! Parando bot...")
                                self.on_stop_limit_cb("loss", self.loss_count)
                                
                                # Notificacao Telegram Stop Loss
                                stop_loss_msg = (
                                    "⚠️ <b>STOP LOSS ALCANÇADO!</b>\n"
                                    "━━━━━━━━━━━━━━━━━━\n"
                                    f"❌ <b>Limite de Perda:</b> {self.loss_count} Losses!\n"
                                    "🏁 <b>Estado:</b> Bot Finalizado (Proteção Ativa)\n"
                                    f"📈 <b>Assertividade Final:</b> {rate:.1f}%\n"
                                    "━━━━━━━━━━━━━━━━━━\n"
                                    "<i>Sessão finalizada. Controle de risco acionado!</i>"
                                )
                                telegram_sender.send_telegram_msg(self.config, stop_loss_msg, self.log)
                                time.sleep(2)  # aguarda envio do Telegram antes de parar
                                self.stop_bot("loss")
                                break
                    else:
                        if loss_conf < (sens - 0.05):
                            self.loss_detected_state = False
            except Exception:
                pass
            
            time.sleep(0.5)

    def _on_api_connection_change(self, connected):
        self.api_connected = connected
        if not connected:
            self.api_authorized = False
            self.log("API Desconectada.")
        else:
            self.log("API Conectada.")

    def _on_api_tick(self, price, is_crash):
        self.api_authorized = True
        self.last_api_tick_time = time.time()
        
        mode = self.config.get("mode", "fixed")
        if mode == "adaptive" and self.running:
            if is_crash:
                if not self.adaptive_crashed:
                    self.adaptive_sequence.append("V")
                    self.adaptive_crashed = True
                    self.adaptive_consec_red_crashes += 1
                    self.adaptive_consec_green_ticks = 0
                    self.adaptive_event_count_since_relearn += 1
                    self.log(f"API Adaptativo: Evento 'V' registrado (Crash via API). Histórico: {len(self.adaptive_sequence)}")
                    self._trigger_relearn_if_needed()
            else:
                if self.adaptive_crashed:
                    self.adaptive_crashed = False
                    self.adaptive_ready_to_click = True
                    self.adaptive_consec_green_ticks = 0
                    
                self.adaptive_sequence.append("G")
                self.adaptive_consec_green_ticks += 1
                self.adaptive_consec_red_crashes = 0
                self.adaptive_event_count_since_relearn += 1
                self.log(f"API Adaptativo: Evento 'G' registrado (Tick via API). Histórico: {len(self.adaptive_sequence)}")
                self._trigger_relearn_if_needed()
                
        elif mode == "ai" and self.running:
            # _process_ai_tick já contém toda a lógica de processamento e decisão de entrada
            self._process_ai_tick(price, is_crash)

    def _on_api_contract_update(self, poc):
        status = poc.get("status")
        is_sold = poc.get("is_sold", 0)
        profit = float(poc.get("profit", 0.0))
        contract_id = poc.get("contract_id")
        
        if self.config.get("mode") == "ai" and status == "open" and is_sold == 0:
            take_profit_target = self.config.get("ai_contract_take_profit", 5.0)
            if profit >= take_profit_target:
                if self.ai_selling_contract_id != contract_id:
                    self.ai_selling_contract_id = contract_id
                    self.log(f"🎯 [Modo IA] Take Profit atingido no contrato: ${profit:.2f} >= ${take_profit_target:.2f}. Solicitando venda antecipada...")
                    if self.api_client:
                        self.api_client.sell_contract(contract_id)

    def _on_api_contract_status(self, status, profit):
        if not self.config.get("deriv_use_api_trading", False):
            return

        # Libera flag de contrato ativo (Modo IA)
        self.ai_active_contract = False
        self.ai_selling_contract_id = None

        self.log(f"[API] Resultado do Contrato: {status.upper()} (Lucro/Prejuízo: ${profit:.2f})")

        now = time.time()
        total_conclusion = self.win_count + self.loss_count + 1
        rate = (self.win_count / total_conclusion * 100) if total_conclusion > 0 else 0.0

        if status == "won":
            self.win_count += 1
            self.martingale_level = 0
            self.on_win_cb(self.win_count)
            self.adaptive_loss_count_since_relearn = 0
            self.current_profit += profit
            if self.on_finance_cb:
                self.on_finance_cb(self.current_profit, self.click_count)

            self.log(f"VITÓRIA via API! Lucro: ${profit:.2f} | Saldo: ${self.current_profit:.2f}")
            self.play_sound("win")
            self.save_result_to_history("WIN")
            self.recent_ops.append(("WIN", profit, datetime.datetime.now().strftime("%H:%M:%S")))
            self.recent_ops = self.recent_ops[-10:]
            
            win_msg = (
                f"🟢 <b>VITÓRIA via API DETECTADA!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"💵 <b>Retorno:</b> ${profit:.2f}\n"
                f"💰 <b>Saldo Atual:</b> ${self.current_profit:.2f}\n"
                "📊 <b>Placar Geral:</b>\n"
                f"├─ Wins: {self.win_count}\n"
                f"└─ Losses: {self.loss_count}\n"
                f"📈 <b>Assertividade:</b> {rate:.1f}%\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            telegram_sender.send_telegram_msg(self.config, win_msg, self.log)
            
            # Limite Meta de Lucro
            finance_mode = self.config.get("finance_mode", "target")
            if finance_mode == "target":
                target = self.config.get("target_profit", 10.00)
                if self.current_profit >= target:
                    self.log(f"Meta de Lucro Atingida (${self.current_profit:.2f} >= ${target:.2f})! Parando bot...")
                    self.on_stop_limit_cb("profit_win", self.current_profit)
                    
                    stop_target_msg = (
                        "💰 <b>META DE LUCRO ALCANÇADA!</b>\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Wins:</b> {self.win_count} | <b>Losses:</b> {self.loss_count}\n"
                        f"💰 <b>Saldo Final:</b> ${self.current_profit:.2f}\n"
                        "━━━━━━━━━━━━━━━━━━"
                    )
                    telegram_sender.send_telegram_msg(self.config, stop_target_msg, self.log)
                    time.sleep(2)
                    self.stop_bot("profit_win")
                    return
                    
            if self.config.get("enable_stop_win", False) and self.win_count >= self.config.get("stop_win", 5):
                self.log(f"Limite Stop Win atingido ({self.win_count} Wins)! Parando bot...")
                self.on_stop_limit_cb("win", self.win_count)
                
                stop_win_msg = (
                    "💰 <b>STOP WIN ALCANÇADO!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"✅ <b>Meta Batida:</b> {self.win_count} Wins!\n"
                    "🏁 <b>Estado:</b> Bot Finalizado (Meta Concluída)\n"
                    f"📈 <b>Assertividade Final:</b> {rate:.1f}%\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "<i>Sessão finalizada com sucesso. Lucro garantido!</i>"
                )
                telegram_sender.send_telegram_msg(self.config, stop_win_msg, self.log)
                time.sleep(2)
                self.stop_bot("win")
                return

        elif status == "lost":
            self.loss_count += 1
            if not hasattr(self, "martingale_level"):
                self.martingale_level = 0
            self.martingale_level += 1
            self.on_loss_cb(self.loss_count)
            
            # Treina imediatamente pós-loss no modo IA
            if self.config.get("mode") == "ai":
                self.force_ai_loss_learning()
            self.current_profit += profit # profit é negativo
            if self.on_finance_cb:
                self.on_finance_cb(self.current_profit, self.click_count)
                
            self.log(f"DERROTA via API! Perda: ${profit:.2f} | Saldo: ${self.current_profit:.2f}")
            self.play_sound("loss")
            self.save_result_to_history("LOSS")
            self.recent_ops.append(("LOSS", profit, datetime.datetime.now().strftime("%H:%M:%S")))
            self.recent_ops = self.recent_ops[-10:]
            
            loss_msg = (
                f"🔴 <b>DERROTA via API DETECTADA!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"💵 <b>Retorno:</b> ${profit:.2f}\n"
                f"💰 <b>Saldo Atual:</b> ${self.current_profit:.2f}\n"
                "📊 <b>Placar Geral:</b>\n"
                f"├─ Wins: {self.win_count}\n"
                f"└─ Losses: {self.loss_count}\n"
                f"📈 <b>Assertividade:</b> {rate:.1f}%\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            telegram_sender.send_telegram_msg(self.config, loss_msg, self.log)
            
            # Reaprende se necessário no modo adaptativo
            self.adaptive_loss_count_since_relearn += 1
            if self.config.get("mode") == "adaptive":
                relearn_losses = self.config.get("adaptive_relearn_losses", 3)
                if self.adaptive_loss_count_since_relearn >= relearn_losses:
                    self.log(f"Gatilho de reaprendizado: {relearn_losses} losses consecutivas atingidas.")
                    self.relearn_strategy()
                    
            if self.config.get("enable_stop_loss", False) and self.loss_count >= self.config.get("stop_loss", 3):
                self.log(f"Limite Stop Loss atingido ({self.loss_count} Losses)! Parando bot...")
                self.on_stop_limit_cb("loss", self.loss_count)
                
                stop_loss_msg = (
                    "⚠️ <b>STOP LOSS ALCANÇADO!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"❌ <b>Limite de Perda:</b> {self.loss_count} Losses!\n"
                    "🏁 <b>Estado:</b> Bot Finalizado (Proteção Ativa)\n"
                    f"📈 <b>Assertividade Final:</b> {rate:.1f}%\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "<i>Sessão finalizada. Controle de risco acionado!</i>"
                )
                telegram_sender.send_telegram_msg(self.config, stop_loss_msg, self.log)
                time.sleep(2)
                self.stop_bot("loss")
                return

    def _on_api_history(self, prices):
        if not prices:
            return
            
        if getattr(self, "is_scanning", False):
            self.scan_history_prices = prices
            return
            
        # Pré-alimentação e treinamento da IA com histórico real
        if self.config.get("mode") == "ai":
            self.log(f"Processando {len(prices)} ticks históricos da API para pré-alimentar e treinar a IA...")
            barrier = float(self.api_client.barrier_distance) if (self.api_client and self.api_client.barrier_distance is not None) else 0.0001
            
            # Limpa buffers da IA para evitar lixo residual
            self.ai_tick_prices = []
            self.ai_observations = []
            self.ai_current_tick_index = 0
            self.ai_last_crash_index = 0
            
            last_price = prices[0]
            for p in prices:
                is_crash = False
                if last_price is not None and barrier > 0:
                    if abs(p - last_price) >= barrier:
                        is_crash = True
                
                self._process_ai_tick(p, is_crash)
                last_price = p
                
            self.log(f"IA pré-alimentada com sucesso. Amostras na memória: {len(self.ai_replay.memory)}")
            return
            
        if self.api_client.barrier_distance is None:
            return
            
        self.log(f"Processando {len(prices)} ticks históricos da API...")
        barrier = float(self.api_client.barrier_distance)
        
        seq = []
        last_price = prices[0]
        for p in prices[1:]:
            diff = abs(p - last_price)
            if diff >= barrier:
                seq.append("V")
            else:
                seq.append("G")
            last_price = p
            
        self.adaptive_sequence = seq
        self.adaptive_event_count_since_relearn = len(seq)
        self.log(f"Sequência adaptativa inicializada via histórico API com {len(seq)} eventos.")
        
        self.adaptive_phase = "operation"
        self.relearn_strategy()

    def force_ai_loss_learning(self):
        contract_mode = self.config.get("deriv_contract_mode", "accumulator")
        self.log(f"🧠 [IA] Loss detectado no modo {contract_mode.upper()}! Iniciando treinamento de adaptação rápida pós-loss...")
        
        # Define status de aprendizado temporário para o overlay
        self.ai_reasoning_status = "Adaptando Pós-Loss 🔧"
        self.ai_reasoning_explanation = "A IA está executando 20 ciclos extras de aprendizado para ajustar os pesos da rede neural após o Loss."
        
        # Incrementa o contador de iterações de treino
        if not hasattr(self, "ai_training_iterations"):
            self.ai_training_iterations = 0
            
        if contract_mode in ["rise_fall", "accumulator"]:
            if len(self.ai_replay.memory) >= 32:
                # 20 ciclos extras de treinamento para adaptação rápida
                for _ in range(20):
                    X_batch, y_batch = self.ai_replay.sample_batch(32)
                    loss_val = self.ai.train_on_batch(X_batch, y_batch)
                    self.ai_training_iterations += 1
                self.ai_loss = loss_val
                self.ai_accuracy = self.ai_replay.get_accuracy(self.ai)
                self.ai.save_weights(filepath=f"capturas/ai_weights_{contract_mode}.json")
                self.log(f"🧠 [IA] Adaptação rápida concluída. Novo Loss: {self.ai_loss:.4f} | Acurácia: {self.ai_accuracy:.1f}%")
        else: # matches, differs
            if len(self.ai_digit_replay.memory) >= 32:
                # 20 ciclos extras de treinamento para adaptação rápida
                for _ in range(20):
                    X_digit_batch, y_digit_batch = self.ai_digit_replay.sample_batch(32)
                    digit_loss = self.digit_ai.train_on_batch(np.array(X_digit_batch, dtype=np.float32), np.array(y_digit_batch, dtype=np.int64))
                    self.ai_training_iterations += 1
                self.ai_loss = digit_loss
                self.ai_accuracy = self.ai_digit_replay.get_accuracy(self.digit_ai)
                self.digit_ai.save_weights()
                self.log(f"🧠 [IA] Adaptação rápida de dígitos concluída. Novo Loss: {self.ai_loss:.4f} | Acurácia: {self.ai_accuracy:.1f}%")

    def _scan_best_asset_and_timeframe(self):
        """
        Pesquisa todos os ativos candidatos e timeframes,
        identificando o melhor par para operar de acordo com o modo de contrato ativo.
        """
        if not self.api_client or not self.api_client.connected:
            self.log("⚠️ [Pesquisa] API desconectada. Pulando pesquisa automática de mercado.")
            return

        self.log("🔍 [Pesquisa] Iniciando escaneamento automático de ativos e timeframes...")
        self.ai_reasoning_status = "Pesquisando Ativos 🔍"
        self.ai_reasoning_explanation = "Solicitando histórico de preços dos principais ativos para avaliar tendências e volatilidade..."

        candidate_symbols = ["R_10", "R_25", "R_50", "R_75", "R_100", "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"]
        contract_mode = self.config.get("deriv_contract_mode", "accumulator")

        best_score = -1.0
        best_symbol = self.config.get("deriv_symbol", "R_100")
        best_val = self.config.get("deriv_rf_duration_value", 5)
        best_unit = self.config.get("deriv_rf_duration_unit", "t")

        # Temporariamente redireciona o callback de histórico
        old_cb = self.api_client.on_history_cb
        self.is_scanning = True
        self.scan_history_prices = None

        # Auxiliar para calcular Kaufmann Efficiency Ratio
        def calculate_er(prices, K):
            if len(prices) < K + 5:
                return 0.0
            ers = []
            for offset in [0, max(5, K // 2), K]:
                end_idx = len(prices) - 1 - offset
                start_idx = end_idx - K
                if start_idx < 0:
                    continue
                price_start = prices[start_idx]
                price_end = prices[end_idx]
                net_change = abs(price_end - price_start)
                total_change = sum(abs(prices[i] - prices[i-1]) for i in range(start_idx + 1, end_idx + 1))
                if total_change > 1e-9:
                    ers.append(net_change / total_change)
            return sum(ers) / len(ers) if ers else 0.0

        for symbol in candidate_symbols:
            if not self.running:
                break
            
            self.log(f"🔍 [Pesquisa] Solicitando ticks de {symbol}...")
            self.ai_reasoning_status = f"Analisando {symbol} 📊"
            self.ai_reasoning_explanation = f"Avaliando a qualidade de sinal de {symbol} no modo {contract_mode.upper()}..."
            
            self.scan_history_prices = None
            self.api_client.request_ticks_history(300, symbol=symbol)
            
            # Espera até 3 segundos pela resposta da API
            waited = 0.0
            while self.scan_history_prices is None and waited < 3.0 and self.running:
                time.sleep(0.1)
                waited += 0.1
                
            if not self.running:
                break
                
            if self.scan_history_prices is None:
                self.log(f"⚠️ [Pesquisa] Sem resposta de histórico para {symbol}. Pulando...")
                continue
                
            prices = self.scan_history_prices
            self.log(f"📊 [Pesquisa] Recebidos {len(prices)} ticks para {symbol}. Calculando métricas...")

            if contract_mode == "rise_fall":
                # Timeframes candidatos: 5 Ticks, 10 Ticks, 1m (30 Ticks), 5m (150 Ticks)
                timeframes = [
                    {"val": 5, "unit": "t", "K": 5, "label": "5 Ticks"},
                    {"val": 10, "unit": "t", "K": 10, "label": "10 Ticks"},
                    {"val": 1, "unit": "m", "K": 30, "label": "1 Minuto"},
                    {"val": 5, "unit": "m", "K": 150, "label": "5 Minutos"}
                ]
                for tf in timeframes:
                    score = calculate_er(prices, tf["K"])
                    self.log(f"   > Timeframe {tf['label']}: Score de Tendência (ER) = {score:.4f}")
                    if score > best_score:
                        best_score = score
                        best_symbol = symbol
                        best_val = tf["val"]
                        best_unit = tf["unit"]
                        
            elif contract_mode in ["matches", "differs"]:
                # Mede viés/concentração de dígitos nos últimos 150 ticks
                if len(prices) >= 150:
                    last_prices = prices[-150:]
                    digits = []
                    for p in last_prices:
                        p_str = f"{p:.5f}" # garante precisão decimal
                        if "." in p_str:
                            digits.append(int(p_str.split(".")[-1][-1]))
                        else:
                            digits.append(int(p_str[-1]))
                    
                    # Desvio padrão das frequências de dígitos de 0 a 9 (uniforme seria 10% cada)
                    counts = [digits.count(d) for d in range(10)]
                    freqs = [c / len(digits) for c in counts]
                    score = float(np.std(freqs))
                    self.log(f"   > Score de Viés de Dígito (Std Dev) = {score:.4f}")
                    if score > best_score:
                        best_score = score
                        best_symbol = symbol
                        best_val = 5  # padrão 5 ticks para dígitos
                        best_unit = "t"
                else:
                    self.log("   > Histórico de ticks insuficiente para análise de dígitos.")

            else: # accumulator
                # Mede a estabilidade (inverso da volatilidade) para sequências maiores
                if len(prices) >= 100:
                    diffs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
                    volatility = sum(diffs) / len(diffs)
                    avg_price = sum(prices) / len(prices)
                    vol_ratio = volatility / (avg_price * 0.0001 + 1e-9)
                    
                    score = 1.0 / (vol_ratio + 1e-6)
                    self.log(f"   > Score de Estabilidade = {score:.4f}")
                    if score > best_score:
                        best_score = score
                        best_symbol = symbol
                        best_val = 5
                        best_unit = "t"
            
            time.sleep(0.1)

        # Restaura o callback
        self.api_client.on_history_cb = old_cb
        self.is_scanning = False

        if best_score > -1.0:
            self.log(f"🎯 [Pesquisa] VENCEDOR: {best_symbol} | Timeframe: {best_val}{best_unit} | Score: {best_score:.4f}")
            
            # Atualiza configurações na memória
            self.config["deriv_symbol"] = best_symbol
            self.config["deriv_rf_duration_value"] = best_val
            self.config["deriv_rf_duration_unit"] = best_unit
            
            # Atualiza o ativo na API
            self.api_client.change_symbol(best_symbol)
            
            # Envia notificação no Telegram
            timeframe_label = f"{best_val} Ticks" if best_unit == "t" else (f"{best_val} Segundos" if best_unit == "s" else f"{best_val} Minutos")
            telegram_msg = (
                "🎯 <b>Pesquisa de Mercado Concluída!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Modo:</b> {contract_mode.upper()}\n"
                f"🟢 <b>Melhor Ativo:</b> {best_symbol}\n"
                f"⏱️ <b>Timeframe:</b> {timeframe_label}\n"
                f"📈 <b>Score de Qualidade:</b> {best_score:.4f}\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>Configuração aplicada automaticamente ao robô!</i>"
            )
            telegram_sender.send_telegram_msg(self.config, telegram_msg, self.log)
        else:
            self.log("⚠️ [Pesquisa] Não foi possível encontrar um vencedor claro. Mantendo configurações originais.")
