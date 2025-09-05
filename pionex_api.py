import os, time, hmac, hashlib, json, requests
from typing import Dict, Any, Optional, Tuple
from filters import normalize

API_BASE = "https://api.pionex.com"

class PionexREST:
    def __init__(self, key: Optional[str]=None, secret: Optional[str]=None):
        self.key = key or os.environ.get("PIONEX_API_KEY","")
        self.secret = secret or os.environ.get("PIONEX_API_SECRET","")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent":"solusdbot/1.2"})

    def _ts(self) -> int:
        return int(time.time()*1000)

    def _sign(self, method: str, path: str, query: Dict[str, Any], body: Optional[Dict[str, Any]] = None):
        q = dict(query or {})
        if "timestamp" not in q: q["timestamp"] = self._ts()
        items = sorted([(k, str(v)) for k,v in q.items()], key=lambda x: x[0])
        qs = "&".join([f"{k}={v}" for k,v in items])
        path_url = f"{path}?{qs}"
        payload = f"{method.upper()}{path_url}"
        if body:
            payload = payload + json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        sig = hmac.new(self.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return sig, q

    def _private(self, method: str, path: str, query: Dict[str, Any] = None, body: Dict[str, Any] = None):
        sig, q = self._sign(method, path, query or {}, body)
        headers = {"PIONEX-KEY": self.key, "PIONEX-SIGNATURE": sig, "Content-Type":"application/json"}
        url = API_BASE + path
        if method.upper() == "GET":
            r = self.session.get(url, params=q, headers=headers, timeout=10)
        elif method.upper() == "POST":
            r = self.session.post(url, params=q, data=json.dumps(body or {}), headers=headers, timeout=10)
        elif method.upper() == "DELETE":
            r = self.session.delete(url, params=q, data=json.dumps(body or {}), headers=headers, timeout=10)
        else:
            raise ValueError("Unsupported method")
        r.raise_for_status()
        return r.json()

    # Public-ish endpoints (best-effort; may vary)
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        # Try a generic listing endpoint
        try:
            r = self.session.get(API_BASE + "/api/v1/market/symbols", timeout=10)
            r.raise_for_status()
            data = r.json()
            for s in data.get("data", []):
                if s.get("symbol") == symbol:
                    return s
        except Exception:
            pass
        return {}

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        # Try a generic ticker
        try:
            r = self.session.get(API_BASE + "/api/v1/market/ticker", params={"symbol": symbol}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    # Trading endpoints
    def get_balance(self):
        return self._private("GET", "/api/v1/account/balance", {})

    def new_order(self, symbol: str, side: str, type_: str, size: Optional[str]=None, price: Optional[str]=None, amount: Optional[str]=None, ioc: bool=False, client_id: Optional[str]=None):
        body = {"symbol": symbol, "side": side, "type": type_}
        if size is not None: body["size"] = str(size)
        if price is not None: body["price"] = str(price)
        if amount is not None: body["amount"] = str(amount)
        if ioc: body["IOC"] = True
        if client_id: body["clientOrderId"] = client_id
        return self._private("POST", "/api/v1/trade/order", {}, body)

    def cancel_all(self, symbol: str):
        return self._private("DELETE", "/api/v1/trade/cancelAll", {}, {"symbol": symbol})

    def get_open_orders(self, symbol: str):
        return self._private("GET", "/api/v1/trade/openOrders", {"symbol": symbol})

class PionexAPI:
    def __init__(self, cfg: Dict[str, Any]):
        self.live = str(os.environ.get("LIVE_MODE","true")).lower() in ("1","true","yes","on")
        self.rest = PionexREST()
        self.cfg = cfg
        self.symbol = cfg["symbol"]
        self.price_tick = float(cfg.get("price_tick_size", 0.001))
        self.size_step = float(cfg.get("size_step_size", 0.01))
        self.autodetect_filters()

    def autodetect_filters(self):
        # 1) Try symbol info
        info = {}
        try:
            info = self.rest.get_symbol_info(self.symbol)
        except Exception:
            info = {}
        pt = info.get("priceTickSize")
        qs = info.get("quantityStepSize")
        changed = False
        try:
            if pt is not None:
                self.price_tick = float(pt); changed = True
        except Exception:
            pass
        try:
            if qs is not None:
                self.size_step = float(qs); changed = True
        except Exception:
            pass
        if changed:
            return

        # 2) Try ticker decimals heuristic (last price decimal precision)
        try:
            t = self.rest.get_ticker(self.symbol)
            # Expect something like {"data":{"price":"123.4567"}} or similar
            price = None
            for k in ("price","last","close","lastPrice"):
                if isinstance(t, dict):
                    v = t.get(k) or (t.get("data", {}) if isinstance(t.get("data", {}), dict) else {}).get(k)
                    if v:
                        price = float(v); break
            if price:
                s = str(price)
                if "." in s:
                    dec = len(s.split(".")[1])
                    self.price_tick = min(self.price_tick, 10**(-dec))
        except Exception:
            pass
        # size_step leaves fallback from config

    def normalize(self, price: float, size: float) -> Tuple[float, float]:
        return normalize(price, size, self.price_tick, self.size_step)

    def apply_grid(self, params: Dict[str, Any]) -> Dict[str, Any]:
        symbol = params["symbol"]
        grid = params["grid"]; lev = float(params.get("leverage", 0.0))
        mid = float(params.get("mid_price"))
        levels = int(grid["levels"]); min_p = float(grid["min_price"]); max_p = float(grid["max_price"])
        alloc = float(params.get("allocation_usdt", 100))
        min_order_usdt = float(params.get("min_order_usdt", 10))

        if not self.live:
            return {"ok": True, "live": False, "detail": "DRY-RUN", "summary": {"levels": levels, "min": min_p, "max": max_p, "lev": lev}, "filters": {"price_tick": self.price_tick, "size_step": self.size_step}}

        try:
            self.cancel_all(symbol)
        except Exception:
            pass

        step = (max_p - min_p) / (levels - 1)
        notional = alloc * max(1.0, lev)
        per_order = max(min_order_usdt, notional / (2*levels))

        placed = 0
        p = mid - step/2.0
        while p >= min_p:
            size = per_order / p
            pr, sz = self.normalize(p, size)
            try:
                self.rest.new_order(symbol, "BUY", "LIMIT", size=f"{sz:.8f}", price=f"{pr:.8f}")
                placed += 1
            except Exception:
                pass
            p -= step

        p = mid + step/2.0
        while p <= max_p:
            size = per_order / p
            pr, sz = self.normalize(p, size)
            try:
                self.rest.new_order(symbol, "SELL", "LIMIT", size=f"{sz:.8f}", price=f"{pr:.8f}")
                placed += 1
            except Exception:
                pass
            p += step

        return {"ok": True, "live": True, "placed": placed, "levels": levels, "range": [min_p, max_p], "lev": lev, "filters": {"price_tick": self.price_tick, "size_step": self.size_step}}

    def cancel_all(self, symbol: str):
        try:
            return self.rest.cancel_all(symbol)
        except Exception as e:
            return {"ok": False, "error": str(e)}
