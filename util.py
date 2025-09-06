import yaml, time, json

def load_cfg(path="config.yaml"):
    with open(path,"r") as f:
        return yaml.safe_load(f)

def now_iso(ts=None):
    ts = ts or time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

def save_json(path, obj):
    with open(path,"w") as f:
        json.dump(obj, f, indent=2)
