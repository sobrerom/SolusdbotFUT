import os, json, logging
from pathlib import Path
from typing import Any, Dict
import yaml
from .pionex_api import PionexAPI
from .strategy_hedge_bi import StrategyHedgeBI
from .data_router import compute_grid
from .backtester_hedge_bi import backtest

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOGS / "solusdbot.log")])
log = logging.getLogger("solusdbot")

def load_config() -> Dict[str, Any]:
    for p in (Path.cwd() / "config.yaml", Path.cwd() / "config.example.yaml"):
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8"))
    return {"base_asset":"BTC","quote_asset":"USDT","grid":{"min_price":58000,"max_price":62000,"levels":50},
            "trend":{"sma_window":20,"levels_bull":60,"levels_bear":30}}

def main() -> None:
    cfg = load_config()
    api = PionexAPI()
    ticker = f"{cfg['base_asset']}{cfg['quote_asset']}"
    price = api.get_market_price(ticker); hist = api.get_prices()
    strat = StrategyHedgeBI(**{k:int(v) for k,v in cfg.get("trend",{}).items() if isinstance(v,(int,str))})
    adj = strat.apply(price, hist, cfg); grid = compute_grid(adj["min_price"], adj["max_price"], adj["levels"])
    params = {"ticker":ticker,"price":price,**adj,"grid_preview":grid[:5]+['...']+grid[-5:]}
    api.set_grid_params(params)
    bt = backtest(hist[-100:], adj)
    log.info("Applied params: %s", json.dumps(params, default=str))
    log.info("Backtest(trailing): %s", bt)
    print(json.dumps({"ok": True, "params": params, "backtest": bt}))

if __name__ == "__main__":
    main()
