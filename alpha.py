from collections import deque
from statistics import pstdev

class AlphaDetector:
    def __init__(self, norm_len=100, box_len=14, strong_close=True,
                 min_box_range_pct=0.15, max_box_range_pct=2.0, signal_hysteresis_bars=2):
        self.norm_len = norm_len
        self.box_len = box_len
        self.strong_close = strong_close
        self.min_box = min_box_range_pct / 100.0
        self.max_box = max_box_range_pct / 100.0
        self.hyst = int(signal_hysteresis_bars)
        self.cl = deque(maxlen=max(norm_len, box_len)+5)
        self.hi = deque(maxlen=max(norm_len, box_len)+5)
        self.lo = deque(maxlen=max(norm_len, box_len)+5)
        self.vo = deque(maxlen=200)
        self.box_top = None
               self.box_bot = None
        self._last_signal = None
        self._persist = 0

    def _norm_vol(self):
        if len(self.cl) < self.norm_len+2: return 0.0
        lowest = min(list(self.lo)[-self.norm_len:])
        highest = max(list(self.hi)[-self.norm_len:])
        denom = max(1e-12, (highest - lowest))
        norm = [(c - lowest)/denom for c in list(self.cl)[-self.norm_len:]]
        if len(norm) < 14: return 0.0
        return pstdev(norm[-14:]) * 100.0

    def _detect_box(self):
        if len(self.cl) < self.box_len: return None, None
        hh = max(list(self.hi)[-self.box_len:])
        ll = min(list(self.lo)[-self.box_len:])
        mid = (hh + ll)/2.0
        rng = max(1e-12, hh - ll)
        pr = max(1e-12, mid)
        rng_pct = rng / pr
        if rng_pct < self.min_box or rng_pct > self.max_box:
            return None, None
        return hh, ll

    def update(self, o, h, l, c, v=None):
        self.cl.append(c); self.hi.append(h); self.lo.append(l)
        if v is not None: self.vo.append(v)
        hh, ll = self._detect_box()
        if hh is not None and ll is not None:
            self.box_top, self.box_bot = hh, ll
        if self.box_top is None or self.box_bot is None:
            return None, self.box_top, self.box_bot, 0.0
        body_mid = (o + c)/2.0
        long_break = c > self.box_top and ((self.strong_close and body_mid > self.box_top) or (not self.strong_close))
        short_break = c < self.box_bot and ((self.strong_close and body_mid < self.box_bot) or (not self.strong_close))
        vol_norm = self._norm_vol()
        sig = None
        if long_break: sig = "long"
        elif short_break: sig = "short"
        if sig == self._last_signal:
            self._persist += 1
        else:
            self._persist = 1
        self._last_signal = sig
        if sig and self._persist >= max(1,self.hyst):
            return sig, self.box_top, self.box_bot, vol_norm
        return None, self.box_top, self.box_bot, vol_norm
