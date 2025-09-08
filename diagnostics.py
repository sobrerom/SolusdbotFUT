import json, os, time
from util import load_cfg
from pionex_api import Pionex
from datafeeds import aggregate_quote_sync

def main():
    out = {"ts": int(time.time()*1000), "checks": []}
    cfg = load_cfg("config.yaml")
    key = os.getenv("PIONEX_API_KEY")
    sec = os.getenv("PIONEX_API_SECRET")
    pnx = Pionex(key, sec, cfg)

    eq = pnx.get_portfolio_equity_usdt()
    out["checks"].append({"name":"auth_balance", "ok": eq is not None, "equityUSDT": eq})

    mi = pnx.market_info()
    out["checks"].append({"name":"market_info", "ok": bool(mi and mi.get("tick_size") and mi.get("step_size")), "market_info": mi})

    mid, vol_pct, div_bps, alive = aggregate_quote_sync()
    out["checks"].append({"name":"datafeeds", "ok": alive>0, "mid": mid, "vol_pct": vol_pct, "div_bps": div_bps, "sources_alive": alive})

    risk = cfg.get("risk", {})
    eq_eff = eq or float(risk.get("portfolio_usdt_fallback", 10000))
    cap_usdt = max(0.0, min(eq_eff * (risk.get("max_portfolio_pct", 3.0)/100.0), eq_eff))
    base_notional = min(cap_usdt, cfg["grid"]["notional_per_side_usdt"])
    lev_min, lev_max = cfg.get("leverage",{}).get("min",0.0), cfg.get("leverage",{}).get("max",1.0)
    lev = max(lev_min, min(lev_max, 1.0))
    levels = int(cfg["grid"]["levels"])

    if not mid or not mi:
        out["checks"].append({"name":"qty_calc", "ok": False, "reason":"no mid or no market info"})
    else:
        qty_per_level = base_notional / max(1,levels) / mid * max(lev, 0.01)
        ok_qty = qty_per_level >= mi["step_size"]
        out["checks"].append({
            "name":"qty_calc", "ok": ok_qty,
            "qty_per_level": qty_per_level, "min_step": mi["step_size"],
            "levels": levels, "base_notional": base_notional, "lev": lev
        })

    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
