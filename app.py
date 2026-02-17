import os
import time
from dataclasses import asdict

import gradio as gr

from engine import MonitorEngine
from models import AppConfig, Profile, SmtpSettings
from storage import ensure_dir, read_json, safe_write_error, write_json
from ui import render_dashboard_html
from utils import duration_to_seconds, iso, normalize_rule_list, now_local, parse_datetime_user


APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(APP_DIR, "Logs")
PROFILES_PATH = os.path.join(LOG_DIR, "profiles.json")
LOG_META_PATH = os.path.join(LOG_DIR, "log_meta.json")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "error.log")

DEFAULT_REFRESH_SECONDS = 1.0

ensure_dir(LOG_DIR)


def load_config() -> AppConfig:
    raw = read_json(PROFILES_PATH, {"profiles": [], "smtp": {}})
    cfg = AppConfig()

    smtp_raw = raw.get("smtp", {}) if isinstance(raw, dict) else {}
    try:
        cfg.smtp = SmtpSettings(**smtp_raw) if isinstance(smtp_raw, dict) else SmtpSettings()
    except Exception:
        cfg.smtp = SmtpSettings()

    profiles_raw = raw.get("profiles", []) if isinstance(raw, dict) else []
    profiles = []
    for p in profiles_raw:
        if not isinstance(p, dict):
            continue
        try:
            profiles.append(Profile(
                profile_id=str(p.get("profile_id", "")),
                display_name=str(p.get("display_name", "")),
                url=str(p.get("url", "")),
                start_datetime=str(p.get("start_datetime", "")),
                interval_seconds=int(p.get("interval_seconds", 0)),
                success_rules=list(p.get("success_rules", []) or []),
                failure_rules=list(p.get("failure_rules", []) or []),
                last_interval_index_ran=p.get("last_interval_index_ran", None),
                last_status=p.get("last_status", None),
            ))
        except Exception:
            continue

    cfg.profiles = [p for p in profiles if p.profile_id and p.display_name and p.url and p.start_datetime and p.interval_seconds > 0]
    return cfg


def save_config(cfg: AppConfig) -> None:
    try:
        data = {
            "profiles": [asdict(p) for p in cfg.profiles],
            "smtp": asdict(cfg.smtp),
        }
        write_json(PROFILES_PATH, data)
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "Failed to save profiles.json: " + repr(e))


CFG = load_config()
ENGINE = MonitorEngine(CFG, LOG_DIR, LOG_META_PATH, ERROR_LOG_PATH)
ENGINE.start()


def ui_dashboard() -> str:
    cfg = ENGINE.get_snapshot()
    return render_dashboard_html(cfg.profiles, ENGINE.get_last30_bars)


def ui_profile_choices():
    cfg = ENGINE.get_snapshot()
    return [(p.display_name, p.profile_id) for p in cfg.profiles]


def ui_open_add_form():
    return (
        gr.update(visible=True),
        "",  # display_name
        "",  # url
        iso(now_local()),  # start
        0, 0, 5, 0,  # dd hh mm ss
        "",  # success rules
        "Application is not available",  # failure rules
        "",  # msg
        "",  # edit_profile_id
        gr.update(visible=True),  # interval row visible for add
        gr.update(visible=False),  # delete visible? no, add mode
    )


def ui_open_edit_form(profile_id: str):
    cfg = ENGINE.get_snapshot()
    p = None
    for x in cfg.profiles:
        if x.profile_id == profile_id:
            p = x
            break
    if not p:
        return (
            gr.update(visible=False),
            "", "", "", 0, 0, 0, 0, "", "", "Pick a valid profile.", "", gr.update(visible=False), gr.update(visible=False)
        )

    dd = p.interval_seconds // 86400
    rem = p.interval_seconds % 86400
    hh = rem // 3600
    rem = rem % 3600
    mm = rem // 60
    ss = rem % 60

    return (
        gr.update(visible=True),
        p.display_name,
        p.url,
        p.start_datetime,
        dd, hh, mm, ss,
        "\n".join(p.success_rules),
        "\n".join(p.failure_rules),
        "",
        p.profile_id,
        gr.update(visible=False),  # interval row hidden for edit (read-only)
        gr.update(visible=True),   # delete visible
    )


