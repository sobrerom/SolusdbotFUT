# diagnostics.py
import json, os, time
from util import load_cfg
from pionex_api import Pionex
from datafeeds import aggregate_quote_sync, get_candles_sync

def _safe_aggregate():
    """Restituisce (mid, vol_pct, div_bps, alive) nel modo più robusto possibile."""
    mid = vol_pct = div_bps = alive = None
    try:
        res = aggregate_quote_sync()
        if isinstance(res, dict):
            mid = res.get("mid")
            vol_pct = res.get("vol_pct")
            div_bps = res.get("div_bps")
            alive = res.get("sources_alive") or res.get("alive") or res.get("quorum")
        elif isinstance(res, (list, tuple)):
            if len(res) >= 4:
                mid, vol_pct, div_bps, alive = res[:4]
            elif len(res) == 3:
                mid, vol_pct, div_bps = res
            elif len(res) == 2:
                mid, vol_pct = res
    except Exception:
        # ignora, proverà il fallback sulle candele
        pass

    if mid is None:
        try:
            candles = get_candles_sync("1m", 5) or []
            if candles:
                c = candles[-1]
                mid = float(c.get("c"))
        except Exception:
            pass
    return mid, vol_pct, div_bps, (alive or 0)

def main():
    out = {"ts": int(time.time()*1000), "checks": []}
    cfg = load_cfg("config.yaml")
    key = os.getenv("PIONEX_API_KEY")
    sec = os.getenv("PIONEX_API_SECRET")
    pnx = Pionex(key, sec, cfg)

    # 1) Balance / auth
    eq = pnx.get_portfolio_equity_usdt()
    out["checks"].append({"name":"auth_balance", "ok": eq is not None, "equityUSDT": eq})

    # 2) Market info
    mi = pnx.market_info()
    ok_mi = bool(mi and mi.get("tick_size") and mi.get("step_size"))
    out["checks"].append({"name":"market_info", "ok": ok_mi, "market_info": mi})

    # 3) Datafeeds / mid
    mid, vol_pct, div_bps, alive = _safe_aggregate()
    out["checks"].append({
        "name":"datafeeds",
        "ok": (alive or 0) > 0 or mid is not None,
        "mid": mid, "vol_pct": vol_pct, "div_bps": div_bps, "sources_alive": alive
    })

    # 4) Qty per livello vs min step
    risk = cfg.get("risk", {})
    eq_eff = eq or float(risk.get("portfolio_usdt_fallback", 10000))
    cap_usdt = max(0.0, min(eq_eff * (risk.get("max_portfolio_pct", 3.0)/100.0), eq_eff))
    base_notional = min(cap_usdt, cfg["grid"]["notional_per_side_usdt"])
    lev_min = cfg.get("leverage",{}).get("min", 0.0)
    lev_max = cfg.get("leverage",{}).get("max", 1.0)
    lev = max(lev_min, min(lev_max, 1.0))
    levels = int(cfg["grid"]["levels"])

    if mid is None or not ok_mi:
        out["checks"].append({"name":"qty_calc", "ok": False, "reason":"no mid or no market info"})
    else:
        qty_per_level = base_notional / max(1, levels) / mid * max(lev, 0.01)
        ok_qty = qty_per_level >= mi["step_size"]
        out["checks"].append({
            "name":"qty_calc", "ok": ok_qty,
            "qty_per_level": qty_per_level, "min_step": mi["step_size"],
            "levels": levels, "base_notional": base_notional, "lev": lev
        })

    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
