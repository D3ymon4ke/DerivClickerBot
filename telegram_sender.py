import threading
import urllib.request
import urllib.parse
import json

def _strip_html_tags(text):
    """Remove tags HTML simples do texto para fallback em texto puro."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    return clean

def _send_request(url, payload_bytes, timeout=10):
    """Executa o request HTTP e retorna (ok, status_code, body_str)."""
    req = urllib.request.Request(url, data=payload_bytes, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return False, e.code, body
    except Exception as exc:
        return False, 0, str(exc)

def send_telegram_msg(config, text, log_callback=None):
    if not config.get("telegram_enabled", False):
        return

    token   = config.get("telegram_token",  "").strip()
    chat_id = config.get("telegram_chat_id","").strip()

    if not token or not chat_id:
        return

    def _send():
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        # --- Tentativa 1: HTML ---
        payload = urllib.parse.urlencode({
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "HTML"
        }).encode("utf-8")

        ok, code, body = _send_request(url, payload)

        if ok:
            return  # Sucesso com HTML

        # --- Diagnóstico do erro ---
        detail = ""
        try:
            detail = json.loads(body).get("description", body)
        except Exception:
            detail = body[:200]

        if log_callback:
            log_callback(f"[Telegram] HTML falhou ({code}): {detail}. Tentando texto puro...")

        # --- Tentativa 2: texto puro (sem parse_mode) ---
        plain_text = _strip_html_tags(text)
        payload2 = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text":    plain_text
        }).encode("utf-8")

        ok2, code2, body2 = _send_request(url, payload2)

        if ok2:
            if log_callback:
                log_callback("[Telegram] Mensagem enviada em texto puro com sucesso.")
        else:
            detail2 = ""
            try:
                detail2 = json.loads(body2).get("description", body2)
            except Exception:
                detail2 = body2[:200]
            if log_callback:
                log_callback(f"[Telegram] Erro final ({code2}): {detail2}")

    threading.Thread(target=_send, daemon=True).start()
