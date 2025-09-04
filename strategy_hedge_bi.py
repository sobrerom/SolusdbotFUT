from typing import Dict, Any, List
import statistics


class StrategyHedgeBI:
    """Simple strategy placeholder with a trend filter.
    - Uses SMA(n) to adjust grid width.
    - If price > SMA => bullish: tighten grid (more levels).
    - If price < SMA => bearish: widen grid (fewer levels).
    """

    def __init__(self, sma_window: int = 20, levels_bull: int = 60, levels_bear: int = 30) -> None:
        self.sma_window = sma_window
        self.levels_bull = levels_bull
        self.levels_bear = levels_bear

    def apply(self, price: float, history: List[float], config: Dict[str, Any]) -> Dict[str, Any]:
        levels = config["grid"]["levels"]
        if len(history) >= self.sma_window:
            sma = statistics.fmean(history[-self.sma_window:])
            if price > sma:
                levels = max(levels, self.levels_bull)
            else:
                levels = min(levels, self.levels_bear)

        # Boundaries from config
        min_p = float(config["grid"]["min_price"])
        max_p = float(config["grid"]["max_price"])
        if min_p >= max_p:
            # auto widen if misconfigured
            mid = price
            min_p, max_p = mid * 0.98, mid * 1.02

        return {
            "levels": int(levels),
            "min_price": min_p,
            "max_price": max_p,
        }
