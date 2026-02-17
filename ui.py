
from utils import seconds_to_pretty

def build_dashboard(cfg):
    profiles = cfg.profiles
    cards = []
    for p in profiles:
        status = p.last_status or "untested"
        cards.append(f"""
        <div style="border:1px solid #444;padding:10px;border-radius:8px;margin:5px;">
            <b>{p.display_name}</b><br>
            Interval: {seconds_to_pretty(p.interval_seconds)}<br>
            Status: {status}
        </div>
        """)
    return "<div>" + "".join(cards) + "</div>"
