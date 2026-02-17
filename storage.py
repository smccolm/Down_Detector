
import os
import json
from datetime import datetime

LOG_MAX_RECORDS = 2000

def ensure_dirs(base):
    os.makedirs(base, exist_ok=True)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def append_log(base_dir, record):
    meta_path = os.path.join(base_dir, "log_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = {"current_log_file": "", "count": 0}

    log_file = meta.get("current_log_file")

    if not log_file or meta["count"] >= LOG_MAX_RECORDS:
        log_file = os.path.join(base_dir, f"uptime_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        meta["count"] = 0

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    meta["current_log_file"] = log_file
    meta["count"] += 1

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
