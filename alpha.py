# alpha.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math, statistics, time

@dataclass
class AlphaConfig:
    # Pesi segnali
    w_breakout: float = 0.6
    w_grid_bias: float = 0.4
    # Parametri breakout
    lookback: int = 60             # campioni per canale
    breakout_thr_bps: float = 4.0  # soglia breakout in bps rispetto al mid del canale
    # Volatilità
    vol_lookback: int = 120        # finestra per realized vol
    # Normalizzazione / finestre statistiche
    norm_len: int = 200            # finestra “lunga” per bias grid (mediana/span)
    # Clamp output
    alpha_min: float = -1.0
    alpha_max: float = 1.0

class AlphaDetector:
    """
    Rilevatore di alpha combinando:
      - breakout su canale (hi/lo ultimi N)
      - bias mean-reverting verso mediana (norm_len)
    Compatibile con:
      - update(o,h,l,c,v)  -> (alpha, box_top, box_bot, vol_norm)
      - update(mid)        -> (alpha, box_top, box_bot, vol_norm)
    """
    def __init__(self, cfg: Optional[AlphaConfig] = None, **kwargs) -> None:
        self.cfg = cfg or AlphaConfig()
        if "norm_len" in kwargs and isinstance(kwargs["norm_len"], (int, float)):
            self.cfg.norm_len = int(kwargs.pop("norm_len")) or self.cfg.norm_len
        # storici
        self._opens:  List[float] = []
        self._highs:  List[float] = []
        self._lows:   List[float] = []
        self._closes: List[float] = []
        self._vols:   List[float] = []
        # cache/ultimo stato
        self._last_alpha: float = 0.0
        self._last_ts: float = 0.0
        self.box_top: float = float("nan")
        self.box_bot: float = float("nan")
        self.box_mid: float = float("nan")
        self._mid_hist: List[float] = []  # per compatibilità e per fallback
        self.box_bot = None  # placeholder opzionale compat con versioni precedenti

    # ---------------------- Helpers ----------------------
    @staticmethod
    def _pct(a: float, b: float) -> float:
        if b == 0 or not math.isfinite(a) or not math.isfinite(b):
            return 0.0
        return (a / b) - 1.0

    def _realized_vol(self, series: List[float], win: int) -> float:
        """Dev standard su rendimenti log in finestra 'win' (non annualizzata)."""
        if len(series) < win + 1:
            return 0.0
        rets = []
        s = series[-(win+1):]
        for i in range(1, len(s)):
            p0, p1 = s[i-1], s[i]
            if p0 and p1 and math.isfinite(p0) and math.isfinite(p1):
                rets.append(math.log(p1 / p0))
        return float(statistics.pstdev(rets)) if rets else 0.0

    def _channel(self, highs: List[float], lows: List[float], lb: int) -> Tuple[float,float,float]:
        if not highs or not lows or len(highs) < 1 or len(lows) < 1:
            return (float("nan"), float("nan"), float("nan"))
        n = min(lb, len(highs), len(lows))
        hi = max(highs[-n:])
        lo = min(lows[-n:])
        mid = (hi + lo) / 2.0
        return (hi, lo, mid)

    # ---------------------- Signals ----------------------
    def _breakout_signal(self, p: float, hi: float, lo: float) -> float:
        if not all(map(math.isfinite, [p, hi, lo])):
            return 0.0
        span = max(1e-9, hi - lo)
        mid = (hi + lo) / 2.0
        bias = (p - mid) / span  # ~[-0.5..0.5]
        thr = self.cfg.breakout_thr_bps / 1e4
        passed = abs(self._pct(p, max(1e-9, mid))) > thr
        edge = max(abs((p - hi) / max(1e-9, hi)),
                   abs((p - lo) / max(1e-9, lo)))
        sig = bias * (1.0 + edge)
        if not passed:
            sig *= 0.5
        return max(-1.0, min(1.0, sig))

    def _grid_bias_signal(self, closes: List[float]) -> float:
        if not closes:
            return 0.0
        n = int(self.cfg.norm_len) if self.cfg.norm_len and self.cfg.norm_len > 0 else 200
        m = min(n, len(closes))
        if m < 20:
            return 0.0
        window = closes[-m:]
        p = window[-1]
        med = statistics.median(window)
        span = max(1e-9, (max(window) - min(window)))
        sig = (med - p) / span  # mean-reversion verso la mediana
        return max(-1.0, min(1.0, sig))

    # ---------------------- Public API ----------------------
    def update(self, *args) -> Tuple[float, float, float, float]:
        """
        update(o,h,l,c,v) -> tuple(alpha, box_top, box_bot, vol_norm)
        update(mid)       -> tuple(alpha, box_top, box_bot, vol_norm)
        """
        if len(args) == 1:
            mid = float(args[0])
            if not math.isfinite(mid):
                return (self._last_alpha, self.box_top, self.box_bot, 0.0)
            # Fallback: trattiamo come close; hi/lo sintetici
            self._opens.append(mid)
            self._highs.append(mid)
            self._lows.append(mid)
            self._closes.append(mid)
            self._vols.append(0.0)
        elif len(args) >= 4:
            o, h, l, c = [float(x) if x is not None else float("nan") for x in args[:4]]
            v = float(args[4]) if len(args) >= 5 and args[4] is not None else 0.0
            # sanity: se close non finito, ripiega su mediana OHLC
            if not math.isfinite(c):
                if all(math.isfinite(x) for x in (o, h, l)):
                    c = (o + h + l) / 3.0
                else:
                    c = o if math.isfinite(o) else h if math.isfinite(h) else l
            self._opens.append(o if math.isfinite(o) else c)
            self._highs.append(h if math.isfinite(h) else c)
            self._lows.append(l if math.isfinite(l) else c)
            self._closes.append(c)
            self._vols.append(v if math.isfinite(v) else 0.0)
        else:
            # input non valido
            return (self._last_alpha, self.box_top, self.box_bot, 0.0)

        # limita crescita
        cap = max(5_000, self.cfg.norm_len * 2 + self.cfg.lookback * 2 + self.cfg.vol_lookback * 2)
        if len(self._closes) > cap:
            k = cap
            self._opens  = self._opens[-k:]
            self._highs  = self._highs[-k:]
            self._lows   = self._lows[-k:]
            self._closes = self._closes[-k:]
            self._vols   = self._vols[-k:]

        # aggiorna mid_hist per compat
        self._mid_hist.append(self._closes[-1])
        if len(self._mid_hist) > cap:
            self._mid_hist = self._mid_hist[-cap:]

        # calcoli canale e segnali
        lb = int(self.cfg.lookback)
        hi, lo, mid_channel = self._channel(self._highs, self._lows, lb)
        self.box_top, self.box_bot, self.box_mid = hi, lo, mid_channel

        p = self._closes[-1]
        breakout = self._breakout_signal(p, hi, lo)
        grid_bias = self._grid_bias_signal(self._closes)

        w1 = float(self.cfg.w_breakout)
        w2 = float(self.cfg.w_grid_bias)
        raw = w1 * breakout + w2 * grid_bias
        alpha = max(self.cfg.alpha_min, min(self.cfg.alpha_max, raw))

        vol_norm = self._realized_vol(self._closes, int(self.cfg.vol_lookback))

        self._last_alpha = float(alpha)
        self._last_ts = time.time()

        return (self._last_alpha, self.box_top, self.box_bot, float(vol_norm))

    def compute_alpha_signal(self) -> float:
        """Compat: calcola alpha usando solo la storia dei close."""
        if not self._closes:
            return 0.0
        lb = int(self.cfg.lookback)
        hi, lo, _ = self._channel(self._highs, self._lows, lb)
        p = self._closes[-1]
        breakout = self._breakout_signal(p, hi, lo)
        grid_bias = self._grid_bias_signal(self._closes)
        raw = self.cfg.w_breakout * breakout + self.cfg.w_grid_bias * grid_bias
        return max(self.cfg.alpha_min, min(self.cfg.alpha_max, raw))

    def state(self) -> Dict[str, Any]:
        return {
            "alpha": self._last_alpha,
            "ts": self._last_ts,
            "hist_len": len(self._closes),
            "box_top": self.box_top,
            "box_bot": self.box_bot,
        }
