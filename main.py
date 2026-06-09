import sys
import os
from app_gui import AppGui

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--webview":
        try:
            import webview
            storage_dir = os.path.join(os.getcwd(), ".deriv_webview_data")
            os.makedirs(storage_dir, exist_ok=True)
            
            url = "https://app.deriv.com/dtrader?lang=PT&account=demo&chart_type=area&interval=1t&symbol=1HZ100V&trade_type=accumulator"
            
            window = webview.create_window(
                'DERIVCLICKER - Navegador Embutido',
                url,
                width=1280,
                height=850,
                resizable=True
            )
            webview.start(private_mode=False, storage_path=storage_dir)
            sys.exit(0)
        except Exception as e:
            print(f"Erro ao iniciar o WebView: {e}")
            sys.exit(1)

    try:
        app = AppGui()
        app.mainloop()
    except Exception as e:
        print(f"Erro fatal ao iniciar aplicacao: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
