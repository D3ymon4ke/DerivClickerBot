import os
import json

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "mode": "fixed",
    "fixed_interval": 5.0,
    "random_min": 2.0,
    "random_max": 10.0,
    "seq_clicks": 3,
    "seq_interval": 2.0,
    "seq_wait": 20.0,
    "sensitivity": 0.8,
    "play_sounds": True,
    "auto_screenshot": False,
    "save_log": True,
    "image_button_path": "capturas/botao.png",
    "image_win_path": "capturas/win.png",
    "image_loss_path": "capturas/loss.png",
    "enable_stop_win": False,
    "stop_win": 5,
    "enable_stop_loss": False,
    "stop_loss": 3,
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": "",
    "image_linered_path": "capturas/linered.png",
    "image_lineblue_path": "capturas/lineblue.png",
    "image_number_path": "capturas/number.png",
    "schedule_enabled": False,
    "schedule_date": "",
    "schedule_time": ""
}

def load_config():
    """Carrega as configuracoes do arquivo JSON. Se nao existir, retorna o padrao."""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Garante que chaves que possam faltar sejam preenchidas com o padrao
            for key, val in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = val
            return config
    except Exception as e:
        print(f"Erro ao carregar configuracoes: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config_data):
    """Salva as configuracoes fornecidas no arquivo JSON."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar configuracoes: {e}")
        return False
