import smtplib
import threading
import time
import traceback
from datetime import timedelta
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple

import requests

from models import AppConfig, Profile, SmtpSettings
from storage import append_log_record, safe_write_error, scan_history_from_logs
from utils import iso, now_local, parse_datetime_user, rule_matches

REQUEST_TIMEOUT_SECONDS = 10.0
CRED_SERVICE_NAME = "DownDetectorSMTP"

# UI history bar count (was 30)
HISTORY_BARS = 120


def _get_password_from_credential_manager(error_log_path: str, username: str) -> str:
    user = (username or "").strip()
    if not user:
        return ""
    try:
        import keyring
    except Exception as e:
        safe_write_error(error_log_path, "keyring not available. Install with: pip install keyring. " + repr(e))
        return ""
    try:
        pw = keyring.get_password(CRED_SERVICE_NAME, user)
        return (pw or "").strip()
    except Exception as e:
        safe_write_error(error_log_path, "Failed reading Credential Manager password via keyring: " + repr(e))
        return ""


def _build_email_message(subject: str, from_addr: str, to_addr: str, lines: List[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content("\n".join(lines))
    return msg


def send_test_email(smtp: SmtpSettings, error_log_path: str) -> Tuple[bool, str]:
    if not smtp.enabled:
        safe_write_error(error_log_path, "Test email: blocked because smtp.enabled is False")
        return (False, "Email is disabled. Enable it first.")

    to_addr = (smtp.to_email or "").strip()
    host = (smtp.host or "").strip()
    user = (smtp.username or "").strip()

    if not to_addr:
        safe_write_error(error_log_path, "Test email: blocked because To email address is blank")
        return (False, "To email address is required.")
    if not host:
        safe_write_error(error_log_path, "Test email: blocked because SMTP host is blank")
        return (False, "SMTP host is required.")
    if not user:
        safe_write_error(error_log_path, "Test email: blocked because SMTP username is blank")
        return (False, "SMTP username is required.")

    password = _get_password_from_credential_manager(error_log_path, user)
    if not password:
        safe_write_error(
            error_log_path,
            f"Test email failed: no password found in Credential Manager for service '{CRED_SERVICE_NAME}' and username '{user}'.",
        )
        return (False, f"No password found in Credential Manager for {user} under {CRED_SERVICE_NAME}.")

    from_addr = (smtp.from_email or "").strip() or user
    port = int(smtp.port or 0) or 587

    subject = "Down Detector: Test email"
    lines = [
        "This is a test email from Down Detector.",
        f"Sent at: {iso(now_local())}",
        f"SMTP host: {host}",
        f"SMTP port: {port}",
        f"SMTP username: {user}",
        f"To: {to_addr}",
    ]
    msg = _build_email_message(subject, from_addr, to_addr, lines)

    try:
        safe_write_error(error_log_path, f"Test email: attempting send to '{to_addr}' via '{host}:{port}' as '{user}'")
        server = smtplib.SMTP(host, port, timeout=15)
        if smtp.use_tls:
            server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        safe_write_error(error_log_path, "Test email: send ok")
        return (True, f"Test email sent to {to_addr}. Check inbox and spam/quarantine.")
    except Exception as e:
        safe_write_error(error_log_path, "Test email: send failed: " + repr(e))
        return (False, "Test email failed. Check Logs/error.log for details: " + repr(e))


def check_url(profile: Profile) -> Tuple[str, Optional[int], Optional[int], str]:
    t0 = time.time()
    try:
        resp = requests.get(
            profile.url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={"User-Agent": "DownDetector/1.0"},
        )
        latency_ms = int((time.time() - t0) * 1000)
        http_status = int(resp.status_code)
        body = resp.text or ""

        for fr in profile.failure_rules:
            if rule_matches(fr, body):
                return ("down", http_status, latency_ms, f"Failure rule matched: {fr}")

        if profile.success_rules:
            any_ok = False
            for sr in profile.success_rules:
                if rule_matches(sr, body):
                    any_ok = True
                    break
            if not any_ok:
                return ("down", http_status, latency_ms, "No success rule matched")

        if 200 <= http_status < 400:
            return ("up", http_status, latency_ms, "HTTP OK")
        return ("down", http_status, latency_ms, f"HTTP {http_status}")
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return ("down", None, latency_ms, repr(e))


def send_email_on_fail(
    smtp: SmtpSettings,
    error_log_path: str,
    profile: Profile,
    scheduled_time,
    status_details: str,
    http_status: Optional[int],
    latency_ms: Optional[int],
) -> None:
    if not smtp.enabled:
        return

    to_addr = (smtp.to_email or "").strip()
    host = (smtp.host or "").strip()
    user = (smtp.username or "").strip()
    if not to_addr or not host or not user:
        return

    password = _get_password_from_credential_manager(error_log_path, user)
    if not password:
        safe_write_error(
            error_log_path,
            f"Email enabled but no password found in Credential Manager for service '{CRED_SERVICE_NAME}' and username '{user}'.",
        )
        return

    from_addr = (smtp.from_email or "").strip() or user
    port = int(smtp.port or 0) or 587

    subject = f"Down Detector: DOWN - {profile.display_name}"
    lines = [
        f"Site: {profile.display_name}",
        f"Scheduled time: {iso(scheduled_time)}",
        f"Observed at: {iso(now_local())}",
        "Status: DOWN",
        f"HTTP status: {http_status if http_status is not None else 'N/A'}",
        f"Latency ms: {latency_ms if latency_ms is not None else 'N/A'}",
        f"Details: {status_details}",
    ]
    msg = _build_email_message(subject, from_addr, to_addr, lines)

    try:
        server = smtplib.SMTP(host, port, timeout=15)
        if smtp.use_tls:
            server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        safe_write_error(error_log_path, "Email send failed: " + repr(e))


class MonitorEngine:
    def __init__(self, cfg: AppConfig, log_dir: str, meta_path: str, error_log_path: str) -> None:
        self._lock = threading.Lock()
        self.cfg = cfg
        self.log_dir = log_dir
        self.meta_path = meta_path
        self.error_log_path = error_log_path

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.history_cache: Dict[str, Dict[int, str]] = scan_history_from_logs(
            self.log_dir, self.error_log_path, [p.profile_id for p in self.cfg.profiles], max_files=2
        )

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._loop, name="DownDetectorEngine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _loop(self) -> None:
        while True:
            try:
                with self._lock:
                    if not self._running:
                        return
                    profiles = list(self.cfg.profiles)
                    smtp = self.cfg.smtp

                now = now_local()
                for p in profiles:
                    try:
                        self._tick_profile(p, smtp, now)
                    except Exception:
                        safe_write_error(self.error_log_path, "tick_profile failed:\n" + traceback.format_exc())

                time.sleep(0.5)
            except Exception:
                safe_write_error(self.error_log_path, "engine loop failed:\n" + traceback.format_exc())
                time.sleep(1.0)

    def _tick_profile(self, p: Profile, smtp: SmtpSettings, now) -> None:
        start_dt = parse_datetime_user(p.start_datetime)
        interval = int(p.interval_seconds)
        if interval <= 0:
            return
        if now < start_dt:
            return

        elapsed = (now - start_dt).total_seconds()
        current_index = int(elapsed // interval)
        scheduled_time = start_dt + timedelta(seconds=current_index * interval)

        with self._lock:
            last_ran = p.last_interval_index_ran

        if last_ran is not None and last_ran >= current_index:
            return

        status, http_status, latency_ms, details = check_url(p)

        record = {
            "ts": iso(now_local()),
            "profile_id": p.profile_id,
            "display_name": p.display_name,
            "interval_seconds": p.interval_seconds,
            "start_datetime": p.start_datetime,
            "interval_index": current_index,
            "scheduled_time": iso(scheduled_time),
            "status": status,
            "http_status": http_status,
            "latency_ms": latency_ms,
            "details": details,
        }
        append_log_record(self.log_dir, self.meta_path, self.error_log_path, record)

        # Robust transition logic
        if status == "up":
            p.down_notified = False

        if status == "down":
            if smtp.only_on_transition_to_down and p.down_notified:
                pass
            else:
                send_email_on_fail(smtp, self.error_log_path, p, scheduled_time, details, http_status, latency_ms)
                p.down_notified = True

        with self._lock:
            p.last_interval_index_ran = current_index
            p.last_status = status
            if p.profile_id not in self.history_cache:
                self.history_cache[p.profile_id] = {}
            self.history_cache[p.profile_id][current_index] = status

    def rescan_history_for_profiles(self, profile_ids: List[str]) -> None:
        more = scan_history_from_logs(self.log_dir, self.error_log_path, profile_ids, max_files=2)
        with self._lock:
            for pid, mp in more.items():
                if pid not in self.history_cache:
                    self.history_cache[pid] = {}
                self.history_cache[pid].update(mp)

    def get_snapshot(self) -> AppConfig:
        with self._lock:
            return self.cfg

    def set_smtp(self, smtp: SmtpSettings) -> None:
        with self._lock:
            self.cfg.smtp = smtp

    def add_profile(self, p: Profile) -> None:
        with self._lock:
            self.cfg.profiles.append(p)
            if p.profile_id not in self.history_cache:
                self.history_cache[p.profile_id] = {}
        self.rescan_history_for_profiles([p.profile_id])

    def update_profile(self, profile_id: str, display_name: str, url: str, start_datetime: str, success_rules: List[str], failure_rules: List[str]) -> bool:
        with self._lock:
            for p in self.cfg.profiles:
                if p.profile_id == profile_id:
                    p.display_name = display_name
                    p.url = url
                    p.start_datetime = start_datetime
                    p.success_rules = list(success_rules)
                    p.failure_rules = list(failure_rules)
                    return True
        return False

    def delete_profile(self, profile_id: str) -> None:
        with self._lock:
            self.cfg.profiles = [p for p in self.cfg.profiles if p.profile_id != profile_id]
            if profile_id in self.history_cache:
                del self.history_cache[profile_id]

    # Keep method name for app.py compatibility, but return HISTORY_BARS bars
    def get_last30_bars(self, p: Profile) -> List[str]:
        try:
            now = now_local()
            start_dt = parse_datetime_user(p.start_datetime)
            if now < start_dt:
                return ["untested"] * HISTORY_BARS

            interval = int(p.interval_seconds)
            if interval <= 0:
                return ["untested"] * HISTORY_BARS

            elapsed = (now - start_dt).total_seconds()
            cur = int(elapsed // interval)

            start_idx = cur - (HISTORY_BARS - 1)

            with self._lock:
                cache = dict(self.history_cache.get(p.profile_id, {}))

            out = []
            for idx in range(start_idx, cur + 1):
                if idx in cache:
                    out.append(cache[idx])
                else:
                    out.append("untested")
            return out
        except Exception:
            return ["untested"] * HISTORY_BARS
