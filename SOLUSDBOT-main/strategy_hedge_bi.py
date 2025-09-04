from typing import Dict, Any, List
import statistics

class StrategyHedgeBI:
    def __init__(self, sma_window: int = 20, levels_bull: int = 60, levels_bear: int = 30) -> None:
        self.sma_window = int(sma_window)
        self.levels_bull = int(levels_bull)
        self.levels_bear = int(levels_bear)

    def apply(self, price: float, history: List[float], config: Dict[str, Any]) -> Dict[str, Any]:
        grid_cfg = (config.get("grid") or {})
        try:
            levels = int(grid_cfg.get("levels", 50))
        except Exception:
            levels = 50
        try:
            min_p = float(grid_cfg.get("min_price", price * 0.98))
        except Exception:
            min_p = price * 0.98
        try:
            max_p = float(grid_cfg.get("max_price", price * 1.02))
        except Exception:
            max_p = price * 1.02

        if history and len(history) >= self.sma_window:
            sma = statistics.fmean(history[-self.sma_window:])
            levels = max(levels, self.levels_bull) if price > sma else min(levels, self.levels_bear)

        if min_p >= max_p:
            mid = price
            min_p, max_p = mid * 0.98, mid * 1.02

        levels = max(2, int(levels))
        return {"levels": int(levels), "min_price": float(min_p), "max_price": float(max_p)}
