import os, time, signal, json
from util import load_cfg
from datafeeds import aggregate_quote_sync, get_candles_sync
from filters import assess, DFStatus
from grid import compute_grid
from pid import PID, leverage_from_pid
from pionex_api import Pionex
from report import write_state_report, write_orders, mirror_config_to_json, bump_trades_today
from alpha import AlphaDetector
from ws_fills import FillsWS

from collections import deque

def calc_atr(candles, n=14):
    trs = []
    prev_c = None
    for c in candles:
        h, l = float(c["h"]), float(c["l"])
        if prev_c is None:
            tr = h - l
        else:
            prev_close = float(prev_c["c"])
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_c = c
    if not trs:
        return 0.0
    n = max(1, int(n))
    vals = trs[-n:] if len(trs) >= n else trs
    return sum(vals)/len(vals)

class StreakBook:
    def __init__(self, path="orders.json"):
        self.path = path
        self.data = {"open":[], "closed":[], "stats":{}}
        try:
            with open(self.path,"r") as f:
                import json
                self.data = json.load(f)
        except Exception:
            pass

    def save(self):
        import json
        with open(self.path,"w") as f:
            json.dump(self.data, f, indent=2)

    def record_entry(self, side, qty, entry_price, sl=None, tp=None, ts=None):
        import time
        o = {"id": int(time.time()*1000), "side": side, "qty": qty,
             "entry": entry_price, "sl": sl, "tp": tp, "ts": ts or int(time.time()*1000)}
        self.data["open"].append(o); self.save(); return o["id"]

    def mark_exit_if_crossed(self, mid):
        import time
        updated = False
        new_open = []
        closed = self.data.get("closed", [])
        for o in self.data.get("open", []):
            hit = None
            if o.get("tp") and ((o["side"]=="BUY" and mid>=o["tp"]) or (o["side"]=="SELL" and mid<=o["tp"])):
                hit = "win"; exit_price = o["tp"]
            elif o.get("sl") and ((o["side"]=="BUY" and mid<=o["sl"]) or (o["side"]=="SELL" and mid>=o["sl"])):
                hit = "loss"; exit_price = o["sl"]
            if hit:
                pl = (exit_price - o["entry"]) * (o["qty"] if o["side"]=="BUY" else -o["qty"])
                closed.append({**o, "exit": exit_price, "result": hit, "pl": pl, "exit_ts": int(time.time()*1000)})
                updated = True
            else:
                new_open.append(o)
        if updated:
            self.data["open"] = new_open
            self.data["closed"] = closed
            last_res = closed[-1]["result"] if closed else None
            streak = 0
            if last_res:
                for c in reversed(closed):
                    if c.get("result") == last_res:
                        streak += 1
                    else:
                        break
            s = self.data.setdefault("stats", {})
            s["last_result"] = last_res
            s["streak"] = streak if last_res else 0
            self.save()
        return updated

    def streak_mult(self, cfg):
        s = self.data.get("stats", {})
        last = s.get("last_result")
        st = int(s.get("streak", 0) or 0)
        r = cfg.get("risk_ladder", {})
        if not r.get("enabled", True):
            return 1.0
        if last == "win" and st > 0:
            return min(1.0 + r.get("win_step_mult",0.25)*st, r.get("max_mult",2.0))
        if last == "loss" and st >= r.get("penalty_after_losses",2):
            return r.get("loss_penalty_mult",0.7)
        return 1.0


def choose_timeframe(status, vol_pct, trades_today, target_trades, last_tf, tf_cfg, stick_counter):
    vol_hi = float(tf_cfg.get("vol_hi_pct",1.5))
    vol_lo = float(tf_cfg.get("vol_lo_pct",0.6))
    warmup = int(tf_cfg.get("warmup_trades",3))
    stickiness = int(tf_cfg.get("stickiness_loops",5))

    desired = last_tf or "1m"
    if status in (DFStatus.PANIC, DFStatus.SUSPEND): desired = "5m"
    elif status == DFStatus.WARN: desired = "5m"
    else:
        if (vol_pct or 0.0) > vol_hi: desired = "5m"
        elif trades_today < max(1, target_trades - warmup): desired = "1m"
        elif (vol_pct or 0.0) < vol_lo: desired = "1m"
        else: desired = last_tf or "1m"
    if desired != last_tf and stick_counter < stickiness:
        return last_tf or desired, stick_counter+1
    return desired, 0

