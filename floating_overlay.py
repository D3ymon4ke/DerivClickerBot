import customtkinter as ctk
import tkinter as tk
import os
from PIL import Image

# Tema de Cores do Bot
BG_MAIN = "#000000"
CARD_BG = "#1e293b"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"
ACCENT_YELLOW = "#f59e0b"

class FloatingOverlay(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Atributos de Janela Overlay
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.82)
        
        # Desabilita o frame do SO
        self.resizable(False, False)
        
        # Dimensoes e Posicionamento Inicial (Canto Superior Direito por padrao)
        self.width = 260
        self.height = 490
        
        screen_w = self.winfo_screenwidth()
        start_x = screen_w - self.width - 50
        start_y = 50
        self.geometry(f"{self.width}x{self.height}+{start_x}+{start_y}")
        
        # Draggable logic
        self.drag_x = 0
        self.drag_y = 0
        
        # Frame Principal com bordas arredondadas e borda slate
        self.main_frame = ctk.CTkFrame(self, fg_color=BG_MAIN, border_color="#334155", border_width=1.5, corner_radius=12)
        self.main_frame.pack(fill="both", expand=True)
        
        # Header / Barra de Arraste
        self.header = ctk.CTkFrame(self.main_frame, fg_color=CARD_BG, height=35, corner_radius=10)
        self.header.pack(fill="x", padx=2, pady=(2, 0))
        self.header.pack_propagate(False)
        
        # Eventos de Arraste (arrastar clicando em qualquer lugar do widget ou no header)
        for widget in [self, self.main_frame, self.header]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            
        # Efeito premium de transparência com hover
        self.bind("<Enter>", lambda e: self.attributes("-alpha", 0.98))
        self.bind("<Leave>", lambda e: self.attributes("-alpha", 0.82))
        
        # Titulo do Header
        self.lbl_title = ctk.CTkLabel(self.header, text="DERIV CLICKER OVERLAY", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8")
        self.lbl_title.pack(side="left", padx=12)
        
        # Botao Fechar (oculta o overlay)
        self.btn_close = ctk.CTkButton(self.header, text="×", width=22, height=22, fg_color="transparent", hover_color="#ef4444", text_color="#94a3b8", font=ctk.CTkFont(size=16, weight="bold"), command=self.withdraw)
        self.btn_close.pack(side="right", padx=6)
        
        # Logo no Topo do Overlay (como banner)
        logo_path = "imagens/logo.png"
        if not os.path.exists(logo_path):
            logo_path = "capturas/logo.png"
            
        if os.path.exists(logo_path):
            try:
                with Image.open(logo_path) as img:
                    orig_w, orig_h = img.size
                    aspect = orig_h / orig_w
                    logo_w = 256
                    logo_h = int(logo_w * aspect)
                
                self.logo_img_pil = Image.open(logo_path)
                self.logo_img = ctk.CTkImage(
                    light_image=self.logo_img_pil,
                    dark_image=self.logo_img_pil,
                    size=(logo_w, logo_h)
                )
                self.lbl_logo = ctk.CTkLabel(self.main_frame, image=self.logo_img, text="", fg_color="transparent")
                self.lbl_logo.pack(fill="x", padx=2, pady=(2, 5))
            except Exception as e:
                print(f"[Overlay] Erro ao carregar logo: {e}")
                
        # --- CORPO DO OVERLAY ---
        body = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        
        # Status Row
        row_status = ctk.CTkFrame(body, fg_color="transparent", height=24)
        row_status.pack(fill="x", pady=(0, 5))
        self.status_dot = ctk.CTkLabel(row_status, text="●", font=ctk.CTkFont(size=18), text_color=ACCENT_RED)
        self.status_dot.pack(side="left", padx=(5, 5))
        self.lbl_status = ctk.CTkLabel(row_status, text="PARADO", font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT_RED)
        self.lbl_status.pack(side="left")
        
        # Divididor
        div = ctk.CTkFrame(body, fg_color="#334155", height=1)
        div.pack(fill="x", pady=(0, 5))
        
        # Metricas Principais (Grid compacta)
        grid_frame = ctk.CTkFrame(body, fg_color="transparent")
        grid_frame.pack(fill="x")
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        
        # Metricas Esquerda
        self.lbl_entradas = self._create_metric_lbl(grid_frame, "Entradas", "0", row=0, col=0)
        self.lbl_wins = self._create_metric_lbl(grid_frame, "Wins", "0", row=1, col=0, val_color=ACCENT_GREEN)
        self.lbl_losses = self._create_metric_lbl(grid_frame, "Losses", "0", row=2, col=0, val_color=ACCENT_RED)
        
        # Metricas Direita
        self.lbl_assert = self._create_metric_lbl(grid_frame, "Win Rate", "0.0%", row=0, col=1, val_color=ACCENT_YELLOW)
        self.lbl_win_streak = self._create_metric_lbl(grid_frame, "Max Win Strk", "0", row=1, col=1, val_color=ACCENT_GREEN)
        self.lbl_loss_streak = self._create_metric_lbl(grid_frame, "Max Loss Strk", "0", row=2, col=1, val_color=ACCENT_RED)
        
        # Divididor 2
        div2 = ctk.CTkFrame(body, fg_color="#334155", height=1)
        div2.pack(fill="x", pady=5)
        
        # Info Financeira e Barra de Progresso
        self.lbl_finance_title = ctk.CTkLabel(body, text="LUCRO / META", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray")
        self.lbl_finance_title.pack(anchor="w")
        
        self.lbl_finance_value = ctk.CTkLabel(body, text="$0.00 / $10.00", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_finance_value.pack(anchor="w", pady=(2, 4))
        
        self.progress = ctk.CTkProgressBar(body, height=6, progress_color=ACCENT_GREEN)
        self.progress.pack(fill="x", pady=(2, 6))
        self.progress.set(0.0)
        
        # Divididor 3
        div3 = ctk.CTkFrame(body, fg_color="#334155", height=1)
        div3.pack(fill="x", pady=4)
        
        # Tempo de Execução e Próximo Clique
        row_time = ctk.CTkFrame(body, fg_color="transparent")
        row_time.pack(fill="x")
        
        ctk.CTkLabel(row_time, text="Tempo:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_timer = ctk.CTkLabel(row_time, text="00:00:00", font=ctk.CTkFont(size=11, weight="bold"), text_color="#e2e8f0")
        self.lbl_timer.pack(side="right")
        
        row_next = ctk.CTkFrame(body, fg_color="transparent")
        row_next.pack(fill="x", pady=(2, 0))
        
        ctk.CTkLabel(row_next, text="Próximo Clique:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_next_click = ctk.CTkLabel(row_next, text="Inativo", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_next_click.pack(side="right")
        
    def _create_metric_lbl(self, parent, label, initial_val, row, col, val_color="#e2e8f0"):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=row, column=col, sticky="w", pady=2)
        
        ctk.CTkLabel(container, text=f"{label}: ", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        val_lbl = ctk.CTkLabel(container, text=initial_val, font=ctk.CTkFont(size=11, weight="bold"), text_color=val_color)
        val_lbl.pack(side="left")
        return val_lbl
        
    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        
    def drag(self, event):
        deltax = event.x - self.drag_x
        deltay = event.y - self.drag_y
        new_x = self.winfo_x() + deltax
        new_y = self.winfo_y() + deltay
        self.geometry(f"+{new_x}+{new_y}")
        
    def update_data(self, status, clicks, wins, losses, rate, win_streak, loss_streak, current_profit, target_profit, finance_mode, free_entries, timer_str, next_click_str):
        # 1. Status
        if status == "EXECUTANDO":
            self.status_dot.configure(text_color=ACCENT_GREEN)
            self.lbl_status.configure(text="EXECUTANDO", text_color=ACCENT_GREEN)
        elif status == "AGENDADO":
            self.status_dot.configure(text_color=ACCENT_YELLOW)
            self.lbl_status.configure(text="AGENDADO", text_color=ACCENT_YELLOW)
        else:
            self.status_dot.configure(text_color=ACCENT_RED)
            self.lbl_status.configure(text="PARADO", text_color=ACCENT_RED)
            
        # 2. Metricas
        self.lbl_entradas.configure(text=str(clicks))
        self.lbl_wins.configure(text=str(wins))
        self.lbl_losses.configure(text=str(losses))
        self.lbl_assert.configure(text=f"{rate:.1f}%")
        self.lbl_win_streak.configure(text=str(win_streak))
        self.lbl_loss_streak.configure(text=str(loss_streak))
        
        # 3. Financeiro e Progresso
        color = ACCENT_GREEN if current_profit >= 0 else ACCENT_RED
        
        if finance_mode == "target":
            self.lbl_finance_title.configure(text="SALDO FINANCEIRO (META)")
            self.lbl_finance_value.configure(text=f"${current_profit:.2f} / ${target_profit:.2f}", text_color=color)
            if target_profit > 0:
                prog = max(0.0, min(1.0, current_profit / target_profit))
            else:
                prog = 0.0
        else:
            self.lbl_finance_title.configure(text="SALDO FINANCEIRO (ENTRADAS)")
            self.lbl_finance_value.configure(text=f"${current_profit:.2f} ({clicks} / {free_entries} Entr.)", text_color=color)
            if free_entries > 0:
                prog = max(0.0, min(1.0, clicks / free_entries))
            else:
                prog = 0.0
                
        self.progress.set(prog)
        
        # 4. Timer e Proximo Clique
        self.lbl_timer.configure(text=timer_str)
        self.lbl_next_click.configure(text=next_click_str)
