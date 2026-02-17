from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SmtpSettings:
    enabled: bool = False
    to_email: str = ""
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_email: str = ""
    only_on_transition_to_down: bool = True


@dataclass
class Profile:
    profile_id: str
    display_name: str
    url: str
    start_datetime: str  # stored as text, parsed when needed
    interval_seconds: int

    success_rules: List[str] = field(default_factory=list)
    failure_rules: List[str] = field(default_factory=list)

    # runtime tracking, persisted
    last_interval_index_ran: Optional[int] = None
    last_status: Optional[str] = None  # "up" | "down" | None


@dataclass
class AppConfig:
    profiles: List[Profile] = field(default_factory=list)
    smtp: SmtpSettings = field(default_factory=SmtpSettings)
