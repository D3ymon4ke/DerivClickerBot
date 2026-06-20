import json
import urllib.request
import urllib.error

class LlamaClient:
    def __init__(self, url="http://localhost:11434/api/generate", model="llama3", enabled=False):
        self.url = url
        self.model = model
        self.enabled = enabled

    def get_decision(self, mode, tick_history, current_profit, winrate, recent_ops):
        """
        Queries Llama model via Ollama with structured market details.
        Returns a dictionary with decision parameters, or None if disabled/failed.
        """
        if not self.enabled:
            return None

        # Build context prompt
        context = {
            "mode": mode,
            "recent_ticks": tick_history[-15:] if len(tick_history) >= 15 else tick_history,
            "current_profit": current_profit,
            "winrate": winrate,
            "recent_ops": [op[0] for op in recent_ops[:5]]  # WIN/LOSS list
        }

        if mode == "rise_fall":
            prompt = (
                f"Analyze the following market tick history and statistics for Deriv Rise/Fall trading:\n"
                f"{json.dumps(context, indent=2)}\n\n"
                f"Predict the next direction (rise or fall), duration in ticks (integer, typically between 1 and 10), "
                f"and confidence percentage (0 to 100).\n"
                f"You MUST return ONLY a JSON object with keys: 'direction' ('rise' or 'fall'), 'duration' (integer), "
                f"'duration_unit' ('t'), and 'confidence' (float). Do not include any explanation or markdown formatting."
            )
        else:  # accumulator
            prompt = (
                f"Analyze the following market tick history and statistics for Deriv Accumulator trading:\n"
                f"{json.dumps(context, indent=2)}\n\n"
                f"Decide if it is safe to open an accumulator position right now (is_safe: true/false), "
                f"and confidence percentage (0 to 100).\n"
                f"You MUST return ONLY a JSON object with keys: 'is_safe' (boolean) and 'confidence' (float). "
                f"Do not include any explanation or markdown formatting."
            )

        data = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }

        try:
            req = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            # 2 second timeout to prevent lag in tick stream
            with urllib.request.urlopen(req, timeout=2.0) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                response_text = res_data.get("response", "")
                decision = json.loads(response_text)
                return decision
        except urllib.error.URLError as e:
            # Silence connection errors to avoid spamming logs when Ollama isn't running
            return None
        except Exception:
            return None