def ui_save_add(display_name: str, url: str, start_dt: str, dd, hh, mm, ss, success_rules_text: str, failure_rules_text: str) -> str:
    try:
        dn = (display_name or "").strip()
        u = (url or "").strip()
        if not dn:
            return "Display name is required."
        if not u:
            return "URL is required."

        parse_datetime_user(start_dt)

        interval_seconds = duration_to_seconds(dd, hh, mm, ss)
        if interval_seconds <= 0:
            return "Interval must be greater than 0."

        pid = f"p_{int(time.time() * 1000)}"
        p = Profile(
            profile_id=pid,
            display_name=dn,
            url=u,
            start_datetime=start_dt.strip(),
            interval_seconds=int(interval_seconds),
            success_rules=normalize_rule_list(success_rules_text),
            failure_rules=normalize_rule_list(failure_rules_text),
        )

        ENGINE.add_profile(p)
        save_config(ENGINE.get_snapshot())
        return "Saved."
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "Save add failed:\n" + repr(e))
        return "Save failed: " + repr(e)


def ui_save_edit(profile_id: str, display_name: str, url: str, start_dt: str, success_rules_text: str, failure_rules_text: str) -> str:
    try:
        pid = (profile_id or "").strip()
        if not pid:
            return "No profile selected."

        dn = (display_name or "").strip()
        u = (url or "").strip()
        if not dn:
            return "Display name is required."
        if not u:
            return "URL is required."

        parse_datetime_user(start_dt)

        ok = ENGINE.update_profile(
            pid,
            dn,
            u,
            start_dt.strip(),
            normalize_rule_list(success_rules_text),
            normalize_rule_list(failure_rules_text),
        )
        if not ok:
            return "Profile not found."

        save_config(ENGINE.get_snapshot())
        return "Saved."
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "Save edit failed:\n" + repr(e))
        return "Save failed: " + repr(e)


def ui_delete_profile(profile_id: str) -> str:
    try:
        pid = (profile_id or "").strip()
        if not pid:
            return "No profile selected."
        ENGINE.delete_profile(pid)
        save_config(ENGINE.get_snapshot())
        return "Deleted."
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "Delete failed:\n" + repr(e))
        return "Delete failed: " + repr(e)


def ui_get_smtp_snapshot():
    cfg = ENGINE.get_snapshot()
    s = cfg.smtp
    return (s.enabled, s.to_email, s.host, s.port, s.username, s.password, s.use_tls, s.from_email, s.only_on_transition_to_down)


def ui_save_smtp(enabled: bool, to_email: str, host: str, port: int, username: str, password: str, use_tls: bool, from_email: str, only_transition: bool) -> str:
    try:
        s = SmtpSettings(
            enabled=bool(enabled),
            to_email=(to_email or "").strip(),
            host=(host or "").strip(),
            port=int(port or 0) if str(port or "").strip() else 0,
            username=(username or "").strip(),
            password=(password or ""),
            use_tls=bool(use_tls),
            from_email=(from_email or "").strip(),
            only_on_transition_to_down=bool(only_transition),
        )
        ENGINE.set_smtp(s)
        save_config(ENGINE.get_snapshot())
        return "Email settings saved."
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "Save SMTP failed:\n" + repr(e))
        return "Save failed: " + repr(e)


