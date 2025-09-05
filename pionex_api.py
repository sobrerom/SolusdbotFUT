import time, json, requests, hmac, hashlib

class Pionex:
    def __init__(self, key, secret, cfg):
        self.key, self.secret = key, secret
        self.cfg = cfg
        self._mktinfo = None
        self.base = cfg["pionex"].get("base_url","https://api.pionex.com")
        ep = cfg["pionex"].get("endpoints",{})
        self.paths = {
            "market_info": ep.get("market_info","/api/v1/marketInfo"),
            "balance":    ep.get("balance","/api/v1/account"),
            "open_orders":ep.get("open_orders","/api/v1/orders/open"),
            "place_order":ep.get("place_order","/api/v1/order"),
            "cancel_all": ep.get("cancel_all","/api/v1/orders/cancelAll"),
            "fills":      ep.get("fills","/api/v1/fills"),
        }
        self.h_key  = cfg["pionex"].get("key_header","X-API-KEY")
        self.h_sign = cfg["pionex"].get("sign_header","X-API-SIGN")
        self.h_ts   = cfg["pionex"].get("ts_header","X-API-TS")

    def _sign(self, ts, method, path, body_str=""):
        prehash = f"{ts}{method.upper()}{path}{body_str}".encode()
        return hmac.new(self.secret.encode(), prehash, hashlib.sha256).hexdigest()

    def _headers(self, ts, sig):
        return { self.h_key: self.key, self.h_sign: sig, self.h_ts: str(ts), "Content-Type":"application/json" }

    def _request(self, method, path, params=None, body=None):
        url = self.base + path
        ts = int(time.time()*1000)
        body_str = json.dumps(body, separators=(",",":")) if (body and method.upper()!="GET") else ""
        sig = self._sign(ts, method, path, body_str)
        headers = self._headers(ts, sig)
        if method.upper()=="GET":
            r = requests.get(url, headers=headers, params=params, timeout=10)
        else:
            r = requests.post(url, headers=headers, params=params, data=body_str, timeout=10)
        r.raise_for_status()
        try: return r.json()
        except Exception: return {"raw": r.text}

    # ----- Public helpers -----
    def market_info(self):
        if self._mktinfo: return self._mktinfo
        try:
            info = self._request("GET", self.paths["market_info"], params={"symbol": self.cfg["pionex"]["symbol"]})
            tick = float(info.get("tickSize")) if isinstance(info, dict) else None
            step = float(info.get("stepSize")) if isinstance(info, dict) else None
        except Exception:
            tick = None; step = None
        tick = tick or self.cfg["pionex"].get("tick_size") or 0.001
        step = step or self.cfg["pionex"].get("step_size") or 0.001
        self._mktinfo = {"tick_size": tick, "step_size": step}
        return self._mktinfo

    def _norm_price(self, p):
        tick = self.market_info()["tick_size"]
        return round(p / tick) * tick

    def _norm_qty(self, q):
        step = self.market_info()["step_size"]
        return round(q / step) * step

    # ----- Trading helpers -----
    def sync_replace_grid(self, symbol, lower, upper, levels, qty, price_ref):
        # cancel all then place symmetric grid
        try:
            self._request("POST", self.paths["cancel_all"], body={"symbol": symbol})
        except Exception:
            pass
        placed = 0
        step = (upper - lower)/max(1,levels-1)
        for i in range(levels):
            price = lower + i*step
            price = self._norm_price(price)
            q = self._norm_qty(qty)
            # BUY below mid, SELL above mid (symmetric)
            side = "BUY" if price <= price_ref else "SELL"
            try:
                self._request("POST", self.paths["place_order"], body={
                    "symbol": symbol, "side": side, "type":"LIMIT",
                    "price": price, "quantity": q, "timeInForce":"GTC"
                })
                placed += 1
            except Exception:
                continue
        return {"ok": True, "placed": placed}

    def list_open_orders(self, symbol):
        try:
            j = self._request("GET", self.paths["open_orders"], params={"symbol": symbol})
            if isinstance(j, dict) and "orders" in j: return j["orders"]
            # else try pass-through format
            if isinstance(j, list): return j
        except Exception:
            pass
        return []

    def list_recent_fills(self, symbol, limit=50):
        try:
            j = self._request("GET", self.paths["fills"], params={"symbol": symbol, "limit": limit})
            if isinstance(j, dict) and "fills" in j: return j["fills"]
            if isinstance(j, list): return j
        except Exception:
            pass
        return []

    def get_portfolio_equity_usdt(self):
        try:
            j = self._request("GET", self.paths["balance"], params={})
            # try common fields
            if isinstance(j, dict):
                for k in ["equityUSDT","equity_usdt","totalEquityUSDT","equity"]:
                    if k in j:
                        return float(j[k])
                # maybe balances list
                for arr_key in ["balances","assets"]:
                    arr = j.get(arr_key, [])
                    for a in arr:
                        if str(a.get("asset","USDT")).upper()=="USDT" and ("equity" in a or "balance" in a):
                            return float(a.get("equity", a.get("balance")))
        except Exception:
            pass
        return None
