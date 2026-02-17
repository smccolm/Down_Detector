from typing import List

from models import Profile
from utils import html_escape, seconds_to_pretty


def render_dashboard_html(profiles: List[Profile], bars_for_profile) -> str:
    """
    bars_for_profile(profile) -> List[str] of length 30 with values:
      "untested" | "up" | "down"
    """
    css = """
    <style>
      .dd-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }
      .dd-card { border: 1px solid rgba(0,0,0,0.14); border-radius: 14px; padding: 12px; background: rgba(255,255,255,0.70); }
      .dd-top { display:flex; align-items:center; justify-content:space-between; gap:10px; }
      .dd-name { font-size: 16px; font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .dd-sub { font-size: 12px; opacity: 0.75; margin-top: 2px; }
      .dd-bars { display:flex; gap:3px; margin-top: 10px; }
      .dd-bar { width: 7px; height: 22px; border-radius: 3px; }
      .dd-up { background: #22c55e; }
      .dd-down { background: #ef4444; }
      .dd-untested { background: #9ca3af; }
      .dd-meta { display:flex; gap:10px; align-items:center; margin-top: 8px; font-size: 12px; opacity: 0.85; }
      .dd-pill { padding: 2px 8px; border-radius: 999px; border: 1px solid rgba(0,0,0,0.12); background: rgba(255,255,255,0.65); }
      .dd-status { font-weight: 650; }
      .dd-status-up { color: #15803d; }
      .dd-status-down { color: #b91c1c; }
      .dd-status-untested { color: #4b5563; }
    </style>
    """

    cards = []
    for p in profiles:
        bars = bars_for_profile(p) or []
        if len(bars) != 30:
            bars = (bars + ["untested"] * 30)[:30]

        cur = bars[-1] if bars else "untested"
        status_label = "Untested" if cur == "untested" else ("Up" if cur == "up" else "Down")
        status_class = "dd-status-untested" if cur == "untested" else ("dd-status-up" if cur == "up" else "dd-status-down")

        bar_html = "".join([
            f'<div class="dd-bar {"dd-up" if s=="up" else ("dd-down" if s=="down" else "dd-untested")}"></div>'
            for s in bars
        ])

        cards.append(f"""
          <div class="dd-card">
            <div class="dd-top">
              <div class="dd-name" title="{html_escape(p.display_name)}">{html_escape(p.display_name)}</div>
            </div>
            <div class="dd-sub">Interval: {seconds_to_pretty(int(p.interval_seconds))} | Start: {html_escape(p.start_datetime)}</div>
            <div class="dd-bars">{bar_html}</div>
            <div class="dd-meta">
              <div class="dd-pill">Last: <span class="dd-status {status_class}">{status_label}</span></div>
            </div>
          </div>
        """)

    if not cards:
        body = '<div style="opacity:0.8; padding:8px;">No profiles yet. Use the + button to add one.</div>'
    else:
        body = f'<div class="dd-grid">{"".join(cards)}</div>'

    return css + body
