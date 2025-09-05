# alpha.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import math, statistics, time

@dataclass
class AlphaConfig:
    # Pesi segnali
    w_breakout: float = 0.6
    w_grid_bias: float = 0.4
    # Parametri breakout
    lookback: int = 60            # campioni per canale
    breakout_thr_bps: float = 4.0 # soglia breakout (bps rispetto al mid)
    # Volatilità
    vol_lookback: int = 120
    # Normalizzazione / finestre statistiche
    norm_len: int = 200           # finestra “lunga” per median/span
    # Output clamp
    alpha_min: float = -1.0
    alpha_max: float = 1.0

class AlphaDetector:
    """
    Combina un segnale di breakout (canale + soglia in bps) con un bias mean-reverting
    verso la mediana locale (utile per la componente grid). Output ∈ [-1,1].
    Compatibile con AlphaDetector(norm_len=...).
    """
    def __init__(self, cfg: Optional[AlphaConfig] = None, **kwargs) -> None:
        # cfg esplicita o default
        self.cfg = cfg or AlphaConfig()
        # Consenti override da kwargs (es. norm_len passato da main.py)
        if "norm_len" in kwargs and isinstance(kwargs["norm_len"], (int, float)):
            self.cfg.norm_len = int(kwargs.pop("norm_len")) or self.cfg.norm_len
        # Ignora eventuali altre kwargs future-compatibili
        self._mid_hist: List[float] = []
        self._last_alpha: float = 0.0
        self._last_ts: float = 0.0
        self.box_bot = None  # placeholder opzionale

    # ---------------------- Helpers ----------------------
    @staticmethod
    def _pct(a: float, b: float) -> float:
        if b == 0 or not math.isfinite(a) or not math.isfinite(b):
            return 0.0
        return (a / b) - 1.0

    def _realized_vol(self, series: List[float], win: int) -> float:
        if len(series) < win + 1:
            return 0.0
        rets = []
        for i in range(-win, -1):
            p0, p1 = series[i - 1], series[i]
            if p0 and p1:
                rets.append(math.log(p1 / p0))
        return float(statistics.pstdev(rets)) if rets else 0.0

    # ---------------------- Signals ----------------------
    def _breakout_signal(self, series: List[float]) -> float:
        lb = int(self.cfg.lookback)
        if len(series) < max(10, lb):
            return 0.0
        window = series[-lb:]
        p = series[-1]
        hi = max(window); lo = min(window)
        mid = (hi + lo) / 2.0
        span = max(1e-9, hi - lo)

        # distanza dal centro (normalizzata sul canale)
        bias = (p - mid) / span  # ~[-0.5..0.5]
        # soglia in bps rispetto al mid
        thr = self.cfg.breakout_thr_bps / 1e4
        passed = abs(self._pct(p, max(1e-9, mid))) > thr

        # più ci si avvicina ai bordi, più “decisa” la spinta
        edge = max(abs((p - hi) / max(1e-9, hi)),
                   abs((p - lo) / max(1e-9, lo)))

        sig = bias * (1.0 + edge)
        if not passed:
            sig *= 0.5  # attenua se non supera la soglia
        return max(-1.0, min(1.0, sig))

    def _grid_bias_signal(self, series: List[float]) -> float:
        n = int(self.cfg.norm_len) if self.cfg.norm_len and self.cfg.norm_len > 0 else 200
        m = min(n, len(series))
        if m < 20:
            return 0.0
        window = series[-m:]
        p = window[-1]
        med = statistics.median(window)
        span = max(1e-9, (max(window) - min(window)))
        # Mean-reversion verso la mediana
        sig = (med - p) / span  # segno inverso: se p > med → negativo
        return max(-1.0, min(1.0, sig))

    # ---------------------- Public API ----------------------
    def update(self, mid: float) -> float:
        if not math.isfinite(mid):
            return self._last_alpha
        self._mid_hist.append(float(mid))
        # evita crescita illimitata
        if len(self._mid_hist) > 20_000:
            self._mid_hist = self._mid_hist[-10_000:]

        self._last_alpha = self.compute_alpha_signal()
        self._last_ts = time.time()
        return self._last_alpha

    def compute_alpha_signal(self) -> float:
        if not self._mid_hist:
            return 0.0
        breakout = self._breakout_signal(self._mid_hist)
        grid_bias = self._grid_bias_signal(self._mid_hist)

        w1 = float(self.cfg.w_breakout)
        w2 = float(self.cfg.w_grid_bias)
        raw = w1 * breakout + w2 * grid_bias
        alpha = max(self.cfg.alpha_min, min(self.cfg.alpha_max, raw))
        return float(alpha)

    def state(self) -> Dict[str, Any]:
        return {"alpha": self._last_alpha, "ts": self._last_ts, "hist_len": len(self._mid_hist)}
