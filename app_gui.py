import os
import time
import threading
import datetime
import subprocess
import sys
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

import config_manager
import telegram_sender
from bot_worker import BotWorker
from global_hotkey import GlobalHotkeyListener

# Define cores esteticas modernas
BG_DARK = "#05070c"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#f43f5e"
ACCENT_BLUE = "#38bdf8"
ACCENT_YELLOW = "#fbbf24"
CARD_BG = "#0f172a"

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

class ExecutionModeDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Modo de Execução")
        self.geometry("600x220")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.result = None # 'browser', 'derivclicker', 'stealth', 'ai_overlay', or None
        
        self.transient(parent)
        self.grab_set()
        
        # Centraliza a janela em relação ao pai
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w - 600) // 2
        y = parent_y + (parent_h - 220) // 2
        self.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(
            self, 
            text="Como deseja executar o robô?", 
            font=ctk.CTkFont(size=16, weight="bold"), 
            text_color="#ffffff"
        )
        lbl.pack(pady=(20, 10))
        
        desc = ctk.CTkLabel(
            self, 
            text="Selecione o modo de navegação ou operação para a Deriv:", 
            font=ctk.CTkFont(size=12), 
            text_color="gray"
        )
        desc.pack(pady=(0, 20))
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15)
        
        btn_browser = ctk.CTkButton(
            btn_frame, 
            text="🌐 NAVEGADOR", 
            fg_color=CARD_BG, 
            hover_color="#1e293b", 
            border_color="#334155",
            border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=130,
            height=40,
            command=self.select_browser
        )
        btn_browser.pack(side="left", padx=4, expand=True)
        
        btn_dc = ctk.CTkButton(
            btn_frame, 
            text="🤖 CLICKERBOT", 
            fg_color=ACCENT_GREEN, 
            hover_color="#059669", 
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=130,
            height=40,
            command=self.select_derivclicker
        )
        btn_dc.pack(side="left", padx=4, expand=True)
        
        btn_stealth = ctk.CTkButton(
            btn_frame, 
            text="🥷 MODO STEALTH", 
            fg_color="#7c3aed", 
            hover_color="#6d28d9", 
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=130,
            height=40,
            command=self.select_stealth
        )
        btn_stealth.pack(side="left", padx=4, expand=True)

        btn_ai = ctk.CTkButton(
            btn_frame, 
            text="🧠 MODO IA (API)", 
            fg_color="#0ea5e9", 
            hover_color="#0284c7", 
            corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=130,
            height=40,
            command=self.select_ai_overlay
        )
        btn_ai.pack(side="left", padx=4, expand=True)
        
        btn_cancel = ctk.CTkButton(
            self, 
            text="Cancelar", 
            fg_color="transparent", 
            hover_color="#1e293b", 
            text_color="gray", 
            width=100,
            height=30,
            command=self.cancel
        )
        btn_cancel.pack(pady=(20, 10))
        
        parent.wait_window(self)
    def select_browser(self):
        self.result = "browser"
        self.destroy()
        
    def select_derivclicker(self):
        self.result = "derivclicker"
        self.destroy()
        
    def select_stealth(self):
        self.result = "stealth"
        self.destroy()

    def select_ai_overlay(self):
        self.result = "ai_overlay"
        self.destroy()
        
    def cancel(self):
        self.result = None
        self.destroy()

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
        self.webview_proc = None
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
        
        # Inicia o listener de comandos do Telegram em segundo plano
        self.tg_listener_running = True
        self.tg_listener_thread = threading.Thread(target=self._telegram_listener_loop, daemon=True)
        self.tg_listener_thread.start()
        
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
        self.configure(fg_color="#090d16")
        
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
        win2_path = self.config.get("image_win2_path", "capturas/win2.png")
        loss_path = self.config.get("image_loss_path", "capturas/loss.png")
        number_path = self.config.get("image_number_path", "capturas/number.png")
        
        btn_exists = os.path.exists(btn_path)
        win_exists = os.path.exists(win_path)
        win2_exists = os.path.exists(win2_path)
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
            
        if win2_exists:
            self.lbl_status_win2_img.configure(text="win2.png: OK", text_color=ACCENT_GREEN)
        else:
            self.lbl_status_win2_img.configure(text="win2.png: Opcional (Ausente)", text_color=ACCENT_YELLOW)

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
        
        # Modo Adaptativo
        self.entry_adaptive_obs.delete(0, "end")
        self.entry_adaptive_obs.insert(0, str(self.config.get("adaptive_observation_minutes", 30)))
        
        self.entry_adaptive_events.delete(0, "end")
        self.entry_adaptive_events.insert(0, str(self.config.get("adaptive_relearn_events", 100)))
        
        self.entry_adaptive_rep_min.delete(0, "end")
        self.entry_adaptive_rep_min.insert(0, str(self.config.get("adaptive_relearn_minutes", 30)))
        
        self.entry_adaptive_losses.delete(0, "end")
        self.entry_adaptive_losses.insert(0, str(self.config.get("adaptive_relearn_losses", 3)))
        
        # Modo IA
        self.entry_ai_threshold.delete(0, "end")
        self.entry_ai_threshold.insert(0, str(self.config.get("ai_threshold", 75.0)))
        
        self.entry_ai_lr.delete(0, "end")
        self.entry_ai_lr.insert(0, str(self.config.get("ai_learning_rate", 0.01)))
        
        self.entry_ai_lookahead.delete(0, "end")
        self.entry_ai_lookahead.insert(0, str(self.config.get("ai_lookahead_ticks", 3)))

        self.entry_ai_cooldown.delete(0, "end")
        self.entry_ai_cooldown.insert(0, str(self.config.get("ai_entry_cooldown", 10)))

        self.entry_ai_min_ticks.delete(0, "end")
        self.entry_ai_min_ticks.insert(0, str(self.config.get("ai_min_ticks_safe", 5)))

        self.entry_ai_min_samples.delete(0, "end")
        self.entry_ai_min_samples.insert(0, str(self.config.get("ai_min_samples_start", 500)))

        self.entry_ai_win_value.delete(0, "end")
        self.entry_ai_win_value.insert(0, f"{self.config.get('win_value', 1.50):.2f}")

        self.entry_ai_contract_take_profit.delete(0, "end")
        self.entry_ai_contract_take_profit.insert(0, f"{self.config.get('ai_contract_take_profit', 5.0):.2f}")

        growth_rate = self.config.get("deriv_growth_rate", 0.01)
        growth_percent_str = f"{int(round(growth_rate * 100))}%"
        if growth_percent_str in ["1%", "2%", "3%", "4%", "5%"]:
            self.combo_ai_growth_rate.set(growth_percent_str)
        else:
            self.combo_ai_growth_rate.set("1%")
        
        # Atualiza a engine de IA na interface
        import ai_model
        if ai_model.HAS_TORCH:
            import torch
            if torch.cuda.is_available() and self.config.get("ai_use_gpu", True):
                self.lbl_ai_engine.configure(text="GPU (PyTorch)", text_color=ACCENT_GREEN)
                self.btn_install_torch.configure(text="GPU Ativa", state="disabled", fg_color="#10b981")
            else:
                self.lbl_ai_engine.configure(text="CPU (PyTorch)", text_color="#f59e0b")
                self.btn_install_torch.configure(text="GPU Disponível", state="disabled", fg_color="#f59e0b")
        else:
            self.lbl_ai_engine.configure(text="CPU (NumPy)", text_color="#f59e0b")
            self.btn_install_torch.configure(text="Instalar PyTorch (GPU)", state="normal", fg_color=ACCENT_BLUE)
        
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

        # Entradas por Ciclo
        cycle_enabled = self.config.get("cycle_enabled", False)
        if cycle_enabled:
            self.switch_cycle.select()
        else:
            self.switch_cycle.deselect()
        self.entry_cycle_max_entries.delete(0, "end")
        self.entry_cycle_max_entries.insert(0, str(self.config.get("cycle_max_entries", 4)))
        self.entry_cycle_cooldown.delete(0, "end")
        self.entry_cycle_cooldown.insert(0, str(self.config.get("cycle_cooldown_minutes", 60)))

        # Deriv API Settings
        deriv_api_token = self.config.get("deriv_api_token", "")
        if hasattr(self, "settings_entry_api_token") and self.settings_entry_api_token and self.settings_entry_api_token.winfo_exists():
            self.settings_entry_api_token.delete(0, "end")
            self.settings_entry_api_token.insert(0, deriv_api_token)
            
        deriv_app_id = self.config.get("deriv_app_id", "1098")
        if hasattr(self, "settings_entry_api_appid") and self.settings_entry_api_appid and self.settings_entry_api_appid.winfo_exists():
            self.settings_entry_api_appid.delete(0, "end")
            self.settings_entry_api_appid.insert(0, deriv_app_id)
            
        deriv_symbol = self.config.get("deriv_symbol", "R_100")
        if hasattr(self, "settings_combo_api_symbol") and self.settings_combo_api_symbol and self.settings_combo_api_symbol.winfo_exists():
            self.settings_combo_api_symbol.set(deriv_symbol)
            
        deriv_growth = self.config.get("deriv_growth_rate", 0.01) * 100.0
        if hasattr(self, "settings_entry_api_growth") and self.settings_entry_api_growth and self.settings_entry_api_growth.winfo_exists():
            self.settings_entry_api_growth.delete(0, "end")
            self.settings_entry_api_growth.insert(0, f"{deriv_growth:.1f}")
            
        deriv_acc_type = self.config.get("deriv_account_type", "demo").title()
        if hasattr(self, "settings_combo_api_account_type") and self.settings_combo_api_account_type and self.settings_combo_api_account_type.winfo_exists():
            self.settings_combo_api_account_type.set(deriv_acc_type)
            
        deriv_use_api = self.config.get("deriv_use_api_trading", False)
        if hasattr(self, "settings_switch_use_api") and self.settings_switch_use_api and self.settings_switch_use_api.winfo_exists():
            if deriv_use_api:
                self.settings_switch_use_api.select()
            else:
                self.settings_switch_use_api.deselect()

        if hasattr(self, "settings_switch_scan_market") and self.settings_switch_scan_market and self.settings_switch_scan_market.winfo_exists():
            deriv_scan_market = self.config.get("deriv_scan_market", False)
            if deriv_scan_market:
                self.settings_switch_scan_market.select()
            else:
                self.settings_switch_scan_market.deselect()

        # Deriv Contract Mode and Rise/Fall options
        deriv_contract_mode = self.config.get("deriv_contract_mode", "accumulator")
        if hasattr(self, "settings_combo_contract_mode") and self.settings_combo_contract_mode and self.settings_combo_contract_mode.winfo_exists():
            if deriv_contract_mode == "rise_fall":
                self.settings_combo_contract_mode.set("Rise/Fall")
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack(fill="x", padx=15, pady=4)
            elif deriv_contract_mode == "matches":
                self.settings_combo_contract_mode.set("Matches")
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack_forget()
            elif deriv_contract_mode == "differs":
                self.settings_combo_contract_mode.set("Differs")
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack_forget()
            else:
                self.settings_combo_contract_mode.set("Accumulator")
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack_forget()

        deriv_rf_dur = self.config.get("deriv_rf_duration_value", 5)
        if hasattr(self, "settings_entry_rf_duration") and self.settings_entry_rf_duration and self.settings_entry_rf_duration.winfo_exists():
            self.settings_entry_rf_duration.delete(0, "end")
            self.settings_entry_rf_duration.insert(0, str(deriv_rf_dur))

        deriv_rf_unit = self.config.get("deriv_rf_duration_unit", "t")
        if hasattr(self, "settings_combo_rf_unit") and self.settings_combo_rf_unit and self.settings_combo_rf_unit.winfo_exists():
            unit_label = "Ticks" if deriv_rf_unit == "t" else ("Segundos" if deriv_rf_unit == "s" else "Minutos")
            self.settings_combo_rf_unit.set(unit_label)

        deriv_rf_auto = self.config.get("deriv_rf_auto_duration", True)
        if hasattr(self, "settings_switch_rf_auto") and self.settings_switch_rf_auto and self.settings_switch_rf_auto.winfo_exists():
            if deriv_rf_auto:
                self.settings_switch_rf_auto.select()
            else:
                self.settings_switch_rf_auto.deselect()

        # Main AI contract mode
        if hasattr(self, "combo_ai_contract_mode") and self.combo_ai_contract_mode.winfo_exists():
            if deriv_contract_mode == "rise_fall":
                self.combo_ai_contract_mode.set("Rise/Fall")
            elif deriv_contract_mode == "matches":
                self.combo_ai_contract_mode.set("Matches")
            elif deriv_contract_mode == "differs":
                self.combo_ai_contract_mode.set("Differs")
            else:
                self.combo_ai_contract_mode.set("Accumulator")

        # Llama integration options
        llama_enabled = self.config.get("llama_enabled", False)
        if hasattr(self, "settings_switch_llama") and self.settings_switch_llama and self.settings_switch_llama.winfo_exists():
            if llama_enabled:
                self.settings_switch_llama.select()
            else:
                self.settings_switch_llama.deselect()

        llama_prov = self.config.get("llama_provider", "ollama")
        if hasattr(self, "settings_combo_llama_provider") and self.settings_combo_llama_provider and self.settings_combo_llama_provider.winfo_exists():
            if llama_prov == "local":
                self.settings_combo_llama_provider.set("Local Embutido")
                if hasattr(self, "settings_entry_llama_url") and self.settings_entry_llama_url.winfo_exists():
                    self.settings_entry_llama_url.configure(state="disabled")
            else:
                self.settings_combo_llama_provider.set("Ollama (API)")
                if hasattr(self, "settings_entry_llama_url") and self.settings_entry_llama_url.winfo_exists():
                    self.settings_entry_llama_url.configure(state="normal")

        llama_url = self.config.get("llama_url", "http://localhost:11434/api/generate")
        if hasattr(self, "settings_entry_llama_url") and self.settings_entry_llama_url and self.settings_entry_llama_url.winfo_exists():
            # If enabled/disabled state is not overridden by Local Embutido, it will write
            current_state = self.settings_entry_llama_url.cget("state")
            if current_state == "disabled":
                self.settings_entry_llama_url.configure(state="normal")
                self.settings_entry_llama_url.delete(0, "end")
                self.settings_entry_llama_url.insert(0, llama_url)
                self.settings_entry_llama_url.configure(state="disabled")
            else:
                self.settings_entry_llama_url.delete(0, "end")
                self.settings_entry_llama_url.insert(0, llama_url)

        llama_model = self.config.get("llama_model", "llama3")
        if hasattr(self, "settings_combo_llama_model") and self.settings_combo_llama_model and self.settings_combo_llama_model.winfo_exists():
            avail_vals = list(self.settings_combo_llama_model.cget("values"))
            if llama_model not in avail_vals:
                avail_vals.append(llama_model)
                self.settings_combo_llama_model.configure(values=avail_vals)
            self.settings_combo_llama_model.set(llama_model)

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
            "linered": "Número Vermelho",
            "adaptive": "Modo IA",
            "ai": "Modo IA"
        }
        return mapping.get(key, "Intervalo Fixo")

    def _mode_key_from_label(self, label):
        mapping = {
            "Intervalo Fixo": "fixed",
            "Intervalo Aleatório": "random",
            "Sequência de Cliques": "sequence",
            "Linha Vermelha": "linered",
            "Número Vermelho": "linered",
            "Modo Inteligente": "ai",
            "Modo IA": "ai"
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
        
        self.lbl_status_win2_img = ctk.CTkLabel(img_check_container.content_frame, text="win2.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_win2_img.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_status_loss_img = ctk.CTkLabel(img_check_container.content_frame, text="loss.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_loss_img.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_status_number_img = ctk.CTkLabel(img_check_container.content_frame, text="number.png: Verificando...", font=ctk.CTkFont(size=11))
        self.lbl_status_number_img.pack(anchor="w", padx=15, pady=2)
        
        # Botoes de Acao Principais
        self.btn_start = ctk.CTkButton(
            left_frame, 
            text="🚀  INICIAR ROBÔ", 
            fg_color=ACCENT_GREEN, 
            hover_color="#059669", 
            font=ctk.CTkFont(size=15, weight="bold"), 
            height=46, 
            corner_radius=10,
            command=self.btn_start_clicked
        )
        self.btn_start.pack(fill="x", padx=15, pady=(20, 10))
        
        self.btn_stop = ctk.CTkButton(
            left_frame, 
            text="🛑  PARAR ROBÔ (F8)", 
            fg_color=ACCENT_RED, 
            hover_color="#e11d48", 
            font=ctk.CTkFont(size=15, weight="bold"), 
            height=46, 
            corner_radius=10,
            command=self.btn_stop_clicked, 
            state="disabled"
        )
        self.btn_stop.pack(fill="x", padx=15, pady=0)
        
        self.btn_overlay = ctk.CTkButton(
            left_frame, 
            text="🎛️  MONITOR SOBREPOSTO (O)", 
            fg_color=CARD_BG, 
            hover_color="#1e293b", 
            border_color="#334155",
            border_width=1,
            font=ctk.CTkFont(size=13, weight="bold"), 
            height=38, 
            corner_radius=10,
            command=self.toggle_overlay
        )
        self.btn_overlay.pack(fill="x", padx=15, pady=(15, 0))
        
        self.btn_settings = ctk.CTkButton(
            left_frame, 
            text="⚙️  CONFIGURAÇÕES DE ACESSO", 
            fg_color=CARD_BG, 
            hover_color="#1e293b", 
            border_color="#334155",
            border_width=1,
            font=ctk.CTkFont(size=13, weight="bold"), 
            height=38, 
            corner_radius=10,
            command=self.open_settings_popup
        )
        self.btn_settings.pack(fill="x", padx=15, pady=(10, 0))

    def _build_right_panel(self):
        # Cria a Tabview principal no lado direito
        self.right_tabview = ctk.CTkTabview(
            self,
            fg_color="transparent",
            segmented_button_selected_color=ACCENT_BLUE,
            segmented_button_selected_hover_color="#2563eb",
            segmented_button_unselected_color="#1e293b",
            segmented_button_unselected_hover_color="#334155",
            text_color="#ffffff"
        )
        self.right_tabview.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Cria as abas
        self.right_tabview.add("Configurações & Painel")
        self.right_tabview.add("Dashboard Estatístico")
        
        # Painel direito — scrollável para não cortar conteúdo (agora dentro da aba de configurações)
        right_frame = ctk.CTkScrollableFrame(
            self.right_tabview.tab("Configurações & Painel"), fg_color="transparent",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
        )
        right_frame.pack(fill="both", expand=True)

        # Titulo da Secao de Configs
        lbl_configs = ctk.CTkLabel(right_frame, text="Painel de Controle & Configurações", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_configs.pack(anchor="w", pady=(10, 15))
        
        # Seletor de Modo (Segmented Button para layout moderno)
        self.seg_mode = ctk.CTkSegmentedButton(right_frame, values=["Intervalo Fixo", "Intervalo Aleatório", "Sequência de Cliques", "Número Vermelho", "Modo IA"], command=self._mode_selection_changed)
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

        # --- SUBFRAME: MODO ADAPTATIVO (INTELIGENTE) ---
        self.frame_adaptive = ctk.CTkFrame(self.mode_container.content_frame, fg_color="transparent")
        lbl_adaptive = ctk.CTkLabel(self.frame_adaptive, text="Configurações do Modo Inteligente", font=ctk.CTkFont(weight="bold"))
        lbl_adaptive.pack(anchor="w", padx=15, pady=(10, 5))
        
        adaptive_info = (
            "O bot entra em fase de observação inicial colhendo dados de comportamento\n"
            "do Accumulator em tempo real, gerando estratégias dinâmicas com base na confiança."
        )
        ctk.CTkLabel(self.frame_adaptive, text=adaptive_info,
                     font=ctk.CTkFont(size=11), text_color="#94a3b8",
                     justify="left").pack(anchor="w", padx=15, pady=(0, 10))
                     
        row_adaptive_inputs = ctk.CTkFrame(self.frame_adaptive, fg_color="transparent")
        row_adaptive_inputs.pack(fill="x", padx=15, pady=5)
        
        # Tempo observação
        col_obs = ctk.CTkFrame(row_adaptive_inputs, fg_color="transparent")
        col_obs.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_obs, text="Obs. Inicial (min)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_adaptive_obs = ctk.CTkEntry(col_obs, height=28, width=70)
        self.entry_adaptive_obs.pack(fill="x", pady=2)
        self.entry_adaptive_obs.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        # Reaprender a cada X eventos
        col_events = ctk.CTkFrame(row_adaptive_inputs, fg_color="transparent")
        col_events.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_events, text="Reaprender (Eventos)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_adaptive_events = ctk.CTkEntry(col_events, height=28, width=70)
        self.entry_adaptive_events.pack(fill="x", pady=2)
        self.entry_adaptive_events.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        # Reaprender a cada X minutos
        col_rep_min = ctk.CTkFrame(row_adaptive_inputs, fg_color="transparent")
        col_rep_min.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_rep_min, text="Reaprender (min)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_adaptive_rep_min = ctk.CTkEntry(col_rep_min, height=28, width=70)
        self.entry_adaptive_rep_min.pack(fill="x", pady=2)
        self.entry_adaptive_rep_min.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        # Reaprender apos X losses
        col_losses = ctk.CTkFrame(row_adaptive_inputs, fg_color="transparent")
        col_losses.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_losses, text="Reaprender (Losses)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_adaptive_losses = ctk.CTkEntry(col_losses, height=28, width=70)
        self.entry_adaptive_losses.pack(fill="x", pady=2)
        self.entry_adaptive_losses.bind("<KeyRelease>", lambda e: self._gui_setting_changed())

        # --- SUBFRAME: MODO IA (NEURAL NETWORK) ---
        self.frame_ai = ctk.CTkFrame(self.mode_container.content_frame, fg_color="transparent")
        lbl_ai = ctk.CTkLabel(self.frame_ai, text="Configurações do Modo IA (Neural Network)", font=ctk.CTkFont(weight="bold"))
        lbl_ai.pack(anchor="w", padx=15, pady=(10, 5))
        
        ai_info = (
            "Utiliza uma Rede Neural Profunda com Online Learning em tempo real para prever a\n"
            "probabilidade de vitória. Auto-supervisionado com detecção de volatilidade do Accumulator."
        )
        ctk.CTkLabel(self.frame_ai, text=ai_info,
                     font=ctk.CTkFont(size=11), text_color="#94a3b8",
                     justify="left").pack(anchor="w", padx=15, pady=(0, 10))
                     
        row_ai_inputs = ctk.CTkFrame(self.frame_ai, fg_color="transparent")
        row_ai_inputs.pack(fill="x", padx=15, pady=5)
        
        # Limiar de Confiança (Threshold)
        col_thresh = ctk.CTkFrame(row_ai_inputs, fg_color="transparent")
        col_thresh.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_thresh, text="Limiar Confiança (%)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_threshold = ctk.CTkEntry(col_thresh, height=28, width=70)
        self.entry_ai_threshold.pack(fill="x", pady=2)
        self.entry_ai_threshold.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        # Learning Rate
        col_lr = ctk.CTkFrame(row_ai_inputs, fg_color="transparent")
        col_lr.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_lr, text="Learning Rate", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_lr = ctk.CTkEntry(col_lr, height=28, width=70)
        self.entry_ai_lr.pack(fill="x", pady=2)
        self.entry_ai_lr.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        # Lookahead Ticks
        col_look = ctk.CTkFrame(row_ai_inputs, fg_color="transparent")
        col_look.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_look, text="Ticks de Validação (K)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_lookahead = ctk.CTkEntry(col_look, height=28, width=70)
        self.entry_ai_lookahead.pack(fill="x", pady=2)
        self.entry_ai_lookahead.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        # GPU / PyTorch status
        col_gpu = ctk.CTkFrame(row_ai_inputs, fg_color="transparent")
        col_gpu.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_gpu, text="Aceleração GPU", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.btn_install_torch = ctk.CTkButton(col_gpu, text="Ativar GPU", height=28, width=80, fg_color=ACCENT_BLUE, text_color="white", command=self._install_torch_async)
        self.btn_install_torch.pack(fill="x", pady=2)

        # Segunda linha de inputs da IA: parâmetros de entrada inteligente
        row_ai_inputs2 = ctk.CTkFrame(self.frame_ai, fg_color="transparent")
        row_ai_inputs2.pack(fill="x", padx=15, pady=5)

        col_cooldown = ctk.CTkFrame(row_ai_inputs2, fg_color="transparent")
        col_cooldown.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_cooldown, text="Cooldown pós-entrada (ticks)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_cooldown = ctk.CTkEntry(col_cooldown, height=28, width=70, placeholder_text="10")
        self.entry_ai_cooldown.pack(fill="x", pady=2)
        self.entry_ai_cooldown.bind("<KeyRelease>", lambda e: self._gui_setting_changed())

        col_min_safe = ctk.CTkFrame(row_ai_inputs2, fg_color="transparent")
        col_min_safe.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_min_safe, text="Ticks seguros mínimos", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_min_ticks = ctk.CTkEntry(col_min_safe, height=28, width=70, placeholder_text="5")
        self.entry_ai_min_ticks.pack(fill="x", pady=2)
        self.entry_ai_min_ticks.bind("<KeyRelease>", lambda e: self._gui_setting_changed())

        col_min_samples = ctk.CTkFrame(row_ai_inputs2, fg_color="transparent")
        col_min_samples.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_min_samples, text="Amostras Mínimas", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_min_samples = ctk.CTkEntry(col_min_samples, height=28, width=70, placeholder_text="500")
        self.entry_ai_min_samples.pack(fill="x", pady=2)
        self.entry_ai_min_samples.bind("<KeyRelease>", lambda e: self._gui_setting_changed())

        # Terceira linha de inputs da IA: valor da entrada, meta do contrato e multiplicador
        row_ai_inputs3 = ctk.CTkFrame(self.frame_ai, fg_color="transparent")
        row_ai_inputs3.pack(fill="x", padx=15, pady=5)

        col_ai_stake = ctk.CTkFrame(row_ai_inputs3, fg_color="transparent")
        col_ai_stake.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_ai_stake, text="Valor Entrada (Stake $)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_win_value = ctk.CTkEntry(col_ai_stake, height=28, width=70)
        self.entry_ai_win_value.pack(fill="x", pady=2)
        self.entry_ai_win_value.bind("<KeyRelease>", lambda e: self._gui_setting_changed())

        col_ai_tp = ctk.CTkFrame(row_ai_inputs3, fg_color="transparent")
        col_ai_tp.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_ai_tp, text="Meta Lucro Contrato ($)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_ai_contract_take_profit = ctk.CTkEntry(col_ai_tp, height=28, width=70)
        self.entry_ai_contract_take_profit.pack(fill="x", pady=2)
        self.entry_ai_contract_take_profit.bind("<KeyRelease>", lambda e: self._gui_setting_changed())

        col_ai_growth = ctk.CTkFrame(row_ai_inputs3, fg_color="transparent")
        col_ai_growth.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_ai_growth, text="Multiplicador (%)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.combo_ai_growth_rate = ctk.CTkComboBox(col_ai_growth, values=["1%", "2%", "3%", "4%", "5%"], height=28, command=lambda e: self._gui_setting_changed())
        self.combo_ai_growth_rate.pack(fill="x", pady=2)

        col_ai_contract_mode = ctk.CTkFrame(row_ai_inputs3, fg_color="transparent")
        col_ai_contract_mode.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_ai_contract_mode, text="Tipo de Contrato", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.combo_ai_contract_mode = ctk.CTkComboBox(col_ai_contract_mode, values=["Accumulator", "Rise/Fall", "Matches", "Differs"], height=28, command=lambda e: self._on_main_contract_mode_changed())
        self.combo_ai_contract_mode.pack(fill="x", pady=2)

        # --- PAINEL DE MÉTRICAS DA IA EM TEMPO REAL ---
        self.frame_ai_metrics = ctk.CTkFrame(self.frame_ai, fg_color="#1e293b", border_width=1, border_color="#334155")
        self.frame_ai_metrics.pack(fill="x", padx=15, pady=(10, 5))
        
        row_metrics = ctk.CTkFrame(self.frame_ai_metrics, fg_color="transparent")
        row_metrics.pack(fill="x", padx=10, pady=8)
        
        # Métrica Loss
        col_m_loss = ctk.CTkFrame(row_metrics, fg_color="transparent")
        col_m_loss.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_m_loss, text="Modelo Loss", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack()
        self.lbl_ai_loss = ctk.CTkLabel(col_m_loss, text="0.0000", font=ctk.CTkFont(size=14, weight="bold", family="Consolas"), text_color=ACCENT_BLUE)
        self.lbl_ai_loss.pack()
        
        # Métrica Acurácia
        col_m_acc = ctk.CTkFrame(row_metrics, fg_color="transparent")
        col_m_acc.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_m_acc, text="Acurácia", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack()
        self.lbl_ai_accuracy = ctk.CTkLabel(col_m_acc, text="0.0%", font=ctk.CTkFont(size=14, weight="bold", family="Consolas"), text_color=ACCENT_GREEN)
        self.lbl_ai_accuracy.pack()
        
        # Métrica Dataset
        col_m_mem = ctk.CTkFrame(row_metrics, fg_color="transparent")
        col_m_mem.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_m_mem, text="Amostras", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack()
        self.lbl_ai_memory = ctk.CTkLabel(col_m_mem, text="0", font=ctk.CTkFont(size=14, weight="bold", family="Consolas"), text_color="white")
        self.lbl_ai_memory.pack()
        
        # Métrica Engine
        col_m_eng = ctk.CTkFrame(row_metrics, fg_color="transparent")
        col_m_eng.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_m_eng, text="Hardware", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack()
        self.lbl_ai_engine = ctk.CTkLabel(col_m_eng, text="CPU (NumPy)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f59e0b")
        self.lbl_ai_engine.pack()

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

        # --- NOVO: CONTAINER DE ENTRADAS POR CICLO (Recolhível) ---
        self.cycle_frame = CollapsibleFrame(right_frame, title="Entradas por Ciclo", start_collapsed=True)
        self.cycle_frame.pack(fill="x", pady=(0, 15))
        
        row_cycle = ctk.CTkFrame(self.cycle_frame.content_frame, fg_color="transparent")
        row_cycle.pack(fill="x", padx=15, pady=10)
        
        self.switch_cycle = ctk.CTkSwitch(row_cycle, text="Ativar Ciclos", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.switch_cycle.pack(side="left", padx=(0, 20))
        
        # Entradas por Ciclo
        col_cycle_entries = ctk.CTkFrame(row_cycle, fg_color="transparent")
        col_cycle_entries.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_cycle_entries, text="Entradas/Ciclo", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_cycle_max_entries = ctk.CTkEntry(col_cycle_entries, height=28)
        self.entry_cycle_max_entries.pack(fill="x", pady=2)
        self.entry_cycle_max_entries.bind("<KeyRelease>", self._gui_setting_changed)
        
        # Pausa por Ciclo (minutos)
        col_cycle_cooldown = ctk.CTkFrame(row_cycle, fg_color="transparent")
        col_cycle_cooldown.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(col_cycle_cooldown, text="Pausa (minutos)", font=ctk.CTkFont(size=11)).pack(anchor="w")
        self.entry_cycle_cooldown = ctk.CTkEntry(col_cycle_cooldown, height=28)
        self.entry_cycle_cooldown.pack(fill="x", pady=2)
        self.entry_cycle_cooldown.bind("<KeyRelease>", self._gui_setting_changed)

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
        
        # Constrói a aba do dashboard
        self._build_dashboard_tab()

    def _build_dashboard_tab(self):
        tab_dash = self.right_tabview.tab("Dashboard Estatístico")
        
        # Frame scrollable para o dashboard
        dash_frame = ctk.CTkScrollableFrame(
            tab_dash, fg_color="transparent",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
        )
        dash_frame.pack(fill="both", expand=True)
        
        # Titulo da Aba
        lbl_dash_title = ctk.CTkLabel(dash_frame, text="Dashboard Estatístico Avançado", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_dash_title.pack(anchor="w", pady=(10, 15))
        
        # Card do Gráfico de Lucros
        self.chart_card = ctk.CTkFrame(dash_frame, fg_color=CARD_BG, border_color="#334155", border_width=1)
        self.chart_card.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.chart_card, text="CURVA DE LUCRO DAS ÚLTIMAS 30 OPERAÇÕES", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 5))
        
        self.chart_canvas = ctk.CTkCanvas(self.chart_card, bg="#0b0f19", highlightthickness=0, height=130)
        self.chart_canvas.pack(fill="x", padx=15, pady=(0, 15))
        self.chart_canvas.bind("<Configure>", lambda e: self.draw_profit_chart())
        
        # Container de duas colunas usando Grid
        grid_container = ctk.CTkFrame(dash_frame, fg_color="transparent")
        grid_container.pack(fill="x", expand=True, pady=(0, 15))
        grid_container.grid_columnconfigure(0, weight=1, minsize=260)
        grid_container.grid_columnconfigure(1, weight=1, minsize=260)
        
        # --- COLUNA 1: METRICAS E CONVERSOR ---
        col1 = ctk.CTkFrame(grid_container, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Card: Streak de Wins Consecutivos
        card_streak_wins = ctk.CTkFrame(col1, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_streak_wins.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card_streak_wins, text="SEQUÊNCIA DIÁRIA DE WINS", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 2))
        self.lbl_streak_wins_val = ctk.CTkLabel(card_streak_wins, text="0 dias (Recorde: 0)", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_GREEN)
        self.lbl_streak_wins_val.pack(pady=(0, 10))
        
        # Card: Streak de Metas Consecutivas
        card_streak_target = ctk.CTkFrame(col1, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_streak_target.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card_streak_target, text="METAS DIÁRIAS CONSECUTIVAS", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 2))
        self.lbl_streak_target_val = ctk.CTkLabel(card_streak_target, text="0 dias (Recorde: 0)", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_streak_target_val.pack(pady=(0, 10))
        
        # Card: Fim do Mês
        card_end_month = ctk.CTkFrame(col1, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_end_month.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card_end_month, text="TEMPO RESTANTE DO MÊS", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 2))
        self.lbl_end_month_val = ctk.CTkLabel(card_end_month, text="-- dias, --h --m", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_end_month_val.pack(pady=(0, 10))
        
        # Card: Conversor USD -> BRL
        card_converter = ctk.CTkFrame(col1, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_converter.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card_converter, text="CONVERSOR DE COTAÇÃO (USD/BRL)", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 5))
        
        # USD input
        row_usd = ctk.CTkFrame(card_converter, fg_color="transparent")
        row_usd.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(row_usd, text="USD ($):", font=ctk.CTkFont(size=11), width=65, anchor="w").pack(side="left")
        self.entry_conv_usd = ctk.CTkEntry(row_usd, height=24, font=ctk.CTkFont(size=11))
        self.entry_conv_usd.pack(side="right", fill="x", expand=True)
        self.entry_conv_usd.insert(0, "1.00")
        
        # BRL output/input
        row_brl = ctk.CTkFrame(card_converter, fg_color="transparent")
        row_brl.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(row_brl, text="BRL (R$):", font=ctk.CTkFont(size=11), width=65, anchor="w").pack(side="left")
        self.entry_conv_brl = ctk.CTkEntry(row_brl, height=24, font=ctk.CTkFont(size=11))
        self.entry_conv_brl.pack(side="right", fill="x", expand=True)
        
        # Cotação info e botão de atualização
        self.usd_rate = 5.20 # default rate
        row_rate_info = ctk.CTkFrame(card_converter, fg_color="transparent")
        row_rate_info.pack(fill="x", padx=15, pady=(5, 10))
        self.lbl_rate_info = ctk.CTkLabel(row_rate_info, text="Taxa: R$ 5.20", font=ctk.CTkFont(size=9), text_color="gray")
        self.lbl_rate_info.pack(side="left")
        btn_update_rate = ctk.CTkButton(row_rate_info, text="Atualizar", width=60, height=18, font=ctk.CTkFont(size=9), fg_color="#334155", hover_color="#475569", command=self.fetch_usd_rate)
        btn_update_rate.pack(side="right")
        
        # Bind bi-direcional nos conversores
        self.entry_conv_usd.bind("<KeyRelease>", self._on_usd_changed)
        self.entry_conv_brl.bind("<KeyRelease>", self._on_brl_changed)
        
        # --- COLUNA 2: ESTATISTICAS HORARIAS E HISTORICO ---
        col2 = ctk.CTkFrame(grid_container, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        # Card: Horário mais operado
        card_peak_hour = ctk.CTkFrame(col2, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_peak_hour.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card_peak_hour, text="HORÁRIO COM MAIS OPERAÇÕES", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 2))
        self.lbl_peak_hour_val = ctk.CTkLabel(card_peak_hour, text="Nenhum registro", font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffffff")
        self.lbl_peak_hour_val.pack(pady=(0, 10))
        
        # Card: Horário mais assertivo (Wins sem Loss)
        card_assertive_hour = ctk.CTkFrame(col2, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_assertive_hour.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card_assertive_hour, text="PERÍODO MAIS ASSERTIVO", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 2))
        self.lbl_assertive_hour_val = ctk.CTkLabel(card_assertive_hour, text="Nenhum registro", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_GREEN)
        self.lbl_assertive_hour_val.pack(pady=(0, 10))
        
        # Card: Histórico de Operações Recentes
        card_history = ctk.CTkFrame(col2, fg_color=CARD_BG, border_color="#334155", border_width=1)
        card_history.pack(fill="both", expand=True, pady=(0, 10))
        ctk.CTkLabel(card_history, text="HISTÓRICO RECENTE (ÚLTIMAS 50)", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 5))
        
        self.history_list_frame = ctk.CTkScrollableFrame(card_history, fg_color="#000000", height=180, border_color="#334155", border_width=1)
        self.history_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Inicializa cotação em tempo real e atualiza dados do dashboard
        self.fetch_usd_rate()
        self.update_dashboard_stats()

    def _on_usd_changed(self, event):
        try:
            val_str = self.entry_conv_usd.get().replace(",", ".")
            if not val_str:
                self.entry_conv_brl.delete(0, "end")
                return
            val_usd = float(val_str)
            val_brl = val_usd * self.usd_rate
            self.entry_conv_brl.delete(0, "end")
            self.entry_conv_brl.insert(0, f"{val_brl:.2f}")
        except ValueError:
            pass

    def _on_brl_changed(self, event):
        try:
            val_str = self.entry_conv_brl.get().replace(",", ".")
            if not val_str:
                self.entry_conv_usd.delete(0, "end")
                return
            val_brl = float(val_str)
            val_usd = val_brl / self.usd_rate
            self.entry_conv_usd.delete(0, "end")
            self.entry_conv_usd.insert(0, f"{val_usd:.2f}")
        except ValueError:
            pass

    def update_converter_ui(self):
        self.lbl_rate_info.configure(text=f"Taxa: R$ {self.usd_rate:.2f}")
        self._on_usd_changed(None)

    def fetch_usd_rate(self):
        def run():
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    "https://economia.awesomeapi.com.br/json/last/USD-BRL",
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    bid = float(data["USDBRL"]["bid"])
                    self.usd_rate = bid
                    self.after(0, self.update_converter_ui)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def update_dashboard_stats(self):
        import csv
        import calendar
        
        # 1. Calcula tempo restante do mês
        now = datetime.datetime.now()
        _, last_day = calendar.monthrange(now.year, now.month)
        end_of_month = datetime.datetime(now.year, now.month, last_day, 23, 59, 59)
        delta = end_of_month - now
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        self.lbl_end_month_val.configure(text=f"{days} dias, {hours:02d}h {minutes:02d}m")
        
        # 2. Processa histórico de operações
        history_file = "wins_history.csv"
        if not os.path.exists(history_file):
            for widget in self.history_list_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.history_list_frame, text="Nenhum registro encontrado.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=10)
            return

        trades = []
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None) # ignora header
                for row in reader:
                    if len(row) >= 2:
                        trades.append(row)
        except Exception:
            return
            
        if not trades:
            for widget in self.history_list_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.history_list_frame, text="Nenhum registro encontrado.", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=10)
            return
            
        # Atualiza a lista visual das últimas 50
        for widget in self.history_list_frame.winfo_children():
            widget.destroy()
            
        recent_trades = list(reversed(trades))[:50]
        for t in recent_trades:
            date_time = t[0]
            res = t[1].upper()
            win_val = self.config.get("win_value", 1.50)
            loss_val = self.config.get("loss_value", 30.00)
            
            if "WIN" in res:
                color = ACCENT_GREEN
                symbol = "🟢 WIN"
                diff = f"+${win_val:.2f}"
            else:
                color = ACCENT_RED
                symbol = "🔴 LOSS"
                diff = f"-${loss_val:.2f}"
                
            row_frame = ctk.CTkFrame(self.history_list_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row_frame, text=symbol, text_color=color, font=ctk.CTkFont(weight="bold", size=11), width=65, anchor="w").pack(side="left")
            ctk.CTkLabel(row_frame, text=date_time, text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
            ctk.CTkLabel(row_frame, text=diff, text_color=color, font=ctk.CTkFont(weight="bold", size=11)).pack(side="right")
            
        # 3. Agrupamento Diário (Streaks)
        daily_stats = {}
        hourly_stats = {}
        
        for t in trades:
            try:
                dt_str = t[0]
                date_str = dt_str.split()[0]
                time_part = dt_str.split()[1]
                hour = int(time_part.split(":")[0])
                res = t[1].upper()
                
                # Daily grouping
                if date_str not in daily_stats:
                    daily_stats[date_str] = {"wins": 0, "losses": 0}
                if "WIN" in res:
                    daily_stats[date_str]["wins"] += 1
                else:
                    daily_stats[date_str]["losses"] += 1
                    
                # Hourly grouping
                if hour not in hourly_stats:
                    hourly_stats[hour] = {"wins": 0, "losses": 0, "total": 0}
                hourly_stats[hour]["total"] += 1
                if "WIN" in res:
                    hourly_stats[hour]["wins"] += 1
                else:
                    hourly_stats[hour]["losses"] += 1
            except Exception:
                continue
                
        # Calcula sequências
        sorted_dates = sorted(daily_stats.keys())
        
        # Sequência de dias com Wins líquidos positivos
        win_days = []
        win_val = self.config.get("win_value", 1.50)
        loss_val = self.config.get("loss_value", 30.00)
        for d in sorted_dates:
            w = daily_stats[d]["wins"]
            l = daily_stats[d]["losses"]
            net = (w * win_val) - (l * loss_val)
            win_days.append(net > 0)
            
        max_streak = 0
        current_streak = 0
        for is_win in win_days:
            if is_win:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
            else:
                current_streak = 0
                
        end_streak = 0
        for is_win in reversed(win_days):
            if is_win:
                end_streak += 1
            else:
                break
        self.lbl_streak_wins_val.configure(text=f"{end_streak} dias (Recorde: {max_streak})")
        
        # Sequência de metas batidas
        target_val = self.config.get("target_profit", 10.00)
        target_days = []
        for d in sorted_dates:
            w = daily_stats[d]["wins"]
            l = daily_stats[d]["losses"]
            net = (w * win_val) - (l * loss_val)
            target_days.append(net >= target_val)
            
        max_target_streak = 0
        current_target_streak = 0
        for is_target in target_days:
            if is_target:
                current_target_streak += 1
                if current_target_streak > max_target_streak:
                    max_target_streak = current_target_streak
            else:
                current_target_streak = 0
                
        end_target_streak = 0
        for is_target in reversed(target_days):
            if is_target:
                end_target_streak += 1
            else:
                break
        self.lbl_streak_target_val.configure(text=f"{end_target_streak} dias (Recorde: {max_target_streak})")
        
        # 4. Estatísticas de Horário
        if hourly_stats:
            peak_hour = max(hourly_stats.keys(), key=lambda h: hourly_stats[h]["total"])
            peak_count = hourly_stats[peak_hour]["total"]
            self.lbl_peak_hour_val.configure(text=f"{peak_hour:02d}:00 - {peak_hour+1:02d}:00 ({peak_count} ops)")
        else:
            self.lbl_peak_hour_val.configure(text="Nenhum registro")
            
        # Horário mais assertivo (mínimo 3 operações)
        valid_hours = [h for h, stat in hourly_stats.items() if stat["total"] >= 3]
        if valid_hours:
            best_hour = max(valid_hours, key=lambda h: (hourly_stats[h]["wins"] / hourly_stats[h]["total"]))
            win_rate = (hourly_stats[best_hour]["wins"] / hourly_stats[best_hour]["total"]) * 100
            self.lbl_assertive_hour_val.configure(text=f"{best_hour:02d}:00 - {best_hour+1:02d}:00 ({win_rate:.1f}% Win)")
        else:
            if hourly_stats:
                best_hour = max(hourly_stats.keys(), key=lambda h: (hourly_stats[h]["wins"] / hourly_stats[h]["total"]))
                win_rate = (hourly_stats[best_hour]["wins"] / hourly_stats[best_hour]["total"]) * 100
                self.lbl_assertive_hour_val.configure(text=f"{best_hour:02d}:00 - {best_hour+1:02d}:00 ({win_rate:.1f}% Win)")
            else:
                self.lbl_assertive_hour_val.configure(text="Nenhum registro")
                
        # Desenha o gráfico de curva de lucros
        self.draw_profit_chart()

    def draw_profit_chart(self):
        w = self.chart_canvas.winfo_width()
        h = self.chart_canvas.winfo_height()
        
        if w < 10 or h < 10:
            return
            
        self.chart_canvas.delete("all")
        
        # 1. Carrega dados do wins_history.csv
        history_file = "wins_history.csv"
        trades = []
        if os.path.exists(history_file):
            try:
                import csv
                with open(history_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None) # ignora header
                    for row in reader:
                        if len(row) >= 2:
                            trades.append(row)
            except Exception:
                pass
                
        if not trades:
            self.chart_canvas.create_text(
                w / 2, h / 2,
                text="Aguardando as primeiras operações para desenhar o gráfico...",
                fill="gray",
                font=ctk.CTkFont(size=11)
            )
            return
            
        # 2. Constrói os lucros acumulados (últimos 30)
        profits = [0.0]
        current = 0.0
        win_val = self.config.get("win_value", 1.50)
        loss_val = self.config.get("loss_value", 30.00)
        
        for t in trades[-30:]:
            res = t[1].upper()
            if "WIN" in res:
                current += win_val
            else:
                current -= loss_val
            profits.append(current)
            
        # 3. Desenha os elementos do gráfico
        pad_x = 45
        pad_y = 20
        n = len(profits)
        
        dx = (w - 2 * pad_x) / (n - 1) if n > 1 else w - 2 * pad_x
        min_p = min(profits)
        max_p = max(profits)
        
        if max_p == min_p:
            min_p -= 1.0
            max_p += 1.0
            
        dy = (h - 2 * pad_y) / (max_p - min_p)
        
        # Linha horizontal do zero
        if min_p <= 0.0 <= max_p:
            y_zero = h - pad_y - (0.0 - min_p) * dy
            self.chart_canvas.create_line(pad_x, y_zero, w - pad_x, y_zero, fill="#1e293b", width=1)
            self.chart_canvas.create_text(pad_x - 10, y_zero, text="$0.0", fill="gray", font=("Consolas", 8), anchor="e")
            
        # Textos Y
        self.chart_canvas.create_text(pad_x - 10, pad_y, text=f"${max_p:.1f}", fill="gray", font=("Consolas", 8), anchor="e")
        self.chart_canvas.create_text(pad_x - 10, h - pad_y, text=f"${min_p:.1f}", fill="gray", font=("Consolas", 8), anchor="e")
        
        points = []
        for i, p in enumerate(profits):
            x = pad_x + i * dx
            y = h - pad_y - (p - min_p) * dy
            points.append((x, y))
            
        is_positive = profits[-1] >= 0.0
        line_color = ACCENT_GREEN if is_positive else ACCENT_RED
        glow_color = "#34d399" if is_positive else "#f87171"
        
        # Desenha a linha neon
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            self.chart_canvas.create_line(x1, y1, x2, y2, fill=line_color, width=3, smooth=True)
            self.chart_canvas.create_line(x1, y1, x2, y2, fill=glow_color, width=1, smooth=True)
            
        # Desenha nós
        for x, y in points:
            self.chart_canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#0b0f19", outline=glow_color, width=1)

    def _telegram_listener_loop(self):
        import time
        import urllib.request
        import urllib.parse
        import json
        
        last_update_id = 0
        self.tg_listener_running = True
        
        while self.tg_listener_running:
            enabled = self.config.get("telegram_enabled", False)
            token = self.config.get("telegram_token", "").strip()
            chat_id = self.config.get("telegram_chat_id", "").strip()
            
            if not enabled or not token or not chat_id:
                time.sleep(2)
                continue
                
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id}&timeout=10"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read().decode())
                    if data.get("ok"):
                        for update in data.get("result", []):
                            last_update_id = update["update_id"] + 1
                            message = update.get("message")
                            if not message:
                                continue
                                
                            from_chat_id = str(message.get("chat", {}).get("id"))
                            if from_chat_id != chat_id:
                                continue
                                
                            text = message.get("text", "").strip()
                            if text.startswith("/"):
                                self._handle_telegram_command(text)
            except Exception:
                time.sleep(5)

    def _handle_telegram_command(self, cmd):
        cmd = cmd.strip()
        parts = cmd.split()
        if not parts:
            return
        base_cmd = parts[0].lower()
        
        if base_cmd == "/status":
            self.after(0, self._send_telegram_status_reply)
        elif base_cmd == "/parar":
            self.after(0, self._execute_telegram_stop)
        elif base_cmd == "/config":
            self.after(0, self._send_telegram_config_reply)
        elif base_cmd == "/ciclo":
            self.after(0, self._send_telegram_cycle_help)
        elif base_cmd == "/ciclo_ativar":
            self.after(0, lambda: self._set_cycle_enabled_telegram(True))
        elif base_cmd == "/ciclo_desativar":
            self.after(0, lambda: self._set_cycle_enabled_telegram(False))
        elif base_cmd == "/ciclo_entradas":
            if len(parts) > 1:
                self.after(0, lambda: self._set_cycle_max_entries_telegram(parts[1]))
            else:
                self.after(0, lambda: self._send_telegram_reply("⚠️ <b>Uso incorreto.</b> Ex: <code>/ciclo_entradas 4</code>"))
        elif base_cmd == "/ciclo_pausa":
            if len(parts) > 1:
                self.after(0, lambda: self._set_cycle_cooldown_telegram(parts[1]))
            else:
                self.after(0, lambda: self._send_telegram_reply("⚠️ <b>Uso incorreto.</b> Ex: <code>/ciclo_pausa 30</code>"))
        elif base_cmd in ["/ciclo_pular", "/pular"]:
            self.after(0, self._execute_telegram_skip_cooldown)

    def _send_telegram_reply(self, text):
        telegram_sender.send_telegram_msg(self.config, text, self.log_message)

    def _update_setting_from_telegram(self, key, value):
        self.config[key] = value
        config_manager.save_config(self.config)
        if self.bot and self.bot.running:
            self.bot.config = self.config
        self.after(0, self._apply_config_to_gui)

    def _send_telegram_cycle_help(self):
        cycle_enabled = self.config.get("cycle_enabled", False)
        max_entries = self.config.get("cycle_max_entries", 4)
        cooldown = self.config.get("cycle_cooldown_minutes", 60)
        
        status_str = "ATIVADO 🟢" if cycle_enabled else "DESATIVADO 🔴"
        
        msg = (
            f"🔄 <b>Comandos de Ciclo</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Estado Atual:</b> {status_str}\n"
            f"• <b>Entradas/Ciclo:</b> {max_entries}\n"
            f"• <b>Tempo de Pausa:</b> {cooldown} min\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Comandos disponíveis:</b>\n"
            f"👉 <code>/ciclo_ativar</code> - Ativa a função de ciclos\n"
            f"👉 <code>/ciclo_desativar</code> - Desativa a função de ciclos\n"
            f"👉 <code>/ciclo_entradas &lt;n&gt;</code> - Define limite de entradas\n"
            f"👉 <code>/ciclo_pausa &lt;min&gt;</code> - Define minutos de pausa\n"
            f"👉 <code>/pular</code> - Pula a pausa do ciclo atual"
        )
        self._send_telegram_reply(msg)

    def _set_cycle_enabled_telegram(self, enabled):
        self._update_setting_from_telegram("cycle_enabled", enabled)
        status = "ATIVADO 🟢" if enabled else "DESATIVADO 🔴"
        self._send_telegram_reply(f"🔄 <b>Ciclo {status} com sucesso!</b>")

    def _set_cycle_max_entries_telegram(self, val_str):
        try:
            val = int(val_str)
            if val <= 0:
                raise ValueError()
            self._update_setting_from_telegram("cycle_max_entries", val)
            self._send_telegram_reply(f"🎯 <b>Entradas por ciclo definidas para:</b> {val}")
        except ValueError:
            self._send_telegram_reply("⚠️ <b>Valor inválido.</b> Insira um número inteiro maior que 0.")

    def _set_cycle_cooldown_telegram(self, val_str):
        try:
            val = int(val_str)
            if val <= 0:
                raise ValueError()
            self._update_setting_from_telegram("cycle_cooldown_minutes", val)
            self._send_telegram_reply(f"⏱️ <b>Tempo de pausa por ciclo definido para:</b> {val} minutos")
        except ValueError:
            self._send_telegram_reply("⚠️ <b>Valor inválido.</b> Insira um número inteiro maior que 0.")

    def _execute_telegram_skip_cooldown(self):
        if self.bot and self.bot.running and getattr(self.bot, "in_cycle_cooldown", False):
            self.bot.in_cycle_cooldown = False
            self.bot.cycle_cooldown_end_time = 0.0
            self.bot.cycle_entries_count = 0
            self._send_telegram_reply("⚡ <b>Pausa do ciclo pulada! Retomando operações imediatamente...</b>")
        else:
            self._send_telegram_reply("⚠️ <b>O bot não está em pausa de ciclo no momento.</b>")

    def _send_telegram_status_reply(self):
        is_running = self.bot and self.bot.running
        if is_running:
            exec_mode = getattr(self, "execution_mode", "desconhecido")
            if exec_mode == "stealth":
                status_str = "STEALTH 🥷 🟢"
            else:
                status_str = "EXECUTANDO 🟢"
        else:
            status_str = "PARADO 🔴"
        
        wins = self.lbl_metric_wins.cget("text")
        losses = self.lbl_metric_losses.cget("text")
        clicks = self.lbl_metric_clicks.cget("text")
        assertiveness = self.lbl_metric_assert.cget("text")
        
        # Check cycle status
        cycle_enabled = self.config.get("cycle_enabled", False)
        if cycle_enabled and is_running:
            in_cooldown = getattr(self.bot, "in_cycle_cooldown", False)
            if in_cooldown:
                cooldown_end = getattr(self.bot, "cycle_cooldown_end_time", 0.0)
                end_str = datetime.datetime.fromtimestamp(cooldown_end).strftime("%H:%M:%S")
                cycle_str = f"PAUSADO ⏳ (Retorno às {end_str})"
                status_str = "PAUSADO (CICLO) ⏳"
            else:
                entries = getattr(self.bot, "cycle_entries_count", 0)
                max_entries = self.config.get("cycle_max_entries", 4)
                cycle_str = f"ATIVO 🔄 ({entries}/{max_entries} entr.)"
        elif cycle_enabled:
            cycle_str = "ATIVO 🔄 (Bot Parado)"
        else:
            cycle_str = "DESATIVADO ⚪"
            
        profit = 0.0
        if self.bot:
            profit = getattr(self.bot, "current_profit", 0.0)
            
        elapsed_str = "00:00:00"
        if is_running:
            elapsed = time.time() - self.start_time
            hours, remainder = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(remainder, 60)
            elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
        adaptive_str = ""
        if is_running and self.config.get("mode") == "adaptive":
            phase = getattr(self.bot, "adaptive_phase", "observation")
            phase_lbl = "Observando 👁️" if phase == "observation" else "Operando 🤖"
            strat = getattr(self.bot, "adaptive_strategy", {})
            events = strat.get("eventos_analisados", 0)
            conf_val = strat.get("confidence", 0.0)
            pattern = strat.get("dominant_pattern", "N/A")
            rule = strat.get("text", "N/A")
            adaptive_str = (
                f"\n━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>Modo Inteligente (IA):</b>\n"
                f"├─ <b>Fase:</b> {phase_lbl}\n"
                f"├─ <b>Eventos:</b> {events}\n"
                f"├─ <b>Confiança:</b> {conf_val:.1f}%\n"
                f"├─ <b>Padrão Dominante:</b> {pattern}\n"
                f"└─ <b>Regra Ativa:</b> {rule}"
            )
            
        msg = (
            f"📊 <b>Status do DerivClickerBot</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Status:</b> {status_str}\n"
            f"• <b>Ciclos:</b> {cycle_str}\n"
            f"• <b>Saldo Atual:</b> ${profit:.2f}\n"
            f"• <b>Wins:</b> {wins} | <b>Losses:</b> {losses}\n"
            f"• <b>Assertividade:</b> {assertiveness}\n"
            f"• <b>Cliques:</b> {clicks}\n"
            f"• <b>Tempo Ativo:</b> {elapsed_str}"
            f"{adaptive_str}"
        )
        telegram_sender.send_telegram_msg(self.config, msg, self.log_message)

    def _execute_telegram_stop(self):
        is_running = self.bot and self.bot.running
        if is_running:
            self.btn_stop_clicked()
            msg = "🛑 <b>Comando recebido: O bot foi PARADO com sucesso!</b>"
        else:
            msg = "⚠️ <b>O bot já está parado.</b>"
        telegram_sender.send_telegram_msg(self.config, msg, self.log_message)

    def _send_telegram_config_reply(self):
        mode = self.seg_mode.get()
        target = self.config.get("target_profit", 10.00)
        win_val = self.config.get("win_value", 1.50)
        loss_val = self.config.get("loss_value", 30.00)
        
        cycle_enabled = self.config.get("cycle_enabled", False)
        cycle_status = "Ativo" if cycle_enabled else "Desativado"
        cycle_max = self.config.get("cycle_max_entries", 4)
        cycle_cool = self.config.get("cycle_cooldown_minutes", 60)
        
        adaptive_str = ""
        if mode == "Modo Inteligente":
            obs_min = self.config.get("adaptive_observation_minutes", 30)
            rel_ev = self.config.get("adaptive_relearn_events", 100)
            rel_min = self.config.get("adaptive_relearn_minutes", 30)
            rel_los = self.config.get("adaptive_relearn_losses", 3)
            adaptive_str = (
                f"\n━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>Parâmetros Inteligentes:</b>\n"
                f"├─ Obs. Inicial: {obs_min}m\n"
                f"├─ Reaprender (Ev): {rel_ev}\n"
                f"├─ Reaprender (min): {rel_min}m\n"
                f"└─ Reaprender (Losses): {rel_los}"
            )
            
        msg = (
            f"⚙️ <b>Configurações do DerivClickerBot</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Modo Ativo:</b> {mode}\n"
            f"• <b>Meta de Lucro (Stop Win):</b> ${target:.2f}\n"
            f"• <b>Valor por Win:</b> ${win_val:.2f}\n"
            f"• <b>Limite por Loss:</b> ${loss_val:.2f}\n"
            f"• <b>Ciclos:</b> {cycle_status} (Entradas: {cycle_max} | Pausa: {cycle_cool}m)"
            f"{adaptive_str}"
        )
        telegram_sender.send_telegram_msg(self.config, msg, self.log_message)

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
        self.frame_adaptive.pack_forget()
        self.frame_ai.pack_forget()
        
        if mode_label == "Intervalo Fixo":
            self.frame_fixed.pack(fill="x", pady=5)
        elif mode_label == "Intervalo Aleatório":
            self.frame_random.pack(fill="x", pady=5)
        elif mode_label == "Sequência de Cliques":
            self.frame_sequence.pack(fill="x", pady=5)
        elif mode_label == "Linha Vermelha" or mode_label == "Número Vermelho":
            self.frame_linered.pack(fill="x", pady=5)
        elif mode_label == "Modo Inteligente" or mode_label == "Modo IA":
            self.frame_ai.pack(fill="x", pady=5)

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

    def _on_main_contract_mode_changed(self):
        if hasattr(self, "combo_ai_contract_mode") and self.combo_ai_contract_mode.winfo_exists():
            val = self.combo_ai_contract_mode.get()
            if val == "Rise/Fall":
                self.config["deriv_contract_mode"] = "rise_fall"
            elif val == "Matches":
                self.config["deriv_contract_mode"] = "matches"
            elif val == "Differs":
                self.config["deriv_contract_mode"] = "differs"
            else:
                self.config["deriv_contract_mode"] = "accumulator"
            if hasattr(self, "settings_combo_contract_mode") and self.settings_combo_contract_mode.winfo_exists():
                self.settings_combo_contract_mode.set(val)
                self._on_contract_mode_changed()
            self._gui_setting_changed()

    def _on_llama_provider_changed(self):
        if hasattr(self, "settings_combo_llama_provider") and self.settings_combo_llama_provider.winfo_exists():
            prov = self.settings_combo_llama_provider.get()
            if prov == "Local Embutido":
                self.config["llama_provider"] = "local"
                if hasattr(self, "settings_entry_llama_url") and self.settings_entry_llama_url.winfo_exists():
                    self.settings_entry_llama_url.configure(state="disabled")
                if hasattr(self, "settings_combo_llama_model") and self.settings_combo_llama_model.winfo_exists():
                    avail_vals = list(self.settings_combo_llama_model.cget("values"))
                    local_model = "Qwen/Qwen2.5-0.5B-Instruct"
                    if local_model not in avail_vals:
                        avail_vals.append(local_model)
                        self.settings_combo_llama_model.configure(values=avail_vals)
                    self.settings_combo_llama_model.set(local_model)
            else:
                self.config["llama_provider"] = "ollama"
                if hasattr(self, "settings_entry_llama_url") and self.settings_entry_llama_url.winfo_exists():
                    self.settings_entry_llama_url.configure(state="normal")
                if hasattr(self, "settings_combo_llama_model") and self.settings_combo_llama_model.winfo_exists():
                    avail = self._get_available_llama_models()
                    self.settings_combo_llama_model.configure(values=avail)
                    if "qwen2.5:0.5b" in avail:
                        self.settings_combo_llama_model.set("qwen2.5:0.5b")
                    else:
                        self.settings_combo_llama_model.set("llama3")
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
            cycle_max_entries_val = int(self.entry_cycle_max_entries.get())
        except ValueError:
            cycle_max_entries_val = 4
            
        try:
            cycle_cooldown_val = int(self.entry_cycle_cooldown.get())
        except ValueError:
            cycle_cooldown_val = 60
            
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
        active_widget = self.focus_get()
        ai_entry_widget = getattr(self, "entry_ai_win_value", None)
        main_entry_widget = getattr(self, "entry_win_value", None)
        
        ai_entry_inner = getattr(ai_entry_widget, "_entry", None) if ai_entry_widget else None
        main_entry_inner = getattr(main_entry_widget, "_entry", None) if main_entry_widget else None

        try:
            if ai_entry_widget and ai_entry_widget.winfo_exists() and active_widget == ai_entry_inner:
                win_val = float(ai_entry_widget.get().replace(",", "."))
                try:
                    main_val = float(main_entry_widget.get().replace(",", "."))
                except ValueError:
                    main_val = -1.0
                if abs(win_val - main_val) > 0.001:
                    main_entry_widget.delete(0, "end")
                    main_entry_widget.insert(0, f"{win_val:.2f}")
            elif main_entry_widget and main_entry_widget.winfo_exists() and active_widget == main_entry_inner:
                win_val = float(main_entry_widget.get().replace(",", "."))
                if ai_entry_widget and ai_entry_widget.winfo_exists():
                    try:
                        ai_val = float(ai_entry_widget.get().replace(",", "."))
                    except ValueError:
                        ai_val = -1.0
                    if abs(win_val - ai_val) > 0.001:
                        ai_entry_widget.delete(0, "end")
                        ai_entry_widget.insert(0, f"{win_val:.2f}")
            else:
                win_val = float(main_entry_widget.get().replace(",", "."))
        except ValueError:
            try:
                win_val = float(self.config.get("win_value", 1.50))
            except Exception:
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
        
        # Modo Adaptativo
        try:
            self.config["adaptive_observation_minutes"] = int(self.entry_adaptive_obs.get())
        except ValueError:
            pass
            
        try:
            self.config["adaptive_relearn_events"] = int(self.entry_adaptive_events.get())
        except ValueError:
            pass
            
        try:
            self.config["adaptive_relearn_minutes"] = int(self.entry_adaptive_rep_min.get())
        except ValueError:
            pass
            
        try:
            self.config["adaptive_relearn_losses"] = int(self.entry_adaptive_losses.get())
        except ValueError:
            pass
            
        # Modo IA
        try:
            self.config["ai_threshold"] = float(self.entry_ai_threshold.get().replace(",", "."))
        except ValueError:
            pass
            
        try:
            self.config["ai_learning_rate"] = float(self.entry_ai_lr.get().replace(",", "."))
        except ValueError:
            pass
            
        try:
            self.config["ai_lookahead_ticks"] = int(self.entry_ai_lookahead.get())
        except ValueError:
            pass

        try:
            self.config["ai_entry_cooldown"] = int(self.entry_ai_cooldown.get())
        except (ValueError, AttributeError):
            pass

        try:
            self.config["ai_min_ticks_safe"] = int(self.entry_ai_min_ticks.get())
        except (ValueError, AttributeError):
            pass

        try:
            self.config["ai_min_samples_start"] = int(self.entry_ai_min_samples.get())
        except (ValueError, AttributeError):
            pass
        
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
        
        # Ciclos de Entradas
        self.config["cycle_enabled"] = self.switch_cycle.get() == 1
        self.config["cycle_max_entries"] = cycle_max_entries_val
        self.config["cycle_cooldown_minutes"] = cycle_cooldown_val
        
        # Deriv API Configuration
        if hasattr(self, "settings_entry_api_token") and self.settings_entry_api_token and self.settings_entry_api_token.winfo_exists():
            self.config["deriv_api_token"] = self.settings_entry_api_token.get().strip()
        if hasattr(self, "settings_entry_api_appid") and self.settings_entry_api_appid and self.settings_entry_api_appid.winfo_exists():
            self.config["deriv_app_id"] = self.settings_entry_api_appid.get().strip()
        if hasattr(self, "settings_combo_api_symbol") and self.settings_combo_api_symbol and self.settings_combo_api_symbol.winfo_exists():
            self.config["deriv_symbol"] = self.settings_combo_api_symbol.get()
        # Multiplicador/Growth Rate synchronisation & parsing
        ai_combo_widget = getattr(self, "combo_ai_growth_rate", None)
        adv_entry_widget = getattr(self, "settings_entry_api_growth", None)
        
        ai_combo_inner = getattr(ai_combo_widget, "_entry", None) if ai_combo_widget else None
        adv_entry_inner = getattr(adv_entry_widget, "_entry", None) if adv_entry_widget else None

        try:
            if ai_combo_widget and ai_combo_widget.winfo_exists() and (active_widget == ai_combo_inner or active_widget == ai_combo_widget):
                growth_pct = int(ai_combo_widget.get().replace("%", ""))
                deriv_growth = round(growth_pct / 100.0, 4)
                if adv_entry_widget and adv_entry_widget.winfo_exists():
                    try:
                        adv_pct = float(adv_entry_widget.get().replace(",", "."))
                    except ValueError:
                        adv_pct = -1.0
                    if abs(growth_pct - adv_pct) > 0.001:
                        adv_entry_widget.delete(0, "end")
                        adv_entry_widget.insert(0, str(growth_pct))
            elif adv_entry_widget and adv_entry_widget.winfo_exists() and active_widget == adv_entry_inner:
                growth_percent = float(adv_entry_widget.get().replace(",", "."))
                deriv_growth = round(growth_percent / 100.0, 4)
                if ai_combo_widget and ai_combo_widget.winfo_exists():
                    growth_percent_str = f"{int(round(growth_percent))}%"
                    if growth_percent_str in ["1%", "2%", "3%", "4%", "5%"] and ai_combo_widget.get() != growth_percent_str:
                        ai_combo_widget.set(growth_percent_str)
            else:
                if hasattr(self, "combo_ai_growth_rate") and self.combo_ai_growth_rate and self.combo_ai_growth_rate.winfo_exists():
                    growth_pct = int(self.combo_ai_growth_rate.get().replace("%", ""))
                    deriv_growth = round(growth_pct / 100.0, 4)
                elif hasattr(self, "settings_entry_api_growth") and self.settings_entry_api_growth and self.settings_entry_api_growth.winfo_exists():
                    try:
                        growth_percent = float(self.settings_entry_api_growth.get().replace(",", "."))
                        deriv_growth = round(growth_percent / 100.0, 4)
                    except ValueError:
                        deriv_growth = self.config.get("deriv_growth_rate", 0.01)
                else:
                    deriv_growth = self.config.get("deriv_growth_rate", 0.01)
        except Exception:
            deriv_growth = self.config.get("deriv_growth_rate", 0.01)
            
        self.config["deriv_growth_rate"] = deriv_growth
        if hasattr(self, "settings_switch_use_api") and self.settings_switch_use_api and self.settings_switch_use_api.winfo_exists():
            self.config["deriv_use_api_trading"] = self.settings_switch_use_api.get() == 1
        if hasattr(self, "settings_switch_scan_market") and self.settings_switch_scan_market and self.settings_switch_scan_market.winfo_exists():
            self.config["deriv_scan_market"] = self.settings_switch_scan_market.get() == 1
        if hasattr(self, "settings_combo_api_account_type") and self.settings_combo_api_account_type and self.settings_combo_api_account_type.winfo_exists():
            self.config["deriv_account_type"] = self.settings_combo_api_account_type.get().strip().lower()
            
        # Meta de Lucro por Contrato (Modo IA)
        try:
            self.config["ai_contract_take_profit"] = float(self.entry_ai_contract_take_profit.get().replace(",", "."))
        except (ValueError, AttributeError):
            pass

        # Modo do Contrato
        if hasattr(self, "combo_ai_contract_mode") and self.combo_ai_contract_mode and self.combo_ai_contract_mode.winfo_exists():
            cm_val = self.combo_ai_contract_mode.get().strip()
            if cm_val == "Rise/Fall":
                self.config["deriv_contract_mode"] = "rise_fall"
            elif cm_val == "Matches":
                self.config["deriv_contract_mode"] = "matches"
            elif cm_val == "Differs":
                self.config["deriv_contract_mode"] = "differs"
            else:
                self.config["deriv_contract_mode"] = "accumulator"
        elif hasattr(self, "settings_combo_contract_mode") and self.settings_combo_contract_mode and self.settings_combo_contract_mode.winfo_exists():
            cm_val = self.settings_combo_contract_mode.get().strip()
            if cm_val == "Rise/Fall":
                self.config["deriv_contract_mode"] = "rise_fall"
            elif cm_val == "Matches":
                self.config["deriv_contract_mode"] = "matches"
            elif cm_val == "Differs":
                self.config["deriv_contract_mode"] = "differs"
            else:
                self.config["deriv_contract_mode"] = "accumulator"

        # Rise/Fall settings
        if hasattr(self, "settings_entry_rf_duration") and self.settings_entry_rf_duration and self.settings_entry_rf_duration.winfo_exists():
            try:
                self.config["deriv_rf_duration_value"] = int(self.settings_entry_rf_duration.get())
            except ValueError:
                pass
        if hasattr(self, "settings_combo_rf_unit") and self.settings_combo_rf_unit and self.settings_combo_rf_unit.winfo_exists():
            unit_val = self.settings_combo_rf_unit.get().strip()
            unit_code = "t" if unit_val == "Ticks" else ("s" if unit_val == "Segundos" else "m")
            self.config["deriv_rf_duration_unit"] = unit_code
        if hasattr(self, "settings_switch_rf_auto") and self.settings_switch_rf_auto and self.settings_switch_rf_auto.winfo_exists():
            self.config["deriv_rf_auto_duration"] = self.settings_switch_rf_auto.get() == 1

        # Llama settings
        if hasattr(self, "settings_switch_llama") and self.settings_switch_llama and self.settings_switch_llama.winfo_exists():
            self.config["llama_enabled"] = self.settings_switch_llama.get() == 1
        if hasattr(self, "settings_combo_llama_provider") and self.settings_combo_llama_provider and self.settings_combo_llama_provider.winfo_exists():
            prov_val = self.settings_combo_llama_provider.get().strip()
            self.config["llama_provider"] = "local" if prov_val == "Local Embutido" else "ollama"
        if hasattr(self, "settings_entry_llama_url") and self.settings_entry_llama_url and self.settings_entry_llama_url.winfo_exists():
            self.config["llama_url"] = self.settings_entry_llama_url.get().strip()
        if hasattr(self, "settings_combo_llama_model") and self.settings_combo_llama_model and self.settings_combo_llama_model.winfo_exists():
            self.config["llama_model"] = self.settings_combo_llama_model.get().strip()

        # Salva no arquivo JSON
        config_manager.save_config(self.config)
        
        # Se o bot estiver rodando, atualiza a configuracao dele dinamicamente
        if self.bot and self.bot.running:
            self.bot.config = self.config
            if self.bot.api_client:
                self.bot.api_client.growth_rate = self.config.get("deriv_growth_rate", 0.01)
                self.bot.api_client._request_proposal()

    def _get_available_llama_models(self):
        models = []
        try:
            import urllib.request
            import json
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=1.0) as response:
                data = json.loads(response.read().decode("utf-8"))
                for m in data.get("models", []):
                    name = m.get("name")
                    if name and name not in models:
                        models.append(name)
        except Exception:
            pass

        defaults = ["qwen2.5:0.5b", "llama3", "Qwen/Qwen2.5-0.5B-Instruct"]
        for d in defaults:
            if d not in models:
                models.append(d)
        return models

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

        # SECTION 5: CONEXÃO API DERIV
        sec5_frame = ctk.CTkFrame(scroll_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        sec5_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_sec5_title = ctk.CTkLabel(sec5_frame, text="🔌 Conexão API da Deriv", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        lbl_sec5_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.settings_switch_use_api = ctk.CTkSwitch(sec5_frame, text="Ativar Operações por API (Sem Cliques)", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_use_api.pack(anchor="w", padx=15, pady=4)
        
        self.settings_switch_scan_market = ctk.CTkSwitch(sec5_frame, text="Pesquisar Melhor Ativo/Timeframe ao Iniciar", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_scan_market.pack(anchor="w", padx=15, pady=4)
        
        row_api_mode = ctk.CTkFrame(sec5_frame, fg_color="transparent")
        row_api_mode.pack(fill="x", padx=15, pady=6)
        
        col_contract_mode = ctk.CTkFrame(row_api_mode, fg_color="transparent")
        col_contract_mode.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_contract_mode, text="Tipo de Contrato", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_combo_contract_mode = ctk.CTkComboBox(col_contract_mode, values=["Accumulator", "Rise/Fall", "Matches", "Differs"], height=28, command=lambda e: self._on_contract_mode_changed())
        self.settings_combo_contract_mode.pack(fill="x", pady=2)
        
        self.settings_frame_rf = ctk.CTkFrame(sec5_frame, fg_color="transparent")
        
        row_rf_inputs = ctk.CTkFrame(self.settings_frame_rf, fg_color="transparent")
        row_rf_inputs.pack(fill="x", pady=6)
        
        col_rf_dur = ctk.CTkFrame(row_rf_inputs, fg_color="transparent")
        col_rf_dur.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_rf_dur, text="Duração do Contrato", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_rf_duration = ctk.CTkEntry(col_rf_dur, height=28, placeholder_text="5")
        self.settings_entry_rf_duration.pack(fill="x", pady=2)
        self.settings_entry_rf_duration.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        col_rf_unit = ctk.CTkFrame(row_rf_inputs, fg_color="transparent")
        col_rf_unit.pack(side="left", fill="x", expand=True, padx=(5, 5))
        ctk.CTkLabel(col_rf_unit, text="Unidade", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_combo_rf_unit = ctk.CTkComboBox(col_rf_unit, values=["Ticks", "Segundos", "Minutos"], height=28, command=lambda e: self._gui_setting_changed())
        self.settings_combo_rf_unit.pack(fill="x", pady=2)
        
        self.settings_switch_rf_auto = ctk.CTkSwitch(self.settings_frame_rf, text="Duração Automática por IA", progress_color=ACCENT_GREEN, command=self._gui_setting_changed)
        self.settings_switch_rf_auto.pack(anchor="w", pady=4)
        
        row_api_inputs = ctk.CTkFrame(sec5_frame, fg_color="transparent")
        row_api_inputs.pack(fill="x", padx=15, pady=6)
        
        col_api_token = ctk.CTkFrame(row_api_inputs, fg_color="transparent")
        col_api_token.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_api_token, text="Token de Acesso API", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_api_token = ctk.CTkEntry(col_api_token, height=28, placeholder_text="Token API")
        self.settings_entry_api_token.pack(fill="x", pady=2)
        self.settings_entry_api_token.bind("<KeyRelease>", self._gui_setting_changed)
        
        col_api_appid = ctk.CTkFrame(row_api_inputs, fg_color="transparent")
        col_api_appid.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(col_api_appid, text="App ID", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_api_appid = ctk.CTkEntry(col_api_appid, height=28, placeholder_text="1098")
        self.settings_entry_api_appid.pack(fill="x", pady=2)
        self.settings_entry_api_appid.bind("<KeyRelease>", self._gui_setting_changed)
        
        row_api_inputs2 = ctk.CTkFrame(sec5_frame, fg_color="transparent")
        row_api_inputs2.pack(fill="x", padx=15, pady=6)
        
        col_api_symbol = ctk.CTkFrame(row_api_inputs2, fg_color="transparent")
        col_api_symbol.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_api_symbol, text="Ativo (Symbol)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_combo_api_symbol = ctk.CTkComboBox(col_api_symbol, values=["R_10", "R_25", "R_50", "R_75", "R_100", "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"], height=28, command=lambda e: self._gui_setting_changed())
        self.settings_combo_api_symbol.pack(fill="x", pady=2)
        
        col_api_growth = ctk.CTkFrame(row_api_inputs2, fg_color="transparent")
        col_api_growth.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(col_api_growth, text="Taxa de Crescimento (%)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_api_growth = ctk.CTkEntry(col_api_growth, height=28, placeholder_text="1.0")
        self.settings_entry_api_growth.pack(fill="x", pady=2)
        self.settings_entry_api_growth.bind("<KeyRelease>", self._gui_setting_changed)
                
        row_api_inputs3 = ctk.CTkFrame(sec5_frame, fg_color="transparent")
        row_api_inputs3.pack(fill="x", padx=15, pady=6)
        
        col_api_account_type = ctk.CTkFrame(row_api_inputs3, fg_color="transparent")
        col_api_account_type.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col_api_account_type, text="Tipo de Conta (PAT)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_combo_api_account_type = ctk.CTkComboBox(col_api_account_type, values=["Demo", "Real"], height=28, command=lambda e: self._gui_setting_changed())
        self.settings_combo_api_account_type.pack(fill="x", pady=2)
        
        row_api_actions = ctk.CTkFrame(sec5_frame, fg_color="transparent")
        row_api_actions.pack(fill="x", padx=15, pady=(4, 12))
        
        self.btn_api_test = ctk.CTkButton(
            row_api_actions, text="🔌 Testar Conexão API", width=150, height=28,
            font=ctk.CTkFont(size=11), fg_color=ACCENT_BLUE, hover_color="#2563eb",
            command=self._test_api_connection
        )
        self.btn_api_test.pack(side="left", padx=(0, 8))
        
        self.lbl_api_status = ctk.CTkLabel(sec5_frame, text="", font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.lbl_api_status.pack(anchor="w", padx=15, pady=(0, 10))

        # SECTION 6: INTEGRAÇÃO IA LLAMA (OLLAMA)
        sec6_frame = ctk.CTkFrame(scroll_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        sec6_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_sec6_title = ctk.CTkLabel(sec6_frame, text="🧠 Integração IA Llama (Ollama)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
        lbl_sec6_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.settings_switch_llama = ctk.CTkSwitch(sec6_frame, text="Habilitar IA Llama (Tomada de Decisão)", progress_color=ACCENT_GREEN, command=lambda: self._gui_setting_changed())
        self.settings_switch_llama.pack(anchor="w", padx=15, pady=4)

        row_llama_provider = ctk.CTkFrame(sec6_frame, fg_color="transparent")
        row_llama_provider.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(row_llama_provider, text="Provedor do Llama", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.settings_combo_llama_provider = ctk.CTkComboBox(row_llama_provider, values=["Ollama (API)", "Local Embutido"], height=28, width=150, command=lambda e: self._on_llama_provider_changed())
        self.settings_combo_llama_provider.pack(side="right")
        
        row_llama_inputs = ctk.CTkFrame(sec6_frame, fg_color="transparent")
        row_llama_inputs.pack(fill="x", padx=15, pady=6)
        
        col_llama_url = ctk.CTkFrame(row_llama_inputs, fg_color="transparent")
        col_llama_url.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(col_llama_url, text="Endpoint URL (Ollama)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        self.settings_entry_llama_url = ctk.CTkEntry(col_llama_url, height=28, placeholder_text="http://localhost:11434/api/generate")
        self.settings_entry_llama_url.pack(fill="x", pady=2)
        self.settings_entry_llama_url.bind("<KeyRelease>", lambda e: self._gui_setting_changed())
        
        col_llama_model = ctk.CTkFrame(row_llama_inputs, fg_color="transparent")
        col_llama_model.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(col_llama_model, text="Modelo Llama", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w")
        avail_models = self._get_available_llama_models()
        self.settings_combo_llama_model = ctk.CTkComboBox(col_llama_model, values=avail_models, height=28, command=lambda e: self._gui_setting_changed())
        self.settings_combo_llama_model.pack(fill="x", pady=2)

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

    def _on_contract_mode_changed(self):
        if hasattr(self, "settings_combo_contract_mode") and self.settings_combo_contract_mode.winfo_exists():
            val = self.settings_combo_contract_mode.get()
            if val == "Rise/Fall":
                self.config["deriv_contract_mode"] = "rise_fall"
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack(fill="x", padx=15, pady=4)
            elif val == "Matches":
                self.config["deriv_contract_mode"] = "matches"
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack_forget()
            elif val == "Differs":
                self.config["deriv_contract_mode"] = "differs"
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack_forget()
            else:
                self.config["deriv_contract_mode"] = "accumulator"
                if hasattr(self, "settings_frame_rf") and self.settings_frame_rf.winfo_exists():
                    self.settings_frame_rf.pack_forget()
            
            # Sync main AI contract mode combo too if exists
            if hasattr(self, "combo_ai_contract_mode") and self.combo_ai_contract_mode.winfo_exists():
                self.combo_ai_contract_mode.set(val)
        self._gui_setting_changed()

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
            
        # Dialogo de escolha de modo de navegacao
        dialog = ExecutionModeDialog(self)
        mode = dialog.result
        
        if not mode:
            return
            
        self._gui_setting_changed()  # Salva tudo antes de iniciar
        self.stop_reason = None
        self.execution_mode = mode
        self.original_use_api_trading = self.config.get("deriv_use_api_trading", False)
        
        if mode == "stealth":
            token = self.config.get("deriv_api_token", "").strip()
            if not token:
                messagebox.showerror("Erro de Configuração", "O Modo Stealth requer um Token de Acesso API da Deriv.\nPor favor, configure o Token nas Configurações Avançadas antes de iniciar.")
                return
            self.config["deriv_use_api_trading"] = True
            self.log_message("Modo STEALTH iniciado: Operações rodando em segundo plano via API da Deriv.")
        elif mode == "ai_overlay":
            self.config["mode"] = "ai"
            self.seg_mode.set("IA (Rede Neural)")
            token = self.config.get("deriv_api_token", "").strip()
            if not token:
                messagebox.showerror("Erro de Configuração", "O Modo IA requer um Token de Acesso API da Deriv.\nPor favor, configure o Token nas Configurações Avançadas antes de iniciar.")
                return
            self.config["deriv_use_api_trading"] = True
            self.log_message("Modo IA (API) iniciado: Operações rodando em segundo plano via API da Deriv e exibindo overlay.")
            
            # Auto-exibe o overlay
            if not self.overlay or not self.overlay.winfo_exists():
                from floating_overlay import FloatingOverlay
                self.overlay = FloatingOverlay(self)
                self.overlay.on_panic_cb = self.btn_panic_clicked
            self.overlay.deiconify()
            self.overlay.reveal_tab = "general" if not hasattr(self.overlay, "active_tab") else self.overlay.active_tab
            self.overlay.lift()
            self.overlay.attributes("-topmost", True)
            self.btn_overlay.configure(fg_color=ACCENT_BLUE)
        elif mode == "derivclicker":
            try:
                if getattr(sys, 'frozen', False):
                    cmd = [sys.executable, "--webview"]
                else:
                    cmd = [sys.executable, sys.argv[0], "--webview"]
                self.webview_proc = subprocess.Popen(cmd)
                self.log_message("Navegador embutido DERIVCLICKER iniciado com sucesso.")
            except Exception as e:
                self.log_message(f"Erro ao iniciar navegador embutido: {e}")
                messagebox.showerror("Erro de Inicialização", f"Não foi possível iniciar o navegador embutido: {e}")
                return
                
        is_scheduled = self.switch_schedule.get() == 1
        if is_scheduled:
            self.lbl_status_value.configure(text="AGENDADO", text_color=ACCENT_YELLOW)
        else:
            if mode == "stealth":
                self.lbl_status_value.configure(text="STEALTH 🥷", text_color="#a855f7")
            elif mode == "ai_overlay" or self.config.get("mode") == "ai":
                self.lbl_status_value.configure(text="EXECUTANDO (IA)", text_color=ACCENT_GREEN)
                # Auto-exibe o overlay também caso o usuário tenha clicado em outro botão mas esteja no modo IA
                if not self.overlay or not self.overlay.winfo_exists():
                    from floating_overlay import FloatingOverlay
                    self.overlay = FloatingOverlay(self)
                    self.overlay.on_panic_cb = self.btn_panic_clicked
                self.overlay.deiconify()
                self.overlay.lift()
                self.overlay.attributes("-topmost", True)
                self.btn_overlay.configure(fg_color=ACCENT_BLUE)
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
        self.bot.on_ai_metrics_cb = self._on_ai_metrics_received
        if self.execution_mode == "derivclicker":
            self.bot.setup_in_progress = True
            threading.Thread(target=self._run_clickerbot_setup, daemon=True).start()
        self.bot.start_bot()

    def _run_clickerbot_setup(self):
        import pyautogui
        self.log_message("[Clickerbot] Iniciando configuração automática do navegador...")
        # Dá 6 segundos para a janela abrir e carregar parcialmente
        time.sleep(6.0)
        
        # Sequência de passos com timeouts personalizados
        # Formato: (arquivo_imagem, nome_do_passo, eh_campo_amount, timeout_segundos)
        steps = [
            ("iniciar.png", "Iniciar", False, 15.0),
            ("demo.png", "Demo", False, 10.0),
            ("acumulators.png", "Acumulators", False, 15.0),  # Aumentado para 15s para aguardar carregamento da página
            ("stake.png", "Stake", False, 2.0),
            ("10.png", "10", False, 2.0),
            ("rate.png", "Rate", False, 2.0),
            ("5%.png", "5%", False, 4.0),
            ("take.png", "Take", False, 2.0),
            ("togle.png", "Togle", False, 2.0),
            ("amount.png", "Amount", True, 4.0),
            ("save.png", "Save", False, 4.0)
        ]
        
        skip_accumulator_steps = False
        skip_rate_steps = False
        screen_width, screen_height = pyautogui.size()
        # Região correspondente aos 65% direitos da tela (para evitar a janela do bot na extrema esquerda e cobrir dropdowns que abrem para a esquerda)
        right_region = (int(screen_width * 0.35), 0, int(screen_width * 0.65), screen_height)
        
        rate_pos = None
        take_pos = None
        
        for filename, name, is_amount, timeout in steps:
            if not self.bot or not self.bot.running:
                self.log_message("[Clickerbot] Configuração interrompida pois o robô foi parado.")
                return
                
            # Se for para pular os passos de seleção do Accumulator
            if skip_accumulator_steps and name in ["Acumulators", "Stake", "10"]:
                self.log_message(f"[Clickerbot] Pulando passo '{name}' (Accumulator já ativo).")
                continue
                
            # Se for para pular os passos de Growth Rate
            if skip_rate_steps and name in ["Rate", "5%"]:
                self.log_message(f"[Clickerbot] Pulando passo '{name}' (Growth rate já está em 5%).")
                continue
                
            path = os.path.join("capturas", filename)
            if not os.path.exists(path):
                self.log_message(f"[Clickerbot] Erro: Imagem de referência '{path}' não encontrada.")
                continue
                
            # Verifica se o Accumulator já está ativo (checando se Togle ou Amount já aparecem na tela)
            if name == "Acumulators":
                try:
                    if (pyautogui.locateOnScreen(os.path.join("capturas", "togle.png"), region=right_region, confidence=0.8) is not None or
                        pyautogui.locateOnScreen(os.path.join("capturas", "amount.png"), region=right_region, confidence=0.8) is not None):
                        self.log_message("[Clickerbot] Painel do Accumulator já está ativo. Pulando passos de seleção do contrato.")
                        skip_accumulator_steps = True
                        continue
                except Exception as e:
                    self.log_message(f"[Clickerbot] Erro ao verificar painel do Accumulator: {e}")
                
            # Verifica se o Growth Rate já está em 5% antes de clicar em Rate (apenas na metade direita da tela)
            if name == "Rate":
                try:
                    found_5 = False
                    for img_name in ["5%ativ.png", "5%.png", "5%on.png"]:
                        img_path = os.path.join("capturas", img_name)
                        if os.path.exists(img_path):
                            for conf in [0.85, 0.8, 0.75, 0.7]:
                                if pyautogui.locateOnScreen(img_path, region=right_region, confidence=conf) is not None:
                                    found_5 = True
                                    break
                            if found_5:
                                break
                    if found_5:
                        self.log_message("[Clickerbot] Growth rate já está configurado como 5% no painel. Ignorando passos Rate e 5%.")
                        skip_rate_steps = True
                        continue
                except Exception as e:
                    self.log_message(f"[Clickerbot] Erro ao checar Growth rate: {e}")
                    
            self.log_message(f"[Clickerbot] Procurando por '{name}' na tela (timeout: {timeout}s)...")
            
            # Define a região de busca (metade direita para os passos internos da sidebar; tela inteira para Iniciar, Demo e Acumulators)
            search_region = right_region if name not in ["Iniciar", "Demo", "Acumulators"] else None
            
            found = False
            start_time = time.time()
            clicked_fallback = False
            while time.time() - start_time < timeout:
                if not self.bot or not self.bot.running:
                    return
                try:
                    pos = None
                    # Tolerâncias decrescentes de confiança para busca robusta
                    for conf in [0.85, 0.8, 0.75, 0.7, 0.65]:
                        if search_region:
                            pos = pyautogui.locateCenterOnScreen(path, region=search_region, confidence=conf)
                        else:
                            pos = pyautogui.locateCenterOnScreen(path, confidence=conf)
                        if pos is not None:
                            break
                    
                    # Se for a etapa de 5% e não encontramos por imagem, tentamos o fallback relativo ao Rate dropdown
                    if name == "5%" and pos is None and not clicked_fallback and (time.time() - start_time > 1.0):
                        self.log_message("[Clickerbot] Elemento 5% não encontrado por imagem. Tentando fallback de clique relativo ao Rate dropdown...")
                        if rate_pos is None:
                            for conf in [0.85, 0.8, 0.75, 0.7]:
                                rate_pos = pyautogui.locateCenterOnScreen(os.path.join("capturas", "rate.png"), region=right_region, confidence=conf)
                                if rate_pos is not None:
                                    break
                        if rate_pos is not None:
                            pos = pyautogui.Point(rate_pos.x - 180, rate_pos.y + 160)
                            clicked_fallback = True
                            self.log_message(f"[Clickerbot] Utilizando fallback relativo ao Rate em {pos}.")
                    
                    # Se for a etapa de Amount e não encontramos por imagem, tentamos o fallback relativo ao Take profit header
                    if name == "Amount" and pos is None and not clicked_fallback and (time.time() - start_time > 1.0):
                        self.log_message("[Clickerbot] Elemento Amount não encontrado por imagem (possível erro vermelho). Tentando fallback relativo ao Take profit header...")
                        if take_pos is None:
                            for conf in [0.9, 0.85, 0.8]:
                                take_pos = pyautogui.locateCenterOnScreen(os.path.join("capturas", "take.png"), region=right_region, confidence=conf)
                                if take_pos is not None:
                                    break
                        if take_pos is not None:
                            pos = pyautogui.Point(take_pos.x + 80, take_pos.y + 90)
                            clicked_fallback = True
                            self.log_message(f"[Clickerbot] Utilizando fallback relativo ao Take profit header em {pos}.")
                            
                    # Se for a etapa de Save e não encontramos por imagem (botão disabled), tentamos o fallback relativo ao Take profit header
                    if name == "Save" and pos is None and not clicked_fallback and (time.time() - start_time > 1.0):
                        self.log_message("[Clickerbot] Elemento Save não encontrado por imagem (possível botão desativado). Tentando fallback relativo ao Take profit header...")
                        if take_pos is None:
                            for conf in [0.9, 0.85, 0.8]:
                                take_pos = pyautogui.locateCenterOnScreen(os.path.join("capturas", "take.png"), region=right_region, confidence=conf)
                                if take_pos is not None:
                                    break
                        if take_pos is not None:
                            pos = pyautogui.Point(take_pos.x + 80, take_pos.y + 185)
                            clicked_fallback = True
                            self.log_message(f"[Clickerbot] Utilizando fallback relativo ao Take profit header em {pos}.")
                        
                    if pos is not None:
                        if is_amount:
                            # Clica e dá double click para obter foco e selecionar texto
                            pyautogui.click(pos)
                            time.sleep(0.2)
                            pyautogui.doubleClick(pos)
                            time.sleep(0.3)
                            # Limpa o campo
                            for _ in range(5):
                                pyautogui.press('backspace')
                                time.sleep(0.05)
                            for _ in range(5):
                                pyautogui.press('delete')
                                time.sleep(0.05)
                            time.sleep(0.2)
                            # Digita o valor
                            pyautogui.write('1', interval=0.1)
                            time.sleep(0.3)
                            pyautogui.press('enter')
                            time.sleep(0.2)
                            self.log_message(f"[Clickerbot] Elemento '{name}' preenchido com '1' em {pos}.")
                        else:
                            # Clica no centro do elemento encontrado ou posição fallback
                            pyautogui.click(pos)
                            self.log_message(f"[Clickerbot] Elemento '{name}' clicado em {pos}.")
                            
                            if name == "Togle":
                                self.log_message("[Clickerbot] Toggle ativado. Aguardando 2 segundos para focar e preencher Amount...")
                                time.sleep(2.0)
                                
                                # Limpa o campo diretamente (já focado por padrão após ativar o toggle)
                                for _ in range(5):
                                    pyautogui.press('backspace')
                                    time.sleep(0.05)
                                for _ in range(5):
                                    pyautogui.press('delete')
                                    time.sleep(0.05)
                                time.sleep(0.2)
                                
                                # Digita o valor 1 diretamente
                                self.log_message("[Clickerbot] Digitando valor '1' sem clicar...")
                                pyautogui.write('1', interval=0.1)
                                time.sleep(0.5)
                                
                                # Coordenada do botão Save (relativo ao toggle pos)
                                save_pos = pyautogui.Point(pos.x - 130, pos.y + 185)
                                self.log_message(f"[Clickerbot] Clicando em Save em {save_pos}...")
                                pyautogui.click(save_pos)
                                time.sleep(0.5)
                                
                                # Como já realizamos Amount e Save, podemos encerrar o setup com sucesso!
                                self.log_message("[Clickerbot] Configuração concluída com sucesso após o Toggle.")
                                if self.bot:
                                    self.bot.setup_in_progress = False
                                return
                        
                        if name == "Rate":
                            rate_pos = pos
                            
                        found = True
                        time.sleep(1.2)  # pequeno delay para transição visual
                        break
                    
                    # Fallback para abrir o dropdown se for a etapa de Acumulators e já passou 3.5 segundos
                    if name == "Acumulators" and not clicked_fallback and (time.time() - start_time > 3.5):
                        clicked_fallback = True
                        self.log_message("[Clickerbot] Elemento Acumulators não detectado na tela inteira. Tentando abrir dropdown clicando acima de Stake...")
                        try:
                            stake_pos = None
                            for conf in [0.85, 0.8, 0.75, 0.7]:
                                stake_pos = pyautogui.locateCenterOnScreen(os.path.join("capturas", "stake.png"), region=right_region, confidence=conf)
                                if stake_pos is not None:
                                    break
                            if stake_pos is not None:
                                click_pos = (stake_pos.x, stake_pos.y - 65)
                                pyautogui.click(click_pos)
                                self.log_message(f"[Clickerbot] Clicado acima de Stake em {click_pos} para tentar abrir dropdown.")
                        except Exception as e:
                            self.log_message(f"[Clickerbot] Falha no clique de fallback acima de Stake: {e}")
                            
                except Exception:
                    pass
                time.sleep(0.4)
                
            if not found:
                self.log_message(f"[Clickerbot] Elemento '{name}' não encontrado. Avançando para o próximo passo...")
                
        self.log_message("[Clickerbot] Sequência de configuração automática concluída!")
        if self.bot:
            self.bot.setup_in_progress = False

    def btn_stop_clicked(self):
        self.stop_reason = None
        if self.bot:
            self.bot.stop_bot()
            self.bot = None
            
        if self.webview_proc:
            try:
                self.webview_proc.terminate()
                self.webview_proc = None
                self.log_message("Navegador embutido DERIVCLICKER encerrado.")
            except Exception:
                pass
                
        if getattr(self, "execution_mode", None) == "stealth" and hasattr(self, "original_use_api_trading"):
            self.config["deriv_use_api_trading"] = self.original_use_api_trading

        self.lbl_status_value.configure(text="PARADO", text_color=ACCENT_RED)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_next_click.configure(text="Inativo", text_color="gray")
        self._update_overlay_data()

    def btn_panic_clicked(self):
        self.log_message("🚨 BOTÃO DE PÂNICO ACIONADO! Parando o robô imediatamente...")
        self.btn_stop_clicked()

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
        
        if self.webview_proc:
            try:
                self.webview_proc.terminate()
                self.webview_proc = None
                self.log_message("Navegador embutido DERIVCLICKER encerrado.")
            except Exception:
                pass
                
        if getattr(self, "execution_mode", None) == "stealth" and hasattr(self, "original_use_api_trading"):
            self.config["deriv_use_api_trading"] = self.original_use_api_trading

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
                err_msg = f"Erro {e.code}: {desc}"
                self.after(0, lambda msg=err_msg: self._fetch_done_error(msg))
                return
            except Exception as exc:
                err_msg = str(exc)
                self.after(0, lambda msg=err_msg: self._fetch_done_error(msg))
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

    def _test_api_connection(self):
        token = self.settings_entry_api_token.get().strip()
        app_id = self.settings_entry_api_appid.get().strip() or "1098"
        symbol = self.settings_combo_api_symbol.get()
        account_type = self.settings_combo_api_account_type.get().strip().lower() if hasattr(self, "settings_combo_api_account_type") else "demo"
        
        if not token:
            self.lbl_api_status.configure(text="❌ Erro: Insira o Token de Acesso API.", text_color="#ef4444")
            return
            
        self.lbl_api_status.configure(text="⏳ Conectando e autenticando...", text_color="#38bdf8")
        self.btn_api_test.configure(state="disabled")
        
        def run_test():
            from deriv_api_client import DerivApiClient
            client = DerivApiClient(token=token, app_id=app_id, symbol=symbol, account_type=account_type)
            
            auth_success = [False]
            error_msg = ["Tempo esgotado."]
            event = threading.Event()
            
            def on_log(msg):
                if "Erro de autenticação" in msg or "Erro" in msg:
                    error_msg[0] = msg
                elif "Autenticado com sucesso" in msg:
                    auth_success[0] = True
                    event.set()
                elif "Conexão fechada" in msg or "Erro na conexão WS" in msg:
                    event.set()
                    
            client.on_log_cb = on_log
            client.connect()
            
            event.wait(10.0)
            client.disconnect()
            
            if auth_success[0]:
                self.after(0, lambda: self.lbl_api_status.configure(text=f"✅ Conexão bem-sucedida! Saldo: ${client.balance:.2f}", text_color=ACCENT_GREEN))
            else:
                self.after(0, lambda: self.lbl_api_status.configure(text=f"❌ Falha: {error_msg[0]}", text_color="#ef4444"))
                
            self.after(0, lambda: self.btn_api_test.configure(state="normal"))
            
        threading.Thread(target=run_test, daemon=True).start()

    def _on_ai_metrics_received(self, loss, accuracy, samples, device):
        self.after(0, lambda: self._update_ai_metrics_ui(loss, accuracy, samples, device))

    def _update_ai_metrics_ui(self, loss, accuracy, samples, device):
        self.lbl_ai_loss.configure(text=f"{loss:.4f}")
        self.lbl_ai_accuracy.configure(text=f"{accuracy:.1f}%")
        self.lbl_ai_memory.configure(text=str(samples))
        
        if device == "GPU":
            self.lbl_ai_engine.configure(text="GPU (PyTorch)", text_color=ACCENT_GREEN)
            self.btn_install_torch.configure(text="GPU Ativa", state="disabled", fg_color="#10b981")
        elif "PyTorch" in device or device == "cuda" or device == "cpu_pytorch":
            self.lbl_ai_engine.configure(text="CPU (PyTorch)", text_color="#f59e0b")
            self.btn_install_torch.configure(text="GPU Disponível", state="disabled", fg_color="#f59e0b")
        else:
            self.lbl_ai_engine.configure(text="CPU (NumPy)", text_color="#f59e0b")
            self.btn_install_torch.configure(text="Instalar PyTorch (GPU)", state="normal", fg_color=ACCENT_BLUE)

    def _install_torch_async(self):
        self.btn_install_torch.configure(text="Instalando...", state="disabled")
        self.log_message("[IA] Iniciando instalação do PyTorch em background com suporte a GPU/CUDA...")
        
        def run_install():
            import subprocess
            import sys
            try:
                # Instalação do PyTorch usando o executável python correto
                cmd = [sys.executable, "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cu121"]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                self.log_message("[IA] PyTorch instalado com sucesso! Por favor, reinicie o bot para ativar a aceleração por GPU.")
                self.after(0, lambda: self.btn_install_torch.configure(text="Instalado!", fg_color="#10b981"))
            except Exception as e:
                self.log_message(f"[IA] Erro ao instalar PyTorch: {e}")
                self.after(0, lambda: self.btn_install_torch.configure(text="Falhou!", state="normal", fg_color=ACCENT_RED))
                
        threading.Thread(target=run_install, daemon=True).start()

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
        self.update_dashboard_stats()

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
        self.update_dashboard_stats()

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
            in_cooldown = getattr(self.bot, "in_cycle_cooldown", False)
            
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
            elif in_cooldown:
                if self.lbl_status_value.cget("text") != "PAUSADO (CICLO)":
                    self.lbl_status_value.configure(text="PAUSADO (CICLO)", text_color=ACCENT_YELLOW)
                    
                elapsed = time.time() - self.start_time
                hours, remainder = divmod(int(elapsed), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.lbl_timer.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                
                rem = getattr(self, "remaining_schedule_time", 0)
                if rem > 0:
                    hours, remainder = divmod(int(rem), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    timer_str = f"Ciclo em {hours:02d}h {minutes:02d}m {seconds:02d}s" if hours > 0 else f"Ciclo em {minutes:02d}m {seconds:02d}s"
                    self.lbl_next_click.configure(text=timer_str, text_color=ACCENT_YELLOW)
                else:
                    self.lbl_next_click.configure(text="Retomando...", text_color=ACCENT_GREEN)
            else:
                mode = self.config.get("mode", "fixed")
                if mode == "adaptive":
                    phase = getattr(self.bot, "adaptive_phase", "observation")
                    if phase == "observation":
                        self.lbl_status_value.configure(text="OBSERVANDO", text_color=ACCENT_YELLOW)
                        rem = getattr(self, "remaining_schedule_time", 0.0)
                        minutes, seconds = divmod(int(rem), 60)
                        self.lbl_next_click.configure(text=f"Obs: {minutes:02d}m {seconds:02d}s", text_color=ACCENT_YELLOW)
                    else:
                        self.lbl_status_value.configure(text="EXECUTANDO (IA)", text_color=ACCENT_GREEN)
                        strat = getattr(self.bot, "adaptive_strategy", {})
                        conf_val = strat.get("confidence", 0.0)
                        text_strat = strat.get("text", "Operando")
                        self.lbl_next_click.configure(text=f"{text_strat} ({conf_val:.1f}%)", text_color=ACCENT_GREEN)
                else:
                    if self.lbl_status_value.cget("text") not in ["EXECUTANDO", "AGENDADO"]:
                        self.lbl_status_value.configure(text="EXECUTANDO", text_color=ACCENT_GREEN)
                
                elapsed = time.time() - self.start_time
                hours, remainder = divmod(int(elapsed), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.lbl_timer.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                
                if mode != "adaptive":
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
            
        # Sincroniza widgets com a config se o bot alterar dinamicamente (ex: no escaneamento automático)
        if self.bot and self.bot.running:
            # Sincroniza Ativo
            current_symbol = self.config.get("deriv_symbol", "R_100")
            if hasattr(self, "settings_combo_api_symbol") and self.settings_combo_api_symbol.winfo_exists():
                if self.settings_combo_api_symbol.get() != current_symbol:
                    self.settings_combo_api_symbol.set(current_symbol)
            # Sincroniza Duração
            if hasattr(self, "settings_entry_rf_duration") and self.settings_entry_rf_duration.winfo_exists():
                config_val = str(self.config.get("deriv_rf_duration_value", 5))
                if self.settings_entry_rf_duration.get() != config_val:
                    self.settings_entry_rf_duration.delete(0, "end")
                    self.settings_entry_rf_duration.insert(0, config_val)
            # Sincroniza Unidade
            if hasattr(self, "settings_combo_rf_unit") and self.settings_combo_rf_unit.winfo_exists():
                config_unit = self.config.get("deriv_rf_duration_unit", "t")
                unit_label = "Ticks" if config_unit == "t" else ("Segundos" if config_unit == "s" else "Minutos")
                if self.settings_combo_rf_unit.get() != unit_label:
                    self.settings_combo_rf_unit.set(unit_label)
            
        # Repassa alteracoes ao overlay em tempo real
        self._update_overlay_data()
        
        # Atualiza estatísticas do dashboard de forma lenta (a cada 5 segundos)
        if not hasattr(self, "_slow_update_counter"):
            self._slow_update_counter = 0
        self._slow_update_counter += 1
        if self._slow_update_counter >= 50:
            self._slow_update_counter = 0
            self.update_dashboard_stats()
        
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
            self.overlay.on_panic_cb = self.btn_panic_clicked
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
        
        mode = self.config.get("mode", "fixed")
        adaptive_phase = getattr(self.bot, "adaptive_phase", "observation") if self.bot else "observation"
        adaptive_rule = "N/A"
        adaptive_conf = 0.0
        ai_loss = 0.0
        ai_accuracy = 0.0
        ai_samples = 0
        ai_device = "CPU (NumPy)"
        if mode == "ai":
            if self.bot:
                samples_len = len(self.bot.ai_replay.memory) if hasattr(self.bot, "ai_replay") else 0
                ai_samples = samples_len
                min_samples = self.config.get("ai_min_samples_start", 500)
                if samples_len < min_samples:
                    adaptive_phase = f"Treinando ({samples_len}/{min_samples})"
                else:
                    adaptive_phase = "Operando"
                
                acc = self.bot.ai_replay.get_accuracy(self.bot.ai) if hasattr(self.bot, "ai_replay") else 0.0
                adaptive_rule = f"Acurácia: {acc:.1f}%"
                adaptive_conf = getattr(self.bot, "ai_prediction_confidence", 0.0) * 100.0
                ai_loss = getattr(self.bot, "ai_loss", 0.0)
                ai_accuracy = acc
                
                if hasattr(self.bot, "ai") and self.bot.ai:
                    if getattr(self.bot.ai, "engine", "numpy") == "pytorch":
                        if getattr(self.bot.ai, "device", "cpu") == "cuda":
                            ai_device = "GPU"
                        else:
                            ai_device = "CPU (PyTorch)"
                    else:
                        ai_device = "CPU (NumPy)"
        elif self.bot and hasattr(self.bot, "adaptive_strategy"):
            strat = getattr(self.bot, "adaptive_strategy", {})
            adaptive_rule = strat.get("text", "N/A")
            adaptive_conf = strat.get("confidence", 0.0)

        deriv_api_status = "Desconectado"
        current_balance = 0.0
        if self.config.get("deriv_use_api_trading", False):
            if self.bot and getattr(self.bot, "api_client", None):
                client = self.bot.api_client
                current_balance = client.balance
                if client.connected:
                    if client.authorized:
                        deriv_api_status = f"Autorizado ✅ (${client.balance:.2f})"
                    else:
                        deriv_api_status = "Autenticando..."
                else:
                    deriv_api_status = "Conectando..."
            else:
                deriv_api_status = "Desconectado"
        else:
            deriv_api_status = "Inativa (OCR)"

        # Collect latency, market trend and contract mode details
        latency_ms = 0
        market_trend = "LATERAL ⚖️"
        ai_reasoning_status = "Inativo"
        ai_reasoning_explanation = "O robô não está ativo ou não iniciou a análise neural."
        contract_mode = "accumulator"
        predicted_barrier = None
        last_digit = None
        expiration_str = "N/A"
        ai_intelligence_str = "Lvl 1 (Iniciando)"
        
        recent_ops = []
        if self.bot:
            recent_ops = getattr(self.bot, "recent_ops", [])
            if getattr(self.bot, "api_client", None):
                latency_ms = getattr(self.bot.api_client, "latency_ms", 0)
            market_trend = getattr(self.bot, "market_trend", "LATERAL ⚖️")
            ai_reasoning_status = getattr(self.bot, "ai_reasoning_status", "Inativo")
            ai_reasoning_explanation = getattr(self.bot, "ai_reasoning_explanation", "Aguardando...")
            contract_mode = self.bot.config.get("deriv_contract_mode", "accumulator")
            predicted_barrier = getattr(self.bot, "predicted_barrier", None)
            if hasattr(self.bot, "ai_tick_digits") and len(self.bot.ai_tick_digits) > 0:
                last_digit = self.bot.ai_tick_digits[-1]
                
            if contract_mode in ["matches", "differs"]:
                expiration_str = "1 Tick (Próximo)"
            elif contract_mode == "rise_fall":
                dur_val = getattr(self.bot, "last_dynamic_duration", None)
                is_dynamic = True
                if dur_val is None:
                    dur_val = self.bot.config.get("deriv_rf_duration_value", 5)
                    is_dynamic = False
                dur_unit = self.bot.config.get("deriv_rf_duration_unit", "t")
                unit_label = "Ticks" if dur_unit == "t" else ("Segs" if dur_unit == "s" else "Mins")
                suffix = " ⚡" if is_dynamic else ""
                expiration_str = f"{dur_val} {unit_label}{suffix}"
            else:
                expiration_str = "Dinâmico (Acu)"

            # Calcula nível de aprendizado / QI
            ai_training_iterations = getattr(self.bot, "ai_training_iterations", 0)
            level = int(ai_training_iterations / 50) + 1
            status_desc = "Básico 👶" if level < 5 else ("Médio 🧠" if level < 15 else ("Avançado 🚀" if level < 30 else "Cérebro 🌌"))
            ai_intelligence_str = f"Lvl {level} ({status_desc})"

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
            next_click_str=next_click_str,
            mode=mode,
            adaptive_phase=adaptive_phase,
            adaptive_rule=adaptive_rule,
            adaptive_conf=adaptive_conf,
            deriv_api_status=deriv_api_status,
            ai_loss=ai_loss,
            ai_accuracy=ai_accuracy,
            ai_samples=ai_samples,
            current_balance=current_balance,
            ai_device=ai_device,
            latency_ms=latency_ms,
            market_trend=market_trend,
            ai_reasoning_status=ai_reasoning_status,
            ai_reasoning_explanation=ai_reasoning_explanation,
            contract_mode=contract_mode,
            predicted_barrier=predicted_barrier,
            last_digit=last_digit,
            expiration_str=expiration_str,
            ai_intelligence_str=ai_intelligence_str,
            recent_ops=recent_ops
        )

    def _show_main_window(self):
        if hasattr(self, "splash") and self.splash.winfo_exists():
            self.splash.destroy()
        self.deiconify()
        self.lift()
        self.focus_force()

    def destroy(self):
        # Finaliza threads ao fechar a janela
        self.tg_listener_running = False
        if self.bot:
            self.bot.stop_bot()
        if self.webview_proc:
            try:
                self.webview_proc.terminate()
            except Exception:
                pass
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        super().destroy()
