import sys
from app_gui import AppGui

def main():
    try:
        app = AppGui()
        app.mainloop()
    except Exception as e:
        print(f"Erro fatal ao iniciar aplicacao: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
