import time, asyncio, aiohttp
from statistics import fmean, pstdev
from collections import deque

BINANCE_F = "https://fapi.binance.com"
BYBIT = "https://api.bybit.com"
OKX   = "https://www.okx.com"

BINANCE_SYMBOL = "SOLUSDT"
BYBIT_SYMBOL   = "SOLUSDT"
OKX_INST_ID    = "SOL-USDT-SWAP"

_vol_window = deque(maxlen=300)

async def fetch_json(session, url, params=None):
    for _ in range(2):
        try:
            async with session.get(url, params=params, timeout=5) as r:
                if r.status == 200:
                    return await r.json()
        except Exception:
            await asyncio.sleep(0.2)
    return None

async def binance_mid(session):
    j = await fetch_json(session, f"{BINANCE_F}/fapi/v1/ticker/bookTicker", {"symbol": BINANCE_SYMBOL})
    if not j: return None
    try:
        b = float(j["bidPrice"]); a = float(j["askPrice"]); return (a+b)/2.0
    except Exception: return None

async def bybit_mid(session):
    j = await fetch_json(session, f"{BYBIT}/v5/market/tickers", {"category":"linear","symbol": BYBIT_SYMBOL})
    try:
        it = j.get("result",{}).get("list",[]); i = it[0]
        b = float(i["bid1Price"]); a = float(i["ask1Price"]); return (a+b)/2.0
    except Exception: return None

async def okx_mid(session):
    j = await fetch_json(session, f"{OKX}/api/v5/market/ticker", {"instId": OKX_INST_ID})
    try:
        i = j.get("data",[])[0]
        b = float(i["bidPx"]); a = float(i["askPx"]); return (a+b)/2.0
    except Exception: return None

def aggregate_quote_sync():
    return asyncio.run(_aggregate_quote())

async def _aggregate_quote():
    async with aiohttp.ClientSession() as session:
        mids = await asyncio.gather(binance_mid(session), bybit_mid(session), okx_mid(session))
    quotes = [q for q in mids if q is not None]
    ts = time.time()
    if len(quotes) == 0:
        return None, 0.0, 0.0, ts, 0
    mid = fmean(quotes)
    qmax, qmin = max(quotes), min(quotes)
    divergence_bps = (qmax - qmin) / mid * 1e4
    _vol_window.append(mid)
    if len(_vol_window) > 2:
        rets = [(_vol_window[i]/_vol_window[i-1]-1.0) for i in range(1, len(_vol_window))]
        vol = (pstdev(rets) * 100.0) if len(rets) > 1 else 0.0
    else:
        vol = 0.0
    return mid, vol, divergence_bps, ts, len(quotes)

async def binance_klines(session, interval="1m", limit=200):
    j = await fetch_json(session, f"{BINANCE_F}/fapi/v1/klines", {"symbol": BINANCE_SYMBOL, "interval": interval, "limit": limit})
    if not j: return []
    out = []
    for k in j:
        o,h,l,c,v,t = float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5]),int(k[0])
        out.append((t,o,h,l,c,v))
    return out

async def bybit_klines(session, interval="1", limit=200):
    j = await fetch_json(session, f"{BYBIT}/v5/market/kline", {"category":"linear","symbol": BYBIT_SYMBOL, "interval": interval, "limit": limit})
    if not j: return []
    arr = j.get("result",{}).get("list",[])
    out = []
    for k in reversed(arr):
        t = int(k[0]); o,h,l,c,v = map(float, [k[1],k[2],k[3],k[4],k[5]])
        out.append((t,o,h,l,c,v))
    return out

async def okx_klines(session, bar="1m", limit=200):
    j = await fetch_json(session, f"{OKX}/api/v5/market/candles", {"instId": OKX_INST_ID, "bar": bar, "limit": limit})
    if not j: return []
    arr = j.get("data",[])
    out = []
    for k in reversed(arr):
        t = int(k[0]); o,h,l,c,v = map(float, [k[1],k[2],k[3],k[4],k[5]])
        out.append((t,o,h,l,c,v))
    return out

def get_candles_sync(timeframe="1m", limit=200):
    return asyncio.run(_get_candles(timeframe, limit))

async def _get_candles(timeframe, limit):
    async with aiohttp.ClientSession() as session:
        if timeframe in ("1m","1"):
            res = await binance_klines(session, "1m", limit) or await bybit_klines(session, "1", limit) or await okx_klines(session, "1m", limit)
            return res
        elif timeframe in ("5m","5"):
            res = await binance_klines(session, "5m", limit) or await bybit_klines(session, "5", limit) or await okx_klines(session, "5m", limit)
            return res
        return []
