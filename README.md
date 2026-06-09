# DerivClickerBot - Bot de Automação para Deriv (Modo Acumulador)

Este é um bot profissional de automação de cliques por reconhecimento de imagem projetado para a plataforma Deriv, focado especificamente na estratégia de **Acumulador** (Accumulator).

## 🎯 Objetivo e Estratégia
* **Meta Principal**: Acumular **$30 dólares** de banca com meta diária de **$1 dólar** utilizando o multiplicador **5x** (1.05x).
* O bot foi desenhado para agilizar as entradas e minimizar o tempo de exposição, realizando operações rápidas e controladas para garantir a meta de consistência estipulada pelo usuário.

---

## 🛠️ Recursos do Bot

### 1. Modos de Operação Dinâmicos
* **Número Vermelho (Recomendado)**: Monitora constantemente a tela do navegador. Quando o número correspondente (`number.png`) é localizado e entra no estado **vermelho**, o bot efetua a entrada (clique) no botão da corretora de forma ultra-rápida. Ele desarma e aguarda o número voltar a cor normal antes de rearmar.
* **Intervalo Fixo**: Realiza cliques automáticos em intervalos definidos (ex: a cada 5 segundos).
* **Intervalo Aleatório**: Adiciona um fator humano variando o tempo entre cliques mínimos e máximos (ex: entre 2s e 10s).
* **Sequência de Cliques**: Executa sequências de cliques em blocos com tempos de descanso programáveis.

### 2. Interface Moderna e Organizada (Accordion UI)
A interface foi projetada utilizando a biblioteca **CustomTkinter** com a paleta visual *Deep Void*. As seções de controle são organizadas em painéis sanfonados (recolhíveis):
* **Configurações do Modo**: Escolha e parametrização do modo ativo.
* **Agendamento de Início**: Permite programar a data (DD/MM/AAAA) e hora (HH:MM) para o bot começar a executar as operações automaticamente.
* **Ajustes & Limites do Bot**: Ajuste fino da sensibilidade do template matching do OpenCV, limites de Stop Win/Loss por quantidade de mensagens/alertas, e chaves gerais de áudio/screenshots.
* **Configurações do Telegram**: Integração nativa para receber notificações e logs direto no seu celular. Contém busca dinâmica de Chat ID e botão de envio de teste.
* **Logs em Tempo Real**: Console integrado com histórico detalhado e salvamento opcional de arquivo log local.

---

## 🚀 Como Iniciar

### Executável Autônomo
Para rodar diretamente no Windows sem instalar o Python, utilize o executável gerado:
1. Abra o arquivo **`DerivClickerBot.exe`**.
2. Certifique-se de que a pasta `capturas/` está no mesmo diretório que o executável, contendo as imagens necessárias (`botao.png`, `win.png`, `loss.png`, `number.png`).
3. Configure os limites e inicie as operações.

### Executando via Código Fonte

1. **Instale as Dependências**:
   ```bash
   pip install customtkinter opencv-python numpy pyautogui keyboard darkdetect requests pillow
   ```
2. **Configure suas Credenciais**:
   Copie o arquivo `config.json.template` para `config.json` e insira suas configurações padrão caso queira persistir dados entre sessões.
3. **Execute o Script Principal**:
   ```bash
   python main.py
   ```

---

## 📂 Estrutura do Projeto

* `main.py`: Ponto de entrada do aplicativo.
* `app_gui.py`: Design e gerenciamento da interface do usuário (CustomTkinter).
* `bot_worker.py`: Lógica de segundo plano de escaneamento de tela, template matching OpenCV e controle de cliques.
* `config_manager.py`: Carregamento e salvamento dinâmico de configurações do arquivo `config.json`.
* `telegram_sender.py`: Lógica de comunicação com a API do Telegram.
* `capturas/`: Diretório que armazena os assets visuais padrão para reconhecimento de imagem na Deriv.
