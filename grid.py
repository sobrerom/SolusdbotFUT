import statistics
from typing import List, Tuple

def rolling_std(prices: List[float], window: int) -> float:
    if len(prices) < 2: return 0.0
    data = prices[-window:] if len(prices) >= window else prices
    if len(data) < 2: return 0.0
    return statistics.pstdev(data)

def make_grid(center_price: float, std: float, k: float, levels: int) -> Tuple[float,float,int]:
    band = max(0.01 * center_price, k * std)
    min_p = center_price - band
    max_p = center_price + band
    levels = max(2, int(levels))
    return min_p, max_p, levels
