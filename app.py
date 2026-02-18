import os
import time
from dataclasses import asdict

import gradio as gr

from engine import MonitorEngine, send_test_email
from models import AppConfig, Profile, SmtpSettings
from storage import ensure_dir, read_json, safe_write_error, write_json
from ui import render_card_html, render_empty_dashboard_html
from utils import duration_to_seconds, iso, normalize_rule_list, now_local, parse_datetime_user

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(APP_DIR, "Logs")
PROFILES_PATH = os.path.join(LOG_DIR, "profiles.json")
LOG_META_PATH = os.path.join(LOG_DIR, "log_meta.json")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "error.log")

DEFAULT_REFRESH_SECONDS = 1.0
MAX_WIDGET_SLOTS = 20

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
                down_notified=bool(p.get("down_notified", False)),
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


def ui_get_slots():
    cfg = ENGINE.get_snapshot()
    profiles = list(cfg.profiles)

    updates = []

    if len(profiles) == 0:
        updates.append((gr.update(visible=True), render_empty_dashboard_html(), "", gr.update(value="Edit", visible=False)))
        for _ in range(1, MAX_WIDGET_SLOTS):
            updates.append((gr.update(visible=False), "", "", gr.update(value="Edit", visible=False)))
        return updates

    for i in range(MAX_WIDGET_SLOTS):
        if i < len(profiles):
            p = profiles[i]
            bars = ENGINE.get_last30_bars(p)
            html = render_card_html(p, bars)
            updates.append((gr.update(visible=True), html, p.profile_id, gr.update(value="Edit", visible=True)))
        else:
            updates.append((gr.update(visible=False), "", "", gr.update(value="Edit", visible=False)))

    return updates


def _split_interval(seconds: int):
    seconds = int(seconds or 0)
    dd = seconds // 86400
    rem = seconds % 86400
    hh = rem // 3600
    rem = rem % 3600
    mm = rem // 60
    ss = rem % 60
    return dd, hh, mm, ss


def ui_open_add_form():
    return (
        gr.update(visible=True),
        "", "", iso(now_local()),
        gr.update(value=0, interactive=True),
        gr.update(value=0, interactive=True),
        gr.update(value=5, interactive=True),
        gr.update(value=0, interactive=True),
        "", "Application is not available",
        "", "", gr.update(visible=False),
    )


def ui_open_edit_form(profile_id: str):
    cfg = ENGINE.get_snapshot()
    p = None
    for x in cfg.profiles:
        if x.profile_id == profile_id:
            p = x
            break
    if not p:
        return (gr.update(visible=False), "", "", "", gr.update(value=0), gr.update(value=0), gr.update(value=0), gr.update(value=0), "", "", "Profile not found.", "", gr.update(visible=False))

    dd, hh, mm, ss = _split_interval(p.interval_seconds)

    return (
        gr.update(visible=True),
        p.display_name,
        p.url,
        p.start_datetime,
        gr.update(value=dd, interactive=False),
        gr.update(value=hh, interactive=False),
        gr.update(value=mm, interactive=False),
        gr.update(value=ss, interactive=False),
        "\n".join(p.success_rules),
        "\n".join(p.failure_rules),
        "",
        p.profile_id,
        gr.update(visible=True),
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
    return (s.enabled, s.to_email, s.host, s.port, s.username, s.use_tls, s.from_email, s.only_on_transition_to_down)


def ui_save_smtp(enabled: bool, to_email: str, host: str, port: int, username: str, use_tls: bool, from_email: str, only_transition: bool) -> str:
    try:
        s = SmtpSettings(
            enabled=bool(enabled),
            to_email=(to_email or "").strip(),
            host=(host or "").strip(),
            port=int(port or 0) if str(port or "").strip() else 0,
            username=(username or "").strip(),
            password="",
            use_tls=bool(use_tls),
            from_email=(from_email or "").strip(),
            only_on_transition_to_down=bool(only_transition),
        )
        ENGINE.set_smtp(s)
        save_config(ENGINE.get_snapshot())
        safe_write_error(ERROR_LOG_PATH, "SMTP settings saved (password via Credential Manager). enabled=" + str(s.enabled))
        return "Email settings saved. Password is read from Windows Credential Manager (DownDetectorSMTP)."
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "Save SMTP failed:\n" + repr(e))
        return "Save failed: " + repr(e)


