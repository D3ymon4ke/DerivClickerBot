import platform
import threading

# Determina se estamos no Windows
is_windows = platform.system().lower() == "windows"

if is_windows:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    # Tecla F8 em hexadecimal
    VK_F8 = 0x77
    # Modificadores de tecla (nenhum)
    MOD_NONE = 0x0000
    # Mensagem de Hotkey do Windows
    WM_HOTKEY = 0x0312
    # Mensagem de Quit para finalizar o loop
    WM_QUIT = 0x0012
else:
    user32 = None

class GlobalHotkeyListener(threading.Thread):
    def __init__(self, callback, key_code=None, modifiers=None):
        super().__init__(daemon=True)
        self.callback = callback
        self.running = False

    def run(self):
        if not is_windows:
            print("[Hotkey] Atalho F8 global desativado: não suportado em sistemas não-Windows.")
            return
            
        self.running = True
        self.hotkey_id = 101  # ID unico para identificar o atalho
        
        # Registrar o hotkey global no Windows
        res = user32.RegisterHotKey(None, self.hotkey_id, MOD_NONE, VK_F8)
        if not res:
            print("[Hotkey] Erro: Nao foi possivel registrar a tecla F8 global.")
            self.running = False
            return
        
        try:
            msg = wintypes.MSG()
            while self.running:
                # GetMessageW bloqueia ate receber uma mensagem para esta thread
                status = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if status == 0 or status == -1:
                    break
                
                if msg.message == WM_HOTKEY:
                    if msg.wParam == self.hotkey_id:
                        # Executa o callback de emergencia
                        self.callback()
                
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            print(f"[Hotkey] Erro no loop de mensagens: {e}")
        finally:
            user32.UnregisterHotKey(None, self.hotkey_id)
            self.running = False

    def stop(self):
        """Interrompe o ouvinte e envia uma mensagem para desbloquear o GetMessageW."""
        self.running = False
        if is_windows and self.ident:
            # Envia mensagem WM_QUIT para acordar o GetMessageW
            user32.PostThreadMessageW(self.ident, WM_QUIT, 0, 0)
