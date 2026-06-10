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

# Evita travar o mouse caso ocorra algum loop infinito (arraste para o canto superior esquerdo para abortar)
pyautogui.FAILSAFE = True

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
        
        # Cria as pastas de historico se nao existirem
        os.makedirs("capturas/historico", exist_ok=True)
        self.history_file = "wins_history.csv"
        
        self.sounds = {}
        self._load_custom_sounds()
        
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
            app_id = self.config.get("deriv_app_id", "1098")
            
            from deriv_api_client import DerivApiClient
            self.api_client = DerivApiClient(
                token=token,
                app_id=app_id,
                symbol=symbol,
                growth_rate=growth_rate
            )
            self.api_client.on_tick_cb = self._on_api_tick
            self.api_client.on_contract_status_cb = self._on_api_contract_status
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

    def _attempt_click(self):
        # --- EXECUÇÃO VIA API DA DERIV ---
        use_api_trading = self.config.get("deriv_use_api_trading", False)
        
        if use_api_trading and self.api_client and self.api_client.connected and self.api_client.authorized:
            stake = self.config.get("win_value", 1.50)
            self.log(f"[API] Enviando ordem de compra via API (Stake: ${stake:.2f})")
            success = self.api_client.buy_accumulator(stake)
            if success:
                self.click_count += 1
                self.on_click_cb(self.click_count)
                if self.on_finance_cb:
                    self.on_finance_cb(self.current_profit, self.click_count)
                self.play_sound("click")
                
                # --- CICLOS DE ENTRADAS ---
                if self.config.get("cycle_enabled", False):
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
            if self.config.get("cycle_enabled", False):
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
                        self.last_win_time = now
                        self.win_detected_state = True
                        
                        self.on_win_cb(self.win_count)
                        self.adaptive_loss_count_since_relearn = 0
                        
                        # Atualiza Saldo Financeiro ($1.00 se for win2, senao win_value)
                        win_val = 1.00 if is_win2 else self.config.get("win_value", 1.50)
                        self.current_profit += win_val
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
                        self.last_loss_time = now
                        self.loss_detected_state = True
                        
                        self.on_loss_cb(self.loss_count)
                        
                        self.adaptive_loss_count_since_relearn += 1
                        if self.config.get("mode") == "adaptive":
                            relearn_losses = self.config.get("adaptive_relearn_losses", 3)
                            if self.adaptive_loss_count_since_relearn >= relearn_losses:
                                self.log(f"Gatilho de reaprendizado: {relearn_losses} losses consecutivas atingidas.")
                                self.relearn_strategy()
                        
                        # Atualiza Saldo Financeiro
                        self.current_profit -= self.config.get("loss_value", 30.00)
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
        
        if self.config.get("mode", "fixed") == "adaptive" and self.running:
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

    def _on_api_contract_status(self, status, profit):
        if not self.config.get("deriv_use_api_trading", False):
            return
            
        self.log(f"[API] Resultado do Contrato: {status.upper()} (Lucro/Prejuízo: ${profit:.2f})")
        
        now = time.time()
        total_conclusion = self.win_count + self.loss_count + 1
        rate = (self.win_count / total_conclusion * 100) if total_conclusion > 0 else 0.0
        
        if status == "won":
            self.win_count += 1
            self.on_win_cb(self.win_count)
            self.adaptive_loss_count_since_relearn = 0
            self.current_profit += profit
            if self.on_finance_cb:
                self.on_finance_cb(self.current_profit, self.click_count)
            
            self.log(f"VITÓRIA via API! Lucro: ${profit:.2f} | Saldo: ${self.current_profit:.2f}")
            self.play_sound("win")
            self.save_result_to_history("WIN")
            
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
            self.on_loss_cb(self.loss_count)
            self.current_profit += profit # profit é negativo
            if self.on_finance_cb:
                self.on_finance_cb(self.current_profit, self.click_count)
                
            self.log(f"DERROTA via API! Perda: ${profit:.2f} | Saldo: ${self.current_profit:.2f}")
            self.play_sound("loss")
            self.save_result_to_history("LOSS")
            
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
        if not prices or self.api_client.barrier_distance is None:
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
