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
    "sensitivity_number": 0.65,
    "play_sounds": True,
    "use_custom_sounds": True,
    "auto_screenshot": False,
    "save_log": True,
    "image_button_path": "capturas/botao.png",
    "image_win_path": "capturas/win.png",
    "image_win2_path": "capturas/win2.png",
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
    "search_region": None,
    "use_search_region": False,
    "schedule_enabled": False,
    "schedule_date": "",
    "schedule_time": "",
    "win_value": 1.50,
    "loss_value": 30.00,
    "target_profit": 10.00,
    "finance_mode": "target",
    "free_entries": 10,
    "cycle_enabled": False,
    "cycle_max_entries": 4,
    "cycle_cooldown_minutes": 60,
    "adaptive_observation_minutes": 30,
    "adaptive_relearn_events": 100,
    "adaptive_relearn_minutes": 30,
    "adaptive_relearn_losses": 3,
    "deriv_api_token": "",
    "deriv_app_id": "1098",
    "deriv_symbol": "R_100",
    "deriv_growth_rate": 0.01,
    "deriv_use_api_trading": False,
    "deriv_account_type": "demo",
    "ai_threshold": 75.0,
    "ai_learning_rate": 0.01,
    "ai_lookahead_ticks": 3,
    "ai_use_gpu": True,
    "ai_entry_cooldown": 10,
    "ai_min_ticks_safe": 5,
    "ai_contract_take_profit": 5.0,
    "ai_min_samples_start": 500,
    "deriv_contract_mode": "accumulator",
    "deriv_rf_duration_unit": "t",
    "deriv_rf_duration_value": 5,
    "deriv_rf_auto_duration": True,
    "llama_enabled": False,
    "llama_url": "http://localhost:11434/api/generate",
    "llama_model": "llama3",
    "llama_provider": "ollama"
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
