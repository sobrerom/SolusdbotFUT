import os
import json
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

from .pionex_api import PionexAPI
from .strategy_hedge_bi import StrategyHedgeBI
from .data_router import compute_grid
from .backtester_hedge_bi import backtest

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS / "solusdbot.log")
    ]
)
log = logging.getLogger("solusdbot")


def load_config() -> Dict[str, Any]:
    cfg_file = Path.cwd() / "config.yaml"
    if not cfg_file.exists():
        # fallback: example
        cfg_file = Path.cwd() / "config.example.yaml"
    with cfg_file.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    config = load_config()
    api = PionexAPI()

    ticker = f"{config['base_asset']}{config['quote_asset']}"
    price = api.get_market_price(ticker)
    history = api.get_prices()

    strat = StrategyHedgeBI(
        sma_window=int(config.get("trend", {}).get("sma_window", 20)),
        levels_bull=int(config.get("trend", {}).get("levels_bull", 60)),
        levels_bear=int(config.get("trend", {}).get("levels_bear", 30)),
    )
    adj = strat.apply(price, history, config)

    grid = compute_grid(adj["min_price"], adj["max_price"], adj["levels"])

    params = {
        "ticker": ticker,
        "price": price,
        "levels": adj["levels"],
        "min_price": adj["min_price"],
        "max_price": adj["max_price"],
        "grid_preview": grid[:5] + ["..."] + grid[-5:],
    }

    # Persist last applied params (acts as source of truth if API lacks getters)
    api.set_grid_params(params)

    # Optional: quick toy backtest on trailing history
    bt = backtest(history[-100:], adj)

    log.info("Applied params: %s", json.dumps(params, default=str))
    log.info("Backtest(trailing): %s", bt)

    # Emit a concise JSON line for CI logs / dashboards
    print(json.dumps({"ok": True, "params": params, "backtest": bt}))

if __name__ == "__main__":
    main()
