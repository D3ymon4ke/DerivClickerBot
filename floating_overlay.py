import customtkinter as ctk
import tkinter as tk
import os
import random
import math
import datetime
import time
from PIL import Image

# Tema de Cores do Bot
BG_MAIN = "#05070c"
CARD_BG = "#0f172a"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#f43f5e"
ACCENT_BLUE = "#38bdf8"
ACCENT_YELLOW = "#fbbf24"

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
        self.width = 1080
        self.height = 840
        
        screen_w = self.winfo_screenwidth()
        start_x = screen_w - self.width - 50
        start_y = 50
        self.geometry(f"{self.width}x{self.height}+{start_x}+{start_y}")
        
        # Draggable logic
        self.drag_x = 0
        self.drag_y = 0
        self.on_panic_cb = None
        
        # Frame Principal com bordas arredondadas e borda slate
        self.main_frame = ctk.CTkFrame(self, width=310, fg_color=BG_MAIN, border_color="#334155", border_width=1.5, corner_radius=12)
        self.main_frame.pack(side="left", fill="both", expand=False)
        self.main_frame.pack_propagate(False)

        # --- SIDEBAR FRAME (PAINEL ADICIONAL RECOLHÍVEL) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=290, fg_color=BG_MAIN, border_color="#334155", border_width=1.5, corner_radius=12)
        self.sidebar_frame.pack(side="left", fill="both", expand=False, padx=(2, 0))
        self.sidebar_frame.pack_propagate(False)
        self.sidebar_expanded = True

        # --- AI REASONING PANEL (TERCEIRO PAINEL RECOLHÍVEL) ---
        self.ai_reasoning_frame = ctk.CTkFrame(self, width=480, fg_color=BG_MAIN, border_color="#334155", border_width=1.5, corner_radius=12)
        self.ai_reasoning_frame.pack(side="left", fill="both", expand=False, padx=(2, 0))
        self.ai_reasoning_frame.pack_propagate(False)
        self.ai_reasoning_expanded = True
        
        # AI Reasoning Header
        self.ai_reasoning_header = ctk.CTkFrame(self.ai_reasoning_frame, fg_color=CARD_BG, height=35, corner_radius=10)
        self.ai_reasoning_header.pack(fill="x", padx=2, pady=(2, 0))
        self.ai_reasoning_header.pack_propagate(False)
        
        for widget in [self.ai_reasoning_frame, self.ai_reasoning_header]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            
        ctk.CTkLabel(self.ai_reasoning_header, text="INSIGHTS & COGNIÇÃO IA", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_BLUE).pack(side="left", padx=12)
        
        # AI Reasoning Body
        ai_body = ctk.CTkFrame(self.ai_reasoning_frame, fg_color="transparent")
        ai_body.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        
        # Status de Decisão
        ctk.CTkLabel(ai_body, text="STATUS DE COGNIÇÃO", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w")
        self.lbl_ai_reasoning_status_val = ctk.CTkLabel(ai_body, text="INATIVO", font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_ai_reasoning_status_val.pack(anchor="w", pady=(0, 10))
        
        # Raciocínio (Explicação)
        ctk.CTkLabel(ai_body, text="PENSAMENTO DA IA / EXPLICAÇÃO", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w")
        
        self.txt_ai_reasoning_explanation = ctk.CTkTextbox(
            ai_body,
            height=190,
            fg_color=CARD_BG,
            border_color="#334155",
            border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#e2e8f0",
            wrap="word"
        )
        self.txt_ai_reasoning_explanation.pack(fill="x", pady=(2, 12))
        self.txt_ai_reasoning_explanation.insert("1.0", "Aguardando dados da IA...")
        self.txt_ai_reasoning_explanation.configure(state="disabled")
        
        # Contexto Técnico
        ctk.CTkLabel(ai_body, text="MÉTRICAS DO CONTEXTO", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w", pady=(5, 2))
        
        stats_ai_reasoning = ctk.CTkFrame(ai_body, fg_color="transparent")
        stats_ai_reasoning.pack(fill="x", pady=2)
        stats_ai_reasoning.grid_columnconfigure(0, weight=1)
        stats_ai_reasoning.grid_columnconfigure(1, weight=1)
        
        self.lbl_reasoning_trend_val = self._create_sidebar_stat(stats_ai_reasoning, "Tendência Atual", "LATERAL ⚖️", 0, 0)
        self.lbl_reasoning_conf_val = self._create_sidebar_stat(stats_ai_reasoning, "Confiança Neural", "0.0%", 0, 1, val_color=ACCENT_YELLOW)
        self.lbl_reasoning_risk_val = self._create_sidebar_stat(stats_ai_reasoning, "Risco Calculado", "MÍNIMO 🟢", 1, 0, val_color=ACCENT_GREEN)
        self.lbl_reasoning_mode_val = self._create_sidebar_stat(stats_ai_reasoning, "Modalidade", "ACCUMULATOR", 1, 1, val_color=ACCENT_BLUE)
        self.lbl_reasoning_target_val = self._create_sidebar_stat(stats_ai_reasoning, "Dígito Alvo", "N/A", 2, 0, val_color=ACCENT_YELLOW)
        self.lbl_reasoning_last_digit_val = self._create_sidebar_stat(stats_ai_reasoning, "Último Dígito", "N/A", 2, 1, val_color="#e2e8f0")
        self.lbl_reasoning_expiration_val = self._create_sidebar_stat(stats_ai_reasoning, "Expiração", "N/A", 3, 0, val_color="#e2e8f0")
        self.lbl_reasoning_intelligence_val = self._create_sidebar_stat(stats_ai_reasoning, "Nível IA / QI", "Lvl 1 (Iniciando)", 3, 1, val_color=ACCENT_GREEN)
        self.profit_history = []
        self.recent_operations = []
        self.last_wins_count = 0
        self.last_losses_count = 0
        self.last_profit_value = 0.0
        self.initial_balance = 0.0
        self.initialized_counts = False
        
        # Sidebar Header
        self.sb_header = ctk.CTkFrame(self.sidebar_frame, fg_color=CARD_BG, height=35, corner_radius=10)
        self.sb_header.pack(fill="x", padx=2, pady=(2, 0))
        self.sb_header.pack_propagate(False)
        
        # Dragging binding for sidebar components
        for widget in [self.sidebar_frame, self.sb_header]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
        
        ctk.CTkLabel(self.sb_header, text="PAINEL DESEMPENHO", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_BLUE).pack(side="left", padx=12)
        
        # Sidebar Body
        sb_body = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        sb_body.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        
        # Lucro Acumulado
        ctk.CTkLabel(sb_body, text="AVANÇO DE LUCRO", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w")
        self.lbl_sb_profit = ctk.CTkLabel(sb_body, text="$0.00", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_GREEN)
        self.lbl_sb_profit.pack(anchor="w", pady=(0, 5))
        
        # Canvas do Gráfico de Lucro
        self.profit_chart_canvas = tk.Canvas(sb_body, height=130, bg=BG_MAIN, highlightthickness=0)
        self.profit_chart_canvas.pack(fill="x", pady=5)
        self.profit_chart_canvas.bind("<Button-1>", self.start_drag)
        self.profit_chart_canvas.bind("<B1-Motion>", self.drag)
        
        # Grid de Estatísticas Detalhadas
        self.stats_grid = ctk.CTkFrame(sb_body, fg_color="transparent")
        self.stats_grid.pack(fill="x", pady=(5, 5))
        self.stats_grid.grid_columnconfigure(0, weight=1)
        self.stats_grid.grid_columnconfigure(1, weight=1)
        
        # Cria rótulos das estatísticas no painel lateral
        self.lbl_sb_banca_ini = self._create_sidebar_stat(self.stats_grid, "Banca Inicial", "$0.00", 0, 0)
        self.lbl_sb_banca_atual = self._create_sidebar_stat(self.stats_grid, "Banca Atual", "$0.00", 0, 1)
        self.lbl_sb_operacoes = self._create_sidebar_stat(self.stats_grid, "Operações", "0", 1, 0)
        self.lbl_sb_win_loss = self._create_sidebar_stat(self.stats_grid, "Wins / Losses", "0 / 0", 1, 1)
        self.lbl_sb_winrate = self._create_sidebar_stat(self.stats_grid, "Assertividade", "0.0%", 2, 0, val_color=ACCENT_YELLOW)
        self.lbl_sb_max_streak = self._create_sidebar_stat(self.stats_grid, "Seq. Max W/L", "0 / 0", 2, 1)
        self.lbl_sb_avg_profit = self._create_sidebar_stat(self.stats_grid, "Lucro Médio", "$0.00", 3, 0, val_color=ACCENT_BLUE)
        self.lbl_sb_avg_time = self._create_sidebar_stat(self.stats_grid, "Tempo Médio", "N/A", 3, 1)
        
        # Barra gráfica de Assertividade
        self.winrate_ratio_canvas = tk.Canvas(sb_body, height=6, bg=BG_MAIN, highlightthickness=0)
        self.winrate_ratio_canvas.pack(fill="x", pady=(0, 5))
        self.winrate_ratio_canvas.bind("<Button-1>", self.start_drag)
        self.winrate_ratio_canvas.bind("<B1-Motion>", self.drag)
        
        # Título P&L Volatility
        self.lbl_volatility_title = ctk.CTkLabel(sb_body, text="DISTRIBUIÇÃO DE RETORNOS (P&L)", font=ctk.CTkFont(size=9, weight="bold"), text_color="gray")
        self.lbl_volatility_title.pack(anchor="w", pady=(5, 2))

        # Canvas da Distribuição de Retornos
        self.pandl_volatility_canvas = tk.Canvas(sb_body, height=50, bg=BG_MAIN, highlightthickness=0)
        self.pandl_volatility_canvas.pack(fill="x", pady=(0, 5))
        self.pandl_volatility_canvas.bind("<Button-1>", self.start_drag)
        self.pandl_volatility_canvas.bind("<B1-Motion>", self.drag)
        
        # Título Recentes
        ctk.CTkLabel(sb_body, text="ÚLTIMAS OPERAÇÕES", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(anchor="w", pady=(5, 2))
        
        # Frame para lista de recentes
        self.recent_ops_frame = ctk.CTkFrame(sb_body, fg_color="transparent")
        self.recent_ops_frame.pack(fill="both", expand=True)
        
        # Mensagem se vazio
        self.lbl_no_ops = ctk.CTkLabel(self.recent_ops_frame, text="Nenhuma operação registrada ainda.", font=ctk.CTkFont(size=10), text_color="#64748b")
        self.lbl_no_ops.pack(pady=20)
        
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
        self.lbl_title = ctk.CTkLabel(self.header, text="DERIV CLICKER", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8")
        self.lbl_title.pack(side="left", padx=12)
        
        # Botao Fechar (oculta o overlay)
        self.btn_close = ctk.CTkButton(self.header, text="×", width=22, height=22, fg_color="transparent", hover_color="#ef4444", text_color="#94a3b8", font=ctk.CTkFont(size=16, weight="bold"), command=self.withdraw)
        self.btn_close.pack(side="right", padx=6)

        # Botao Toggle Sidebar (estatísticas)
        self.btn_toggle_sidebar = ctk.CTkButton(
            self.header,
            text="📊",
            width=22,
            height=22,
            fg_color=CARD_BG,
            hover_color="#1e293b",
            text_color=ACCENT_BLUE,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_sidebar
        )
        self.btn_toggle_sidebar.pack(side="right", padx=(0, 2))
        
        # Botão Toggle Cognição IA (🧠)
        self.btn_toggle_ai_reasoning = ctk.CTkButton(
            self.header,
            text="🧠",
            width=22,
            height=22,
            fg_color=CARD_BG,
            hover_color="#1e293b",
            text_color=ACCENT_BLUE,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_ai_reasoning
        )
        self.btn_toggle_ai_reasoning.pack(side="right", padx=(0, 2))
        
        # Botão de Pânico (🚨 PANIC)
        self.btn_panic = ctk.CTkButton(
            self.header,
            text="🚨 PANIC",
            width=50,
            height=22,
            fg_color="#7f1d1d",
            hover_color="#ef4444",
            text_color="#fca5a5",
            font=ctk.CTkFont(size=9, weight="bold"),
            command=self._on_panic_click
        )
        self.btn_panic.pack(side="right", padx=(0, 6))

        # Indicador de Latência/Ping
        self.lbl_latency = ctk.CTkLabel(
            self.header,
            text="0ms",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#64748b"
        )
        self.lbl_latency.pack(side="right", padx=(0, 6))
        
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
        
        # --- TABS SELECTOR (Mantido oculto para compatibilidade com o loop de eventos) ---
        self.tab_frame = ctk.CTkFrame(body, fg_color="transparent", height=1)

        # --- TAB FRAMES ---
        self.tab_general_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.tab_general_frame.pack(fill="both", expand=True)
        
        self.tab_ai_frame = ctk.CTkFrame(body, fg_color="transparent")
        
        self.active_tab = "general"
        self.current_mode = "fixed"
        self.confidence_history = []

        # --- CONTEÚDO TAB GERAL ---
        # Canvas do Status
        self.status_canvas = tk.Canvas(self.tab_general_frame, height=35, bg=BG_MAIN, highlightthickness=0)
        self.status_canvas.pack(fill="x", pady=(0, 5))
        self.status_canvas.bind("<Button-1>", self.start_drag)
        self.status_canvas.bind("<B1-Motion>", self.drag)
        
        # Divididor
        div = ctk.CTkFrame(self.tab_general_frame, fg_color="#334155", height=1)
        div.pack(fill="x", pady=(0, 5))
        
        # Metricas Principais (Grid compacta)
        grid_frame = ctk.CTkFrame(self.tab_general_frame, fg_color="transparent")
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
        div2 = ctk.CTkFrame(self.tab_general_frame, fg_color="#334155", height=1)
        div2.pack(fill="x", pady=5)
        
        # Info Financeira e Barra de Progresso Customizada (Canvas)
        self.lbl_finance_title = ctk.CTkLabel(self.tab_general_frame, text="LUCRO / META", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray")
        self.lbl_finance_title.pack(anchor="w")
        
        self.lbl_finance_value = ctk.CTkLabel(self.tab_general_frame, text="$0.00 / $10.00", font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_finance_value.pack(anchor="w", pady=(2, 4))
        
        self.progress_canvas = tk.Canvas(self.tab_general_frame, height=22, bg=BG_MAIN, highlightthickness=0)
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
        
        # Divididor 3
        div3 = ctk.CTkFrame(self.tab_general_frame, fg_color="#334155", height=1)
        div3.pack(fill="x", pady=4)
        
        # Tempo de Execução e Próximo Clique
        row_time = ctk.CTkFrame(self.tab_general_frame, fg_color="transparent")
        row_time.pack(fill="x")
        
        ctk.CTkLabel(row_time, text="Tempo:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_timer = ctk.CTkLabel(row_time, text="00:00:00", font=ctk.CTkFont(size=11, weight="bold"), text_color="#e2e8f0")
        self.lbl_timer.pack(side="right")
        
        self.row_next = ctk.CTkFrame(self.tab_general_frame, fg_color="transparent")
        self.row_next.pack(fill="x", pady=(2, 0))
        
        ctk.CTkLabel(self.row_next, text="Próximo Clique:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_next_click = ctk.CTkLabel(self.row_next, text="Inativo", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_next_click.pack(side="right")
        
        row_api = ctk.CTkFrame(self.tab_general_frame, fg_color="transparent")
        row_api.pack(fill="x", pady=(2, 0))
        
        ctk.CTkLabel(row_api, text="Conexão API:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_api_conn_status = ctk.CTkLabel(row_api, text="Inativa (OCR)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b")
        self.lbl_api_conn_status.pack(side="right")
        
        # --- SEÇÃO ADAPTATIVA NO RODAPÉ ---
        self.frame_adaptive_overlay = ctk.CTkFrame(self.tab_general_frame, fg_color="transparent")
        self.frame_adaptive_overlay.pack(fill="x", pady=(5, 0))
        
        # Divididor Adaptativo
        self.div_adaptive = ctk.CTkFrame(self.frame_adaptive_overlay, fg_color="#334155", height=1)
        self.div_adaptive.pack(fill="x", pady=(0, 4))
        
        row_phase = ctk.CTkFrame(self.frame_adaptive_overlay, fg_color="transparent")
        row_phase.pack(fill="x")
        ctk.CTkLabel(row_phase, text="Fase IA:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_adaptive_phase = ctk.CTkLabel(row_phase, text="Observação", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_YELLOW)
        self.lbl_adaptive_phase.pack(side="right")
        
        row_pattern = ctk.CTkFrame(self.frame_adaptive_overlay, fg_color="transparent")
        row_pattern.pack(fill="x", pady=(2, 4))
        ctk.CTkLabel(row_pattern, text="Regra IA:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_adaptive_rule = ctk.CTkLabel(row_pattern, text="3 ciclos -> repetição", font=ctk.CTkFont(size=10, weight="bold"), text_color="#e2e8f0")
        self.lbl_adaptive_rule.pack(side="right")
        
        # Barra de Confiança
        row_conf = ctk.CTkFrame(self.frame_adaptive_overlay, fg_color="transparent")
        row_conf.pack(fill="x")
        ctk.CTkLabel(row_conf, text="Confiança:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.lbl_adaptive_conf = ctk.CTkLabel(row_conf, text="0.0%", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_BLUE)
        self.lbl_adaptive_conf.pack(side="right")
        
        self.conf_canvas = tk.Canvas(self.frame_adaptive_overlay, height=14, bg=BG_MAIN, highlightthickness=0)
        self.conf_canvas.pack(fill="x", pady=(2, 0))
        self.conf_canvas.bind("<Button-1>", self.start_drag)
        self.conf_canvas.bind("<B1-Motion>", self.drag)
        
        self.adaptive_conf_val = 0.0
        
        # --- CONTEÚDO TAB IA ---
        self.frame_ai_overlay = ctk.CTkFrame(self.tab_ai_frame, fg_color="transparent")
        self.frame_ai_overlay.pack(fill="both", expand=True)
        
        # Painel IA Header
        row_ai_head = ctk.CTkFrame(self.frame_ai_overlay, fg_color="transparent")
        row_ai_head.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(row_ai_head, text="PAINEL NEURAL IA", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_BLUE).pack(side="left")
        self.lbl_ai_state = ctk.CTkLabel(row_ai_head, text="Operando", font=ctk.CTkFont(size=9, weight="bold"), text_color=ACCENT_GREEN)
        self.lbl_ai_state.pack(side="right")
        self.lbl_ai_device = ctk.CTkLabel(row_ai_head, text="CPU (NumPy)", font=ctk.CTkFont(size=9, weight="bold"), text_color="#64748b")
        self.lbl_ai_device.pack(side="right", padx=(0, 8))
        
        # Grid de Métricas IA no Overlay
        grid_ai = ctk.CTkFrame(self.frame_ai_overlay, fg_color="transparent")
        grid_ai.pack(fill="x", pady=2)
        grid_ai.grid_columnconfigure(0, weight=1)
        grid_ai.grid_columnconfigure(1, weight=1)
        
        # Métricas da IA no Overlay (Grid compacto)
        self.lbl_ov_ai_loss = self._create_metric_lbl(grid_ai, "Loss", "0.0000", row=0, col=0)
        self.lbl_ov_ai_accuracy = self._create_metric_lbl(grid_ai, "Acurácia", "0.0%", row=1, col=0, val_color=ACCENT_GREEN)
        self.lbl_ov_ai_samples = self._create_metric_lbl(grid_ai, "Amostras", "0", row=0, col=1)
        self.lbl_ov_ai_conf = self._create_metric_lbl(grid_ai, "Confiança", "0.0%", row=1, col=1, val_color=ACCENT_YELLOW)
        self.lbl_ov_ai_trend = self._create_metric_lbl(grid_ai, "Tendência", "LATERAL ⚖️", row=2, col=0, val_color=ACCENT_BLUE)
        
        # Barra de progresso da Confiança IA
        self.ai_conf_canvas = tk.Canvas(self.frame_ai_overlay, height=8, bg=BG_MAIN, highlightthickness=0)
        self.ai_conf_canvas.pack(fill="x", pady=(2, 4))
        self.ai_conf_canvas_val = 0.0
        
        # Canvas da Rede Neural Animada
        self.lbl_nn_title = ctk.CTkLabel(self.frame_ai_overlay, text="Atividade da Rede Neural:", font=ctk.CTkFont(size=9, weight="bold"), text_color="gray")
        self.lbl_nn_title.pack(anchor="w", pady=(2, 0))
        
        self.nn_canvas = tk.Canvas(self.frame_ai_overlay, height=65, bg=BG_MAIN, highlightthickness=0)
        self.nn_canvas.pack(fill="x", pady=(2, 0))
        self.nn_canvas.bind("<Button-1>", self.start_drag)
        self.nn_canvas.bind("<B1-Motion>", self.drag)

        # Canvas do Gráfico de Confiança
        self.lbl_chart_title = ctk.CTkLabel(self.frame_ai_overlay, text="Histórico de Confiança IA:", font=ctk.CTkFont(size=9, weight="bold"), text_color="gray")
        self.lbl_chart_title.pack(anchor="w", pady=(5, 0))
        
        self.ai_chart_canvas = tk.Canvas(self.frame_ai_overlay, height=65, bg=BG_MAIN, highlightthickness=0)
        self.ai_chart_canvas.pack(fill="x", pady=(2, 0))
        self.ai_chart_canvas.bind("<Button-1>", self.start_drag)
        self.ai_chart_canvas.bind("<B1-Motion>", self.drag)
        
        # Variáveis da animação da rede neural
        self.nn_pulse_time = 0.0
        self.nn_particles = [] # Lista de partículas fluindo pelas conexões
        
        # Inicia o loop de animação ao final do __init__
        self.update_loop()
        
    def _create_sidebar_stat(self, parent, label, initial_val, row, col, val_color="#e2e8f0"):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=row, column=col, sticky="w", pady=2, padx=4)
        
        ctk.CTkLabel(container, text=f"{label}:", font=ctk.CTkFont(size=9), text_color="#64748b").pack(anchor="w")
        val_lbl = ctk.CTkLabel(container, text=initial_val, font=ctk.CTkFont(size=11, weight="bold"), text_color=val_color)
        val_lbl.pack(anchor="w")
        return val_lbl

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
        
    def show_general_tab(self):
        self.active_tab = "general"
        self._resize_overlay()

    def show_ai_tab(self):
        self.active_tab = "ai"
        self._resize_overlay()

    def _on_panic_click(self):
        if hasattr(self, "on_panic_cb") and self.on_panic_cb:
            self.on_panic_cb()

    def _resize_overlay(self):
        if self.current_mode == "ai":
            target_height = 840
        elif self.current_mode == "adaptive":
            target_height = 580
        else:
            target_height = 480
            
        target_width = 310
        if self.sidebar_expanded:
            target_width += 290
        if hasattr(self, "ai_reasoning_expanded") and self.ai_reasoning_expanded:
            target_width += 480
            
        # Update frame heights and widths explicitly
        if hasattr(self, "main_frame") and self.main_frame.winfo_exists():
            self.main_frame.configure(width=310, height=target_height)
        if hasattr(self, "sidebar_frame") and self.sidebar_frame.winfo_exists():
            self.sidebar_frame.configure(width=290, height=target_height)
        if hasattr(self, "ai_reasoning_frame") and self.ai_reasoning_frame.winfo_exists():
            self.ai_reasoning_frame.configure(width=480, height=target_height)
        
        if self.height != target_height or self.width != target_width:
            self.height = target_height
            self.width = target_width
            curr_x = self.winfo_x()
            curr_y = self.winfo_y()
            if curr_x <= 1 and curr_y <= 1:
                screen_w = self.winfo_screenwidth()
                curr_x = screen_w - self.width - 50
                curr_y = 50
            self.geometry(f"{self.width}x{self.height}+{curr_x}+{curr_y}")

    def update_data(self, status, clicks, wins, losses, rate, win_streak, loss_streak, current_profit, target_profit, finance_mode, free_entries, timer_str, next_click_str, mode="fixed", adaptive_phase="observation", adaptive_rule="N/A", adaptive_conf=0.0, deriv_api_status="Inativa (OCR)", ai_loss=0.0, ai_accuracy=0.0, ai_samples=0, current_balance=0.0, ai_device="CPU (NumPy)", latency_ms=0, market_trend="LATERAL ⚖️", ai_reasoning_status="Inativo", ai_reasoning_explanation="Aguardando...", contract_mode="accumulator", predicted_barrier=None, last_digit=None, expiration_str="N/A", ai_intelligence_str="Lvl 1 (Iniciando)", recent_ops=None):
        # 1. Status and Color Mapping
        new_status = status.upper()
        
        if "OBSERVANDO" in new_status:
            self.status_text = "OBSERVANDO"
            self.status_rgb = (245, 158, 11)
        elif "STEALTH" in new_status:
            self.status_text = "STEALTH 🥷"
            self.status_rgb = (168, 85, 247)
        elif "EXECUTANDO (IA)" in new_status:
            self.status_text = "IA OPERANDO"
            self.status_rgb = (16, 185, 129)
        elif new_status == "EXECUTANDO":
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
        elif "PAUSADO" in new_status or "CICLO" in new_status:
            self.status_text = "PAUSA CICLO"
            self.status_rgb = (245, 158, 11)
        else:
            self.status_text = "PARADO"
            self.status_rgb = (239, 68, 68)
            
        # Update AI Device badge
        if "GPU" in ai_device:
            self.lbl_ai_device.configure(text="GPU ⚡", text_color=ACCENT_GREEN)
        elif "PyTorch" in ai_device or "cpu_pytorch" in ai_device or "cuda" in ai_device:
            self.lbl_ai_device.configure(text="CPU (PyTorch) 💻", text_color=ACCENT_YELLOW)
        else:
            self.lbl_ai_device.configure(text="CPU (NumPy) 💻", text_color="#64748b")
            
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
            
        # Record confidence history
        if "PARADO" not in self.status_text:
            self.confidence_history.append(adaptive_conf / 100.0)
            if len(self.confidence_history) > 40:
                self.confidence_history.pop(0)
        else:
            self.confidence_history = []
  
        # Reset sidebar metrics if stats are cleared/stopped
        if wins == 0 and losses == 0 and current_profit == 0.0 and (self.last_wins_count > 0 or self.last_losses_count > 0):
            self.profit_history = []
            self.recent_operations = []
            self.last_wins_count = 0
            self.last_losses_count = 0
            self.last_profit_value = 0.0
            self.initial_balance = current_balance
            self.lbl_no_ops.pack(pady=20)
            if hasattr(self, "trade_timestamps"):
                self.trade_timestamps = []
            for child in self.recent_ops_frame.winfo_children():
                if child != self.lbl_no_ops:
                    child.destroy()
  
        # Initialize counts on first data update
        if not getattr(self, "initialized_counts", False):
            self.last_wins_count = wins
            self.last_losses_count = losses
            self.last_profit_value = current_profit
            self.initialized_counts = True

        # Update sidebar statistics
        if not hasattr(self, "initial_balance") or self.initial_balance == 0.0:
            if current_balance > 0.0:
                self.initial_balance = current_balance
            else:
                self.initial_balance = 10.0  # fallback se não tiver saldo real
                
        banca_atual = current_balance if current_balance > 0.0 else (self.initial_balance + current_profit)
        
        self.lbl_sb_banca_ini.configure(text=f"${self.initial_balance:.2f}")
        self.lbl_sb_banca_atual.configure(text=f"${banca_atual:.2f}", text_color=ACCENT_GREEN if current_profit >= 0 else ACCENT_RED)
        
        total_ops = wins + losses
        self.lbl_sb_operacoes.configure(text=str(total_ops))
        self.lbl_sb_win_loss.configure(text=f"{wins} / {losses}")
        self.lbl_sb_winrate.configure(text=f"{rate:.1f}%", text_color=ACCENT_GREEN if rate >= 70.0 else (ACCENT_YELLOW if rate >= 50.0 else ACCENT_RED))
        self.lbl_sb_max_streak.configure(text=f"{win_streak} / {loss_streak}")
        
        # Lucro Médio
        avg_profit = current_profit / max(1, total_ops)
        sign = "+" if avg_profit >= 0 else ""
        avg_profit_color = ACCENT_GREEN if avg_profit >= 0 else ACCENT_RED
        self.lbl_sb_avg_profit.configure(text=f"{sign}${avg_profit:.2f}", text_color=avg_profit_color)
        
        # Tempo Médio
        avg_time_str = "N/A"
        if hasattr(self, "trade_timestamps") and len(self.trade_timestamps) >= 2:
            avg_sec = (self.trade_timestamps[-1] - self.trade_timestamps[0]) / (len(self.trade_timestamps) - 1)
            if avg_sec >= 60:
                m, s = divmod(int(avg_sec), 60)
                avg_time_str = f"{m}m {s}s"
            else:
                avg_time_str = f"{int(avg_sec)}s"
        self.lbl_sb_avg_time.configure(text=avg_time_str)

        # Track profit history (up to 50 entries)
        if not self.profit_history or self.profit_history[-1] != banca_atual:
            self.profit_history.append(banca_atual)
            if len(self.profit_history) > 50:
                self.profit_history.pop(0)
                
        # Track recent operations (P&L badges)
        if recent_ops is not None:
            new_ops = []
            for item in recent_ops:
                if len(item) == 3:
                    new_ops.insert(0, item)
                elif len(item) == 2:
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    new_ops.insert(0, (item[0], item[1], timestamp))
            
            if new_ops != self.recent_operations:
                self.recent_operations = new_ops
                self.lbl_no_ops.pack_forget()
                for child in self.recent_ops_frame.winfo_children():
                    if child != self.lbl_no_ops:
                        child.destroy()
                
                for op, val, t in self.recent_operations[:5]:
                    row = ctk.CTkFrame(self.recent_ops_frame, fg_color="#1e293b" if op == "WIN" else "#271c1c", height=28, corner_radius=6)
                    row.pack(fill="x", pady=2)
                    row.pack_propagate(False)
                    
                    # Indicator dot
                    indicator = ctk.CTkLabel(row, text="●", text_color=ACCENT_GREEN if op == "WIN" else ACCENT_RED, font=ctk.CTkFont(size=14))
                    indicator.pack(side="left", padx=(8, 4))
                    
                    # Text
                    lbl_text = ctk.CTkLabel(row, text=f"{op} ({t})", font=ctk.CTkFont(size=10, weight="bold"), text_color="#e2e8f0")
                    lbl_text.pack(side="left")
                    
                    sign = "+" if val >= 0 else "-"
                    val_color = ACCENT_GREEN if op == "WIN" else ACCENT_RED
                    lbl_val = ctk.CTkLabel(row, text=f"{sign}${abs(val):.2f}", font=ctk.CTkFont(size=10, weight="bold"), text_color=val_color)
                    lbl_val.pack(side="right", padx=8)
        else:
            diff_wins = wins - self.last_wins_count
            diff_losses = losses - self.last_losses_count
            
            if diff_wins > 0 or diff_losses > 0:
                if not hasattr(self, "trade_timestamps"):
                    self.trade_timestamps = []
                self.trade_timestamps.append(time.time())
                if len(self.trade_timestamps) > 20:
                    self.trade_timestamps.pop(0)
                    
                diff_profit = current_profit - self.last_profit_value
                op_type = "WIN" if diff_wins > 0 else "LOSS"
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                self.recent_operations.insert(0, (op_type, diff_profit, timestamp))
                if len(self.recent_operations) > 10:
                    self.recent_operations.pop()
                    
                self.last_wins_count = wins
                self.last_losses_count = losses
                self.last_profit_value = current_profit
                
                # Rebuild recent operations list UI
                self.lbl_no_ops.pack_forget()
                for child in self.recent_ops_frame.winfo_children():
                    if child != self.lbl_no_ops:
                        child.destroy()
                    
                for op, val, t in self.recent_operations[:5]:
                    row = ctk.CTkFrame(self.recent_ops_frame, fg_color="#1e293b" if op == "WIN" else "#271c1c", height=28, corner_radius=6)
                    row.pack(fill="x", pady=2)
                    row.pack_propagate(False)
                    
                    # Indicator dot
                    indicator = ctk.CTkLabel(row, text="●", text_color=ACCENT_GREEN if op == "WIN" else ACCENT_RED, font=ctk.CTkFont(size=14))
                    indicator.pack(side="left", padx=(8, 4))
                    
                    # Text
                    lbl_text = ctk.CTkLabel(row, text=f"{op} ({t})", font=ctk.CTkFont(size=10, weight="bold"), text_color="#e2e8f0")
                    lbl_text.pack(side="left")
                    
                    sign = "+" if val >= 0 else "-"
                    val_color = ACCENT_GREEN if op == "WIN" else ACCENT_RED
                    lbl_val = ctk.CTkLabel(row, text=f"{sign}${abs(val):.2f}", font=ctk.CTkFont(size=10, weight="bold"), text_color=val_color)
                    lbl_val.pack(side="right", padx=8)

        # Update sidebar profit label
        sb_profit_color = ACCENT_GREEN if current_profit >= 0 else ACCENT_RED
        self.lbl_sb_profit.configure(text=f"${current_profit:.2f}", text_color=sb_profit_color)
 
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
        
        # Update Latency display in header
        if "Inativa" in deriv_api_status or "OCR" in deriv_api_status or "Desconectado" in deriv_api_status:
            self.lbl_latency.configure(text="OCR Mode", text_color="#64748b")
        else:
            lat_color = ACCENT_GREEN if latency_ms < 150 else (ACCENT_YELLOW if latency_ms < 300 else ACCENT_RED)
            self.lbl_latency.configure(text=f"{latency_ms}ms", text_color=lat_color)
            
        # 4b. API Status Update
        self.lbl_api_conn_status.configure(text=deriv_api_status)
        if "Autorizado" in deriv_api_status or "✅" in deriv_api_status:
            self.lbl_api_conn_status.configure(text_color=ACCENT_GREEN)
        elif "Inativa" in deriv_api_status or "OCR" in deriv_api_status:
            self.lbl_api_conn_status.configure(text_color="#64748b")
        elif "Desconectado" in deriv_api_status:
            self.lbl_api_conn_status.configure(text_color=ACCENT_RED)
        else:
            self.lbl_api_conn_status.configure(text_color=ACCENT_YELLOW)
            
        # 5. Configuração Dinâmica de Layout (IA vs Adaptativo vs Fixo)
        self.current_mode = mode
        
        if mode == "ai":
            # Hide tab selector since we have a unified premium view!
            self.tab_frame.pack_forget()
            
            # Hide next click row (not needed/inactive in AI mode)
            self.row_next.pack_forget()
            
            # Pack both general and AI frames so they are both visible!
            self.tab_general_frame.pack(fill="x", side="top")
            self.tab_ai_frame.pack(fill="both", side="top", expand=True)
            
            # Hide adaptive frame inside general tab
            self.frame_adaptive_overlay.pack_forget()
            
            # Update AI tab widgets
            state_color = ACCENT_YELLOW if "Treinando" in adaptive_phase else ACCENT_GREEN
            self.lbl_ai_state.configure(text=adaptive_phase.upper(), text_color=state_color)
            self.lbl_ov_ai_loss.configure(text=f"{ai_loss:.4f}")
            self.lbl_ov_ai_accuracy.configure(text=f"{ai_accuracy:.1f}%")
            self.lbl_ov_ai_samples.configure(text=str(ai_samples))
            self.lbl_ov_ai_conf.configure(text=f"{adaptive_conf:.1f}%")
            trend_color = ACCENT_GREEN if "ALTA" in market_trend else (ACCENT_RED if "BAIXA" in market_trend else ACCENT_BLUE)
            self.lbl_ov_ai_trend.configure(text=market_trend, text_color=trend_color)
            self.ai_conf_canvas_val = adaptive_conf / 100.0
            self.adaptive_conf_val = self.ai_conf_canvas_val
            
        elif mode == "adaptive":
            # Hide tab selection
            self.tab_frame.pack_forget()
            self.tab_ai_frame.pack_forget()
            self.tab_general_frame.pack(fill="both", expand=True)
            
            # Show next click row
            self.row_next.pack(fill="x", pady=(2, 0))
            
            # Update Adaptive widgets inside general tab
            self.frame_adaptive_overlay.pack(fill="x", pady=(5, 0))
            phase_lbl = "Observando 👁️" if adaptive_phase == "observation" else "Operando 🤖"
            phase_color = ACCENT_YELLOW if adaptive_phase == "observation" else ACCENT_GREEN
            self.lbl_adaptive_phase.configure(text=phase_lbl, text_color=phase_color)
            self.lbl_adaptive_rule.configure(text=adaptive_rule)
            self.lbl_adaptive_conf.configure(text=f"{adaptive_conf:.1f}%")
            self.adaptive_conf_val = adaptive_conf / 100.0
            
        else: # fixed mode
            # Hide tab selection
            self.tab_frame.pack_forget()
            self.tab_ai_frame.pack_forget()
            self.tab_general_frame.pack(fill="both", expand=True)
            
            # Show next click row
            self.row_next.pack(fill="x", pady=(2, 0))
            
            # Hide adaptive frame
            self.frame_adaptive_overlay.pack_forget()
            
        # Update AI reasoning panel if elements exist
        if hasattr(self, "lbl_ai_reasoning_status_val") and self.lbl_ai_reasoning_status_val.winfo_exists():
            self.lbl_ai_reasoning_status_val.configure(text=ai_reasoning_status.upper())
            if "CONFIRMADA" in ai_reasoning_status.upper() or "EFETUADA" in ai_reasoning_status.upper() or "OPERANDO" in ai_reasoning_status.upper():
                self.lbl_ai_reasoning_status_val.configure(text_color=ACCENT_GREEN)
            elif "VETO" in ai_reasoning_status.upper() or "BLOQUEADO" in ai_reasoning_status.upper() or "CRASH" in ai_reasoning_status.upper():
                self.lbl_ai_reasoning_status_val.configure(text_color=ACCENT_RED)
            elif "AGUARDANDO" in ai_reasoning_status.upper() or "COLETANDO" in ai_reasoning_status.upper() or "CONSULTANDO" in ai_reasoning_status.upper():
                self.lbl_ai_reasoning_status_val.configure(text_color=ACCENT_YELLOW)
            else:
                self.lbl_ai_reasoning_status_val.configure(text_color=ACCENT_BLUE)

        if hasattr(self, "txt_ai_reasoning_explanation") and self.txt_ai_reasoning_explanation.winfo_exists():
            self.txt_ai_reasoning_explanation.configure(state="normal")
            self.txt_ai_reasoning_explanation.delete("1.0", "end")
            self.txt_ai_reasoning_explanation.insert("1.0", ai_reasoning_explanation)
            self.txt_ai_reasoning_explanation.configure(state="disabled")

        if hasattr(self, "lbl_reasoning_trend_val") and self.lbl_reasoning_trend_val.winfo_exists():
            self.lbl_reasoning_trend_val.configure(text=market_trend)
            trend_color = ACCENT_GREEN if "ALTA" in market_trend else (ACCENT_RED if "BAIXA" in market_trend else ACCENT_BLUE)
            self.lbl_reasoning_trend_val.configure(text_color=trend_color)

        if hasattr(self, "lbl_reasoning_conf_val") and self.lbl_reasoning_conf_val.winfo_exists():
            self.lbl_reasoning_conf_val.configure(text=f"{adaptive_conf:.1f}%")

        if hasattr(self, "lbl_reasoning_risk_val") and self.lbl_reasoning_risk_val.winfo_exists():
            total_ops = wins + losses
            if total_ops > 0:
                acc_rate = wins / total_ops
                if acc_rate >= 0.7:
                    risk = "BAIXO 🟢"
                    risk_color = ACCENT_GREEN
                elif acc_rate >= 0.5:
                    risk = "MÉDIO 🟡"
                    risk_color = ACCENT_YELLOW
                else:
                    risk = "ALTO 🔴"
                    risk_color = ACCENT_RED
            else:
                risk = "MÍNIMO 🟢"
                risk_color = ACCENT_GREEN
            self.lbl_reasoning_risk_val.configure(text=risk, text_color=risk_color)

        if hasattr(self, "lbl_reasoning_mode_val") and self.lbl_reasoning_mode_val.winfo_exists():
            self.lbl_reasoning_mode_val.configure(text=contract_mode.upper())
            
        if hasattr(self, "lbl_reasoning_target_val") and self.lbl_reasoning_target_val.winfo_exists():
            target_str = str(predicted_barrier) if predicted_barrier is not None else "N/A"
            self.lbl_reasoning_target_val.configure(text=target_str)
            
        if hasattr(self, "lbl_reasoning_last_digit_val") and self.lbl_reasoning_last_digit_val.winfo_exists():
            last_digit_str = str(last_digit) if last_digit is not None else "N/A"
            self.lbl_reasoning_last_digit_val.configure(text=last_digit_str)
            
        if hasattr(self, "lbl_reasoning_expiration_val") and self.lbl_reasoning_expiration_val.winfo_exists():
            self.lbl_reasoning_expiration_val.configure(text=expiration_str)
            
        if hasattr(self, "lbl_reasoning_intelligence_val") and self.lbl_reasoning_intelligence_val.winfo_exists():
            self.lbl_reasoning_intelligence_val.configure(text=ai_intelligence_str)

        # Perform resize if height or width changed
        self._resize_overlay()

    # --- CANVAS & ANIMATION SYSTEM ---
    def update_loop(self):
        try:
            if self.winfo_exists():
                self._update_physics()
                
                # Sempre desenha o status e progresso do saldo
                self._draw_status_canvas()
                self._draw_progress_canvas()
                
                # Se estiver no modo adaptativo, desenha o canvas de confiança adaptativa
                if self.current_mode == "adaptive":
                    if hasattr(self, 'frame_adaptive_overlay') and self.frame_adaptive_overlay.winfo_exists() and self.frame_adaptive_overlay.winfo_ismapped():
                        self._draw_conf_canvas()
                        
                # Se estiver no modo IA, desenha os componentes da IA
                if self.current_mode == "ai":
                    if hasattr(self, 'frame_ai_overlay') and self.frame_ai_overlay.winfo_exists() and self.frame_ai_overlay.winfo_ismapped():
                        self._draw_ai_conf_canvas()
                        self._draw_nn_canvas()
                        self._draw_chart_canvas()
                
                # Desenha o gráfico do sidebar se expandido
                if self.sidebar_expanded:
                    self._draw_profit_chart_canvas()
                    self._draw_winrate_ratio_canvas()
                    self._draw_volatility_canvas()
                    
                self.after(25, self.update_loop)
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
            
        if self.status_text in ["EXECUTANDO", "AGENDADO", "PAUSA CICLO", "STEALTH 🥷"]:
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
                 
        # 6. Atualização Física da Rede Neural IA
        if self.frame_ai_overlay.winfo_ismapped():
            self.nn_pulse_time += 0.05
            if self.nn_pulse_time >= 2 * math.pi:
                self.nn_pulse_time = 0.0
                
            inputs = [(25, 8), (25, 20), (25, 32), (25, 44), (25, 56)]
            hiddens = [(118, 14), (118, 26), (118, 38), (118, 50)]
            outputs = [(211, 32)]
            
            # Criação de impulsos nas sinapses (sinapses input -> hidden)
            if random.random() < 0.20:
                in_idx = random.randint(0, len(inputs) - 1)
                hid_idx = random.randint(0, len(hiddens) - 1)
                x1, y1 = inputs[in_idx]
                x2, y2 = hiddens[hid_idx]
                self.nn_particles.append({
                    "x": x1, "y": y1,
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "t": 0.0,
                    "speed": random.uniform(0.04, 0.08),
                    "color": (56, 189, 248) # Azul Celeste
                })
                
            # Criação de impulsos oculto -> saída
            if random.random() < 0.20:
                hid_idx = random.randint(0, len(hiddens) - 1)
                x1, y1 = hiddens[hid_idx]
                x2, y2 = outputs[0]
                col = (16, 185, 129) if self.adaptive_conf_val > 0.7 else (56, 189, 248) # Verde ou Azul
                self.nn_particles.append({
                    "x": x1, "y": y1,
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "t": 0.0,
                    "speed": random.uniform(0.04, 0.08),
                    "color": col
                })
                
            # Avança o progresso (tempo) das sinapses
            for p in self.nn_particles:
                p["t"] += p["speed"]
                p["x"] = p["x1"] + (p["x2"] - p["x1"]) * p["t"]
                p["y"] = p["y1"] + (p["y2"] - p["y1"]) * p["t"]
                
            # Filtra apenas as ativas
            self.nn_particles = [p for p in self.nn_particles if p["t"] < 1.0]

        # 7. Confidence Pulse Effect on Borders
        if self.adaptive_conf_val >= 0.8 and "PARADO" not in self.status_text:
            # Pulsing color interpolation
            pulse = math.sin(self.nn_pulse_time * 2.5) * 0.5 + 0.5
            r = int(51 + (16 - 51) * pulse)
            g = int(65 + (185 - 65) * pulse)
            b = int(85 + (129 - 85) * pulse)
            color_hex = f"#{r:02x}{g:02x}{b:02x}"
            self.main_frame.configure(border_color=color_hex)
            self.sidebar_frame.configure(border_color=color_hex)
        else:
            self.main_frame.configure(border_color="#334155")
            self.sidebar_frame.configure(border_color="#334155")

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

    def _draw_conf_canvas(self):
        canvas = self.conf_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 14
            
        bar_w = w - 10
        start_x = 5
        end_x = 5 + bar_w
        active_x = 5 + int(bar_w * self.adaptive_conf_val)
        y = h / 2
        
        # Track background
        canvas.create_line(start_x, y, end_x, y, fill="#1e293b", width=6, capstyle="round")
        
        if self.adaptive_conf_val > 0.0:
            glow_rgb = (int(59 * 0.4), int(130 * 0.4), int(246 * 0.4))
            glow_hex = f"#{glow_rgb[0]:02x}{glow_rgb[1]:02x}{glow_rgb[2]:02x}"
            canvas.create_line(start_x, y, active_x, y, fill=glow_hex, width=10, capstyle="round")
            
            core_hex = ACCENT_BLUE
            canvas.create_line(start_x, y, active_x, y, fill=core_hex, width=4, capstyle="round")

    def _draw_ai_conf_canvas(self):
        canvas = self.ai_conf_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 8
            
        bar_w = w - 10
        start_x = 5
        end_x = 5 + bar_w
        active_x = 5 + int(bar_w * self.ai_conf_canvas_val)
        y = h / 2
        
        # Track background
        canvas.create_line(start_x, y, end_x, y, fill="#1e293b", width=4, capstyle="round")
        
        if self.ai_conf_canvas_val > 0.0:
            if self.ai_conf_canvas_val >= 0.75:
                color_hex = ACCENT_GREEN
            elif self.ai_conf_canvas_val >= 0.5:
                color_hex = ACCENT_YELLOW
            else:
                color_hex = ACCENT_RED
                
            canvas.create_line(start_x, y, active_x, y, fill=color_hex, width=4, capstyle="round")

    def _draw_nn_canvas(self):
        canvas = self.nn_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 65
            
        # Posições dos neurônios (Grid 5x4x1)
        inputs = [(25, 8), (25, 20), (25, 32), (25, 44), (25, 56)]
        hiddens = [(118, 14), (118, 26), (118, 38), (118, 50)]
        outputs = [(211, 32)]
        
        # 1. Desenha as conexões
        for i_x, i_y in inputs:
            for h_x, h_y in hiddens:
                canvas.create_line(i_x, i_y, h_x, h_y, fill="#1e293b", width=1)
                
        for h_x, h_y in hiddens:
            for o_x, o_y in outputs:
                canvas.create_line(h_x, h_y, o_x, o_y, fill="#1e293b", width=1)
                
        # 2. Desenha os impulsos/partículas passando pelas conexões
        for p in self.nn_particles:
            color_hex = f"#{p['color'][0]:02x}{p['color'][1]:02x}{p['color'][2]:02x}"
            canvas.create_oval(p["x"] - 2.5, p["y"] - 2.5, p["x"] + 2.5, p["y"] + 2.5, fill=color_hex, outline="")
            
        # 3. Desenha os neurônios
        # Neurônios de Entrada (Inputs)
        for i_x, i_y in inputs:
            pulse = math.sin(self.nn_pulse_time + i_y) * 0.5 + 0.5
            r = 3.0 + 0.5 * pulse
            canvas.create_oval(i_x - r, i_y - r, i_x + r, i_y + r, fill="#38bdf8", outline="#0284c7", width=1)
            
        # Neurônios Ocultos (Hidden Nodes)
        for h_x, h_y in hiddens:
            pulse = math.sin(self.nn_pulse_time + h_y) * 0.5 + 0.5
            r = 3.5 + 0.5 * pulse
            canvas.create_oval(h_x - r, h_y - r, h_x + r, h_y + r, fill="#818cf8", outline="#4f46e5", width=1)
            
        # Neurônio de Saída (Output Node)
        out_x, out_y = outputs[0]
        pulse = math.sin(self.nn_pulse_time * 1.5) * 1.0 + 1.0
        r = 4.5 + 1.0 * pulse
        
        if self.adaptive_conf_val >= 0.75:
            node_color = ACCENT_GREEN
            node_outline = "#059669"
        elif self.adaptive_conf_val >= 0.5:
            node_color = ACCENT_YELLOW
            node_outline = "#d97706"
        else:
            node_color = ACCENT_RED
            node_outline = "#dc2626"
            
        # Desenha aura de brilho
        if self.adaptive_conf_val > 0.0:
            glow_r = r + 4 * self.adaptive_conf_val
            canvas.create_oval(out_x - glow_r, out_y - glow_r, out_x + glow_r, out_y + glow_r, fill="", outline=node_color, width=1)
            
        canvas.create_oval(out_x - r, out_y - r, out_x + r, out_y + r, fill=node_color, outline=node_outline, width=1.5)

    def _draw_chart_canvas(self):
        canvas = self.ai_chart_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 65
            
        # Draw grid lines
        canvas.create_line(0, h/2, w, h/2, fill="#1e293b", dash=(2, 2))
        canvas.create_line(0, h/4, w, h/4, fill="#1e293b", dash=(1, 4))
        canvas.create_line(0, 3*h/4, w, 3*h/4, fill="#1e293b", dash=(1, 4))
        
        if len(self.confidence_history) < 2:
            canvas.create_text(w/2, h/2, text="Aguardando dados da IA...", fill="#64748b", font=("Arial", 9))
            return
            
        points = []
        step = w / (len(self.confidence_history) - 1)
        for i, val in enumerate(self.confidence_history):
            x = i * step
            y = h - 6 - val * (h - 12)
            points.append((x, y))
            
        # Plot lines
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            canvas.create_line(x1, y1, x2, y2, fill=ACCENT_BLUE, width=2)
            
        # Draw current dot
        cx, cy = points[-1]
        canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill=ACCENT_YELLOW, outline=ACCENT_BLUE, width=1)

    def get_fade_color(self, rgb, life):
        r, g, b = rgb
        factor = max(0.0, min(1.0, life))
        nr = int(r * factor)
        ng = int(g * factor)
        nb = int(b * factor)
        return f"#{nr:02x}{ng:02x}{nb:02x}"

    def toggle_sidebar(self):
        if self.sidebar_expanded:
            self.sidebar_expanded = False
            self.sidebar_frame.pack_forget()
            self.btn_toggle_sidebar.configure(fg_color="transparent", text_color="#94a3b8")
        else:
            self.sidebar_expanded = True
            self.sidebar_frame.pack(side="left", fill="both", expand=False, padx=(2, 0))
            self.btn_toggle_sidebar.configure(fg_color=CARD_BG, text_color=ACCENT_BLUE)
        self._resize_overlay()

    def toggle_ai_reasoning(self):
        if self.ai_reasoning_expanded:
            self.ai_reasoning_expanded = False
            self.ai_reasoning_frame.pack_forget()
            self.btn_toggle_ai_reasoning.configure(fg_color="transparent", text_color="#94a3b8")
        else:
            self.ai_reasoning_expanded = True
            self.ai_reasoning_frame.pack(side="left", fill="both", expand=False, padx=(2, 0))
            self.btn_toggle_ai_reasoning.configure(fg_color=CARD_BG, text_color=ACCENT_BLUE)
        self._resize_overlay()

    def _draw_profit_chart_canvas(self):
        canvas = self.profit_chart_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 130
            
        if not self.profit_history:
            canvas.create_text(w/2, h/2, text="Aguardando operações...", fill="#64748b", font=("Arial", 9))
            return
            
        # Determine min/max values to scale
        max_val = max(max(self.profit_history), self.initial_balance + 1.0)
        min_val = min(min(self.profit_history), self.initial_balance - 1.0)
        
        # Expand range to fit nicely
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1.0
            
        points = []
        step = w / max(1, len(self.profit_history) - 1) if len(self.profit_history) > 1 else w / 2
        for i, val in enumerate(self.profit_history):
            x = i * step if len(self.profit_history) > 1 else w / 2
            # Scale value to canvas height (leaving 12px margins at top/bottom)
            y = h - 12 - ((val - min_val) / val_range) * (h - 24)
            points.append((x, y))
            
        # Baseline y-position
        baseline_y = h - 12 - ((self.initial_balance - min_val) / val_range) * (h - 24)
        
        # Draw baseline grid
        canvas.create_line(0, baseline_y, w, baseline_y, fill="#334155", width=1, dash=(2, 2))
        canvas.create_text(35, baseline_y - 8, text=f"${self.initial_balance:.2f}", fill="#64748b", font=("Arial", 8))
        
        # Plot lines and area
        if len(points) >= 2:
            poly_points = []
            poly_points.append(points[0][0])
            poly_points.append(baseline_y)
            for pt in points:
                poly_points.append(pt[0])
                poly_points.append(pt[1])
            poly_points.append(points[-1][0])
            poly_points.append(baseline_y)
            
            # Fill area: green if final balance is above or equal to initial balance, else red
            area_color = "#022c22" if self.profit_history[-1] >= self.initial_balance else "#2d0606"
            canvas.create_polygon(poly_points, fill=area_color, outline="")
            
            # Plot lines
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i+1]
                color = ACCENT_GREEN if y2 <= baseline_y else ACCENT_RED
                canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
                
        # Draw current dot
        cx, cy = points[-1]
        color = ACCENT_GREEN if self.profit_history[-1] >= self.initial_balance else ACCENT_RED
        canvas.create_oval(cx-4, cy-4, cx+4, cy+4, fill=color, outline="#ffffff", width=1)
        
        # Display max and min on chart
        canvas.create_text(w - 15, 12, text=f"Max: ${max_val:.2f}", fill=ACCENT_GREEN, font=("Arial", 8), anchor="e")
        canvas.create_text(w - 15, h - 12, text=f"Min: ${min_val:.2f}", fill=ACCENT_RED, font=("Arial", 8), anchor="e")

    def _draw_winrate_ratio_canvas(self):
        canvas = self.winrate_ratio_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 340
        if h < 10:
            h = 6
            
        wins = self.last_wins_count
        losses = self.last_losses_count
        total = wins + losses
        
        if total == 0:
            canvas.create_line(3, h/2, w-3, h/2, fill="#475569", width=4, capstyle="round")
            return
            
        win_ratio = wins / total
        split_x = 3 + int((w - 6) * win_ratio)
        
        if wins > 0:
            canvas.create_line(3, h/2, split_x, h/2, fill=ACCENT_GREEN, width=4, capstyle="round")
        if losses > 0:
            canvas.create_line(split_x, h/2, w-3, h/2, fill=ACCENT_RED, width=4, capstyle="round")

    def _draw_volatility_canvas(self):
        canvas = self.pandl_volatility_canvas
        canvas.delete("all")
        
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            w = 236
        if h < 10:
            h = 50
            
        baseline_y = h / 2
        canvas.create_line(0, baseline_y, w, baseline_y, fill="#334155", width=1)
        
        if not self.recent_operations:
            canvas.create_text(w/2, h/2, text="Aguardando operações...", fill="#64748b", font=("Arial", 9))
            return
            
        ops = self.recent_operations[:10]
        ops = list(reversed(ops))
        
        max_abs = max(abs(val) for _, val, _ in ops)
        if max_abs == 0:
            max_abs = 1.0
            
        bar_w = 12
        gap = 4
        total_w = len(ops) * bar_w + (len(ops) - 1) * gap
        start_x = (w - total_w) / 2
        
        for i, (op_type, val, _) in enumerate(ops):
            max_h = (h / 2) - 4
            bar_h = (abs(val) / max_abs) * max_h
            
            x1 = start_x + i * (bar_w + gap)
            x2 = x1 + bar_w
            
            if op_type == "WIN":
                y1 = baseline_y - bar_h
                y2 = baseline_y
                color = ACCENT_GREEN
            else:
                y1 = baseline_y
                y2 = baseline_y + bar_h
                color = ACCENT_RED
                
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="", width=0)
            
        canvas.create_text(5, 8, text=f"+${max_abs:.2f}", fill=ACCENT_GREEN, font=("Arial", 7), anchor="w")
        canvas.create_text(5, h - 8, text=f"-${max_abs:.2f}", fill=ACCENT_RED, font=("Arial", 7), anchor="w")
