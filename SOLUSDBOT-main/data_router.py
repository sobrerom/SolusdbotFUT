from typing import List

def compute_grid(min_price: float, max_price: float, levels: int) -> List[float]:
    if levels < 2:
        return [min_price, max_price]
    step = (max_price - min_price) / (levels - 1)
    return [min_price + i * step for i in range(levels)]
