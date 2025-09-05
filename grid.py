def compute_grid(mid, std_pct, cfg, status):
    k = cfg["grid"]["k"]
    if status == "WARN":
        k *= cfg["safe_mode"]["widen_factor_warn"]
    elif status in ("PANIC", "SUSPEND" ):
        k *= cfg["safe_mode"]["widen_factor_panic"]
    band_pct = max(0.01, k * (std_pct or 0.0))  # min 1%
    upper = mid * (1 + band_pct/100)
    lower = mid * (1 - band_pct/100)
    levels = cfg["grid"]["levels"]
    return lower, upper, levels
