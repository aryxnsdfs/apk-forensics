from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Difficulty = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    difficulty: Difficulty
    title: str
    objective: str
    incident_summary: str
    artifacts: dict[str, str]
    required_artifacts: tuple[str, ...]
    required_ticket_keywords: tuple[str, ...]
    required_fix_keywords: tuple[str, ...]
    required_resolution_keywords: tuple[str, ...]
    required_status_keywords: tuple[str, ...] = ()
    max_steps: int = 6
    success_threshold: float = 0.8


# VaultAgent malware forensic tasks. The TaskSpec shape is preserved so the
# OpenEnv environment/rubrics keep working; the keyword fields are repurposed:
#   artifacts            -> manifest / permissions / code evidence to inspect
#   required_ticket_*    -> expected malware flags
#   required_fix_*       -> expected mitigation keywords
#   required_resolution_*-> expected verdict / family keywords
#   required_status_*    -> expected evidence/behavior keywords
TASKS: dict[str, TaskSpec] = {
    "task_easy_sms_stealer": TaskSpec(
        task_id="task_easy_sms_stealer",
        difficulty="easy",
        title="SMS / OTP Stealer Triage",
        objective=(
            "Analyze a flashlight app that requests SMS interception and network "
            "access, determine the malware behavior, and issue a verdict with RCA."
        ),
        incident_summary=(
            "A 'Flashlight Pro' APK requests RECEIVE_SMS + INTERNET and ships an "
            "exported SmsRx receiver that POSTs to a hardcoded IP."
        ),
        artifacts={
            "manifest": (
                "package=com.flashlight.app permissions=[RECEIVE_SMS, READ_SMS, "
                "INTERNET] exported receiver=.SmsRx"
            ),
            "permissions": "RECEIVE_SMS + INTERNET is a known OTP-exfiltration combo.",
            "code": (
                "SmsRx.onReceive() reads the SMS body and calls HttpURLConnection "
                "POST to http://192.0.2.10/gate."
            ),
        },
        required_artifacts=("manifest", "code"),
        required_ticket_keywords=("flag_sms_theft", "flag_c2"),
        required_fix_keywords=("uninstall", "revoke", "block"),
        required_resolution_keywords=("threat_high", "sms-stealer", "otp"),
        required_status_keywords=("smsrx", "onreceive", "exfiltration"),
        max_steps=6,
    ),
    "task_medium_banking_overlay": TaskSpec(
        task_id="task_medium_banking_overlay",
        difficulty="medium",
        title="Banking Overlay Credential Theft",
        objective=(
            "Analyze an app abusing SYSTEM_ALERT_WINDOW to phish banking "
            "credentials, classify the family, and recommend mitigation."
        ),
        incident_summary=(
            "A 'Battery Saver' APK draws overlays over banking apps and uploads "
            "captured credentials."
        ),
        artifacts={
            "manifest": (
                "permissions=[SYSTEM_ALERT_WINDOW, INTERNET, READ_PHONE_STATE] "
                "exported service=.OverlayService"
            ),
            "permissions": "SYSTEM_ALERT_WINDOW + INTERNET enables overlay phishing.",
            "code": (
                "OverlayService inflates a fake bank login view and sends typed "
                "fields to 198.51.100.7."
            ),
        },
        required_artifacts=("manifest", "code"),
        required_ticket_keywords=("flag_overlay_attack", "flag_credential_stealing"),
        required_fix_keywords=("uninstall", "revoke", "overlay"),
        required_resolution_keywords=("threat_high", "banking-overlay", "credential"),
        required_status_keywords=("overlayservice", "login", "credential"),
        max_steps=10,
    ),
    "task_hard_accessibility_trojan": TaskSpec(
        task_id="task_hard_accessibility_trojan",
        difficulty="hard",
        title="Accessibility Trojan / Keylogger",
        objective=(
            "Analyze a trojan abusing the accessibility service to scrape UI text "
            "and keystrokes, identify obfuscation, and write the RCA."
        ),
        incident_summary=(
            "A 'Cleaner Max' APK binds an accessibility service, overlays content, "
            "and exfiltrates keystrokes; strings are obfuscated."
        ),
        artifacts={
            "manifest": (
                "permissions=[BIND_ACCESSIBILITY_SERVICE, INTERNET, "
                "SYSTEM_ALERT_WINDOW] service=.A11yService"
            ),
            "permissions": "Accessibility + INTERNET enables UI scraping / keylogging.",
            "code": (
                "A11yService.onAccessibilityEvent() captures node text; payload is "
                "base64+XOR obfuscated before upload to 192.0.2.200."
            ),
        },
        required_artifacts=("manifest", "code"),
        required_ticket_keywords=("flag_spyware", "flag_credential_stealing", "flag_obfuscation"),
        required_fix_keywords=("uninstall", "revoke", "accessibility"),
        required_resolution_keywords=("threat_high", "accessibility-trojan", "keylog"),
        required_status_keywords=("a11yservice", "onaccessibilityevent", "obfuscat"),
        max_steps=15,
    ),
}


def get_task(task_id: str) -> TaskSpec:
    try:
        return TASKS[task_id]
    except KeyError as exc:
        raise KeyError(f"Unknown task_id: {task_id}") from exc


def list_task_ids() -> list[str]:
    return list(TASKS.keys())
