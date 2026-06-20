![Logo do Projeto](capturas/logo.png)

# DerivClickerBot - Bot de Automação para Deriv (Modo Acumulador)

O **DerivClickerBot** é uma plataforma profissional de automação e trading inteligente projetada para a corretora Deriv, focada especificamente nas modalidades **Accumulator** (Acumulador), **Matches/Differs** (Dígitos) e **Rise/Fall** (Alta/Baixa). O sistema combina controle visual via processamento de imagem (OpenCV), integração nativa e assíncrona via API WebSocket da Deriv, modos adaptativos baseados em IA estatística e redes neurais profundas, além de suporte multiplataforma.

---

## 🎯 Objetivo e Estratégia
* **Meta Principal**: Acumular banca utilizando estratégias matemáticas de probabilidade, inteligência adaptativa e redes neurais preditivas.
* O bot minimiza o tempo de exposição e a latência de execução das operações, oferecendo tanto operações via simulação de cliques (OCR clássico) quanto operações digitais diretas (via API) de alta velocidade.

---

## 🛠️ Recursos e Funcionalidades

### 1. Modos de Operação Dinâmicos
* **🧠 Modo Inteligente (Adaptive Mode)**:
  * **Fase 1 — Coleta de Dados**: O bot entra em uma fase de observação (configurável em minutos) lendo a sequência de ticks e registrando quebras (crashes vermelhos) e ticks verdes. *Quando a API está conectada, o bot busca instantaneamente os últimos 1000 ticks históricos para pular o tempo de espera.*
  * **Fase 2 — Análise Estatística**: O motor de IA calcula a frequência de repetições e o tamanho médio das sequências para criar regras de entrada customizadas em tempo real.
  * **Re-aprendizado Dinâmico**: A IA reconstrói e otimiza a estratégia automaticamente a cada intervalo de tempo ou a cada $X$ eventos coletados.
* **🤖 Modo Inteligência Artificial (Rede Neural Preditiva)**:
  * **Motor Neural**: Rede neural multicamadas (MLP) com suporte automático a **PyTorch** (com aceleração por GPU se disponível) ou fallback para **NumPy**.
  * **Classificação de Dígitos (Matches/Differs)**: Previsão da probabilidade de ocorrência de cada dígito (0-9) no próximo tick utilizando um buffer de Experience Replay independente.
  * **Rise/Fall Inteligente**: Decisão baseada na direção e confiança calculadas pela IA sobre a variação dos preços recentes.
  * **Treinamento Rápido Pós-Loss**: Ao detectar uma derrota (via API ou OCR), a IA realiza **20 ciclos imediatos de treinamento intensivo** focando no contexto mais recente para evitar a repetição de erros.
* **Número Vermelho (OCR clássico)**: Monitora constantemente a tela. Quando o contador de ticks entra no estado **vermelho**, o bot efetua a entrada de forma ultra-rápida.
* **Intervalo Fixo/Aleatório**: Realiza cliques em intervalos definidos ou variando o tempo simulando comportamento humano.

### 2. Recursos Avançados de Gestão de Risco (Rise/Fall)
* **🛑 Filtro de Tendência SMA (Trend Veto)**: Bloqueia automaticamente operações sugeridas pela IA que sejam contra a tendência macro do mercado, comparando a Média Móvel Rápida (**SMA 10**) com a Média Lenta (**SMA 30**), a menos que a confiança da IA seja ultra-forte (+15% do limiar).
* **⚡ Expiração Adaptativa por Volatilidade**: Calcula o desvio médio dos últimos 20 ticks e ajusta dinamicamente a expiração dos contratos de Rise/Fall (de 3 a 8 ticks) para momentum ótimo.
* **🛑 Martingale Inteligente**: Aumenta o rigor da IA em ciclos de recuperação, exigindo pelo menos **70% de confiança** (ou +10% do limite regular) para realizar entradas de Martingale, protegendo a banca.

