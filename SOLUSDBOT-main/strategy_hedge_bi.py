from typing import Dict, Any, List
import statistics

class StrategyHedgeBI:
    def __init__(self, sma_window: int = 20, levels_bull: int = 60, levels_bear: int = 30) -> None:
        self.sma_window = sma_window
        self.levels_bull = levels_bull
        self.levels_bear = levels_bear

    def apply(self, price: float, history: List[float], config: Dict[str, Any]) -> Dict[str, Any]:
        levels = int(config["grid"]["levels"])
        if len(history) >= self.sma_window:
            sma = statistics.fmean(history[-self.sma_window:])
            levels = self.levels_bull if price > sma else self.levels_bear
        min_p = float(config["grid"]["min_price"]); max_p = float(config["grid"]["max_price"])
        if min_p >= max_p:
            mid = price; min_p, max_p = mid * 0.98, mid * 1.02
        return {"levels": levels, "min_price": min_p, "max_price": max_p}
