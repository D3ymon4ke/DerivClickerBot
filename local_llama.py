import json
import threading
import torch
import os

class LocalLlamaClient:
    def __init__(self, model_name="Qwen/Qwen2.5-0.5B-Instruct", enabled=False):
        self.model_name = model_name
        self.enabled = enabled
        self.tokenizer = None
        self.model = None
        self.pipe = None
        self.loading = False
        self.loaded = False
        self._lock = threading.Lock()
        
        if self.enabled:
            self.start_loading()

    def start_loading(self):
        with self._lock:
            if self.loading or self.loaded:
                return
            self.loading = True
        
        def _load():
            try:
                # Evita avisos de paralelismo do tokenizers
                os.environ["TOKENIZERS_PARALLELISM"] = "false"
                
                print(f"🧠 [Local Llama] Carregando modelo {self.model_name}...")
                from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
                
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map="auto" if torch.cuda.is_available() else None,
                    torch_dtype="auto"
                )
                self.pipe = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer
                )
                with self._lock:
                    self.loaded = True
                    self.loading = False
                print(f"✅ [Local Llama] Modelo {self.model_name} carregado com sucesso!")
            except Exception as e:
                print(f"❌ [Local Llama] Erro ao carregar o modelo: {e}")
                with self._lock:
                    self.loading = False
                    self.loaded = False

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()

    def get_decision(self, mode, tick_history, current_profit, winrate, recent_ops):
        if not self.enabled:
            return None
            
        if not self.loaded:
            if not self.loading:
                self.start_loading()
            return None  # Ainda carregando em segundo plano

        context = {
            "mode": mode,
            "recent_ticks": tick_history[-15:] if len(tick_history) >= 15 else tick_history,
            "current_profit": current_profit,
            "winrate": winrate,
            "recent_ops": [op[0] for op in recent_ops[:5]]
        }

        if mode == "rise_fall":
            sys_prompt = (
                "You are an AI trading agent. Analyze the market and return a JSON object with keys: "
                "'direction' ('rise' or 'fall'), 'duration' (integer between 1 and 10), 'duration_unit' ('t'), "
                "and 'confidence' (float between 0 and 100). Do not include explanation, code block, or markdown. Only return pure JSON."
            )
            user_prompt = f"Market Context:\n{json.dumps(context)}"
        else:
            sys_prompt = (
                "You are an AI trading agent. Analyze the market and return a JSON object with keys: "
                "'is_safe' (boolean) and 'confidence' (float between 0 and 100). "
                "Do not include explanation, code block, or markdown. Only return pure JSON."
            )
            user_prompt = f"Market Context:\n{json.dumps(context)}"

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            outputs = self.pipe(
                prompt,
                max_new_tokens=128,
                do_sample=False,
                temperature=0.0
            )
            generated_text = outputs[0]["generated_text"]
            
            # Extrai o texto gerado
            response_part = generated_text[len(prompt):].strip()
            
            # Limpa qualquer delimitador markdown
            if response_part.startswith("```json"):
                response_part = response_part[7:]
            if response_part.startswith("```"):
                response_part = response_part[3:]
            if response_part.endswith("```"):
                response_part = response_part[:-3]
            response_part = response_part.strip()
            
            decision = json.loads(response_part)
            return decision
        except Exception:
            return None
