import os, time, signal, json
from util import load_cfg
from datafeeds import aggregate_quote_sync, get_candles_sync
from filters import assess, DFStatus
from grid import compute_grid
from pid import PID, leverage_from_pid
from pionex_api import Pionex
from report import write_state_report, write_orders, mirror_config_to_json, bump_trades_today
from alpha import AlphaDetector

def choose_timeframe(status, vol_pct, trades_today, target_trades, last_tf):
    # Regime logic: prefer 1m in piatto (vol bassa) o se stiamo sotto target trade; 5m in warn/panic o vol alta
    if status in (DFStatus.PANIC, DFStatus.SUSPEND):
        return "5m"
    if status == DFStatus.WARN:
        return "5m"
    # thresholds (tunable)
    if (vol_pct or 0.0) > 1.5:
        return "5m"
    if trades_today < max(1, target_trades//2):
        return "1m"
    # hysteresis: stick to last unless reason to switch
    return last_tf or "1m"

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
    )
    last_long_ts = 0.0
    last_short_ts = 0.0
    last_tf = None

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
      qty_per_level = base_notional / levels / mid * max(lev, 0.01)

      import os
      trades_today = 0
      if os.path.exists("orders.json"):
          try:
              with open("orders.json","r") as f:
                  trades_today = int((json.load(f).get("stats",{}) or {}).get("trades_day", 0))
          except Exception:
              trades_today = 0
      target_trades = int(a_cfg.get("daily_trade_target", 6))
      cooloff = int(a_cfg.get("cooloff_seconds", 900))

      # ----- Auto timeframe selection -----
      tf = choose_timeframe(status, vol_pct, trades_today, target_trades, last_tf)
      last_tf = tf

      # ----- Alpha using last closed candle of chosen tf -----
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

      if alpha_on and alpha_signal in ("long","short") and can_trade_more:
          micro_levels = max(3, min(6, levels//2))
          band_center = (box_top if alpha_signal=="long" else box_bot) if (box_top and box_bot) else mid
          micro_span = max(0.002*mid, 0.5 * (upper - lower))
          mg_lower = band_center - micro_span
          mg_upper = band_center + micro_span

          if alpha_signal=="long" and can_long:
              pnx.sync_replace_grid(symbol=cfg["pionex"]["symbol"],
                                    lower=mg_lower, upper=mg_upper, levels=micro_levels,
                                    qty=qty_per_level, price_ref=mid)
              last_long_ts = ts
              bump_trades_today(1)
              place_grid = False
          elif alpha_signal=="short" and can_short:
              pnx.sync_replace_grid(symbol=cfg["pionex"]["symbol"],
                                    lower=mg_lower, upper=mg_upper, levels=micro_levels,
                                    qty=qty_per_level, price_ref=mid)
              last_short_ts = ts
              bump_trades_today(1)
              place_grid = False

      if place_grid:
          pnx.sync_replace_grid(symbol=cfg["pionex"]["symbol"],
                                lower=lower, upper=upper, levels=levels,
                                qty=qty_per_level, price_ref=mid)
          last_mid = mid
          last_status = status

      indicators = {"alpha_signal": alpha_signal, "box": [box_bot, box_top], "tf": tf}
      write_state_report(ts, status.value, reason, mid, vol_pct, div_bps,
                         extra={"lev": lev, "u": u, "grid":[lower, upper, levels], "indicators": indicators})

      opens = pnx.list_open_orders(symbol=cfg["pionex"]["symbol"])
      fills = pnx.list_recent_fills(symbol=cfg["pionex"]["symbol"], limit=50)
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
