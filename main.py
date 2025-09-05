import os, time, json, logging, yaml
from typing import Any, Dict

from util import load_state, save_state, now_ms, install_sigterm_handler, should_stop
from datafeeds import fetch_prices
from grid import rolling_std, make_grid
from pid import pid_step
from pionex_api import PionexAPI

logging.basicConfig(level=os.environ.get("LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("solusdbot")

def load_config() -> Dict[str, Any]:
    with open("config.yaml","r",encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def basis_points_diff(a: float, b: float) -> float:
    return abs(a-b)/((a+b)/2.0) * 10000.0

def compute_safe_penalty(vol: float, cfg: Dict[str,Any]) -> float:
    sconf = cfg.get("safe_mode", {})
    if not sconf.get("enable", True): return 0.0
    v0, v1 = float(sconf.get("vol_floor", 0.005)), float(sconf.get("vol_ceiling", 0.03))
    maxp = float(sconf.get("max_penalty", 0.7))
    if vol <= v0: return 0.0
    if vol >= v1: return maxp
    return max(0.0, min(maxp, (vol - v0) / (v1 - v0) * maxp))

def should_suspend(prices, cfg, state) -> bool:
    if len(prices) == 0: return True
    if len(prices) >= 2:
        if basis_points_diff(max(prices), min(prices)) > cfg["max_bp_divergence"]:
            return True
    hist = state.get("prices", [])
    if len(hist) >= 10:
        std = rolling_std(hist, cfg["vol_window"])
        vol = std / (hist[-1] or 1.0)
        if vol > cfg["uncertainty_vol_threshold"]:
            return True
    return False

def should_resume(cfg, state) -> bool:
    hist = state.get("prices", [])
    if len(hist) < 10: return True
    std = rolling_std(hist, cfg["vol_window"])
    vol = std / (hist[-1] or 1.0)
    return vol < cfg["resume_vol_threshold"]

def estimate_daily_return(state: Dict[str,Any]) -> float:
    hist = state.get("prices", [])
    if len(hist) < 20: return 0.0
    s = 0.0
    for a,b in zip(hist[-100:], hist[-99:]):
        s += abs(b-a)/a
    return 0.10 * s

def run_once(cfg: Dict[str,Any], state: Dict[str,Any], api: PionexAPI) -> Dict[str,Any]:
    prices, sources = fetch_prices()
    if len(prices) == 0:
        state["suspended"] = True; save_state(state)
        return {"ok": True, "suspended": True, "reason": "no data sources", "backoff": cfg["daemon"]["backoff_initial"]}

    mid = sum(prices)/len(prices)
    hist = state.get("prices", []); hist.append(mid); state["prices"] = hist[-600:]

    if state.get("suspended", False):
        if should_resume(cfg, state):
            state["suspended"] = False
        else:
            save_state(state)
            return {"ok": True, "suspended": True, "reason":"volatility high/wait", "backoff": cfg["daemon"]["backoff_initial"]}

    if should_suspend(prices, cfg, state):
        state["suspended"] = True; save_state(state)
        return {"ok": True, "suspended": True, "reason":"uncertain market/data", "backoff": cfg["daemon"]["backoff_initial"]}

    std = rolling_std(state["prices"], cfg["vol_window"])
    gmin, gmax, levels = make_grid(mid, std, cfg["band_k"], cfg["grid_levels"])

    target = cfg["target_daily_return"]; realized = estimate_daily_return(state)
    error = target - realized
    pid_state = state.get("pid", {"integral":0.0, "last_error":0.0})
    out, integ = pid_step(error, 1.0, cfg["pid"]["kp"], cfg["pid"]["ki"], cfg["pid"]["kd"], pid_state.get("integral",0.0), pid_state.get("last_error",0.0), cfg["pid"]["integrator_limit"])
    lev = max(cfg["pid"]["output_min"], min(cfg["pid"]["output_max"], out))
    lev = min(lev, cfg["max_leverage"])

    vol_ratio = (std / mid) if mid else 0.0
    penalty = compute_safe_penalty(vol_ratio, cfg)
    lev_eff = lev * (1.0 - penalty)

    pid_state["integral"] = integ; pid_state["last_error"] = error
    state["pid"] = pid_state; state["leverage"] = lev_eff

    params = {
        "symbol": cfg["symbol"],
        "grid": {"min_price": gmin, "max_price": gmax, "levels": int(cfg["grid_levels"]/2)},
        "leverage": lev_eff,
        "mode": "long_short",
        "mid_price": mid,
        "std": std,
        "sources": sources,
        "allocation_usdt": cfg.get("allocation_usdt", 300),
        "min_order_usdt": cfg.get("min_order_usdt", 10)
    }

    result = api.apply_grid(params)
    state["last_apply"] = {"t": now_ms(), "result": result, "params": params}
    save_state(state)

    return {"ok": bool(result.get("ok")), "suspended": False, "mid": mid, "std": std, "lev_eff": lev_eff, "placed": result.get("placed"), "interval": cfg["daemon"]["interval_sec"]}

def main():
    cfg = load_config()
    api = PionexAPI(cfg)
    install_sigterm_handler()

    state = load_state()
    if not cfg.get("daemon", {}).get("enable", True):
        # single run
        out = run_once(cfg, state, api)
        print(json.dumps(out))
        return

    # daemon loop
    start = time.time()
    backoff = cfg["daemon"]["backoff_initial"]
    backoff_max = cfg["daemon"]["backoff_max"]
    interval = cfg["daemon"]["interval_sec"]
    max_runtime = cfg["daemon"]["max_runtime_sec"]

    while True:
        if should_stop():
            print(json.dumps({"ok": True, "stopped": True, "reason": "SIGTERM"}))
            break
        if time.time() - start > max_runtime:
            print(json.dumps({"ok": True, "stopped": True, "reason": "max_runtime"}))
            break
        try:
            out = run_once(cfg, load_state(), api)
            print(json.dumps(out))
            # reset backoff on success or active run
            if not out.get("suspended"):
                time.sleep(interval)
                backoff = cfg["daemon"]["backoff_initial"]
            else:
                time.sleep(min(backoff, backoff_max))
                backoff = min(backoff*2, backoff_max)
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            time.sleep(min(backoff, backoff_max))
            backoff = min(backoff*2, backoff_max)

if __name__ == "__main__":
    main()
