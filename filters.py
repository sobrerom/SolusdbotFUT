from enum import Enum

class DFStatus(Enum):
    OK = "OK"
    WARN = "WARN"
    PANIC = "PANIC"
    SUSPEND = "SUSPEND"

def assess(mid, vol_pct, div_bps, sources_alive, cfg):
    if sources_alive == 0:
        return DFStatus.SUSPEND, "no datafeeds"
    if sources_alive < cfg["datafeed"]["quorum"]:
        return DFStatus.WARN, "low quorum"
    if div_bps > cfg["datafeed"]["divergence_bps"]:
        return DFStatus.WARN, f"divergence {div_bps:.1f}bps"
    if cfg["safe_mode"]["enabled"]:
        if (vol_pct or 0.0) >= cfg["safe_mode"]["vol_panic_pct"]:
            return DFStatus.PANIC, f"vol {vol_pct:.2f}% >= panic"
        if (vol_pct or 0.0) >= cfg["safe_mode"]["vol_warn_pct"]:
            return DFStatus.WARN, f"vol {vol_pct:.2f}% >= warn"
    return DFStatus.OK, "ok"
