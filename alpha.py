# alpha.py — spaces only, LF

from collections import deque
from statistics import pstdev

class AlphaDetector:
    def __init__(
        self,
        norm_len: int = 100,
        box_len: int = 14,
        strong_close: bool = True,
        min_box_range_pct: float = 0.15,
        max_box_range_pct: float = 2.0,
        signal_hysteresis_bars: int = 2,
    ):
        self.norm_len = int(norm_len)
        self.box_len = int(box_len)
        self.strong_close = bool(strong_close)
        self.min_box = float(min_box_range_pct) / 100.0
        self.max_box = float(max_box_range_pct) / 100.0
        self.hyst = int(signal_hysteresis_bars)

        self.cl = deque(maxlen=max(self.norm_len, self.box_len) + 5)
        self.hi = deque(maxlen=max(self.norm_len, self.box_len) + 5)
        self.lo = deque(maxlen=max(self.norm_len, self.box_len) + 5)
        self.vo = deque(maxlen=200)

        self.box_top = None
        self.box_bot = None
        self._last_signal = None
        self._persist = 0

    def _norm_vol(self):
        if len(self.vo) < 5:
            return 0.0
        try:
            return pstdev(self.vo)
        except Exception:
            return 0.0

    def update(self, *args, **kwargs):
        """
        Accetta:
          - update(candle_dict) con chiavi 'o','h','l','c','v'
          - update(o,h,l,c) oppure update(o,h,l,c,v)
          - update(o=o,h=h,l=l,c=c,v=v)
        Ritorna: (signal|None, box_top, box_bot, vol_norm)
        """
        # normalizza input
        if len(args) == 1 and isinstance(args[0], dict):
            candle = args[0]
        elif len(args) >= 4:
            o, h, l, c = args[:4]
            v = args[4] if len(args) >= 5 else kwargs.get("v", 0.0)
            candle = {"o": o, "h": h, "l": l, "c": c, "v": v}
        else:
            try:
                candle = {
                    "o": kwargs["o"], "h": kwargs["h"],
                    "l": kwargs["l"], "c": kwargs["c"],
                    "v": kwargs.get("v", 0.0)
                }
            except KeyError:
                raise TypeError("AlphaDetector.update(): expected candle dict or (o,h,l,c[,v]).")

        o = float(candle.get("o"))
        h = float(candle.get("h"))
        l = float(candle.get("l"))
        c = float(candle.get("c"))
        v = float(candle.get("v", 0.0))

        self.cl.append(c)
        self.hi.append(h)
        self.lo.append(l)
        self.vo.append(v)

        if len(self.cl) < self.box_len:
            return None, self.box_top, self.box_bot, 0.0

        window_hi = list(self.hi)[-self.box_len:]
        window_lo = list(self.lo)[-self.box_len:]
        box_top = max(window_hi)
        box_bot = min(window_lo)

        mid = (box_top + box_bot) / 2.0
        box_range = max(1e-9, box_top - box_bot)
        box_range_pct = box_range / max(1e-9, mid)

        if box_range_pct < self.min_box or box_range_pct > self.max_box:
            self.box_top, self.box_bot = box_top, box_bot
            self._last_signal = None
            self._persist = 0
            return None, self.box_top, self.box_bot, self._norm_vol()

        self.box_top, self.box_bot = box_top, box_bot

        body_mid = (o + c) / 2.0
        long_break = c > self.box_top and (not self.strong_close or body_mid > self.box_top)
        short_break = c < self.box_bot and (not self.strong_close or body_mid < self.box_bot)

        sig = "long" if long_break else ("short" if short_break else None)

        if sig == self._last_signal and sig is not None:
            self._persist += 1
        else:
            self._persist = 1
        self._last_signal = sig

        if sig and self._persist >= max(1, self.hyst):
            return sig, self.box_top, self.box_bot, self._norm_vol()

        return None, self.box_top, self.box_bot, self._norm_vol()
