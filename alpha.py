# alpha.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import math
import statistics
import time


@dataclass
class AlphaConfig:
    # Pesi segnali
    w_breakout: float = 0.6
    w_grid_bias: float = 0.4
    # Parametri breakout
    lookback: int = 60          # campioni
    breakout_thr_bps: float = 4 # soglia in bps
    # Volatilità
    vol_lookback: int = 120
    # Output clamp
    alpha_min: float = -1.0
    alpha_max: float = 1.0


class AlphaDetector:
    """
    Combina un segnale breakout (basato su canale/volatilità) con un bias per la grid.
    Restituisce un alpha in [-1, 1].
    """
    def __init__(self, cfg: Optional[AlphaConfig] = None) -> None:
        self.cfg = cfg or AlphaConfig()
        self._mid_hist: List[float] = []
        self._last_alpha: float = 0.0
        self._last_ts: float = 0.0
        # placeholder per eventuale oggetto esterno (es. “box bot”)
        self.box_bot = None  # <— riga indicata: corretta indentazione

    # ---------------------- Helpers ----------------------

    @staticmethod
    def _bps(pct: float) -> float:
        return pct * 1e4

    @staticmethod
    def _pct(a: float, b: float) -> float:
        if b == 0 or not math.isfinite(a) or not math.isfinite(b):
            return 0.0
        return (a / b) - 1.0

    def _realized_vol(self, series: List[float], win: int) -> float:
        """Dev stdev sui rendimenti log (approx) per finestra win."""
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
        """Breakout su canale semplice + soglia in bps normalizzata su prezzo."""
        lb = self.cfg.lookback
        if len(series) < max(10, lb):
            return 0.0
        window = series[-lb:]
        p = series[-1]
        hi = max(window)
        lo = min(window)
        mid = (hi + lo) / 2.0
        span = max(1e-9, hi - lo)

        # distanza dal centro del canale, normalizzata
        bias = (p - mid) / span  # ~[-0.5..0.5] tipicamente
        # breakout forte quando p vicino ai bordi
        edge = max(abs((p - hi) / max(1e-9, hi)),
                   abs((p - lo) / max(1e-9, lo)))
        # threshold in bps sul prezzo
        thr = self.cfg.breakout_thr_bps / 1e4
        passed = abs((p - mid) / max(1e-9, mid)) > thr

        sig = bias * (1.0 + edge)
        if not passed:
            sig *= 0.5  # attenua se non supera la soglia
        return max(-1.0, min(1.0, sig))

    def _grid_bias_signal(self, series: List[float]) -> float:
        """Bias lievemente mean-reverting verso la mediana locale."""
        if len(series) < 20:
            return 0.0
        p = series[-1]
        med = statistics.median(series[-40:]) if len(series) >= 40 else statistics.median(series[-20:])
        span = max(1e-9, (max(series[-40:]) - min(series[-40:])) if len(series) >= 40 else (max(series[-20:]) - min(series[-20:])))
        # Segno inverso (ritorno verso mediana)
        sig = (med - p) / span
        return max(-1.0, min(1.0, sig))

    # ---------------------- Public API ----------------------

    def update(self, mid: float) -> float:
        """Aggiorna lo stato con l’ultimo mid e calcola alpha."""
        if not math.isfinite(mid):
            return self._last_alpha
        self._mid_hist.append(float(mid))
        # limita la dimensione dell’history (evita crescita infinita)
        if len(self._mid_hist) > 10_000:
            self._mid_hist = self._mid_hist[-5000:]

        self._last_alpha = self.compute_alpha_signal()
        self._last_ts = time.time()
        return self._last_alpha

    def compute_alpha_signal(self) -> float:
        if not self._mid_hist:
            return 0.0
        breakout = self._breakout_signal(self._mid_hist)
        grid_bias = self._grid_bias_signal(self._mid_hist)

        w1, w2 = self.cfg.w_breakout, self.cfg.w_grid_bias
        raw = w1 * breakout + w2 * grid_bias
        alpha = max(self.cfg.alpha_min, min(self.cfg.alpha_max, raw))
        return float(alpha)

    # opzionale: accessori per esportazione stato
    def state(self) -> Dict[str, Any]:
        return {
            "alpha": self._last_alpha,
            "ts": self._last_ts,
            "hist_len": len(self._mid_hist),
        }
