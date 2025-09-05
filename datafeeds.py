import requests, math

HEADERS = {"User-Agent": "solusdbot/1.2"}

def _get(url: str, timeout: float = 5.0):
    return requests.get(url, headers=HEADERS, timeout=timeout)

def binance_futures_SOLUSDT():
    url = "https://fapi.binance.com/fapi/v1/ticker/price?symbol=SOLUSDT"
    r = _get(url); r.raise_for_status()
    return float(r.json()["price"])

def bybit_linear_SOLUSDT():
    url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=SOLUSDT"
    r = _get(url); r.raise_for_status()
    rows = r.json().get("result", {}).get("list", [])
    if not rows: return None
    return float(rows[0]["lastPrice"])

def okx_swap_SOL_USDT():
    url = "https://www.okx.com/api/v5/market/ticker?instId=SOL-USDT-SWAP"
    r = _get(url); r.raise_for_status()
    rows = r.json().get("data", [])
    if not rows: return None
    return float(rows[0]["last"])

def fetch_prices():
    prices, tags = [], []
    for fn, name in ((binance_futures_SOLUSDT, "binance"), (bybit_linear_SOLUSDT, "bybit"), (okx_swap_SOL_USDT, "okx")):
        try:
            px = fn()
            if px is not None and math.isfinite(px):
                prices.append(px); tags.append(name)
        except Exception:
            pass
    return prices, tags
