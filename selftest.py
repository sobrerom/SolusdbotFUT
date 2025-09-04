import os
import sys
from pathlib import Path
import yaml

def main():
    ok = True
    # Check env
    for var in ["PIONEX_API_KEY", "PIONEX_API_SECRET", "DASHBOARD_TOKEN"]:
        if not os.environ.get(var):
            print(f"WARN: {var} not set (expected in CI secrets).")
    # Check config
    cfg = Path.cwd() / "config.yaml"
    if not cfg.exists():
        cfg = Path.cwd() / "config.example.yaml"
        if not cfg.exists():
            print("ERROR: config.yaml or config.example.yaml missing.")
            ok = False
        else:
            print("INFO: using config.example.yaml")
    try:
        yaml.safe_load(cfg.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: failed to parse {cfg}: {e}")
        ok = False
    print("SELFTEST:", "OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
