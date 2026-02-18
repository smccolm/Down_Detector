from typing import List, Optional

from models import Profile
from utils import html_escape, seconds_to_pretty


def _card_css() -> str:
    return """
    <style>
      .dd-wrap { padding: 6px 2px; }
      .dd-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 12px; }

      .dd-card {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 16px;
        padding: 12px 12px 10px 12px;
        background: rgba(17, 24, 39, 0.92);
        box-shadow: 0 1px 8px rgba(0,0,0,0.18);
      }

      .dd-top {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
      }

      .dd-name {
        font-size: 16px;
        font-weight: 650;
        color: rgba(255,255,255,0.92);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .dd-sub {
        font-size: 12px;
        color: rgba(255,255,255,0.65);
        margin-top: 2px;
      }

      .dd-bars {
        display:flex;
        gap:3px;
        margin-top: 10px;
        align-items: flex-end;
      }

      .dd-bar {
        width: 7px;
        height: 22px;
        border-radius: 3px;
        opacity: 0.95;
      }

      .dd-up { background: #22c55e; }
      .dd-down { background: #ef4444; }
      .dd-untested { background: #6b7280; }

      .dd-meta {
        display:flex;
        gap:10px;
        align-items:center;
        margin-top: 8px;
        font-size: 12px;
        color: rgba(255,255,255,0.70);
      }

      .dd-pill {
        padding: 2px 10px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.06);
      }

      .dd-status {
        font-weight: 650;
      }

      .dd-status-up { color: #34d399; }
      .dd-status-down { color: #f87171; }
      .dd-status-untested { color: #cbd5e1; }

      .dd-empty {
        padding: 10px 6px;
        color: rgba(0,0,0,0.6);
      }
    </style>
    """


def render_card_html(p: Profile, bars: List[str]) -> str:
    if not bars or len(bars) != 30:
        bars = (bars or []) + ["untested"] * 30
        bars = bars[:30]

    cur = bars[-1] if bars else "untested"
    status_label = "Untested" if cur == "untested" else ("Up" if cur == "up" else "Down")
    status_class = "dd-status-untested" if cur == "untested" else ("dd-status-up" if cur == "up" else "dd-status-down")

    bar_html = "".join([
        f'<div class="dd-bar {"dd-up" if s=="up" else ("dd-down" if s=="down" else "dd-untested")}"></div>'
        for s in bars
    ])

    return f"""
      {_card_css()}
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
    """


def render_empty_dashboard_html() -> str:
    return f"""
      {_card_css()}
      <div class="dd-empty">No profiles yet. Click Add to create one.</div>
    """
