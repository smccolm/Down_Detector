from utils import seconds_to_pretty


def render_empty_dashboard_html() -> str:
    return """
    <div style="padding:14px;border-radius:12px;border:1px solid #e5e7eb;background:#f9fafb;">
      <div style="color:#6b7280;">No profiles yet. Click Add to create one.</div>
    </div>
    """


def _bar_color(status: str) -> str:
    s = (status or "").lower().strip()
    if s == "up":
        return "#22c55e"
    if s == "down":
        return "#ef4444"
    return "#9ca3af"


def render_card_html(profile, last30_statuses) -> str:
    """
    Neutral dark card.
    Display name (white) top-left overlay.
    Interval (white) top-right overlay.
    Bars are on their own line.
    'Last: X' pill is BELOW the bars (no obstruction).
    """
    last = (profile.last_status or "untested").lower().strip()
    display_name = (profile.display_name or "").strip()
    interval_txt = seconds_to_pretty(int(profile.interval_seconds or 0))

    bars_html = "".join(
        "<div style=\"width:6px;height:18px;border-radius:2px;opacity:0.95;background:%s;\"></div>"
        % _bar_color(x)
        for x in (last30_statuses or [])
    )

    return f"""
    <div style="
        position:relative;
        width:100%;
        border-radius:12px;
        padding:12px;
        box-sizing:border-box;
        background:#111827;
        border:1px solid #374151;
        overflow:hidden;
        min-height:90px;
    ">

      <!-- Overlays -->
      <div style="
          position:absolute;
          top:10px; left:12px;
          color:#ffffff;
          font-weight:700;
          font-size:16px;
          line-height:1.1;
          text-shadow:0 1px 2px rgba(0,0,0,0.45);
          max-width:72%;
          overflow:hidden;
          text-overflow:ellipsis;
          white-space:nowrap;
          z-index:2;
      ">{display_name}</div>

      <div style="
          position:absolute;
          top:10px; right:12px;
          color:#ffffff;
          font-weight:700;
          font-size:14px;
          line-height:1.1;
          text-shadow:0 1px 2px rgba(0,0,0,0.45);
          max-width:26%;
          overflow:hidden;
          text-overflow:ellipsis;
          white-space:nowrap;
          text-align:right;
          z-index:2;
      ">{interval_txt}</div>

      <!-- Flow content: bars first, then Last pill below -->
      <div style="padding-top:34px;">
        <div style="
            display:flex;
            gap:3px;
            align-items:flex-end;
            height:18px;
        ">
          {bars_html}
        </div>

        <div style="
            margin-top:8px;
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:rgba(0,0,0,0.40);
            border:1px solid rgba(255,255,255,0.18);
            color:#ffffff;
            font-weight:700;
            font-size:12px;
        ">Last: {last.upper()}</div>
      </div>
    </div>
    """
