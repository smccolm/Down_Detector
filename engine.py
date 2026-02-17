
import requests
from datetime import datetime, timedelta
from utils import iso, rule_matches
from storage import append_log

REQUEST_TIMEOUT = 10

def check_profile(profile):
    try:
        r = requests.get(profile.url, timeout=REQUEST_TIMEOUT)
        body = r.text or ""
        for fr in profile.failure_rules:
            if rule_matches(fr, body):
                return "down", r.status_code
        if profile.success_rules:
            if not any(rule_matches(sr, body) for sr in profile.success_rules):
                return "down", r.status_code
        return ("up" if 200 <= r.status_code < 400 else "down"), r.status_code
    except Exception:
        return "down", None

def run_tick(profile, base_dir):
    now = datetime.now()
    start = datetime.fromisoformat(profile.start_datetime)
    elapsed = (now - start).total_seconds()
    idx = int(elapsed // profile.interval_seconds)
    scheduled = start + timedelta(seconds=idx * profile.interval_seconds)
    status, http_status = check_profile(profile)

    record = {
        "ts": iso(now),
        "profile_id": profile.profile_id,
        "display_name": profile.display_name,
        "interval_index": idx,
        "scheduled_time": iso(scheduled),
        "status": status,
        "http_status": http_status
    }
    append_log(base_dir, record)
    profile.last_interval_index_ran = idx
    profile.last_status = status
    return status
