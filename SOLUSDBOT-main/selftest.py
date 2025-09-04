import os, sys
from pathlib import Path
import yaml
def main():
    ok = True
    cfg = Path.cwd() / "config.yaml"
    if not cfg.exists():
        cfg = Path.cwd() / "config.example.yaml"
        print("INFO: using example config" if cfg.exists() else "WARN: no config found")
    if cfg.exists():
        try:
            yaml.safe_load(cfg.read_text(encoding="utf-8"))
        except Exception as e:
            print("ERROR parsing config:", e); ok=False
    print("SELFTEST:", "OK" if ok else "FAILED"); sys.exit(0 if ok else 1)
if __name__ == "__main__": main()
