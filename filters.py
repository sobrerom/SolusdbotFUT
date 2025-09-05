import math

def round_to_step(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

def normalize(price: float, size: float, price_tick: float, size_step: float):
    p = round_to_step(price, price_tick)
    q = round_to_step(size, size_step)
    return (round(p, 10), round(q, 10))