def run():
    cfg = load_cfg()
    pnx = Pionex(key=os.environ.get("PIONEX_API_KEY",""), secret=os.environ.get("PIONEX_API_SECRET",""), cfg=cfg)
    pid = PID(cfg["pid"]["kp"], cfg["pid"]["ki"], cfg["pid"]["kd"], cfg["pid"]["out_min"], cfg["pid"]["out_max"])
    start = time.time()
    backoff = 0
    stopping = False

    def _sigterm(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, _sigterm)

    last_mid = None
    last_status = DFStatus.OK

    a_cfg = cfg.get("alpha", {})
    alpha_on = bool(a_cfg.get("enabled", True))
    alpha = AlphaDetector(
        norm_len=a_cfg.get("norm_len", 100),
        box_len=a_cfg.get("box_len", 14),
        strong_close=a_cfg.get("strong_close", True),
        min_box_range_pct=a_cfg.get("min_box_range_pct", 0.15),
        max_box_range_pct=a_cfg.get("max_box_range_pct", 2.0),
        signal_hysteresis_bars=a_cfg.get("signal_hysteresis_bars", 2),
    )
    last_long_ts = 0.0
    last_short_ts = 0.0
    last_tf = None
    tf_stick = 0

    ws_cfg = cfg.get("websocket",{})
    ws = None
    if ws_cfg.get("fills_enabled", False) and ws_cfg.get("url"):
        try:
            ws = FillsWS(ws_cfg["url"], headers=ws_cfg.get("headers",{}))
            ws.start()
        except Exception:
            ws = None

    while not stopping and time.time() - start < cfg["daemon"]["max_runtime_seconds"]:
      loop_s = cfg["daemon"]["loop_seconds"]
      mid, vol_pct, div_bps, ts, alive = aggregate_quote_sync()
      status, reason = assess(mid, vol_pct, div_bps, alive, cfg)

      if mid is None or status in (DFStatus.SUSPEND, DFStatus.PANIC):
          write_state_report(ts, status.value, reason, mid, vol_pct, div_bps)
          backoff = min(cfg["daemon"]["exponential_backoff_max_s"], max(1, (backoff*2) or loop_s))
          time.sleep(backoff); continue

      lower, upper, levels = compute_grid(mid, std_pct=vol_pct, cfg=cfg, status=status.name)

      error = cfg["pid"]["target_vol_pct"] - (vol_pct or 0.0)
      u = pid.step(error, dt=max(loop_s, 1.0))
      lev = leverage_from_pid(u, cfg["leverage"]["min"], cfg["leverage"]["max"])

      risk_cfg = cfg.get("risk", {})
      eq = pnx.get_portfolio_equity_usdt() or float(risk_cfg.get("portfolio_usdt_fallback", 10_000))
      cap_usdt = max(0.0, min(eq * (risk_cfg.get("max_portfolio_pct", 3.0)/100.0), eq))
      base_notional = min(cap_usdt, cfg["grid"]["notional_per_side_usdt"])

      trades_today = 0
      if os.path.exists("orders.json"):
          try:
              with open("orders.json","r") as f:
                  trades_today = int((json.load(f).get("stats",{}) or {}).get("trades_day", 0))
          except Exception:
              trades_today = 0
      t_cfg = cfg.get("timeframe_auto",{})
      target_trades = int(cfg.get("alpha",{}).get("daily_trade_target", 6))
      cooloff = int(cfg.get("alpha",{}).get("cooloff_seconds", 900))

      tf, tf_stick = choose_timeframe(status, vol_pct, trades_today, target_trades, last_tf, t_cfg, tf_stick)
      last_tf = tf

      alpha_signal = None; box_top = box_bot = None
      if alpha_on:
          try:
              candles = get_candles_sync(tf, limit=200)
              if candles:
                  t,o,h,l,c,v = candles[-1]
                  alpha_signal, box_top, box_bot, vol_norm = alpha.update(o,h,l,c,v)
              else:
                  o=h=l=c=mid
                  alpha_signal, box_top, box_bot, vol_norm = alpha.update(o,h,l,c,None)
          except Exception:
              o=h=l=c=mid
              alpha_signal, box_top, box_bot, vol_norm = alpha.update(o,h,l,c,None)

      can_trade_more = trades_today < target_trades
      elapsed_long  = ts - last_long_ts
      elapsed_short = ts - last_short_ts
      can_long  = elapsed_long  >= cooloff
      can_short = elapsed_short >= cooloff

      place_grid = (last_mid is None or abs(mid - last_mid)/mid > 0.003 or status != last_status)

      trading_mode = cfg.get("trading",{}).get("mode","grid")
      sltp_on = bool(cfg.get("trading",{}).get("sltp_enabled", True))
      sl_buf = float(cfg.get("trading",{}).get("sl_buffer_pct", 0.35))/100.0
      dyn = cfg.get("dynamic_sl",{})
      use_atr = dyn.get("use_atr", True)
      atr_len = int(dyn.get("atr_len",14))
      atr_mult = float(dyn.get("atr_mult",1.2))
      use_box = dyn.get("use_box", True)
      box_share = float(dyn.get("box_sl_share",0.5))
      rr = float(cfg.get("trading",{}).get("tp_rr", 1.5))
      entry_kind = cfg.get("trading",{}).get("entry_kind","MARKET")

      lad = StreakBook()
      lad.mark_exit_if_crossed(mid)
      size_mult = lad.streak_mult(cfg)
      adj_notional = base_notional * size_mult
      qty_per_level = adj_notional / max(1,levels) / mid * max(lev, 0.01)
      qty_breakout = (adj_notional / mid) * max(lev, 0.01)

      if alpha_on and alpha_signal in ("long","short") and can_trade_more:
          if trading_mode == "breakout" and sltp_on and ( (alpha_signal=="long" and can_long) or (alpha_signal=="short" and can_short) ):
              ref = box_top if alpha_signal=="long" else box_bot
              ref = ref or mid
              if alpha_signal=="long":
                  sl = ref * (1.0 - sl_buf)
                  tp = ref + (ref - sl) * rr
                  side = "BUY"
              else:
                  sl = ref * (1.0 + sl_buf)
                  tp = ref - (sl - ref) * rr
                  side = "SELL"
              pnx.place_breakout_bracket(
                  symbol=cfg["pionex"]["symbol"], side=side, price_ref=mid,
                  qty=qty_breakout, sl_price=sl, tp_price=tp,
                  entry_kind=entry_kind, reduce_only=cfg.get("trading",{}).get("reduce_only", True)
              )
              bump_trades_today(1)
              try:
                  lad.record_entry(side=side, qty=qty_breakout, entry_price=ref, sl=sl, tp=tp, ts=ts)
              except Exception:
                  pass
              if alpha_signal=="long": last_long_ts = ts
              else: last_short_ts = ts
              place_grid = False
          else:
              micro_levels = max(3, min(6, levels//2))
              band_center = (box_top if alpha_signal=="long" else box_bot) if (box_top and box_bot) else mid
              lower, upper, _ = compute_grid(mid, std_pct=vol_pct, cfg=cfg, status=status.name)
              micro_span = max(0.002*mid, 0.5 * (upper - lower))
              mg_lower = band_center - micro_span
              mg_upper = band_center + micro_span
              if alpha_signal=="long" and can_long:
                  pnx.sync_replace_grid(cfg["pionex"]["symbol"], mg_lower, mg_upper, micro_levels, qty_per_level, mid)
                  last_long_ts = ts
                  bump_trades_today(1)
                  place_grid = False
              elif alpha_signal=="short" and can_short:
                  pnx.sync_replace_grid(cfg["pionex"]["symbol"], mg_lower, mg_upper, micro_levels, qty_per_level, mid)
                  last_short_ts = ts
                  bump_trades_today(1)
                  place_grid = False

      if place_grid and trading_mode == "grid":
          pnx.sync_replace_grid(symbol=cfg["pionex"]["symbol"],
                                lower=lower, upper=upper, levels=levels,
                                qty=qty_per_level, price_ref=mid)
          last_mid = mid
          last_status = status

      indicators = {"alpha_signal": alpha_signal, "box": [box_bot, box_top], "tf": tf, "mode": trading_mode}
      write_state_report(ts, status.value, reason, mid, vol_pct, div_bps,
                         extra={"lev": lev, "u": u, "grid":[lower, upper, levels], "indicators": indicators})

      ws_fills = None
      try:
          with open("ws_fills.json","r") as f:
              ws_fills = json.load(f).get("fills",[])
      except Exception:
          ws_fills = None

      opens = pnx.list_open_orders(symbol=cfg["pionex"]["symbol"]) or []
      fills = ws_fills if (ws_fills is not None) else (pnx.list_recent_fills(symbol=cfg["pionex"]["symbol"], limit=50) or [])

      write_orders(opens, fills, stats={
          "pnl_day": None,
          "trades_day": trades_today,
          "win_7d": None,
          "sharpe_30d": None
      })
      mirror_config_to_json(cfg)

      backoff = 0
      time.sleep(loop_s)

    time.sleep(cfg["daemon"]["sigterm_grace_seconds"])

if __name__ == "__main__":
    run()
