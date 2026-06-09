import os
import time
import threading
import datetime
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

import config_manager
import telegram_sender
from bot_worker import BotWorker
from global_hotkey import GlobalHotkeyListener

# Define cores esteticas modernas
BG_DARK = "#000000"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"
ACCENT_YELLOW = "#f59e0b"
CARD_BG = "#1e293b"

class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Carrega a imagem da splashscreen
        from PIL import Image
        if os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                orig_w, orig_h = img.size
                aspect = orig_h / orig_w
                w = 600
                h = int(w * aspect)
            except Exception:
                w, h = 600, 350
        else:
            w, h = 600, 350
            
        # Centraliza a splashscreen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Exibe a imagem
        loaded = False
        if os.path.exists(image_path):
            try:
                self.photo = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
                lbl = ctk.CTkLabel(self, image=self.photo, text="")
                lbl.pack(fill="both", expand=True)
                loaded = True
            except Exception:
                pass
                
        if not loaded:
            lbl = ctk.CTkLabel(self, text="DERIV CLICKER BOT PRO\nCarregando...", font=ctk.CTkFont(size=20, weight="bold"))
            lbl.pack(fill="both", expand=True)

class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title="", start_collapsed=False, **kwargs):
        # Usamos CARD_BG e borda fina para combinar com a identidade visual do app
        super().__init__(parent, fg_color=CARD_BG, border_color="#334155", border_width=1, **kwargs)
        
        self.title = title
        self.collapsed = start_collapsed
        
        # Botão/Cabeçalho de toggle do recolhível
        self.toggle_btn = ctk.CTkButton(
            self, 
            text=f"▼  {title}" if not start_collapsed else f"▶  {title}", 
            anchor="w", 
            fg_color="#1e293b", 
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            corner_radius=4,
            command=self.toggle
        )
        self.toggle_btn.pack(fill="x", padx=1, pady=1)
        
        # Subframe interno contendo os elementos filhos
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        
        if not start_collapsed:
            self.content_frame.pack(fill="both", expand=True, padx=0, pady=0)
            
    def toggle(self):
        if self.collapsed:
            self.content_frame.pack(fill="both", expand=True, padx=0, pady=0)
            self.toggle_btn.configure(text=f"▼  {self.title}")
            self.collapsed = False
        else:
            self.content_frame.pack_forget()
            self.toggle_btn.configure(text=f"▶  {self.title}")
            self.collapsed = True

