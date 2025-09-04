import json
from pathlib import Path
from typing import Any, Dict, Optional
import os, time

STATE_FILE = Path(__file__).resolve().parent / "state.json"

class PionexAPI:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("PIONEX_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("PIONEX_API_SECRET", "")
        if not STATE_FILE.exists():
            STATE_FILE.write_text(json.dumps({"last_params": None, "prices": []}, indent=2))

    def _load(self) -> Dict[str, Any]:
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {"last_params": None, "prices": []}

    def _save(self, st: Dict[str, Any]) -> None:
        STATE_FILE.write_text(json.dumps(st, indent=2))

    def get_market_price(self, ticker: str) -> float:
        st = self._load()
        base = 60000.0
        noise = (time.time() % 1000) / 10.0
        price = base + noise
        st["prices"] = (st.get("prices") or []) + [price]
        st["prices"] = st["prices"][-200:]
        self._save(st)
        return price

    def set_grid_params(self, params: Dict[str, Any]) -> None:
        st = self._load()
        st["last_params"] = params
        self._save(st)

    def get_prices(self) -> list[float]:
        return self._load().get("prices", [])
