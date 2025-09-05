import json, time, signal
from pathlib import Path
from typing import Any, Dict

STATE_PATH = Path("state.json")
_STOP = {"flag": False}

def now_ms() -> int:
    return int(time.time()*1000)

def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"prices": [], "pid": {"integral": 0.0, "last_error": 0.0}, "leverage": 0.0, "suspended": False, "last_apply": None}

def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))

def install_sigterm_handler():
    def handler(signum, frame):
        _STOP["flag"] = True
    try:
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)
    except Exception:
        pass

def should_stop() -> bool:
    return _STOP["flag"]