def ui_send_test_email(enabled: bool, to_email: str, host: str, port: int, username: str, use_tls: bool, from_email: str, only_transition: bool) -> str:
    try:
        s = SmtpSettings(
            enabled=bool(enabled),
            to_email=(to_email or "").strip(),
            host=(host or "").strip(),
            port=int(port or 0) if str(port or "").strip() else 0,
            username=(username or "").strip(),
            password="",
            use_tls=bool(use_tls),
            from_email=(from_email or "").strip(),
            only_on_transition_to_down=bool(only_transition),
        )
        safe_write_error(ERROR_LOG_PATH, "Test email clicked: enabled=" + str(s.enabled) + " host=" + (s.host or "") + " port=" + str(s.port or "") + " user=" + (s.username or "") + " to=" + (s.to_email or ""))
        ok, msg = send_test_email(s, ERROR_LOG_PATH)
        return msg
    except Exception as e:
        safe_write_error(ERROR_LOG_PATH, "UI test email failed: " + repr(e))
        return "Test email failed. Check Logs/error.log: " + repr(e)


with gr.Blocks(title="Down Detector", theme=gr.themes.Soft()) as demo:
    with gr.Row():
        gr.Markdown("## Down Detector")
        add_btn = gr.Button("Add", size="sm")

    slot_groups, slot_cards, slot_pids, slot_edit_btns = [], [], [], []
    with gr.Group():
        for _ in range(MAX_WIDGET_SLOTS):
            with gr.Group(visible=False) as g:
                with gr.Row():
                    card = gr.HTML(scale=9, min_width=0)
                    pid_state = gr.State("")
                    edit_btn = gr.Button("Edit", size="sm", visible=False, scale=1, min_width=90)
                slot_groups.append(g)
                slot_cards.append(card)
                slot_pids.append(pid_state)
                slot_edit_btns.append(edit_btn)

    with gr.Group(visible=False) as editor_group:
        edit_profile_id = gr.State("")

        gr.Markdown("### Profile")
        display_name_in = gr.Textbox(label="Display name", placeholder="blog-external")
        url_in = gr.Textbox(label="URL", placeholder="https://example.com/landing")
        start_dt_in = gr.Textbox(label="Start datetime (local)", placeholder="YYYY-MM-DD HH:MM[:SS]")

        with gr.Row():
            dd_in = gr.Number(label="dd", value=0, precision=0)
            hh_in = gr.Number(label="hh", value=0, precision=0)
            mm_in = gr.Number(label="mm", value=5, precision=0)
            ss_in = gr.Number(label="ss", value=0, precision=0)

        gr.Markdown("Interval is editable only when creating a new profile.")

        success_rules_in = gr.Textbox(label="Success match rules (optional, one per line). Use re: for regex.", lines=4)
        failure_rules_in = gr.Textbox(label="Failure match rules (optional, one per line). Use re: for regex.", lines=4)

        with gr.Row():
            save_btn = gr.Button("Save", variant="primary")
            delete_btn = gr.Button("Delete profile", variant="stop", visible=False)
            close_btn = gr.Button("Close")

        save_msg = gr.Markdown("")

    with gr.Accordion("Email on fail (optional)", open=False):
        enabled_in = gr.Checkbox(label="Enable email on failure", value=False)
        to_email_in = gr.Textbox(label="To email address")
        host_in = gr.Textbox(label="SMTP host", placeholder="smtp.gmail.com")
        port_in = gr.Number(label="SMTP port", value=587, precision=0)
        username_in = gr.Textbox(label="SMTP username")
        use_tls_in = gr.Checkbox(label="Use TLS (STARTTLS)", value=True)
        from_email_in = gr.Textbox(label="From email (optional)")
        only_transition_in = gr.Checkbox(label="Only email when status transitions to Down", value=True)

        with gr.Row():
            save_smtp_btn = gr.Button("Save email settings")
            test_email_btn = gr.Button("Send test email")

        smtp_msg = gr.Markdown("")
        test_msg = gr.Markdown("")

        gr.Markdown("Password is not entered here. Store it in Windows Credential Manager as a Generic Credential named `DownDetectorSMTP` with username equal to the SMTP username.")

    demo.load(fn=ui_get_smtp_snapshot, outputs=[enabled_in, to_email_in, host_in, port_in, username_in, use_tls_in, from_email_in, only_transition_in])

    timer = gr.Timer(DEFAULT_REFRESH_SECONDS)

    def apply_slot_updates():
        upd = ui_get_slots()
        outs = []
        for (g_upd, html, pid, btn_upd) in upd:
            outs.extend([g_upd, html, pid, btn_upd])
        return outs

    slot_outputs = []
    for i in range(MAX_WIDGET_SLOTS):
        slot_outputs.extend([slot_groups[i], slot_cards[i], slot_pids[i], slot_edit_btns[i]])

    demo.load(fn=apply_slot_updates, outputs=slot_outputs)
    timer.tick(fn=apply_slot_updates, outputs=slot_outputs)

    add_btn.click(
        fn=ui_open_add_form,
        outputs=[editor_group, display_name_in, url_in, start_dt_in, dd_in, hh_in, mm_in, ss_in, success_rules_in, failure_rules_in, save_msg, edit_profile_id, delete_btn]
    )

    def open_edit_from_pid(pid: str):
        if not pid:
            return (gr.update(visible=False), "", "", "", gr.update(value=0), gr.update(value=0), gr.update(value=0), gr.update(value=0), "", "", "Profile not found.", "", gr.update(visible=False))
        return ui_open_edit_form(pid)

    for i in range(MAX_WIDGET_SLOTS):
        slot_edit_btns[i].click(
            fn=open_edit_from_pid,
            inputs=[slot_pids[i]],
            outputs=[editor_group, display_name_in, url_in, start_dt_in, dd_in, hh_in, mm_in, ss_in, success_rules_in, failure_rules_in, save_msg, edit_profile_id, delete_btn]
        )

    def do_save(edit_pid: str, display_name: str, url: str, start_dt: str, dd, hh, mm, ss, sr: str, fr: str):
        if edit_pid:
            return ui_save_edit(edit_pid, display_name, url, start_dt, sr, fr)
        return ui_save_add(display_name, url, start_dt, dd, hh, mm, ss, sr, fr)

    save_btn.click(
        fn=do_save,
        inputs=[edit_profile_id, display_name_in, url_in, start_dt_in, dd_in, hh_in, mm_in, ss_in, success_rules_in, failure_rules_in],
        outputs=save_msg
    ).then(fn=apply_slot_updates, outputs=slot_outputs)

    delete_btn.click(
        fn=ui_delete_profile,
        inputs=[edit_profile_id],
        outputs=save_msg
    ).then(fn=lambda: gr.update(visible=False), outputs=editor_group
    ).then(fn=lambda: "", outputs=edit_profile_id
    ).then(fn=apply_slot_updates, outputs=slot_outputs)

    close_btn.click(fn=lambda: gr.update(visible=False), outputs=editor_group)

    save_smtp_btn.click(fn=ui_save_smtp, inputs=[enabled_in, to_email_in, host_in, port_in, username_in, use_tls_in, from_email_in, only_transition_in], outputs=smtp_msg)
    test_email_btn.click(fn=ui_send_test_email, inputs=[enabled_in, to_email_in, host_in, port_in, username_in, use_tls_in, from_email_in, only_transition_in], outputs=test_msg)

    gr.Markdown("Data files are stored in `./Logs/` next to `app.py`. Main log files rotate after 2000 records. App issues go to `Logs/error.log`.")

if __name__ == "__main__":
    demo.queue()
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
