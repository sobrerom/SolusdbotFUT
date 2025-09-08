import os, json
from util import load_cfg
from pionex_api import Pionex

def main():
    cfg = load_cfg("config.yaml")
    pnx = Pionex(os.getenv("PIONEX_API_KEY"), os.getenv("PIONEX_API_SECRET"), cfg)
    sym = cfg["pionex"]["symbol"]
    mi = pnx.market_info()
    q = max(mi["step_size"], 0.001)
    mid = 100.0  # placeholder

    try:
        r1 = pnx.place_breakout_entry(symbol=sym, side="BUY", price_ref=mid, qty=q,
                                      sl_price=None, tp_price=None,
                                      entry_kind="IOC", reduce_only=True)
    except Exception as e:
        r1 = {"ok": False, "error": str(e)}
    try:
        r2 = pnx.place_breakout_entry(symbol=sym, side="SELL", price_ref=mid, qty=q,
                                      sl_price=None, tp_price=None,
                                      entry_kind="IOC", reduce_only=True)
    except Exception as e:
        r2 = {"ok": False, "error": str(e)}

    print(json.dumps({"buy_ioc_reduceonly": r1, "sell_ioc_reduceonly": r2}, indent=2))

if __name__ == "__main__":
    main()
