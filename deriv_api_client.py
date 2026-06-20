import websocket
import json
import threading
import time
import requests

class DerivApiClient:
    def __init__(self, token, app_id="1098", symbol="R_100", growth_rate=0.01, account_type="demo"):
        self.token = token
        self.app_id = str(app_id).strip() if (app_id and str(app_id).strip()) else "1098"
        self.symbol = symbol
        self.growth_rate = growth_rate
        self.account_type = account_type.strip().lower() if account_type else "demo"
        
        self.ws = None
        self.connected = False
        self.authorized = False
        self.balance = 0.0
        self.barrier_distance = None
        
        # Callbacks
        self.on_tick_cb = None
        self.on_contract_status_cb = None
        self.on_contract_update_cb = None
        self.on_history_cb = None
        self.on_log_cb = None
        self.on_connection_change_cb = None
        
        self._thread = None
        self._stop_event = threading.Event()
        self.active_contract_id = None
        self.last_tick_price = None
        self.latency_ms = 0
        self.ping_sent_time = 0.0

    def log(self, message):
        msg = f"[Deriv API] {message}"
        if self.on_log_cb:
            self.on_log_cb(msg)
        else:
            print(msg)

    def connect(self):
        if self.connected:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._stop_event.set()
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.connected = False
        self.authorized = False
        if self.on_connection_change_cb:
            self.on_connection_change_cb(False)

    def _run_ws(self):
        while not self._stop_event.is_set():
            is_pat = self.token.startswith("pat_")
            url = None
            
            if is_pat:
                try:
                    self.log("Identificado token PAT. Obtendo URL WebSocket com OTP via REST API...")
                    headers = {
                        "Deriv-App-ID": self.app_id,
                        "Authorization": f"Bearer {self.token}"
                    }
                    
                    # 1. Busca as contas na nova plataforma
                    res = requests.get("https://api.derivws.com/trading/v1/options/accounts", headers=headers, timeout=10)
                    if res.status_code != 200:
                        raise Exception(f"Falha ao buscar contas (status {res.status_code}): {res.text}")
                    
                    accounts = res.json().get("data", [])
                    target_account = None
                    for acc in accounts:
                        if acc.get("account_type") == self.account_type.lower():
                            target_account = acc
                            break
                            
                    if not target_account:
                        raise Exception(f"Nenhuma conta do tipo '{self.account_type}' encontrada!")
                        
                    acc_id = target_account["account_id"]
                    self.balance = float(target_account.get("balance", 0.0))
                    self.log(f"Conta encontrada: {acc_id} | Saldo: ${self.balance:.2f}")
                    
                    # 2. Solicita o OTP
                    res_otp = requests.post(f"https://api.derivws.com/trading/v1/options/accounts/{acc_id}/otp", headers=headers, timeout=10)
                    if res_otp.status_code != 200:
                        raise Exception(f"Falha ao gerar OTP (status {res_otp.status_code}): {res_otp.text}")
                        
                    url = res_otp.json().get("data", {}).get("url")
                    if not url:
                        raise Exception("Resposta de OTP não contém a URL do WebSocket.")
                        
                except Exception as e:
                    self.log(f"Erro no fluxo de autenticação PAT/OTP: {e}")
                    self.log("Tentando novamente em 5 segundos...")
                    time.sleep(5)
                    continue
            else:
                url = f"wss://ws.derivws.com/websockets/v3?app_id={self.app_id}"
                
            def on_open(ws):
                self.log("Conexão WebSocket aberta.")
                self.connected = True
                if self.on_connection_change_cb:
                    self.on_connection_change_cb(True)
                
                if is_pat:
                    self.authorized = True
                    self.log(f"Autenticado com sucesso! Saldo: ${self.balance:.2f}")
                    # Requisita a proposta para obter o barrier_distance
                    self._request_proposal()
                else:
                    # Envia autorização (funciona para tokens normais e PATs com o App ID correto)
                    auth_msg = {"authorize": self.token}
                    ws.send(json.dumps(auth_msg))
                        
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    msg_type = data.get("msg_type")
                    
                    if msg_type == "authorize":
                        if "error" in data:
                            self.log(f"Erro de autenticação: {data['error'].get('message')}")
                            self.authorized = False
                            self.disconnect()
                        else:
                            self.authorized = True
                            auth = data.get("authorize", {})
                            self.balance = float(auth.get("balance", 0.0))
                            self.log(f"Autenticado com sucesso! Saldo: ${self.balance:.2f}")
                            # Requisita a proposta para obter o barrier_distance
                            self._request_proposal()
                    elif msg_type == "proposal":
                        if "error" in data:
                            self.log(f"Erro ao obter proposta: {data['error'].get('message')}")
                        else:
                            prop = data.get("proposal", {})
                            self.barrier_distance = prop.get("barrier_distance") or prop.get("contract_details", {}).get("barrier_spot_distance")
                            self.log(f"Distância da barreira obtida: {self.barrier_distance}")
                            # Subscrever aos ticks
                            self._subscribe_ticks()
                            
                    elif msg_type == "tick":
                        tick = data.get("tick", {})
                        price = tick.get("quote")
                        if price is not None and self.barrier_distance is not None:
                            is_crash = False
                            if self.last_tick_price is not None:
                                diff = abs(price - self.last_tick_price)
                                # Se a flutuação superar a distância da barreira, conta como quebra (crash)
                                if diff >= float(self.barrier_distance):
                                    is_crash = True
                            self.last_tick_price = price
                            
                            if self.on_tick_cb:
                                self.on_tick_cb(price, is_crash)
                                
                    elif msg_type == "proposal_open_contract":
                        poc = data.get("proposal_open_contract", {})
                        if poc:
                            self._handle_contract_update(poc)
                            
                    elif msg_type == "buy":
                        if "error" in data:
                            self.log(f"Falha na compra via API: {data['error'].get('message')}")
                        else:
                            buy = data.get("buy", {})
                            contract_id = buy.get("contract_id")
                            self.active_contract_id = contract_id
                            self.log(f"Ordem de Compra executada via API. Contrato ID: {contract_id}")
                            self._subscribe_contract(contract_id)
                            
                    elif msg_type in ["history", "ticks_history"]:
                        if "error" in data:
                            self.log(f"Erro ao carregar histórico: {data['error'].get('message')}")
                        else:
                            history = data.get("history", {})
                            if history and self.on_history_cb:
                                prices = history.get("prices", [])
                                self.on_history_cb(prices)
                                
                    elif msg_type == "ping":
                        if self.ping_sent_time > 0.0:
                            self.latency_ms = int((time.time() - self.ping_sent_time) * 1000)
                                
                except Exception as e:
                    self.log(f"Erro ao processar mensagem WS: {e}")
                
            def on_error(ws, error):
                self.log(f"Erro na conexão WS: {error}")
                
            def on_close(ws, close_status_code, close_msg):
                self.log("Conexão fechada.")
                self.connected = False
                self.authorized = False
                if self.on_connection_change_cb:
                    self.on_connection_change_cb(False)
                
            self.ws = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            # Envia Ping periódico para manter a conexão aberta
            ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            ping_thread.start()
            
            self.ws.run_forever()
            
            if self._stop_event.is_set():
                break
            self.log("Tentando reconectar em 5 segundos...")
            time.sleep(5)

    def _ping_loop(self):
        while self.connected and not self._stop_event.is_set():
            if self.ws and self.connected:
                try:
                    self.ping_sent_time = time.time()
                    self.ws.send(json.dumps({"ping": 1}))
                except Exception:
                    break
            time.sleep(5)

    def _request_proposal(self):
        if self.ws and self.authorized:
            req = {
                "proposal": 1,
                "amount": 1,
                "basis": "stake",
                "contract_type": "ACCU",
                "currency": "USD",
                "underlying_symbol": self.symbol,
                "growth_rate": float(self.growth_rate)
            }
            self.ws.send(json.dumps(req))

    def _subscribe_ticks(self):
        if self.ws and self.authorized:
            self.log(f"Subscrevendo ao canal de ticks para {self.symbol}...")
            self.ws.send(json.dumps({"ticks": self.symbol}))

    def _subscribe_contract(self, contract_id):
        if self.ws and self.authorized:
            self.ws.send(json.dumps({
                "proposal_open_contract": 1,
                "contract_id": contract_id,
                "subscribe": 1
            }))

    def _handle_contract_update(self, poc):
        status = poc.get("status")
        is_sold = poc.get("is_sold", 0)
        profit = float(poc.get("profit", 0.0))
        contract_id = poc.get("contract_id")
        
        if self.on_contract_update_cb:
            try:
                self.on_contract_update_cb(poc)
            except Exception as e:
                self.log(f"Erro no callback de contract_update: {e}")
                
        if is_sold == 1 or status in ["won", "lost"]:
            if contract_id == self.active_contract_id:
                self.active_contract_id = None
                # Atualiza saldo local
                self.balance += profit
                if self.on_contract_status_cb:
                    self.on_contract_status_cb(status, profit)

    def sell_contract(self, contract_id):
        if not self.connected or not self.authorized:
            self.log("Erro: API não autorizada ou não conectada para vender contrato.")
            return False
            
        sell_msg = {
            "sell": contract_id,
            "price": 0
        }
        try:
            self.log(f"Enviando ordem de venda (Take Profit) para o contrato {contract_id}")
            self.ws.send(json.dumps(sell_msg))
            return True
        except Exception as e:
            self.log(f"Erro ao enviar sell via API: {e}")
            return False

    def buy_accumulator(self, stake):
        if not self.connected or not self.authorized:
            self.log("Erro: API não autorizada ou não conectada.")
            return False
            
        buy_msg = {
            "buy": "1",
            "price": 100,
            "parameters": {
                "amount": float(stake),
                "basis": "stake",
                "contract_type": "ACCU",
                "currency": "USD",
                "underlying_symbol": self.symbol,
                "growth_rate": float(self.growth_rate)
            }
        }
        try:
            self.ws.send(json.dumps(buy_msg))
            return True
        except Exception as e:
            self.log(f"Erro ao enviar buy via API: {e}")
            return False

    def buy_rise_fall(self, stake, direction, duration, duration_unit):
        if not self.connected or not self.authorized:
            self.log("Erro: API não autorizada ou não conectada.")
            return False
            
        buy_msg = {
            "buy": "1",
            "price": 100,
            "parameters": {
                "amount": float(stake),
                "basis": "stake",
                "contract_type": "CALL" if direction.lower() == "rise" else "PUT",
                "currency": "USD",
                "underlying_symbol": self.symbol,
                "duration": int(duration),
                "duration_unit": duration_unit
            }
        }
        try:
            self.ws.send(json.dumps(buy_msg))
            return True
        except Exception as e:
            self.log(f"Erro ao enviar buy rise/fall via API: {e}")
            return False

    def buy_digits(self, stake, contract_type, barrier):
        """
        contract_type: "DIGITMATCH" or "DIGITDIFF"
        barrier: last digit prediction (0-9) as an integer or string
        """
        if not self.connected or not self.authorized:
            self.log("Erro: API não autorizada ou não conectada.")
            return False
            
        buy_msg = {
            "buy": "1",
            "price": 100,
            "parameters": {
                "amount": float(stake),
                "basis": "stake",
                "contract_type": contract_type.upper(),
                "barrier": str(barrier),
                "currency": "USD",
                "underlying_symbol": self.symbol,
                "duration": 1,
                "duration_unit": "t"
            }
        }
        try:
            self.ws.send(json.dumps(buy_msg))
            return True
        except Exception as e:
            self.log(f"Erro ao enviar buy digits via API: {e}")
            return False

    def request_ticks_history(self, count=1000, symbol=None):
        if not self.connected or not self.authorized:
            self.log("Erro: API não conectada para puxar histórico.")
            return False
            
        req = {
            "ticks_history": symbol or self.symbol,
            "end": "latest",
            "count": int(count),
            "style": "ticks"
        }
        try:
            self.ws.send(json.dumps(req))
            return True
        except Exception as e:
            self.log(f"Erro ao solicitar histórico de ticks: {e}")
            return False

    def change_symbol(self, new_symbol):
        if self.symbol == new_symbol:
            return
        self.log(f"Alterando ativo da API: {self.symbol} -> {new_symbol}")
        try:
            self.ws.send(json.dumps({"forget_all": "ticks"}))
        except Exception:
            pass
        self.symbol = new_symbol
        self._subscribe_ticks()
        self._request_proposal()