with gr.Blocks(title="Down Detector", theme=gr.themes.Soft()) as demo:
    with gr.Row():
        gr.Markdown("## Down Detector")
        add_btn = gr.Button("＋", size="sm")

    dashboard = gr.HTML(value=ui_dashboard())

    timer = gr.Timer(DEFAULT_REFRESH_SECONDS)
    timer.tick(fn=ui_dashboard, outputs=dashboard)

    with gr.Row():
        profile_pick = gr.Dropdown(choices=ui_profile_choices(), label="Select profile to edit", value=None, interactive=True)
        edit_btn = gr.Button("⚙ Edit selected", size="sm")

    with gr.Group(visible=False) as editor_group:
        edit_profile_id = gr.State("")

        gr.Markdown("### Profile")
        display_name_in = gr.Textbox(label="Display name", placeholder="blog-external")
        url_in = gr.Textbox(label="URL", placeholder="https://example.com/landing")
        start_dt_in = gr.Textbox(label="Start datetime (local)", placeholder="YYYY-MM-DD HH:MM[:SS]")

        with gr.Row(visible=True) as interval_row:
            dd_in = gr.Number(label="dd", value=0, precision=0)
            hh_in = gr.Number(label="hh", value=0, precision=0)
            mm_in = gr.Number(label="mm", value=5, precision=0)
            ss_in = gr.Number(label="ss", value=0, precision=0)

        gr.Markdown("Interval becomes read-only after the initial save.")

        success_rules_in = gr.Textbox(
            label="Success match rules (optional, one per line). Use re: for regex.",
            lines=4,
            placeholder="Example:\nre:<title>My App</title>\nWelcome",
        )
        failure_rules_in = gr.Textbox(
            label="Failure match rules (optional, one per line). Use re: for regex.",
            lines=4,
            placeholder="Example:\nApplication is not available\nre:5\\d\\d\\s+Internal Server Error",
        )

        with gr.Row():
            save_btn = gr.Button("Save", variant="primary")
            delete_btn = gr.Button("Delete profile", variant="stop", visible=False)
            close_btn = gr.Button("Close")

        save_msg = gr.Markdown("")

    with gr.Accordion("Email on fail (optional)", open=False):
        enabled_in = gr.Checkbox(label="Enable email on failure", value=False)
        to_email_in = gr.Textbox(label="To email address", placeholder="you@example.com")
        host_in = gr.Textbox(label="SMTP host", placeholder="smtp.office365.com")
        port_in = gr.Number(label="SMTP port", value=587, precision=0)
        username_in = gr.Textbox(label="SMTP username", placeholder="user@domain.com")
        password_in = gr.Textbox(label="SMTP password", type="password")
        use_tls_in = gr.Checkbox(label="Use TLS (STARTTLS)", value=True)
        from_email_in = gr.Textbox(label="From email (optional)", placeholder="monitor@domain.com")
        only_transition_in = gr.Checkbox(label="Only email when status transitions to Down", value=True)
        save_smtp_btn = gr.Button("Save email settings")
        smtp_msg = gr.Markdown("")

    demo.load(fn=ui_get_smtp_snapshot, outputs=[
        enabled_in, to_email_in, host_in, port_in, username_in, password_in, use_tls_in, from_email_in, only_transition_in
    ])
    demo.load(fn=ui_profile_choices, outputs=profile_pick)

    def refresh_picker():
        return ui_profile_choices()

    def open_add():
        return ui_open_add_form()

    def open_edit(profile_id: str):
        if not profile_id:
            return (
                gr.update(visible=False),
                "", "", "", 0, 0, 0, 0, "", "", "Pick a profile first.", "", gr.update(visible=False), gr.update(visible=False)
            )
        return ui_open_edit_form(profile_id)

    add_btn.click(
        fn=open_add,
        outputs=[editor_group, display_name_in, url_in, start_dt_in, dd_in, hh_in, mm_in, ss_in, success_rules_in, failure_rules_in, save_msg, edit_profile_id, interval_row, delete_btn]
    ).then(fn=refresh_picker, outputs=profile_pick).then(fn=ui_dashboard, outputs=dashboard)

    edit_btn.click(
        fn=open_edit,
        inputs=[profile_pick],
        outputs=[editor_group, display_name_in, url_in, start_dt_in, dd_in, hh_in, mm_in, ss_in, success_rules_in, failure_rules_in, save_msg, edit_profile_id, interval_row, delete_btn]
    )

    def do_save(edit_pid: str, display_name: str, url: str, start_dt: str, dd, hh, mm, ss, sr: str, fr: str):
        if edit_pid:
            return ui_save_edit(edit_pid, display_name, url, start_dt, sr, fr)
        return ui_save_add(display_name, url, start_dt, dd, hh, mm, ss, sr, fr)

    save_btn.click(
        fn=do_save,
        inputs=[edit_profile_id, display_name_in, url_in, start_dt_in, dd_in, hh_in, mm_in, ss_in, success_rules_in, failure_rules_in],
        outputs=save_msg
    ).then(fn=refresh_picker, outputs=profile_pick).then(fn=ui_dashboard, outputs=dashboard)

    delete_btn.click(
        fn=ui_delete_profile,
        inputs=[edit_profile_id],
        outputs=save_msg
    ).then(fn=lambda: gr.update(visible=False), outputs=editor_group
    ).then(fn=lambda: "", outputs=edit_profile_id
    ).then(fn=refresh_picker, outputs=profile_pick
    ).then(fn=ui_dashboard, outputs=dashboard)

    close_btn.click(fn=lambda: gr.update(visible=False), outputs=editor_group)

    save_smtp_btn.click(
        fn=ui_save_smtp,
        inputs=[enabled_in, to_email_in, host_in, port_in, username_in, password_in, use_tls_in, from_email_in, only_transition_in],
        outputs=smtp_msg
    )

    gr.Markdown("Data files are stored in `./Logs/` next to `app.py`. Main log files rotate after 2000 records. App issues go to `Logs/error.log`.")

if __name__ == "__main__":
    demo.queue()
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
