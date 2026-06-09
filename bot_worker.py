import os
import time
import random
import threading
import datetime
import csv
import winsound
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
        
        self.win_detected_state = False
        self.last_win_time = 0
        
        self.loss_detected_state = False
        self.last_loss_time = 0
        
        # Cria as pastas de historico se nao existirem
        os.makedirs("capturas/historico", exist_ok=True)
        self.history_file = "wins_history.csv"
        
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
                if sound_type == "click":
                    winsound.Beep(1000, 150)
                elif sound_type == "win":
                    winsound.Beep(1800, 200)
                    winsound.Beep(2200, 300)
                elif sound_type == "loss":
                    winsound.Beep(800, 250)
                    winsound.Beep(500, 350)
                elif sound_type == "stop":
                    winsound.Beep(600, 250)
                elif sound_type == "start":
                    winsound.Beep(1200, 150)
                    winsound.Beep(1500, 150)
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

    def stop_bot(self):
        if self.running:
            self.running = False
            self.play_sound("stop")
            self.log("Bot parado.")
            self.on_status_cb(False)

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
        except Exception as e:
            self.log(f"Erro de execucao do bot: {e}")
            self.stop_bot()

    def _run_fixed_mode(self):
        fixed_interval = self.config.get("fixed_interval", 5.0)
        self.log(f"Modo Intervalo Fixo ativo: clique a cada {fixed_interval}s.")
        
        while self.running:
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

    def _attempt_click(self):
        image_path = self.config.get("image_button_path", "capturas/botao.png")
        sens = self.config.get("sensitivity", 0.8)
        
        pos, conf = self.find_image(image_path, sens)
        if pos:
            x, y = pos
            # Retorna mouse a posicao original
            orig_x, orig_y = pyautogui.position()
            
            # Executa clique
            pyautogui.click(x, y)
            pyautogui.moveTo(orig_x, orig_y)
            
            self.click_count += 1
            self.on_click_cb(self.click_count)
            if self.on_finance_cb:
                self.on_finance_cb(self.current_profit, self.click_count)
                
            self.log(f"Botao encontrado (Confianca: {conf:.2f}), clicado em ({x}, {y}).")
            self.play_sound("click")
            
            # Limite Modo Livre (Entradas)
            finance_mode = self.config.get("finance_mode", "target")
            if finance_mode == "free":
                limit_entries = self.config.get("free_entries", 10)
                if self.click_count >= limit_entries:
                    self.log(f"Limite de Entradas atingido ({self.click_count}/{limit_entries} em Modo Livre)! Parando bot...")
                    self.on_stop_limit_cb("entries", self.click_count)
                    
                    # Notificacao Telegram Limite de Entradas
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
                    self.stop_bot()
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
        win_image_path = self.config.get("image_win_path", "capturas/win.png")
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
                if win_pos:
                    if not self.win_detected_state and (now - self.last_win_time > 3.0):
                        self.win_count += 1
                        self.last_win_time = now
                        self.win_detected_state = True
                        
                        self.on_win_cb(self.win_count)
                        
                        # Atualiza Saldo Financeiro
                        self.current_profit += self.config.get("win_value", 1.50)
                        if self.on_finance_cb:
                            self.on_finance_cb(self.current_profit, self.click_count)
                        
                        self.log(f"WIN detectado! (Confianca: {win_conf:.2f}) - Wins Totais: {self.win_count} | Saldo: ${self.current_profit:.2f}")
                        self.play_sound("win")
                        self.save_result_to_history("WIN")
                        self.take_screenshot_from_frame(screenshot, "win")
                        
                        # Notificacao Telegram Win
                        total_conclusion = self.win_count + self.loss_count
                        rate = (self.win_count / total_conclusion * 100) if total_conclusion > 0 else 0.0
                        win_msg = (
                            "🟢 <b>WIN DETECTADO!</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "🏆 <b>Resultado:</b> VITÓRIA!\n"
                            f"🔥 <b>Confiança:</b> {win_conf:.2f}\n"
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
                                self.stop_bot()
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
                            self.stop_bot()
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
                            self.stop_bot()
                            break
                else:
                    if loss_conf < (sens - 0.05):
                        self.loss_detected_state = False
            except Exception:
                pass
            
            time.sleep(0.5)
