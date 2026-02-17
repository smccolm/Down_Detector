import json
import os
from typing import Any, Dict, List, Optional

from utils import iso, now_local

LOG_MAX_RECORDS = 2000


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_text(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def safe_write_error(error_log_path: str, msg: str) -> None:
    try:
        write_text(error_log_path, f"[{iso(now_local())}] {msg}\n")
    except Exception:
        pass


def read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _new_log_file_name(log_dir: str) -> str:
    return os.path.join(log_dir, f"uptime_log_{now_local().strftime('%Y%m%d_%H%M%S')}.jsonl")


def read_log_meta(meta_path: str) -> Dict[str, Any]:
    if not os.path.exists(meta_path):
        return {"current_log_file": "", "current_record_count": 0, "created_at": iso(now_local())}
    try:
        return read_json(meta_path, {"current_log_file": "", "current_record_count": 0})
    except Exception:
        return {"current_log_file": "", "current_record_count": 0, "created_at": iso(now_local())}


def write_log_meta(meta_path: str, meta: Dict[str, Any]) -> None:
    write_json(meta_path, meta)


def append_log_record(log_dir: str, meta_path: str, error_log_path: str, record: Dict[str, Any]) -> None:
    ensure_dir(log_dir)

    meta = read_log_meta(meta_path)
    current_file = str(meta.get("current_log_file") or "").strip()
    count = int(meta.get("current_record_count") or 0)

    if (not current_file) or (count >= LOG_MAX_RECORDS) or (not os.path.exists(current_file)):
        current_file = _new_log_file_name(log_dir)
        count = 0

    try:
        with open(current_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        count += 1
        meta["current_log_file"] = current_file
        meta["current_record_count"] = count
        meta["last_write_at"] = iso(now_local())
        write_log_meta(meta_path, meta)
    except Exception as e:
        safe_write_error(error_log_path, "Failed to append log record: " + repr(e))


def list_recent_log_files(log_dir: str, max_files: int = 2) -> List[str]:
    try:
        files = [
            os.path.join(log_dir, fn)
            for fn in os.listdir(log_dir)
            if fn.startswith("uptime_log_") and fn.endswith(".jsonl")
        ]
        files.sort(reverse=True)
        return files[:max_files]
    except Exception:
        return []


def scan_history_from_logs(
    log_dir: str,
    error_log_path: str,
    profile_ids: List[str],
    max_files: int = 2
) -> Dict[str, Dict[int, str]]:
    """
    Returns:
      { profile_id: { interval_index: "up"|"down" } }

    Reads the newest logs first and keeps the newest record per interval index.
    """
    out: Dict[str, Dict[int, str]] = {pid: {} for pid in profile_ids}
    if not profile_ids:
        return out

    wanted = set(profile_ids)
    files = list_recent_log_files(log_dir, max_files=max_files)

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue

                pid = str(rec.get("profile_id", ""))
                if pid not in wanted:
                    continue

                idx = rec.get("interval_index", None)
                status = str(rec.get("status", "")).lower()
                if idx is None or status not in ("up", "down"):
                    continue

                try:
                    idx_i = int(idx)
                except Exception:
                    continue

                if idx_i not in out[pid]:
                    out[pid][idx_i] = status
        except Exception as e:
            safe_write_error(error_log_path, "Failed reading log file for history: " + fp + " " + repr(e))

    return out
