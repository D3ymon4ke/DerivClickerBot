import customtkinter as ctk
import tkinter as tk
import os
import random
import math
from PIL import Image

# Tema de Cores do Bot
BG_MAIN = "#000000"
CARD_BG = "#1e293b"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"
ACCENT_YELLOW = "#f59e0b"

class OverlayParticle:
    def __init__(self, x, y, dx, dy, color, size, life, decay, gravity=0.0):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = color
        self.size = size
        self.life = life       # Começa em 1.0 e decai até 0.0
        self.decay = decay     # Fração subtraída a cada frame
        self.gravity = gravity

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
        
        # Canvas do Status
        self.status_canvas = tk.Canvas(body, height=35, bg=BG_MAIN, highlightthickness=0)
        self.status_canvas.pack(fill="x", pady=(0, 5))
        self.status_canvas.bind("<Button-1>", self.start_drag)
        self.status_canvas.bind("<B1-Motion>", self.drag)
        
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
        
        # Info Financeira e Barra de Progresso Customizada (Canvas)
        self.lbl_finance_title = ctk.CTkLabel(body, text="LUCRO / META", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray")
        self.lbl_finance_title.pack(anchor="w")
        
        self.lbl_finance_value = ctk.CTkLabel(body, text="$0.00 / $10.00", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_finance_value.pack(anchor="w", pady=(2, 4))
        
        self.progress_canvas = tk.Canvas(body, height=22, bg=BG_MAIN, highlightthickness=0)
        self.progress_canvas.pack(fill="x", pady=(2, 6))
        self.progress_canvas.bind("<Button-1>", self.start_drag)
        self.progress_canvas.bind("<B1-Motion>", self.drag)
        
        # --- ESTADO DE ANIMAÇÃO E PARTÍCULAS ---
        self.status_particles = []
        self.progress_particles = []
        self.progress_val = 0.0
        self.status_text = "PARADO"
        self.status_rgb = (239, 68, 68)
        self.last_status = None
        self.status_pulse = 0.0
        self.status_pulse_dir = 1
        
        # Inicia o loop de animação
        self.update_loop()
        
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
        # 1. Status and Color Mapping
        new_status = status.upper()
        
        if new_status == "EXECUTANDO":
            self.status_text = "EXECUTANDO"
            self.status_rgb = (16, 185, 129)
        elif new_status == "AGENDADO":
            self.status_text = "AGENDADO"
            self.status_rgb = (245, 158, 11)
        elif new_status in ["STOP WIN", "META BATIDA"]:
            self.status_text = "STOP WIN"
            self.status_rgb = (16, 185, 129)
        elif new_status == "STOP LOSS":
            self.status_text = "STOP LOSS"
            self.status_rgb = (239, 68, 68)
        elif new_status in ["LIMIT ENTRADAS", "LIMITE ENTRADAS"]:
            self.status_text = "LIMIT ENTRADAS"
            self.status_rgb = (59, 130, 246)
        else:
            self.status_text = "PARADO"
            self.status_rgb = (239, 68, 68)
            
        # Trigger burst explosion on state transition
        canvas_w = self.status_canvas.winfo_width()
        if canvas_w < 10:
            canvas_w = 236
            
        if self.status_text != self.last_status:
            # Transition occurred!
            if self.status_text == "STOP WIN":
                # Spawn celebratory victory fountain burst!
                for _ in range(45):
                    px = canvas_w / 2
                    py = 17
                    a = random.uniform(-math.pi * 0.8, -math.pi * 0.2) # pointing upwards
                    s = random.uniform(1.2, 4.0)
                    pdx = math.cos(a) * s
                    pdy = math.sin(a) * s - 0.5
                    decay = random.uniform(0.015, 0.035)
                    # Mix of green and gold
                    rgb = (16, 185, 129) if random.random() < 0.6 else (251, 191, 36)
                    p = OverlayParticle(px, py, pdx, pdy, rgb, random.uniform(2.0, 4.5), 1.0, decay, gravity=0.06)
                    self.status_particles.append(p)
            elif self.status_text == "STOP LOSS":
                # Spawn loss ember burst!
                for _ in range(35):
                    px = canvas_w / 2
                    py = 10
                    a = random.uniform(0.1 * math.pi, 0.9 * math.pi) # pointing downwards
                    s = random.uniform(1.0, 3.0)
                    pdx = math.cos(a) * s
                    pdy = math.sin(a) * s
                    decay = random.uniform(0.02, 0.045)
                    p = OverlayParticle(px, py, pdx, pdy, (239, 68, 68), random.uniform(1.8, 3.8), 1.0, decay, gravity=0.07)
                    self.status_particles.append(p)
            self.last_status = self.status_text
            
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
                
        self.progress_val = prog
        
        # 4. Timer e Proximo Clique
        self.lbl_timer.configure(text=timer_str)
        self.lbl_next_click.configure(text=next_click_str)

    # --- CANVAS & ANIMATION SYSTEM ---
    def update_loop(self):
        try:
            if self.winfo_exists():
                self._update_physics()
                self._draw_status_canvas()
                self._draw_progress_canvas()
                self.after(25, self.update_loop) # ~40 FPS
        except Exception as e:
            print(f"[Overlay] Erro no loop de animação: {e}")

    def _update_physics(self):
        # 1. Update status pulse
        self.status_pulse += 0.05 * self.status_pulse_dir
        if self.status_pulse >= 1.0:
            self.status_pulse = 1.0
            self.status_pulse_dir = -1
        elif self.status_pulse <= 0.0:
            self.status_pulse = 0.0
            self.status_pulse_dir = 1
            
        # 2. Update status particles
        for p in self.status_particles:
            p.dy += p.gravity
            p.x += p.dx
            p.y += p.dy
            p.life -= p.decay
        self.status_particles = [p for p in self.status_particles if p.life > 0.0]
        
        # 3. Update progress particles
        for p in self.progress_particles:
            p.dy += p.gravity
            p.x += p.dx
            p.y += p.dy
            p.life -= p.decay
        self.progress_particles = [p for p in self.progress_particles if p.life > 0.0]
        
        # 4. Spawners based on state
        canvas_w = self.status_canvas.winfo_width()
        if canvas_w < 10:
            canvas_w = 236
            
        if self.status_text in ["EXECUTANDO", "AGENDADO"]:
            # Spawn fireflies
            if random.random() < 0.25:
                px = random.uniform(10, canvas_w - 10)
                py = 35
                pdx = random.uniform(-0.3, 0.3)
                pdy = random.uniform(-0.8, -0.3)
                decay = random.uniform(0.015, 0.03)
                p = OverlayParticle(px, py, pdx, pdy, self.status_rgb, random.uniform(1.5, 3.0), 1.0, decay)
                self.status_particles.append(p)
                
        elif self.status_text == "STOP WIN":
            # Continuous celebratory sparkles
            if random.random() < 0.4:
                px = random.uniform(canvas_w // 2 - 40, canvas_w // 2 + 40)
                py = random.uniform(5, 25)
                pdx = random.uniform(-0.5, 0.5)
                pdy = random.uniform(-1.0, 0.2)
                # Green/gold mix
                rgb = (16, 185, 129) if random.random() < 0.6 else (251, 191, 36)
                p = OverlayParticle(px, py, pdx, pdy, rgb, random.uniform(1.5, 3.5), 1.0, random.uniform(0.02, 0.05), gravity=0.03)
                self.status_particles.append(p)
                
        elif self.status_text == "STOP LOSS":
            # Continuous falling embers
            if random.random() < 0.3:
                px = random.uniform(canvas_w // 2 - 40, canvas_w // 2 + 40)
                py = random.uniform(5, 20)
                pdx = random.uniform(-0.3, 0.3)
                pdy = random.uniform(0.1, 0.8)
                p = OverlayParticle(px, py, pdx, pdy, (239, 68, 68), random.uniform(1.5, 3.0), 1.0, random.uniform(0.03, 0.06), gravity=0.04)
                self.status_particles.append(p)
                
        # 5. Progress Bar tip particle emitter
        prog_w = self.progress_canvas.winfo_width()
        if prog_w < 10:
            prog_w = 236
        bar_width = prog_w - 10
        active_x = 5 + int(bar_width * self.progress_val)
        y = 11
        
        if self.progress_val > 0.0:
            tip_rgb = self.status_rgb
            for _ in range(random.randint(1, 2)):
                pdx = random.uniform(-1.8, 0.2)
                pdy = random.uniform(-0.8, 0.8)
                decay = random.uniform(0.03, 0.07)
                p = OverlayParticle(active_x, y, pdx, pdy, tip_rgb, random.uniform(1.5, 3.5), 1.0, decay, gravity=0.02)
                self.progress_particles.append(p)

    def _draw_status_canvas(self):
        canvas = self.status_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 35
            
        cx = w / 2
        cy = h / 2
        
        # Draw particles behind the text
        for p in self.status_particles:
            color = self.get_fade_color(p.color, p.life)
            r = p.size
            canvas.create_oval(p.x - r, p.y - r, p.x + r, p.y + r, fill=color, outline="")
            
        # Pulsing neon glow for the text
        glow_factor = 0.2 + 0.4 * self.status_pulse
        glow_rgb = (
            int(self.status_rgb[0] * glow_factor),
            int(self.status_rgb[1] * glow_factor),
            int(self.status_rgb[2] * glow_factor)
        )
        glow_hex = f"#{glow_rgb[0]:02x}{glow_rgb[1]:02x}{glow_rgb[2]:02x}"
        
        text = self.status_text
        font_glow = ctk.CTkFont(size=14, weight="bold")
        font_core = ctk.CTkFont(size=13, weight="bold")
        
        # Draw neon offsets
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            canvas.create_text(cx + dx, cy + dy, text=text, fill=glow_hex, font=font_glow)
            
        # Core text
        core_hex = f"#{self.status_rgb[0]:02x}{self.status_rgb[1]:02x}{self.status_rgb[2]:02x}"
        canvas.create_text(cx, cy, text=text, fill=core_hex, font=font_core)

    def _draw_progress_canvas(self):
        canvas = self.progress_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 22
            
        bar_w = w - 10
        start_x = 5
        end_x = 5 + bar_w
        active_x = 5 + int(bar_w * self.progress_val)
        y = h / 2
        
        # Draw track
        canvas.create_line(start_x, y, end_x, y, fill="#1e293b", width=8, capstyle="round")
        canvas.create_line(start_x, y, end_x, y, fill="#334155", width=2, capstyle="round")
        
        if self.progress_val > 0.0:
            # Glow layers
            # 15% brightness
            glow15_rgb = (int(self.status_rgb[0] * 0.15), int(self.status_rgb[1] * 0.15), int(self.status_rgb[2] * 0.15))
            glow15_hex = f"#{glow15_rgb[0]:02x}{glow15_rgb[1]:02x}{glow15_rgb[2]:02x}"
            canvas.create_line(start_x, y, active_x, y, fill=glow15_hex, width=12, capstyle="round")
            
            # 40% brightness
            glow40_rgb = (int(self.status_rgb[0] * 0.4), int(self.status_rgb[1] * 0.4), int(self.status_rgb[2] * 0.4))
            glow40_hex = f"#{glow40_rgb[0]:02x}{glow40_rgb[1]:02x}{glow40_rgb[2]:02x}"
            canvas.create_line(start_x, y, active_x, y, fill=glow40_hex, width=8, capstyle="round")
            
            # 70% brightness
            glow70_rgb = (int(self.status_rgb[0] * 0.7), int(self.status_rgb[1] * 0.7), int(self.status_rgb[2] * 0.7))
            glow70_hex = f"#{glow70_rgb[0]:02x}{glow70_rgb[1]:02x}{glow70_rgb[2]:02x}"
            canvas.create_line(start_x, y, active_x, y, fill=glow70_hex, width=5, capstyle="round")
            
            # Core line
            core_hex = f"#{self.status_rgb[0]:02x}{self.status_rgb[1]:02x}{self.status_rgb[2]:02x}"
            canvas.create_line(start_x, y, active_x, y, fill=core_hex, width=2, capstyle="round")
            
        # Draw progress particles
        for p in self.progress_particles:
            color = self.get_fade_color(p.color, p.life)
            r = p.size
            canvas.create_oval(p.x - r, p.y - r, p.x + r, p.y + r, fill=color, outline="")

    def get_fade_color(self, rgb, life):
        r, g, b = rgb
        factor = max(0.0, min(1.0, life))
        nr = int(r * factor)
        ng = int(g * factor)
        nb = int(b * factor)
        return f"#{nr:02x}{ng:02x}{nb:02x}"
