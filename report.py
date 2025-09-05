import json, time, os

def write_state_report(ts, status, reason, mid, vol_pct, div_bps, extra=None):
    payload = {
        "ts": ts,
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        "status": status,
        "reason": reason,
        "mid": mid,
        "vol_pct": vol_pct,
        "div_bps": div_bps,
        **(extra or {})
    }
    with open("state.json", "w") as f:
        json.dump(payload, f, indent=2)
    # <- QUI era il problema: assicurati che la stringa termini con "\n"
    with open("report.json", "a") as f:
        f.write(json.dumps(payload) + "\n")

def write_orders(open_orders, closed_orders, stats=None):
    payload = {"open": open_orders or [], "closed": closed_orders or [], "stats": stats or {}}
    with open("orders.json", "w") as f:
        json.dump(payload, f, indent=2)

def mirror_config_to_json(cfg):
    with open("config.json", "w") as f:
        json.dump(cfg, f, indent=2)

def bump_trades_today(n=1):
    path = "orders.json"
    data = {"open": [], "closed": [], "stats": {}}
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    stats = data.get("stats", {})
    stats["trades_day"] = int(stats.get("trades_day", 0)) + n
    data["stats"] = stats
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
