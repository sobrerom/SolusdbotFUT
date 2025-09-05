import json, yaml
from pionex_api import PionexAPI

def load_config():
    with open("config.yaml","r",encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def main():
    cfg = load_config()
    api = PionexAPI(cfg)
    rep = {"live": api.live, "symbol": cfg["symbol"], "filters": {"price_tick": api.price_tick, "size_step": api.size_step}}
    try:
        rep["open_orders"] = api.rest.get_open_orders(cfg["symbol"])
    except Exception as e:
        rep["open_orders_error"] = str(e)
    try:
        rep["balance"] = api.rest.get_balance()
    except Exception as e:
        rep["balance_error"] = str(e)
    with open("report.json","w",encoding="utf-8") as f:
        json.dump(rep, f, indent=2)

if __name__ == "__main__":
    main()
