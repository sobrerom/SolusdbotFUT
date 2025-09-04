import json
from pathlib import Path
from typing import Any, Dict, Optional
import os
import time

STATE_FILE = Path(__file__).resolve().parent / "state.json"


class PionexAPI:
    """Minimal Pionex API wrapper (stubbed).
    Replace stubbed methods with real HTTP calls if/when needed.
    Persists last-applied parameters and last price to state.json.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("PIONEX_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("PIONEX_API_SECRET", "")
        self._ensure_state()

    def _ensure_state(self) -> None:
        if not STATE_FILE.exists():
            STATE_FILE.write_text(json.dumps({"last_params": None, "prices": []}, indent=2))

    def _load_state(self) -> Dict[str, Any]:
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {"last_params": None, "prices": []}

    def _save_state(self, state: Dict[str, Any]) -> None:
        STATE_FILE.write_text(json.dumps(state, indent=2))

    def get_market_price(self, ticker: str) -> float:
        """Stub: returns a pseudo price; replace with real API price fetch."""
        state = self._load_state()
        # generate a pseudo price using time as noise around 60000
        base = 60000.0
        noise = (time.time() % 1000) / 10.0  # 0..100 range
        price = base + noise
        # Maintain a rolling window of last 200 prices
        prices = (state.get("prices") or []) + [price]
        state["prices"] = prices[-200:]
        self._save_state(state)
        return price

    def set_grid_params(self, params: Dict[str, Any]) -> None:
        state = self._load_state()
        state["last_params"] = params
        self._save_state(state)

    def get_last_params(self) -> Optional[Dict[str, Any]]:
        state = self._load_state()
        return state.get("last_params")

    def get_prices(self) -> list[float]:
        state = self._load_state()
        return state.get("prices", [])