### 3. Modos de Execução
Ao iniciar, o bot oferece três alternativas de execução:
* **🌐 NAVEGADOR**: Abre um navegador integrado e embutido (PyWebView) para navegação direta na Deriv.
* **🤖 CLICKERBOT**: Executa cliques físicos diretamente sobre a tela/navegador externo do usuário.
* **🥷 MODO STEALTH (Segundo Plano)**: 
  * Executa em background total sem simular cliques de mouse ou abrir navegadores.
  * Realiza compras e recebe o resultado de contratos (Win/Loss) de forma 100% digital usando a API WebSocket.
  * **Libera o PC do usuário**, permitindo trabalhar, navegar ou jogar normalmente enquanto o robô opera em segundo plano.

### 4. Integração com a API da Deriv (WebSocket)
* **Conexão Direta**: Conectado à rede WebSocket oficial da Deriv para recepção de ticks em milissegundos.
* **Testador de Conexão**: Interface para validar tokens de acesso com feedback visual imediato e exibição de saldo de conta em tempo real.
* **Operação Instantânea**: Envio de ordens assíncronas e telemetria de contratos via eventos para capturar retornos reais e placares de asserts.

### 5. Interface CustomTkinter "Deep Void"
Interface moderna, fluida e com visual escuro neon de alto contraste:
* **Design Responsivo**: Painéis sanfonados colapsáveis (Accordion) para manter a tela limpa.
* **Overlay Flutuante Inteligente**: Mini-painel flutuante sem bordas que exibe status, saldo, assertividade, progresso da IA, gráfico de ticks, nível de inteligência/QI da IA, e o feed das últimas operações com sincronização direta livre de inconsistências visuais. Mantém a posição exata na tela ao ser redimensionado.
* **Controle pelo Telegram**: Envio de mensagens de Win, Loss, atingimento de metas e relatórios estatísticos periódicos com suporte a comandos remotos (como `/status`).

---

## 🍏 Suporte Multiplataforma (Windows e macOS)

O código-fonte do projeto foi adaptado para ser totalmente cross-platform:
* **Windows**: Suporte completo com hooks de atalhos globais de teclado (tecla F8 para parada de emergência) e alertas de som clássicos.
* **macOS**: Tratamento de exceções e fallbacks para remover dependências exclusivas do Windows (como `winsound` e bibliotecas `ctypes` do `user32.dll`).

Para facilitar a distribuição, o projeto conta com pastas preparadas de distribuição independente:
* **[`Windows_Release/`](file:///c:/Users/deymon/Documents/t/Windows_Release/)**: Contém o executável autônomo `DerivClickerBot.exe` consolidado junto às pastas de suporte `capturas/` e `songs/`.
* **[`macOS_Release/`](file:///c:/Users/deymon/Documents/t/macOS_Release/)**: Contém o código limpo, manual de instruções para liberação de permissões do Mac (Acessibilidade e Gravação de Tela) e o script de compilação automática em um clique `build_mac.sh`.

---

## 🚀 Como Executar (Código Fonte)

1. **Instale as Dependências**:
   ```bash
   pip install customtkinter opencv-python-headless numpy pyautogui pygame websocket-client requests pillow torch torchvision
   ```
2. **Configure suas Credenciais**:
   Copie o arquivo `config.json.template` para `config.json` e insira suas credenciais iniciais.
3. **Execute o Script Principal**:
   ```bash
   python main.py
   ```

---

## 📂 Estrutura do Projeto

* `main.py`: Ponto de entrada do aplicativo.
* `app_gui.py`: Gerenciador da interface do usuário (CustomTkinter) e validações.
* `bot_worker.py`: Lógica do bot, gerenciador de loops de execução (OCR e API) e gerador de IA estatística.
* `deriv_api_client.py`: Cliente de rede WebSocket para interação direta com os servidores da Deriv.
* `floating_overlay.py`: Janela flutuante minimalista de monitoramento.
* `global_hotkey.py`: Ouvinte de tecla de emergência (F8) multiplataforma.
* `telegram_sender.py`: Módulo de disparos e relatórios via API do Telegram.
* `capturas/`: Diretório de templates de imagem para busca do OpenCV.
* `songs/`: Arquivos sonoros de áudio do sistema.
