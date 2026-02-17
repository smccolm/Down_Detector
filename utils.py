
import re
from datetime import datetime

def now_local():
    return datetime.now()

def iso(dt):
    return dt.replace(microsecond=0).isoformat(sep=" ")

def parse_datetime_user(text):
    t = (text or "").strip().replace("T", " ")
    if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", t):
        t += ":00"
    return datetime.fromisoformat(t)

def duration_to_seconds(dd, hh, mm, ss):
    return int(dd)*86400 + int(hh)*3600 + int(mm)*60 + int(ss)

def seconds_to_pretty(total):
    dd, rem = divmod(total, 86400)
    hh, rem = divmod(rem, 3600)
    mm, ss = divmod(rem, 60)
    parts = []
    if dd: parts.append(f"{dd}d")
    if hh: parts.append(f"{hh}h")
    if mm: parts.append(f"{mm}m")
    if ss or not parts: parts.append(f"{ss}s")
    return " ".join(parts)

def normalize_rule_list(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip()]

def rule_matches(rule, body):
    if rule.lower().startswith("re:"):
        return re.search(rule[3:], body or "", re.I | re.M) is not None
    return rule.lower() in (body or "").lower()
