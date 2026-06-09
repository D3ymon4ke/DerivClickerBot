import tkinter as tk
from PIL import ImageTk, Image
import pyautogui

class RegionSelector:
    def __init__(self, parent=None):
        # Captura a tela inteira antes de exibir o seletor
        self.screenshot = pyautogui.screenshot()
        
        # Usa Toplevel em vez de tk.Tk para compartilhar o mesmo interpretador Tcl e evitar erros de imagem
        self.root = tk.Toplevel(parent)
        self.root.title("Selecionar Região de Busca")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="cross")
        
        # Converte a imagem capturada para o formato suportado pelo Tkinter
        self.bg_image = ImageTk.PhotoImage(self.screenshot)
        
        # Cria o Canvas para desenho do retângulo
        self.canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Desenha o fundo da tela congelada
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image)
        
        # Texto de ajuda centralizado no topo
        screen_w = self.root.winfo_screenwidth()
        self.canvas.create_text(
            screen_w // 2, 40,
            text="CLIQUE E ARRASTE para definir a área de busca do Preço. Pressione ESC para cancelar.",
            fill="#f8fafc", font=("Arial", 14, "bold"),
            justify="center"
        )
        
        # Eventos do mouse e teclado
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", self.on_esc)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.coords = None
        
    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        # Cria um retângulo vermelho com contorno espesso
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#ef4444", width=2
        )
        
    def on_move_press(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        
    def on_button_release(self, event):
        end_x, end_y = event.x, event.y
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        w = x2 - x1
        h = y2 - y1
        
        # Evita seleções de clique único acidental
        if w > 5 and h > 5:
            self.coords = (x1, y1, w, h)
        
        self.root.destroy()
        
    def on_esc(self, event):
        self.coords = None
        self.root.destroy()
        
    def get_region(self):
        self.root.grab_set()      # Torna a janela modal
        self.root.wait_window()   # Bloqueia até a janela ser destruída
        return self.coords
