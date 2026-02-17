import re
from datetime import datetime


def now_local() -> datetime:
    return datetime.now()


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat(sep=" ")


def parse_datetime_user(text: str) -> datetime:
    """
    Accepts:
      YYYY-MM-DD HH:MM
      YYYY-MM-DD HH:MM:SS
      YYYY-MM-DDTHH:MM
      YYYY-MM-DDTHH:MM:SS
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("Start datetime is required.")
    t = t.replace("T", " ")
    if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", t):
        t = t + ":00"
    try:
        return datetime.fromisoformat(t)
    except Exception as e:
        raise ValueError("Invalid datetime. Use YYYY-MM-DD HH:MM or YYYY-MM-DD HH:MM:SS") from e


def duration_to_seconds(dd: int, hh: int, mm: int, ss: int) -> int:
    dd = int(dd or 0)
    hh = int(hh or 0)
    mm = int(mm or 0)
    ss = int(ss or 0)
    return dd * 86400 + hh * 3600 + mm * 60 + ss


def seconds_to_pretty(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "0s"
    dd, rem = divmod(total_seconds, 86400)
    hh, rem = divmod(rem, 3600)
    mm, ss = divmod(rem, 60)
    parts = []
    if dd:
        parts.append(f"{dd}d")
    if hh:
        parts.append(f"{hh}h")
    if mm:
        parts.append(f"{mm}m")
    if ss or not parts:
        parts.append(f"{ss}s")
    return " ".join(parts)


def normalize_rule_list(text: str):
    lines = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if s:
            lines.append(s)
    return lines


def rule_matches(rule: str, body: str) -> bool:
    """
    Rule format:
      - Plain substring (case-insensitive)
      - Regex: prefix with 're:' (case-insensitive, multiline)
    """
    b = body or ""
    r = (rule or "").strip()
    if not r:
        return False

    if r.lower().startswith("re:"):
        pat = r[3:].strip()
        try:
            return re.search(pat, b, flags=re.IGNORECASE | re.MULTILINE) is not None
        except re.error:
            return False

    return r.lower() in b.lower()


def html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