class AppGui(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Garante o ícone correto na barra de tarefas no Windows
        import ctypes
        try:
            myappid = 'deriv.clicker.bot.v1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
            
        self.withdraw()
        
        # Mostra a Splash Screen
        splash_path = "capturas/splashscren.png"
        self.splash = SplashScreen(self, splash_path)
        
        # Agenda exibir a janela principal
        self.after(2500, self._show_main_window)
        
        # Carrega configuracoes
        self.config = config_manager.load_config()
        self.bot = None
        self.hotkey_listener = None
        self.overlay = None
        self.stop_reason = None
        self.settings_win = None
        
        # Reseta streaks
        self.max_win_streak = 0
        self.max_loss_streak = 0
        self.current_win_streak = 0
        self.current_loss_streak = 0
        
        # Atalho local para o Overlay (Tecla O)
        self.bind_all("<Key-o>", lambda e: self.toggle_overlay())
        self.bind_all("<Key-O>", lambda e: self.toggle_overlay())
        
        # Timer e contadores locais para interface
        self.start_time = 0
        self.next_click_deadline = 0
        
        # Configura a janela
        self.title("Deriv Clicker Bot Pro")
        if os.path.exists("icon.ico"):
            try:
                self.iconbitmap("icon.ico")
            except Exception:
                pass
                
        # Dimensões e Centralização
        w, h = 1110, 965
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(1024, 700)            # tamanho mínimo para que nada fique cortado
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Garante foco ao abrir
        self.lift()
        self.focus_force()
        
        # Cria o layout de Grid principal
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=2, minsize=560)
        self.grid_rowconfigure(0, weight=1)
        
        self._build_left_panel()
        self._build_right_panel()
        
        # Carrega configuracoes salvas na interface
        self._apply_config_to_gui()
        
        # Atualiza o status de existencia dos arquivos de imagem
        self._check_image_files()
        
        # Inicia loop do timer da GUI
        self.update_gui_loop()
        
        # Inicia hotkey global de emergencia (F8)
        self._start_global_hotkey()
        
        self.log_message("[GUI] Interface carregada com sucesso. Pressione F8 a qualquer momento para parar o bot.")

        # Envia notificacao de Bot Preparado se Telegram estiver ativo
        modo_lbl = self._mode_label_from_key(self.config.get("mode", "fixed"))
        sens = self.config.get("sensitivity", 0.8)
        sens_num = self.config.get("sensitivity_number", 0.65)
        stop_win_info = f"{self.config.get('stop_win', 5)} Wins" if self.config.get("enable_stop_win", False) else "Desativado"
        stop_loss_info = f"{self.config.get('stop_loss', 3)} Losses" if self.config.get("enable_stop_loss", False) else "Desativado"
        
        prep_msg = (
            "🤖 <b>Deriv Clicker Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "⚡ <b>Estado:</b> Bot Preparado!\n"
            f"⚙️ <b>Modo Atual:</b> {modo_lbl}\n"
            f"🎯 <b>Sensibilidade Geral:</b> {sens:.2f}\n"
            f"🎯 <b>Sensibilidade Número:</b> {sens_num:.2f}\n"
            "📊 <b>Limites de Stop:</b>\n"
            f"├─ Stop Win: {stop_win_info}\n"
            f"└─ Stop Loss: {stop_loss_info}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<i>Pronto para iniciar a operação!</i>"
        )
        telegram_sender.send_telegram_msg(self.config, prep_msg, self.log_message)

    # --- ATALHO GLOBAL (F8) ---
    def _start_global_hotkey(self):
        try:
            self.hotkey_listener = GlobalHotkeyListener(callback=self.stop_bot_from_hotkey)
            self.hotkey_listener.start()
        except Exception as e:
            self.log_message(f"[Erro] Falha ao registrar F8 global: {e}")

    def stop_bot_from_hotkey(self):
        # Chamado de fora da thread principal (da thread de hotkey)
        # Usamos self.after para rodar na thread da GUI com seguranca
        self.after(0, self._handle_hotkey_stop)

    def _handle_hotkey_stop(self):
        if self.bot and self.bot.running:
            self.log_message("[Hotkey] F8 pressionado! Parada de emergencia acionada.")
            self.btn_stop_clicked()
        else:
            self.log_message("[Hotkey] F8 pressionado, mas o bot ja esta inativo.")

    # --- VERIFICA ARQUIVOS DE IMAGEM ---
    def _check_image_files(self):
        btn_path = self.config.get("image_button_path", "capturas/botao.png")
        win_path = self.config.get("image_win_path", "capturas/win.png")
        loss_path = self.config.get("image_loss_path", "capturas/loss.png")
        number_path = self.config.get("image_number_path", "capturas/number.png")
        
        btn_exists = os.path.exists(btn_path)
        win_exists = os.path.exists(win_path)
        loss_exists = os.path.exists(loss_path)
        number_exists = os.path.exists(number_path)
        
        if btn_exists:
            self.lbl_status_btn_img.configure(text="botao.png: OK", text_color=ACCENT_GREEN)
        else:
            self.lbl_status_btn_img.configure(text="botao.png: Ausente", text_color=ACCENT_RED)
            self.log_message(f"[Alerta] Arquivo '{btn_path}' nao encontrado na pasta do projeto!")
            
        if win_exists:
            self.lbl_status_win_img.configure(text="win.png: OK", text_color=ACCENT_GREEN)
        else:
            self.lbl_status_win_img.configure(text="win.png: Ausente", text_color=ACCENT_RED)
            self.log_message(f"[Alerta] Arquivo '{win_path}' nao encontrado na pasta do projeto!")

        if loss_exists:
            self.lbl_status_loss_img.configure(text="loss.png: OK", text_color=ACCENT_GREEN)
        else:
            self.lbl_status_loss_img.configure(text="loss.png: Ausente", text_color=ACCENT_RED)
            self.log_message(f"[Alerta] Arquivo '{loss_path}' nao encontrado na pasta do projeto!")

        if number_exists:
            self.lbl_status_number_img.configure(text="number.png: OK", text_color=ACCENT_GREEN)
        else:
            self.lbl_status_number_img.configure(text="number.png: Ausente", text_color=ACCENT_RED)

    # --- APLICACAO DAS CONFIGURACOES NA GUI ---
    def _apply_config_to_gui(self):
        # Modo
        mode = self.config.get("mode", "fixed")
        self.seg_mode.set(self._mode_label_from_key(mode))
        self._toggle_mode_frames(self._mode_label_from_key(mode))
        
        # Valores dos campos
        self.slider_fixed.set(self.config.get("fixed_interval", 5.0))
        self.lbl_fixed_val.configure(text=f"{self.config.get('fixed_interval', 5.0):.1f}s")
        
        self.slider_rand_min.set(self.config.get("random_min", 2.0))
        self.lbl_rand_min_val.configure(text=f"{self.config.get('random_min', 2.0):.1f}s")
        self.slider_rand_max.set(self.config.get("random_max", 10.0))
        self.lbl_rand_max_val.configure(text=f"{self.config.get('random_max', 10.0):.1f}s")
        
        self.entry_seq_clicks.delete(0, "end")
        self.entry_seq_clicks.insert(0, str(self.config.get("seq_clicks", 3)))
        self.entry_seq_interval.delete(0, "end")
        self.entry_seq_interval.insert(0, f"{self.config.get('seq_interval', 2.0):.1f}")
        self.entry_seq_wait.delete(0, "end")
        self.entry_seq_wait.insert(0, f"{self.config.get('seq_wait', 20.0):.1f}")
        
        # Sensibilidade (se janela de config estiver aberta)
        sens = self.config.get("sensitivity", 0.8)
        if hasattr(self, "settings_slider_sens") and self.settings_slider_sens and self.settings_slider_sens.winfo_exists():
            self.settings_slider_sens.set(sens)
        if hasattr(self, "lbl_sens_val") and self.lbl_sens_val and self.lbl_sens_val.winfo_exists():
            self.lbl_sens_val.configure(text=f"{sens:.2f}")
            
        # Sensibilidade do Número
        sens_num = self.config.get("sensitivity_number", 0.65)
        if hasattr(self, "settings_slider_sens_num") and self.settings_slider_sens_num and self.settings_slider_sens_num.winfo_exists():
            self.settings_slider_sens_num.set(sens_num)
        if hasattr(self, "lbl_sens_num_val") and self.lbl_sens_num_val and self.lbl_sens_num_val.winfo_exists():
            self.lbl_sens_num_val.configure(text=f"{sens_num:.2f}")
            
        # Região de Busca do Número
        use_region = self.config.get("use_search_region", False)
        if use_region:
            self.check_use_region.select()
        else:
            self.check_use_region.deselect()
            
        region = self.config.get("search_region", None)
        if region:
            self.lbl_region_coords.configure(text=f"{region[0]},{region[1]} ({region[2]}x{region[3]})")
        else:
            self.lbl_region_coords.configure(text="Não definida")
        
        # Gerenciamento Financeiro
        self.entry_win_value.delete(0, "end")
        self.entry_win_value.insert(0, f"{self.config.get('win_value', 1.50):.2f}")
        
        self.entry_loss_value.delete(0, "end")
        self.entry_loss_value.insert(0, f"{self.config.get('loss_value', 30.00):.2f}")
        
        self.entry_target_profit.delete(0, "end")
        self.entry_target_profit.insert(0, f"{self.config.get('target_profit', 10.00):.2f}")
        
        self.entry_free_entries.delete(0, "end")
        self.entry_free_entries.insert(0, str(self.config.get('free_entries', 10)))
        
        fin_mode = self.config.get("finance_mode", "target")
        if fin_mode == "target":
            self.seg_finance_mode.set("Meta de Lucro")
            self.frame_finance_free.pack_forget()
            self.frame_finance_target.pack(fill="x", padx=15, pady=(0, 10))
        else:
            self.seg_finance_mode.set("Livre")
            self.frame_finance_target.pack_forget()
            self.frame_finance_free.pack(fill="x", padx=15, pady=(0, 10))

        # Opcoes Extras (Janela de Configurações)
        play_sounds = self.config.get("play_sounds", True)
        if hasattr(self, "settings_switch_sounds") and self.settings_switch_sounds and self.settings_switch_sounds.winfo_exists():
            if play_sounds:
                self.settings_switch_sounds.select()
            else:
                self.settings_switch_sounds.deselect()
                
        auto_screenshot = self.config.get("auto_screenshot", False)
        if hasattr(self, "settings_switch_screenshot") and self.settings_switch_screenshot and self.settings_switch_screenshot.winfo_exists():
            if auto_screenshot:
                self.settings_switch_screenshot.select()
            else:
                self.settings_switch_screenshot.deselect()
                
        save_log = self.config.get("save_log", True)
        if hasattr(self, "settings_switch_logs") and self.settings_switch_logs and self.settings_switch_logs.winfo_exists():
            if save_log:
                self.settings_switch_logs.select()
            else:
                self.settings_switch_logs.deselect()

        use_custom_sounds = self.config.get("use_custom_sounds", True)
        if hasattr(self, "settings_switch_custom_sounds") and self.settings_switch_custom_sounds and self.settings_switch_custom_sounds.winfo_exists():
            if use_custom_sounds:
                self.settings_switch_custom_sounds.select()
            else:
                self.settings_switch_custom_sounds.deselect()

        # Stop Win / Stop Loss
        if self.config.get("enable_stop_win", False):
            self.check_stop_win.select()
        else:
            self.check_stop_win.deselect()
        self.entry_stop_win.delete(0, "end")
        self.entry_stop_win.insert(0, str(self.config.get("stop_win", 5)))
        
        if self.config.get("enable_stop_loss", False):
            self.check_stop_loss.select()
        else:
            self.check_stop_loss.deselect()
        self.entry_stop_loss.delete(0, "end")
        self.entry_stop_loss.insert(0, str(self.config.get("stop_loss", 3)))

        # Telegram config loading
        tg_enabled = self.config.get("telegram_enabled", False)
        if hasattr(self, "settings_switch_telegram") and self.settings_switch_telegram and self.settings_switch_telegram.winfo_exists():
            if tg_enabled:
                self.settings_switch_telegram.select()
            else:
                self.settings_switch_telegram.deselect()
        if hasattr(self, "settings_entry_tg_token") and self.settings_entry_tg_token and self.settings_entry_tg_token.winfo_exists():
            self.settings_entry_tg_token.delete(0, "end")
            self.settings_entry_tg_token.insert(0, self.config.get("telegram_token", ""))
        if hasattr(self, "settings_entry_tg_chat") and self.settings_entry_tg_chat and self.settings_entry_tg_chat.winfo_exists():
            self.settings_entry_tg_chat.delete(0, "end")
            self.settings_entry_tg_chat.insert(0, self.config.get("telegram_chat_id", ""))

        # Agendamento config loading
        if self.config.get("schedule_enabled", False):
            self.switch_schedule.select()
        else:
            self.switch_schedule.deselect()
            
        date_val = self.config.get("schedule_date", "")
        time_val = self.config.get("schedule_time", "")
        
        if not date_val:
            date_val = datetime.datetime.now().strftime("%d/%m/%Y")
        if not time_val:
            time_val = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M")
            
        self.entry_sched_date.delete(0, "end")
        self.entry_sched_date.insert(0, date_val)
        self.entry_sched_time.delete(0, "end")
        self.entry_sched_time.insert(0, time_val)

    def _mode_label_from_key(self, key):
        mapping = {
            "fixed": "Intervalo Fixo",
            "random": "Intervalo Aleatório",
            "sequence": "Sequência de Cliques",
            "linered": "Número Vermelho"
        }
        return mapping.get(key, "Intervalo Fixo")

    def _mode_key_from_label(self, label):
        mapping = {
            "Intervalo Fixo": "fixed",
            "Intervalo Aleatório": "random",
            "Sequência de Cliques": "sequence",
            "Linha Vermelha": "linered",
            "Número Vermelho": "linered"
        }
        return mapping.get(label, "fixed")

    # --- MONTAGEM DA INTERFACE ---
    def _build_left_panel(self):
        # Painel esquerdo
        left_frame = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Titulo do App (Logo ou Texto se não existir)
        logo_path = "imagens/logo.png"
        if not os.path.exists(logo_path):
            logo_path = "capturas/logo.png"
            
        loaded_logo = False
        if os.path.exists(logo_path):
            try:
                with Image.open(logo_path) as img:
                    orig_w, orig_h = img.size
                    aspect = orig_h / orig_w
                    logo_w = 320
                    logo_h = int(logo_w * aspect)
                    
                self.logo_img_pil = Image.open(logo_path)
                self.logo_img = ctk.CTkImage(
                    light_image=self.logo_img_pil,
                    dark_image=self.logo_img_pil,
                    size=(logo_w, logo_h)
                )
                lbl_title = ctk.CTkLabel(left_frame, image=self.logo_img, text="", fg_color="transparent")
                lbl_title.pack(fill="x", padx=0, pady=(0, 15))
                loaded_logo = True
            except Exception as e:
                print(f"[GUI] Erro ao carregar logo: {e}")
                
        if not loaded_logo:
            lbl_title = ctk.CTkLabel(left_frame, text="DERIV CLICKER", font=ctk.CTkFont(size=22, weight="bold"))
            lbl_title.pack(pady=(20, 5))
            lbl_subtitle = ctk.CTkLabel(left_frame, text="Automação Inteligente v1.0", text_color="gray", font=ctk.CTkFont(size=12))
            lbl_subtitle.pack(pady=(0, 20))
        
        # Status Card
        status_card = ctk.CTkFrame(left_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        status_card.pack(fill="x", padx=15, pady=10)
        
        lbl_status_title = ctk.CTkLabel(status_card, text="STATUS DO BOT", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray")
        lbl_status_title.pack(pady=(10, 2))
        
        self.lbl_status_value = ctk.CTkLabel(status_card, text="PARADO", text_color=ACCENT_RED, font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_status_value.pack(pady=(0, 10))
        
        # Painel de Metricas (Wins, Losses, Cliques, Assertividade)
        metrics_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=15, pady=10)
        metrics_frame.grid_columnconfigure(0, weight=1)
        metrics_frame.grid_columnconfigure(1, weight=1)
        metrics_frame.grid_columnconfigure(2, weight=1)
        
        # Card Cliques
        card_cliques = ctk.CTkFrame(metrics_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_cliques.grid(row=0, column=0, padx=(0, 2), pady=5, sticky="nsew")
        ctk.CTkLabel(card_cliques, text="CLIQUES", font=ctk.CTkFont(size=9, weight="bold"), text_color="gray").pack(pady=(8, 2))
        self.lbl_metric_clicks = ctk.CTkLabel(card_cliques, text="0", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_metric_clicks.pack(pady=(0, 8))
        
        # Card Wins
        card_wins = ctk.CTkFrame(metrics_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_wins.grid(row=0, column=1, padx=2, pady=5, sticky="nsew")
        ctk.CTkLabel(card_wins, text="WINS", font=ctk.CTkFont(size=9, weight="bold"), text_color="gray").pack(pady=(8, 2))
        self.lbl_metric_wins = ctk.CTkLabel(card_wins, text="0", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_GREEN)
        self.lbl_metric_wins.pack(pady=(0, 8))
        
        # Card Losses
        card_losses = ctk.CTkFrame(metrics_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_losses.grid(row=0, column=2, padx=(2, 0), pady=5, sticky="nsew")
        ctk.CTkLabel(card_losses, text="LOSSES", font=ctk.CTkFont(size=9, weight="bold"), text_color="gray").pack(pady=(8, 2))
        self.lbl_metric_losses = ctk.CTkLabel(card_losses, text="0", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_RED)
        self.lbl_metric_losses.pack(pady=(0, 8))
        
        # Card Assertividade (Taxa de acertos)
        card_rate = ctk.CTkFrame(left_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_rate.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(card_rate, text="ASSERTIVIDADE (TAXA DE WIN)", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(8, 2))
        self.lbl_metric_rate = ctk.CTkLabel(card_rate, text="0.0%", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_metric_rate.pack(pady=(0, 8))
        
        # Card Saldo Financeiro / Meta
        self.card_finance = ctk.CTkFrame(left_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        self.card_finance.pack(fill="x", padx=15, pady=5)
        
        self.lbl_finance_title = ctk.CTkLabel(self.card_finance, text="SALDO FINANCEIRO (META)", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray")
        self.lbl_finance_title.pack(pady=(8, 2))
        
        self.lbl_finance_value = ctk.CTkLabel(self.card_finance, text="$0.00 / $10.00", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_finance_value.pack(pady=(0, 5))
        
        self.progress_finance = ctk.CTkProgressBar(self.card_finance, height=8, progress_color=ACCENT_GREEN)
        self.progress_finance.pack(fill="x", padx=15, pady=(0, 10))
        self.progress_finance.set(0.0)
        
        # Card Tempo e Contadores
        info_card = ctk.CTkFrame(left_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        info_card.pack(fill="x", padx=15, pady=10)
        
        # Timer de Execucao
        row_time = ctk.CTkFrame(info_card, fg_color="transparent")
        row_time.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row_time, text="Tempo de Execução:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.lbl_timer = ctk.CTkLabel(row_time, text="00:00:00", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_timer.pack(side="right")
        
        # Contagem regressiva proximo clique
        row_next = ctk.CTkFrame(info_card, fg_color="transparent")
        row_next.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row_next, text="Próximo Clique:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.lbl_next_click = ctk.CTkLabel(row_next, text="Aguardando...", font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_next_click.pack(side="right")
        
        # Painel do Validador de Imagens (Agora Recolhível)
        img_check_container = CollapsibleFrame(left_frame, title="Verificador de Imagens", start_collapsed=True)
        img_check_container.pack(fill="x", padx=15, pady=(10, 5))
        
        self.lbl_status_btn_img = ctk.CTkLabel(img_check_container.content_frame, text="botao.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_btn_img.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_status_win_img = ctk.CTkLabel(img_check_container.content_frame, text="win.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_win_img.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_status_loss_img = ctk.CTkLabel(img_check_container.content_frame, text="loss.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_loss_img.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_status_number_img = ctk.CTkLabel(img_check_container.content_frame, text="number.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_number_img.pack(anchor="w", padx=15, pady=2)
        
        # Botoes de Acao Principais
        self.btn_start = ctk.CTkButton(left_frame, text="INICIAR BOT", fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=16, weight="bold"), height=45, command=self.btn_start_clicked)
        self.btn_start.pack(fill="x", padx=15, pady=(20, 10))
        
        self.btn_stop = ctk.CTkButton(left_frame, text="PARAR BOT (F8)", fg_color=ACCENT_RED, hover_color="#dc2626", font=ctk.CTkFont(size=16, weight="bold"), height=45, command=self.btn_stop_clicked, state="disabled")
        self.btn_stop.pack(fill="x", padx=15, pady=0)
        
        self.btn_overlay = ctk.CTkButton(
            left_frame, 
            text="WIDGET OVERLAY (O)", 
            fg_color="#475569", 
            hover_color="#334155", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            height=35, 
            command=self.toggle_overlay
        )
        self.btn_overlay.pack(fill="x", padx=15, pady=(15, 0))
        
        self.btn_settings = ctk.CTkButton(
            left_frame, 
            text="⚙️ CONFIGURAÇÕES", 
            fg_color="#1e293b", 
            hover_color="#334155", 
            border_color="#334155",
            border_width=1,
            font=ctk.CTkFont(size=14, weight="bold"), 
            height=35, 
            command=self.open_settings_popup
        )
        self.btn_settings.pack(fill="x", padx=15, pady=(10, 0))

    def _build_right_panel(self):
        # Painel direito — scrollável para não cortar conteúdo
        right_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
        )
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Titulo da Secao de Configs
        lbl_configs = ctk.CTkLabel(right_frame, text="Painel de Controle & Configurações", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_configs.pack(anchor="w", pady=(10, 15))
        
        # Seletor de Modo (Segmented Button para layout moderno)
        self.seg_mode = ctk.CTkSegmentedButton(right_frame, values=["Intervalo Fixo", "Intervalo Aleatório", "Sequência de Cliques", "Número Vermelho"], command=self._mode_selection_changed)
        self.seg_mode.pack(fill="x", pady=(0, 15))
        
        # Container de Modos Dinamicos (Agora Recolhível)
        self.mode_container = CollapsibleFrame(right_frame, title="Configurações do Modo", start_collapsed=True)
        self.mode_container.pack(fill="x", pady=(0, 15))
        
        # --- SUBFRAME: MODO FIXO ---
        self.frame_fixed = ctk.CTkFrame(self.mode_container.content_frame, fg_color="transparent")
        lbl_fixed = ctk.CTkLabel(self.frame_fixed, text="Configuração do Tempo Fixo", font=ctk.CTkFont(weight="bold"))
        lbl_fixed.pack(anchor="w", padx=15, pady=(10, 5))
        
        sub_fixed = ctk.CTkFrame(self.frame_fixed, fg_color="transparent")
        sub_fixed.pack(fill="x", padx=15, pady=5)
        self.slider_fixed = ctk.CTkSlider(sub_fixed, from_=1.0, to=60.0, number_of_steps=118, command=self._slider_fixed_changed)
        self.slider_fixed.pack(side="left", fill="x", expand=True)
        self.lbl_fixed_val = ctk.CTkLabel(sub_fixed, text="5.0s", width=50, font=ctk.CTkFont(weight="bold"))
        self.lbl_fixed_val.pack(side="right", padx=(10, 0))
        
        # --- SUBFRAME: MODO ALEATORIO ---
        self.frame_random = ctk.CTkFrame(self.mode_container.content_frame, fg_color="transparent")
        lbl_rand = ctk.CTkLabel(self.frame_random, text="Configuração do Intervalo Aleatório", font=ctk.CTkFont(weight="bold"))
        lbl_rand.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Slider Min
        row_min = ctk.CTkFrame(self.frame_random, fg_color="transparent")
        row_min.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row_min, text="Mínimo:", width=60, anchor="w").pack(side="left")
        self.slider_rand_min = ctk.CTkSlider(row_min, from_=1.0, to=30.0, number_of_steps=58, command=self._slider_rand_min_changed)
        self.slider_rand_min.pack(side="left", fill="x", expand=True)
        self.lbl_rand_min_val = ctk.CTkLabel(row_min, text="2.0s", width=50, font=ctk.CTkFont(weight="bold"))
        self.lbl_rand_min_val.pack(side="right", padx=(10, 0))
        
        # Slider Max
        row_max = ctk.CTkFrame(self.frame_random, fg_color="transparent")
        row_max.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row_max, text="Máximo:", width=60, anchor="w").pack(side="left")
        self.slider_rand_max = ctk.CTkSlider(row_max, from_=2.0, to=120.0, number_of_steps=118, command=self._slider_rand_max_changed)
        self.slider_rand_max.pack(side="left", fill="x", expand=True)
        self.lbl_rand_max_val = ctk.CTkLabel(row_max, text="10.0s", width=50, font=ctk.CTkFont(weight="bold"))
        self.lbl_rand_max_val.pack(side="right", padx=(10, 0))
        
        # --- SUBFRAME: MODO SEQUENCIA ---
        self.frame_sequence = ctk.CTkFrame(self.mode_container.content_frame, fg_color="transparent")
        lbl_seq = ctk.CTkLabel(self.frame_sequence, text="Configuração da Sequência de Cliques", font=ctk.CTkFont(weight="bold"))
        lbl_seq.pack(anchor="w", padx=15, pady=(10, 5))
        
        row_inputs = ctk.CTkFrame(self.frame_sequence, fg_color="transparent")
        row_inputs.pack(fill="x", padx=15, pady=(5, 15))
        
        # Cliques
        col1 = ctk.CTkFrame(row_inputs, fg_color="transparent")
        col1.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col1, text="Cliques por Ciclo", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_seq_clicks = ctk.CTkEntry(col1, height=28, width=70)
        self.entry_seq_clicks.pack(fill="x", pady=2)
        
        # Intervalo entre cliques
        col2 = ctk.CTkFrame(row_inputs, fg_color="transparent")
        col2.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col2, text="Intervalo Clicar (s)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_seq_interval = ctk.CTkEntry(col2, height=28, width=70)
        self.entry_seq_interval.pack(fill="x", pady=2)
        
        # Espera ciclo
        col3 = ctk.CTkFrame(row_inputs, fg_color="transparent")
        col3.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col3, text="Espera Ciclo (s)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_seq_wait = ctk.CTkEntry(col3, height=28, width=70)
        self.entry_seq_wait.pack(fill="x", pady=2)
 
        # --- SUBFRAME: MODO NÚMERO VERMELHO ---
        self.frame_linered = ctk.CTkFrame(self.mode_container.content_frame, fg_color="transparent")
        lbl_linered = ctk.CTkLabel(self.frame_linered, text="Modo Número Vermelho", font=ctk.CTkFont(weight="bold"))
        lbl_linered.pack(anchor="w", padx=15, pady=(10, 5))
        linered_info = (
            "O bot monitora a tela continuamente.\n"
            "Quando o número (number.png) for encontrado e ficar vermelho, clica no botão de entrada.\n"
            "O bot aguarda o número deixar de ser vermelho antes de entrar novamente."
        )
        ctk.CTkLabel(self.frame_linered, text=linered_info,
                     font=ctk.CTkFont(size=11), text_color="#94a3b8",
                     justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        # Configuração de Área de Busca do Número
        row_region = ctk.CTkFrame(self.frame_linered, fg_color="transparent")
        row_region.pack(fill="x", padx=15, pady=(0, 10))
        
        self.check_use_region = ctk.CTkCheckBox(row_region, text="Limitar Área de Busca", font=ctk.CTkFont(size=12), command=self._gui_setting_changed)
        self.check_use_region.pack(side="left", padx=(0, 10))
        
        self.btn_select_region = ctk.CTkButton(row_region, text="Definir Área", font=ctk.CTkFont(size=11), width=100, height=26, fg_color=ACCENT_BLUE, hover_color="#2563eb", command=self.btn_select_region_clicked)
        self.btn_select_region.pack(side="left", padx=(0, 10))
        
        self.lbl_region_coords = ctk.CTkLabel(row_region, text="Não definida", font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.lbl_region_coords.pack(side="left")

        # --- NOVO: CONTAINER DE AGENDAMENTO (Agora Recolhível) ---
        self.schedule_frame = CollapsibleFrame(right_frame, title="Agendamento de Início", start_collapsed=True)
        self.schedule_frame.pack(fill="x", pady=(0, 15))
        
        row_sched = ctk.CTkFrame(self.schedule_frame.content_frame, fg_color="transparent")
        row_sched.pack(fill="x", padx=15, pady=10)
        
        self.switch_schedule = ctk.CTkSwitch(row_sched, text="Ativar Agendamento", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.switch_schedule.pack(side="left", padx=(0, 20))
        
        # Data
        col_sched_date = ctk.CTkFrame(row_sched, fg_color="transparent")
        col_sched_date.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_sched_date, text="Data (DD/MM/AAAA)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_sched_date = ctk.CTkEntry(col_sched_date, height=28, placeholder_text="Ex: 10/06/2026")
        self.entry_sched_date.pack(fill="x", pady=2)
        self.entry_sched_date.bind("<KeyRelease>", self._gui_setting_changed)
        
        # Horário
        col_sched_time = ctk.CTkFrame(row_sched, fg_color="transparent")
        col_sched_time.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_sched_time, text="Hora (HH:MM)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_sched_time = ctk.CTkEntry(col_sched_time, height=28, placeholder_text="Ex: 10:00")
        self.entry_sched_time.pack(fill="x", pady=2)
        self.entry_sched_time.bind("<KeyRelease>", self._gui_setting_changed)

        # --- LIMITES DE RISCO (Recolhível) ---
        limits_frame = CollapsibleFrame(right_frame, title="Limites de Risco (Stop Win / Loss)", start_collapsed=True)
        limits_frame.pack(fill="x", pady=(0, 15))
        
        row_stops = ctk.CTkFrame(limits_frame.content_frame, fg_color="transparent")
        row_stops.pack(fill="x", padx=15, pady=10)
        
        # Stop Win
        col_stop_win = ctk.CTkFrame(row_stops, fg_color="transparent")
        col_stop_win.pack(side="left", fill="x", expand=True, padx=5)
        self.check_stop_win = ctk.CTkCheckBox(col_stop_win, text="Stop Win (Wins):", font=ctk.CTkFont(size=12), command=self._gui_setting_changed)
        self.check_stop_win.pack(side="left", padx=(0, 5))
        self.entry_stop_win = ctk.CTkEntry(col_stop_win, width=55, height=26)
        self.entry_stop_win.pack(side="left")
        self.entry_stop_win.bind("<KeyRelease>", self._gui_setting_changed)
        
        # Stop Loss
        col_stop_loss = ctk.CTkFrame(row_stops, fg_color="transparent")
        col_stop_loss.pack(side="left", fill="x", expand=True, padx=5)
        self.check_stop_loss = ctk.CTkCheckBox(col_stop_loss, text="Stop Loss (Losses):", font=ctk.CTkFont(size=12), command=self._gui_setting_changed)
        self.check_stop_loss.pack(side="left", padx=(0, 5))
        self.entry_stop_loss = ctk.CTkEntry(col_stop_loss, width=55, height=26)
        self.entry_stop_loss.pack(side="left")
        self.entry_stop_loss.bind("<KeyRelease>", self._gui_setting_changed)

        # --- GERENCIAMENTO FINANCEIRO (Recolhível) ---
        finance_frame = CollapsibleFrame(right_frame, title="Gerenciamento Financeiro (Meta / Livre)", start_collapsed=True)
        finance_frame.pack(fill="x", pady=(0, 15))

        # Configurações de Win/Loss (Comum)
        row_values = ctk.CTkFrame(finance_frame.content_frame, fg_color="transparent")
        row_values.pack(fill="x", padx=15, pady=(5, 5))
        
        # Win value
        col_win = ctk.CTkFrame(row_values, fg_color="transparent")
        col_win.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_win, text="Retorno por Win ($)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_win_value = ctk.CTkEntry(col_win, height=28)
        self.entry_win_value.pack(fill="x", pady=2)
        self.entry_win_value.bind("<KeyRelease>", self._gui_setting_changed)
        
        # Loss value
        col_loss = ctk.CTkFrame(row_values, fg_color="transparent")
        col_loss.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(col_loss, text="Custo por Loss ($)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_loss_value = ctk.CTkEntry(col_loss, height=28)
        self.entry_loss_value.pack(fill="x", pady=2)
        self.entry_loss_value.bind("<KeyRelease>", self._gui_setting_changed)
        
        # Modo de Gerenciamento
        lbl_mode_title = ctk.CTkLabel(finance_frame.content_frame, text="Modo de Gerenciamento", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_mode_title.pack(anchor="w", padx=15, pady=(5, 2))
        
        self.seg_finance_mode = ctk.CTkSegmentedButton(
            finance_frame.content_frame, 
            values=["Meta de Lucro", "Livre"], 
            command=self._finance_mode_changed
        )
        self.seg_finance_mode.pack(fill="x", padx=15, pady=(0, 10))
        
        # Sub-frames específicos para cada modo
        self.frame_finance_target = ctk.CTkFrame(finance_frame.content_frame, fg_color="transparent")
        self.frame_finance_target.pack(fill="x", padx=15, pady=(0, 10))
        
        # Meta de Lucro
        ctk.CTkLabel(self.frame_finance_target, text="Meta de Lucro ($)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_target_profit = ctk.CTkEntry(self.frame_finance_target, height=28)
        self.entry_target_profit.pack(fill="x", pady=2)
        self.entry_target_profit.bind("<KeyRelease>", self._gui_setting_changed)
        
        # Livre
        self.frame_finance_free = ctk.CTkFrame(finance_frame.content_frame, fg_color="transparent")
        
        ctk.CTkLabel(self.frame_finance_free, text="Quantidade Limite de Entradas (Livre)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_free_entries = ctk.CTkEntry(self.frame_finance_free, height=28)
        self.entry_free_entries.pack(fill="x", pady=2)
        self.entry_free_entries.bind("<KeyRelease>", self._gui_setting_changed)

        # --- LOG CONSOLE EM TEMPO REAL (Agora Recolhível) ---
        console_frame = CollapsibleFrame(right_frame, title="Logs de Operação em Tempo Real", start_collapsed=True)
        console_frame.pack(fill="both", expand=True)
        
        row_console_hdr = ctk.CTkFrame(console_frame.content_frame, fg_color="transparent")
        row_console_hdr.pack(fill="x", padx=15, pady=(10, 5))
        
        btn_clear_log = ctk.CTkButton(row_console_hdr, text="Limpar Logs", width=90, height=22, font=ctk.CTkFont(size=11), fg_color="#475569", hover_color="#334155", command=self.btn_clear_log_clicked)
        btn_clear_log.pack(side="right")
        
        self.txt_log = ctk.CTkTextbox(console_frame.content_frame, font=ctk.CTkFont(family="Consolas", size=12), text_color="#f8fafc", fg_color="#000000", border_color="#334155", border_width=1)
        self.txt_log.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.txt_log.configure(state="disabled")

    # --- LISTENER DE MUDANCA DE CONTROLES ---
    def _mode_selection_changed(self, value):
        self._toggle_mode_frames(value)
        self._gui_setting_changed()

    def _toggle_mode_frames(self, mode_label):
        # Esconde todos primeiro
        self.frame_fixed.pack_forget()
        self.frame_random.pack_forget()
        self.frame_sequence.pack_forget()
        self.frame_linered.pack_forget()
        
        if mode_label == "Intervalo Fixo":
            self.frame_fixed.pack(fill="x", pady=5)
        elif mode_label == "Intervalo Aleatório":
            self.frame_random.pack(fill="x", pady=5)
        elif mode_label == "Sequência de Cliques":
            self.frame_sequence.pack(fill="x", pady=5)
        elif mode_label == "Linha Vermelha" or mode_label == "Número Vermelho":
            self.frame_linered.pack(fill="x", pady=5)

    def _slider_fixed_changed(self, val):
        self.lbl_fixed_val.configure(text=f"{val:.1f}s")
        self._gui_setting_changed()

    def _slider_rand_min_changed(self, val):
        # Garante que min nao seja maior que max
        max_val = self.slider_rand_max.get()
        if val > max_val:
            self.slider_rand_max.set(val)
            self.lbl_rand_max_val.configure(text=f"{val:.1f}s")
        self.lbl_rand_min_val.configure(text=f"{val:.1f}s")
        self._gui_setting_changed()

    def _slider_rand_max_changed(self, val):
        # Garante que max nao seja menor que min
        min_val = self.slider_rand_min.get()
        if val < min_val:
            self.slider_rand_min.set(val)
            self.lbl_rand_min_val.configure(text=f"{val:.1f}s")
        self.lbl_rand_max_val.configure(text=f"{val:.1f}s")
        self._gui_setting_changed()

    def _slider_sens_changed(self, val):
        if hasattr(self, "lbl_sens_val") and self.lbl_sens_val and self.lbl_sens_val.winfo_exists():
            self.lbl_sens_val.configure(text=f"{val:.2f}")
        self._gui_setting_changed()

    def _slider_sens_num_changed(self, val):
        if hasattr(self, "lbl_sens_num_val") and self.lbl_sens_num_val and self.lbl_sens_num_val.winfo_exists():
            self.lbl_sens_num_val.configure(text=f"{val:.2f}")
        self._gui_setting_changed()

    # --- SALVAR CONFIGURACOES AUTOMATICAMENTE ---
    def _gui_setting_changed(self, *args):
        # Tenta ler a sequencia com segurança
        try:
            seq_clicks = int(self.entry_seq_clicks.get())
        except ValueError:
            seq_clicks = 3
            
        try:
            seq_interval = float(self.entry_seq_interval.get())
        except ValueError:
            seq_interval = 2.0
            
        try:
            seq_wait = float(self.entry_seq_wait.get())
        except ValueError:
            seq_wait = 20.0

        try:
            stop_win_val = int(self.entry_stop_win.get())
        except ValueError:
            stop_win_val = 5

        try:
            stop_loss_val = int(self.entry_stop_loss.get())
        except ValueError:
            stop_loss_val = 3

        # Atualiza o dicionario
        # Validação financeira
        try:
            win_val = float(self.entry_win_value.get().replace(",", "."))
        except ValueError:
            win_val = 1.50
            
        try:
            loss_val = float(self.entry_loss_value.get().replace(",", "."))
        except ValueError:
            loss_val = 30.00
            
        try:
            target_profit_val = float(self.entry_target_profit.get().replace(",", "."))
        except ValueError:
            target_profit_val = 10.00
            
        try:
            free_entries_val = int(self.entry_free_entries.get())
        except ValueError:
            free_entries_val = 10
            
        self.config["win_value"] = win_val
        self.config["loss_value"] = loss_val
        self.config["target_profit"] = target_profit_val
        self.config["free_entries"] = free_entries_val
        self.config["finance_mode"] = "target" if self.seg_finance_mode.get() == "Meta de Lucro" else "free"

        self.config["mode"] = self._mode_key_from_label(self.seg_mode.get())
        self.config["fixed_interval"] = round(self.slider_fixed.get(), 1)
        self.config["random_min"] = round(self.slider_rand_min.get(), 1)
        self.config["random_max"] = round(self.slider_rand_max.get(), 1)
        self.config["seq_clicks"] = seq_clicks
        self.config["seq_interval"] = round(seq_interval, 1)
        self.config["seq_wait"] = round(seq_wait, 1)
        self.config["use_search_region"] = self.check_use_region.get() == 1
        
        # Leitura da janela de configurações se estiver aberta
        if hasattr(self, "settings_slider_sens") and self.settings_slider_sens and self.settings_slider_sens.winfo_exists():
            self.config["sensitivity"] = round(self.settings_slider_sens.get(), 2)
        if hasattr(self, "settings_slider_sens_num") and self.settings_slider_sens_num and self.settings_slider_sens_num.winfo_exists():
            self.config["sensitivity_number"] = round(self.settings_slider_sens_num.get(), 2)
        if hasattr(self, "settings_switch_sounds") and self.settings_switch_sounds and self.settings_switch_sounds.winfo_exists():
            self.config["play_sounds"] = self.settings_switch_sounds.get() == 1
        if hasattr(self, "settings_switch_screenshot") and self.settings_switch_screenshot and self.settings_switch_screenshot.winfo_exists():
            self.config["auto_screenshot"] = self.settings_switch_screenshot.get() == 1
        if hasattr(self, "settings_switch_logs") and self.settings_switch_logs and self.settings_switch_logs.winfo_exists():
            self.config["save_log"] = self.settings_switch_logs.get() == 1
        if hasattr(self, "settings_switch_custom_sounds") and self.settings_switch_custom_sounds and self.settings_switch_custom_sounds.winfo_exists():
            self.config["use_custom_sounds"] = self.settings_switch_custom_sounds.get() == 1
            
        self.config["enable_stop_win"] = self.check_stop_win.get() == 1
        self.config["stop_win"] = stop_win_val
        self.config["enable_stop_loss"] = self.check_stop_loss.get() == 1
        self.config["stop_loss"] = stop_loss_val

        # Telegram Configuration
        if hasattr(self, "settings_switch_telegram") and self.settings_switch_telegram and self.settings_switch_telegram.winfo_exists():
            self.config["telegram_enabled"] = self.settings_switch_telegram.get() == 1
        if hasattr(self, "settings_entry_tg_token") and self.settings_entry_tg_token and self.settings_entry_tg_token.winfo_exists():
            self.config["telegram_token"] = self.settings_entry_tg_token.get().strip()
        if hasattr(self, "settings_entry_tg_chat") and self.settings_entry_tg_chat and self.settings_entry_tg_chat.winfo_exists():
            self.config["telegram_chat_id"] = self.settings_entry_tg_chat.get().strip()
        
        # Agendamento
        self.config["schedule_enabled"] = self.switch_schedule.get() == 1
        self.config["schedule_date"] = self.entry_sched_date.get().strip()
        self.config["schedule_time"] = self.entry_sched_time.get().strip()
        
        # Salva no arquivo JSON
        config_manager.save_config(self.config)
        
        # Se o bot estiver rodando, atualiza a configuracao dele dinamicamente
        if self.bot and self.bot.running:
            self.bot.config = self.config

    def open_settings_popup(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.focus()
            return
            
        self.settings_win = ctk.CTkToplevel(self)
        self.settings_win.title("⚙️ Configurações Avançadas")
        self.settings_win.geometry("540x650")
        self.settings_win.resizable(False, False)
        self.settings_win.transient(self) # Foca no topo da janela principal
        
        # Centraliza a janela de configurações na tela
        self.settings_win.update_idletasks()
        width = 540
        height = 650
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        self.settings_win.geometry(f"{width}x{height}+{x}+{y}")
        
        # Main container
        main_frame = ctk.CTkFrame(self.settings_win, fg_color="#0f172a")
        main_frame.pack(fill="both", expand=True)
        
        # Header title
        lbl_header = ctk.CTkLabel(
            main_frame, 
            text="⚙️ CONFIGURAÇÕES AVANÇADAS", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f8fafc"
        )
        lbl_header.pack(pady=(20, 10))
        
        # Scrollable Frame to avoid clipping
        scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color="#1e293b", scrollbar_button_color="#475569", scrollbar_button_hover_color="#64748b")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # SECTION 1: SENSIBILIDADE
        sec1_frame = ctk.CTkFrame(scroll_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        sec1_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_sec1_title = ctk.CTkLabel(sec1_frame, text="🎯 Sensibilidade OpenCV", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        lbl_sec1_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Sensibilidade Geral
        ctk.CTkLabel(sec1_frame, text="Sensibilidade Geral (Botões, Win/Loss)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=15)
        row_sens = ctk.CTkFrame(sec1_frame, fg_color="transparent")
        row_sens.pack(fill="x", padx=15, pady=(2, 8))
        self.settings_slider_sens = ctk.CTkSlider(row_sens, from_=0.5, to=1.0, number_of_steps=50, command=self._slider_sens_changed)
        self.settings_slider_sens.pack(side="left", fill="x", expand=True)
        self.lbl_sens_val = ctk.CTkLabel(row_sens, text="0.80", width=40, font=ctk.CTkFont(weight="bold"))
        self.lbl_sens_val.pack(side="right", padx=(10, 0))
        
        # Sensibilidade do Número
        ctk.CTkLabel(sec1_frame, text="Sensibilidade do Número (Preço / Sinal)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=15)
        row_sens_num = ctk.CTkFrame(sec1_frame, fg_color="transparent")
        row_sens_num.pack(fill="x", padx=15, pady=(2, 12))
        self.settings_slider_sens_num = ctk.CTkSlider(row_sens_num, from_=0.5, to=1.0, number_of_steps=50, command=self._slider_sens_num_changed)
        self.settings_slider_sens_num.pack(side="left", fill="x", expand=True)
        self.lbl_sens_num_val = ctk.CTkLabel(row_sens_num, text="0.65", width=40, font=ctk.CTkFont(weight="bold"))
        self.lbl_sens_num_val.pack(side="right", padx=(10, 0))

        # SECTION 2: AUDIO E SONS
        sec2_frame = ctk.CTkFrame(scroll_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        sec2_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_sec2_title = ctk.CTkLabel(sec2_frame, text="🔊 Avisos Sonoros & Recursos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        lbl_sec2_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.settings_switch_sounds = ctk.CTkSwitch(sec2_frame, text="Ativar Sons de Eventos", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_sounds.pack(anchor="w", padx=15, pady=4)
        
        self.settings_switch_custom_sounds = ctk.CTkSwitch(sec2_frame, text="Usar Sons Personalizados (.mp3)", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_custom_sounds.pack(anchor="w", padx=15, pady=4)
        
        # Testador de Sons
        row_sound_test = ctk.CTkFrame(sec2_frame, fg_color="transparent")
        row_sound_test.pack(fill="x", padx=15, pady=(8, 12))
        self.settings_sound_test_combo = ctk.CTkComboBox(row_sound_test, values=["Entrada", "Vitória", "Derrota", "Início", "Stop Win", "Stop Loss"], height=28)
        self.settings_sound_test_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        btn_test_sound = ctk.CTkButton(row_sound_test, text="▶ Testar", width=80, height=28, command=self._test_sound, fg_color="#475569", hover_color="#334155")
        btn_test_sound.pack(side="right")

        # SECTION 3: TELEGRAM
        sec3_frame = ctk.CTkFrame(scroll_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        sec3_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_sec3_title = ctk.CTkLabel(sec3_frame, text="💬 Notificações do Telegram", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        lbl_sec3_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.settings_switch_telegram = ctk.CTkSwitch(sec3_frame, text="Ativar Envio para Telegram", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_telegram.pack(anchor="w", padx=15, pady=4)
        
        row_tg_inputs = ctk.CTkFrame(sec3_frame, fg_color="transparent")
        row_tg_inputs.pack(fill="x", padx=15, pady=6)
        
        col_token = ctk.CTkFrame(row_tg_inputs, fg_color="transparent")
        col_token.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_token, text="Bot Token API", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_tg_token = ctk.CTkEntry(col_token, height=28, placeholder_text="Token API")
        self.settings_entry_tg_token.pack(fill="x", pady=2)
        self.settings_entry_tg_token.bind("<KeyRelease>", self._gui_setting_changed)
        
        col_chat = ctk.CTkFrame(row_tg_inputs, fg_color="transparent")
        col_chat.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(col_chat, text="Chat ID", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_tg_chat = ctk.CTkEntry(col_chat, height=28, placeholder_text="Chat ID")
        self.settings_entry_tg_chat.pack(fill="x", pady=2)
        self.settings_entry_tg_chat.bind("<KeyRelease>", self._gui_setting_changed)
        
        row_tg_actions = ctk.CTkFrame(sec3_frame, fg_color="transparent")
        row_tg_actions.pack(fill="x", padx=15, pady=(4, 12))
        
        self.btn_fetch_chat_id = ctk.CTkButton(
            row_tg_actions, text="🔍 Buscar Chat ID", width=130, height=28,
            font=ctk.CTkFont(size=11), fg_color=ACCENT_BLUE, hover_color="#2563eb",
            command=self._fetch_chat_id_clicked
        )
        self.btn_fetch_chat_id.pack(side="left", padx=(0, 8))
        
        self.btn_tg_test = ctk.CTkButton(
            row_tg_actions, text="✉️ Testar Envio", width=110, height=28,
            font=ctk.CTkFont(size=11), fg_color="#475569", hover_color="#334155",
            command=self._tg_test_clicked
        )
        self.btn_tg_test.pack(side="left")
        
        self.lbl_tg_status = ctk.CTkLabel(sec3_frame, text="", font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.lbl_tg_status.pack(anchor="w", padx=15, pady=(0, 10))

        # SECTION 4: SISTEMA E LOGS
        sec4_frame = ctk.CTkFrame(scroll_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        sec4_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_sec4_title = ctk.CTkLabel(sec4_frame, text="💻 Sistema & Diagnósticos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        lbl_sec4_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.settings_switch_screenshot = ctk.CTkSwitch(sec4_frame, text="Salvar Captura de Tela (Win/Loss)", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_screenshot.pack(anchor="w", padx=15, pady=4)
        
        self.settings_switch_logs = ctk.CTkSwitch(sec4_frame, text="Gravar Logs Locais", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_logs.pack(anchor="w", padx=15, pady=(4, 12))
        
        # Botão Fechar no rodapé
        btn_close = ctk.CTkButton(
            main_frame, 
            text="FECHAR E APLICAR", 
            fg_color=ACCENT_GREEN, 
            hover_color="#059669", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self.settings_win.destroy
        )
        btn_close.pack(fill="x", padx=15, pady=15)
        
        # Popula as configurações nos novos widgets da tela de settings
        self._apply_config_to_gui()

    def _test_sound(self):
        import winsound, pygame, os
        selected = self.settings_sound_test_combo.get()
        mapping = {
            "Entrada": "click",
            "Vitória": "win",
            "Derrota": "loss",
            "Início": "start",
            "Stop Win": "stopwin",
            "Stop Loss": "stoploss"
        }
        sound_key = mapping.get(selected)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            path_mapping = {
                "click": "songs/entrada.mp3",
                "win": "songs/win.mp3",
                "loss": "songs/loss.mp3",
                "start": "songs/start.mp3",
                "stopwin": "songs/stopwin.mp3",
                "stoploss": "songs/stoploss.mp3"
            }
            p = path_mapping.get(sound_key)
            if self.config.get("use_custom_sounds", True) and p and os.path.exists(p):
                s = pygame.mixer.Sound(p)
                s.play()
            else:
                # Classic winsound beeps fallback for test
                if sound_key == "click":
                    winsound.Beep(1000, 150)
                elif sound_key in ["win", "stopwin"]:
                    winsound.Beep(1800, 200)
                    winsound.Beep(2200, 300)
                elif sound_key in ["loss", "stoploss"]:
                    winsound.Beep(800, 250)
                    winsound.Beep(500, 350)
                elif sound_key == "start":
                    winsound.Beep(1200, 150)
                    winsound.Beep(1500, 150)
        except Exception as e:
            print(f"Erro ao testar som: {e}")

    # --- COMANDOS DE BOTOES ---
    def btn_start_clicked(self):
        # Valida primeiro se os inputs de sequencia estao certos caso esteja no modo sequencia
        if self.seg_mode.get() == "Sequência de Cliques":
            try:
                int(self.entry_seq_clicks.get())
                float(self.entry_seq_interval.get())
                float(self.entry_seq_wait.get())
            except ValueError:
                messagebox.showerror("Erro de Configuração", "Os campos da sequência de cliques devem conter apenas números!")
                return
        
        # Valida agendamento se estiver ativo
        if self.switch_schedule.get() == 1:
            date_str = self.entry_sched_date.get().strip()
            time_str = self.entry_sched_time.get().strip()
            try:
                target_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
                now_dt = datetime.datetime.now()
                if target_dt <= now_dt:
                    messagebox.showerror("Erro de Agendamento", "O horário agendado deve ser no futuro!")
                    return
            except ValueError:
                messagebox.showerror("Erro de Agendamento", "Formato de data ou hora inválido! Use DD/MM/AAAA e HH:MM.")
                return

        # Valida arquivos de imagem
        btn_path = self.config.get("image_button_path", "capturas/botao.png")
        if not os.path.exists(btn_path):
            messagebox.showerror("Erro de Arquivo", f"Não foi possível iniciar. A imagem de referência do botão não foi encontrada em: {btn_path}")
            return
            
        self._gui_setting_changed()  # Salva tudo antes de iniciar
        self.stop_reason = None
        
        is_scheduled = self.switch_schedule.get() == 1
        if is_scheduled:
            self.lbl_status_value.configure(text="AGENDADO", text_color=ACCENT_YELLOW)
        else:
            self.lbl_status_value.configure(text="EXECUTANDO", text_color=ACCENT_GREEN)
            
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        
        # Reseta metricas na GUI
        self.lbl_metric_clicks.configure(text="0")
        self.lbl_metric_wins.configure(text="0")
        self.lbl_metric_losses.configure(text="0")
        self.lbl_metric_rate.configure(text="0.0%")
        self.lbl_timer.configure(text="00:00:00")
        self.lbl_next_click.configure(text="Aguardando...")
        
        # Reseta streaks
        self.max_win_streak = 0
        self.max_loss_streak = 0
        self.current_win_streak = 0
        self.current_loss_streak = 0
        
        self._update_overlay_data()
        
        # Reseta financeiro na GUI
        fin_mode = self.config.get("finance_mode", "target")
        if fin_mode == "target":
            target = self.config.get("target_profit", 10.00)
            self.lbl_finance_title.configure(text="SALDO FINANCEIRO (META)")
            self.lbl_finance_value.configure(text=f"$0.00 / ${target:.2f}", text_color=ACCENT_BLUE)
        else:
            limit_entries = self.config.get("free_entries", 10)
            self.lbl_finance_title.configure(text="SALDO FINANCEIRO (ENTRADAS)")
            self.lbl_finance_value.configure(text=f"$0.00 (0 / {limit_entries} Entr.)", text_color=ACCENT_BLUE)
        self.progress_finance.set(0.0)
        
        # Inicia o thread do BotWorker
        self.start_time = time.time()
        self.remaining_schedule_time = 0
        self.bot = BotWorker(
            config=self.config,
            on_click_cb=self.update_clicks_metric,
            on_win_cb=self.update_wins_metric,
            on_loss_cb=self.update_losses_metric,
            on_log_cb=self.log_message,
            on_status_cb=self.bot_status_changed_external,
            on_next_time_cb=self.update_next_click_metric,
            on_stop_limit_cb=self._on_stop_limit,
            on_start_execution_cb=self.bot_started_execution,
            on_finance_cb=self.update_finance_metric
        )
        self.bot.start_bot()

    def btn_stop_clicked(self):
        self.stop_reason = None
        if self.bot:
            self.bot.stop_bot()
            self.bot = None
            
        self.lbl_status_value.configure(text="PARADO", text_color=ACCENT_RED)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_next_click.configure(text="Inativo", text_color="gray")
        self._update_overlay_data()

    def bot_status_changed_external(self, running):
        # Chamado pelo bot_worker se ele parar sozinho ou devido a erro
        if not running:
            self.after(0, self._handle_bot_stopped_external)

    def _handle_bot_stopped_external(self):
        reason = getattr(self, "stop_reason", None)
        if reason in ["win", "profit_win"]:
            self.lbl_status_value.configure(text="STOP WIN", text_color=ACCENT_GREEN)
        elif reason == "loss":
            self.lbl_status_value.configure(text="STOP LOSS", text_color=ACCENT_RED)
        elif reason == "entries":
            self.lbl_status_value.configure(text="LIMIT ENTRADAS", text_color=ACCENT_BLUE)
        else:
            self.lbl_status_value.configure(text="PARADO", text_color=ACCENT_RED)
            
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_next_click.configure(text="Inativo", text_color="gray")
        self.bot = None
        self._update_overlay_data()

    def _on_stop_limit(self, limit_type, count):
        """Chamado pelo BotWorker quando o Stop Win ou Stop Loss e atingido."""
        self.stop_reason = limit_type
        self.after(0, lambda: self._show_stop_limit_popup(limit_type, count))

    def _show_stop_limit_popup(self, limit_type, count):
        """Exibe uma janela modal informando que o limite foi atingido."""
        popup = ctk.CTkToplevel(self)
        popup.grab_set()
        popup.resizable(False, False)
        popup.overrideredirect(True)  # sem barra de titulo do OS

        if limit_type == "win":
            bg_color   = "#064e3b"   # verde escuro
            border_col = "#10b981"
            icon       = "💰"
            title_txt  = "STOP WIN ATINGIDO!"
            detail_txt = f"Meta de {count} vitórias alcançada!\nExcelente sessão! Lucro garantido."
        elif limit_type == "profit_win":
            bg_color   = "#064e3b"   # verde escuro
            border_col = "#10b981"
            icon       = "💰"
            title_txt  = "META DE LUCRO BATIDA!"
            detail_txt = f"Meta de Lucro de ${count:.2f} alcançada!\nExcelente sessão! Lucro garantido."
        elif limit_type == "entries":
            bg_color   = "#1e3a8a"   # azul escuro
            border_col = "#3b82f6"
            icon       = "🏁"
            title_txt  = "LIMITE DE ENTRADAS!"
            detail_txt = f"Limite de {count} entradas alcançado (Modo Livre).\nOperações finalizadas com sucesso."
        else:
            bg_color   = "#7f1d1d"   # vermelho escuro
            border_col = "#ef4444"
            icon       = "⚠️"
            title_txt  = "STOP LOSS ATINGIDO!"
            detail_txt = f"Limite de {count} derrotas alcançado.\nBot parado para proteger seu capital."

        popup.configure(fg_color=bg_color)

        # Centraliza na janela principal
        self.update_idletasks()
        w, h = 380, 200
        px = self.winfo_x() + (self.winfo_width()  - w) // 2
        py = self.winfo_y() + (self.winfo_height() - h) // 2
        popup.geometry(f"{w}x{h}+{px}+{py}")

        # Borda colorida via frame externo
        border_frame = ctk.CTkFrame(popup, fg_color=border_col, corner_radius=12)
        border_frame.pack(fill="both", expand=True, padx=2, pady=2)

        inner = ctk.CTkFrame(border_frame, fg_color=bg_color, corner_radius=10)
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=36)).pack(pady=(18, 4))
        ctk.CTkLabel(inner, text=title_txt,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=border_col).pack()
        ctk.CTkLabel(inner, text=detail_txt,
                     font=ctk.CTkFont(size=12),
                     text_color="#e2e8f0",
                     justify="center").pack(pady=(6, 14))
        ctk.CTkButton(inner, text="OK", width=100, height=30,
                      fg_color=border_col, hover_color=bg_color,
                      command=popup.destroy).pack()

    def btn_clear_log_clicked(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    # --- TELEGRAM: BUSCAR CHAT ID e TESTAR ---
    def _fetch_chat_id_clicked(self):
        """Chama getUpdates para descobrir o chat_id do último usuário que mandou mensagem."""
        import threading, urllib.request, urllib.error, json

        if hasattr(self, "settings_entry_tg_token") and self.settings_entry_tg_token and self.settings_entry_tg_token.winfo_exists():
            token = self.settings_entry_tg_token.get().strip()
        elif hasattr(self, "entry_tg_token") and self.entry_tg_token and self.entry_tg_token.winfo_exists():
            token = self.entry_tg_token.get().strip()
        else:
            token = self.config.get("telegram_token", "")

        if not token:
            self.lbl_tg_status.configure(text="⚠ Cole o Token primeiro.", text_color=ACCENT_YELLOW)
            return

        self.btn_fetch_chat_id.configure(state="disabled", text="Buscando...")
        self.lbl_tg_status.configure(text="Consultando Telegram...", text_color="#94a3b8")

        def _do_fetch():
            url = f"https://api.telegram.org/bot{token}/getUpdates?limit=10&offset=-10"
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                desc = json.loads(body).get("description", body) if body else str(e)
                self.after(0, lambda: self._fetch_done_error(f"Erro {e.code}: {desc}"))
                return
            except Exception as exc:
                self.after(0, lambda: self._fetch_done_error(str(exc)))
                return

            results = data.get("result", [])
            if not results:
                self.after(0, lambda: self._fetch_done_error(
                    "Nenhuma mensagem encontrada. Envie /start para o bot e tente novamente."))
                return

            # Pega o chat_id da última mensagem recebida
            last_update = results[-1]
            msg = last_update.get("message") or last_update.get("channel_post") or {}
            chat = msg.get("chat", {})
            chat_id = str(chat.get("id", ""))
            name    = chat.get("first_name") or chat.get("title") or "desconhecido"

            if not chat_id:
                self.after(0, lambda: self._fetch_done_error("Não foi possível extrair o Chat ID."))
                return

            self.after(0, lambda: self._fetch_done_ok(chat_id, name))

        threading.Thread(target=_do_fetch, daemon=True).start()

    def _fetch_done_ok(self, chat_id, name):
        if hasattr(self, "settings_entry_tg_chat") and self.settings_entry_tg_chat and self.settings_entry_tg_chat.winfo_exists():
            self.settings_entry_tg_chat.delete(0, "end")
            self.settings_entry_tg_chat.insert(0, chat_id)
        elif hasattr(self, "entry_tg_chat") and self.entry_tg_chat and self.entry_tg_chat.winfo_exists():
            self.entry_tg_chat.delete(0, "end")
            self.entry_tg_chat.insert(0, chat_id)
            
        self.lbl_tg_status.configure(
            text=f"✅ Chat ID de '{name}' preenchido!", text_color=ACCENT_GREEN)
        self.btn_fetch_chat_id.configure(state="normal", text="🔍 Buscar Chat ID")
        self._gui_setting_changed()

    def _fetch_done_error(self, msg):
        self.lbl_tg_status.configure(text=f"❌ {msg}", text_color=ACCENT_RED)
        self.btn_fetch_chat_id.configure(state="normal", text="🔍 Buscar Chat ID")

    def _tg_test_clicked(self):
        """Envia uma mensagem de teste para confirmar que Token e Chat ID estão corretos."""
        self._gui_setting_changed()  # garante que config está atualizado
        if not self.config.get("telegram_token", "").strip():
            self.lbl_tg_status.configure(text="⚠ Token vazio.", text_color=ACCENT_YELLOW)
            return
        if not self.config.get("telegram_chat_id", "").strip():
            self.lbl_tg_status.configure(text="⚠ Chat ID vazio. Use 'Buscar Chat ID' primeiro.", text_color=ACCENT_YELLOW)
            return

        self.lbl_tg_status.configure(text="Enviando mensagem de teste...", text_color="#94a3b8")

        import datetime
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_msg = (
            "✅ <b>Teste de Conexão</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🤖 <b>Deriv Clicker Bot</b>\n"
            f"⏱️ <b>Horário:</b> {ts}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<i>Conexão com Telegram configurada com sucesso!</i>"
        )

        # Usa callback para atualizar status após o envio
        cfg_copy = dict(self.config)
        cfg_copy["telegram_enabled"] = True  # força envio mesmo se desativado

        def _after_test(result_msg, ok):
            color = ACCENT_GREEN if ok else ACCENT_RED
            self.after(0, lambda: self.lbl_tg_status.configure(text=result_msg, text_color=color))

        import threading, urllib.request, urllib.parse, urllib.error, json
        def _do_test():
            token   = cfg_copy.get("telegram_token", "")
            chat_id = cfg_copy.get("telegram_chat_id", "")
            url     = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = urllib.parse.urlencode({
                "chat_id": chat_id, "text": test_msg, "parse_mode": "HTML"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            try:
                with urllib.request.urlopen(req, timeout=10):
                    _after_test("✅ Mensagem de teste enviada!", True)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                desc = json.loads(body).get("description", body) if body else str(e)
                _after_test(f"❌ Erro {e.code}: {desc}", False)
            except Exception as exc:
                _after_test(f"❌ {exc}", False)
        threading.Thread(target=_do_test, daemon=True).start()

    # --- CALLBACKS DO TRABALHADOR ---
    def update_clicks_metric(self, click_count):
        self.after(0, lambda: self._update_clicks_on_ui(click_count))

    def _update_clicks_on_ui(self, click_count):
        self.lbl_metric_clicks.configure(text=str(click_count))
        self._update_overlay_data()

    def update_wins_metric(self, win_count):
        self.after(0, lambda: self._update_wins_on_ui(win_count))

    def _update_wins_on_ui(self, win_count):
        self.lbl_metric_wins.configure(text=str(win_count))
        self._update_assertiveness_rate()
        
        # Streak tracker
        self.current_win_streak += 1
        self.current_loss_streak = 0
        if self.current_win_streak > self.max_win_streak:
            self.max_win_streak = self.current_win_streak
            
        self._update_overlay_data()

    def update_losses_metric(self, loss_count):
        self.after(0, lambda: self._update_losses_on_ui(loss_count))

    def _update_losses_on_ui(self, loss_count):
        self.lbl_metric_losses.configure(text=str(loss_count))
        self._update_assertiveness_rate()
        
        # Streak tracker
        self.current_loss_streak += 1
        self.current_win_streak = 0
        if self.current_loss_streak > self.max_loss_streak:
            self.max_loss_streak = self.current_loss_streak
            
        self._update_overlay_data()

    def _update_assertiveness_rate(self):
        try:
            wins = int(self.lbl_metric_wins.cget("text"))
            losses = int(self.lbl_metric_losses.cget("text"))
            total = wins + losses
            if total > 0:
                rate = (wins / total) * 100
                self.lbl_metric_rate.configure(text=f"{rate:.1f}%")
            else:
                self.lbl_metric_rate.configure(text="0.0%")
        except Exception:
            pass
            pass

    def update_next_click_metric(self, wait_seconds):
        if wait_seconds < 0:
            self.after(0, lambda: self._set_schedule_remaining(-wait_seconds))
        else:
            self.after(0, lambda: self._set_next_click_deadline(wait_seconds))

    def _set_next_click_deadline(self, wait_seconds):
        self.next_click_deadline = time.time() + wait_seconds

    def _set_schedule_remaining(self, remaining):
        self.remaining_schedule_time = remaining
        self.next_click_deadline = 0

    def bot_started_execution(self):
        self.after(0, self._handle_bot_started_execution)

    def _handle_bot_started_execution(self):
        self.lbl_status_value.configure(text="EXECUTANDO", text_color=ACCENT_GREEN)
        self.start_time = time.time()
        self.remaining_schedule_time = 0
        self._update_overlay_data()

    def log_message(self, message):
        # Permite chamar de threads
        self.after(0, lambda: self._write_log_to_console(message))

    def _write_log_to_console(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.configure(state="disabled")
        self.txt_log.see("end")

    # --- LOOPS DE ATUALIZACAO ---
    def update_gui_loop(self):
        # 1. Atualiza tempo de execucao
        if self.bot and self.bot.running:
            if self.lbl_status_value.cget("text") == "AGENDADO":
                rem = getattr(self, "remaining_schedule_time", 0)
                if rem > 0:
                    hours, remainder = divmod(int(rem), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    if hours > 0:
                        timer_str = f"Em {hours:02d}h {minutes:02d}m"
                    else:
                        timer_str = f"Em {minutes:02d}m {seconds:02d}s"
                    self.lbl_next_click.configure(text=timer_str, text_color=ACCENT_YELLOW)
                else:
                    self.lbl_next_click.configure(text="Iniciando...", text_color=ACCENT_GREEN)
                self.lbl_timer.configure(text="00:00:00")
            else:
                elapsed = time.time() - self.start_time
                hours, remainder = divmod(int(elapsed), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.lbl_timer.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                
                # 2. Atualiza contagem regressiva proximo clique
                if self.next_click_deadline > 0:
                    remaining = self.next_click_deadline - time.time()
                    if remaining > 0:
                        self.lbl_next_click.configure(text=f"{remaining:.1f}s", text_color=ACCENT_YELLOW)
                    else:
                        self.lbl_next_click.configure(text="Processando...", text_color=ACCENT_GREEN)
                else:
                    self.lbl_next_click.configure(text="Escaneando...", text_color=ACCENT_BLUE)
        else:
            self.lbl_next_click.configure(text="Inativo", text_color="gray")
            
        # Repassa alteracoes ao overlay em tempo real
        self._update_overlay_data()
        
        # Roda novamente em 100ms para manter contagem fluida
        self.after(100, self.update_gui_loop)

    def btn_select_region_clicked(self):
        # Minimiza a janela principal para não atrapalhar
        self.withdraw()
        self.after(300, self._launch_selector)
        
    def _launch_selector(self):
        try:
            from region_selector import RegionSelector
            selector = RegionSelector(self)
            coords = selector.get_region()
            
            if coords:
                # coords = (x, y, w, h)
                self.config["search_region"] = coords
                self.config["use_search_region"] = True
                self.check_use_region.select()
                self.lbl_region_coords.configure(text=f"{coords[0]},{coords[1]} ({coords[2]}x{coords[3]})")
                self.log_message(f"[Config] Região de busca definida: {coords}")
            else:
                self.log_message("[Config] Seleção de região cancelada.")
        except Exception as e:
            self.log_message(f"[Erro] Falha ao abrir seletor: {e}")
            messagebox.showerror("Erro", f"Não foi possível abrir o seletor: {e}")
        finally:
            # Restaura a janela
            self.deiconify()
            self._gui_setting_changed()

    def _finance_mode_changed(self, mode_name):
        if mode_name == "Meta de Lucro":
            self.frame_finance_free.pack_forget()
            self.frame_finance_target.pack(fill="x", padx=15, pady=(0, 10))
        else:
            self.frame_finance_target.pack_forget()
            self.frame_finance_free.pack(fill="x", padx=15, pady=(0, 10))
        self._gui_setting_changed()

    def update_finance_metric(self, current_profit, total_entries):
        self.after(0, lambda: self._update_finance_on_ui(current_profit, total_entries))

    def _update_finance_on_ui(self, current_profit, total_entries):
        finance_mode = self.config.get("finance_mode", "target")
        
        # Determina a cor com base no lucro
        color = ACCENT_GREEN if current_profit >= 0 else ACCENT_RED
        
        if finance_mode == "target":
            target = self.config.get("target_profit", 10.00)
            self.lbl_finance_title.configure(text="SALDO FINANCEIRO (META)")
            self.lbl_finance_value.configure(text=f"${current_profit:.2f} / ${target:.2f}", text_color=color)
            
            if target > 0:
                progress = max(0.0, min(1.0, current_profit / target))
            else:
                progress = 0.0
            self.progress_finance.set(progress)
        else:
            limit_entries = self.config.get("free_entries", 10)
            self.lbl_finance_title.configure(text="SALDO FINANCEIRO (ENTRADAS)")
            self.lbl_finance_value.configure(text=f"${current_profit:.2f} ({total_entries} / {limit_entries} Entr.)", text_color=color)
            
            if limit_entries > 0:
                progress = max(0.0, min(1.0, total_entries / limit_entries))
            else:
                progress = 0.0
            self.progress_finance.set(progress)
            
        self._update_overlay_data()

    def toggle_overlay(self):
        if not self.overlay or not self.overlay.winfo_exists():
            from floating_overlay import FloatingOverlay
            self.overlay = FloatingOverlay(self)
            self._update_overlay_data()
        
        if self.overlay.winfo_viewable():
            self.overlay.withdraw()
            self.btn_overlay.configure(fg_color="#475569")
        else:
            self.overlay.deiconify()
            self.overlay.lift()
            self.overlay.attributes("-topmost", True)
            self.btn_overlay.configure(fg_color=ACCENT_BLUE)

    def _update_overlay_data(self):
        if not self.overlay or not self.overlay.winfo_exists():
            return
            
        status = self.lbl_status_value.cget("text")
        
        try:
            clicks = int(self.lbl_metric_clicks.cget("text"))
        except ValueError:
            clicks = 0
            
        try:
            wins = int(self.lbl_metric_wins.cget("text"))
        except ValueError:
            wins = 0
            
        try:
            losses = int(self.lbl_metric_losses.cget("text"))
        except ValueError:
            losses = 0
            
        total = wins + losses
        rate = (wins / total * 100) if total > 0 else 0.0
        
        current_profit = getattr(self.bot, "current_profit", 0.0) if self.bot else 0.0
        target = self.config.get("target_profit", 10.00)
        fin_mode = self.config.get("finance_mode", "target")
        free_entries = self.config.get("free_entries", 10)
        
        timer_str = self.lbl_timer.cget("text")
        next_click_str = self.lbl_next_click.cget("text")
        
        win_streak = getattr(self, "max_win_streak", 0)
        loss_streak = getattr(self, "max_loss_streak", 0)
        
        self.overlay.update_data(
            status=status,
            clicks=clicks,
            wins=wins,
            losses=losses,
            rate=rate,
            win_streak=win_streak,
            loss_streak=loss_streak,
            current_profit=current_profit,
            target_profit=target,
            finance_mode=fin_mode,
            free_entries=free_entries,
            timer_str=timer_str,
            next_click_str=next_click_str
        )

    def _show_main_window(self):
        if hasattr(self, "splash") and self.splash.winfo_exists():
            self.splash.destroy()
        self.deiconify()
        self.lift()
        self.focus_force()

    def destroy(self):
        # Finaliza threads ao fechar a janela
        if self.bot:
            self.bot.stop_bot()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        super().destroy()
