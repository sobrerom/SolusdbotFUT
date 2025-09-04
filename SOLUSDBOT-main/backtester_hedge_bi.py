from typing import List, Dict, Any
def backtest(prices: List[float], params: Dict[str, Any]) -> Dict[str, Any]:
    if not prices: return {"trades": 0, "pnl": 0.0}
    min_p, max_p, levels = params["min_price"], params["max_price"], max(2, int(params["levels"]))
    step = (max_p - min_p) / (levels - 1)
    pnl = 0.0; trades = 0
    for a, b in zip(prices, prices[1:]):
        crosses = int(abs(b - a) // step)
        pnl += crosses * step * 0.001; trades += crosses
    return {"trades": trades, "pnl": round(pnl, 6)}
