"""
APK Feature Heuristics — VaultAgent rule-based threat seed.

Pure-Python (no LLM, no network). Consumes the compact metadata dict from
`apk_extractor.extract()` and produces:

  * a rule-based threat seed (score + flags) so the dashboard shows signal even
    before / without the LLM,
  * the list of code snippets Stage 2 (Reverse Engineer) should request,
  * suspicious permission combinations.

Flag vocabulary is shared with the agents and the GRPO reward function:
  FLAG_SMS_THEFT, FLAG_CREDENTIAL_STEALING, FLAG_C2, FLAG_SPYWARE,
  FLAG_DEVICE_ADMIN_ABUSE, FLAG_OVERLAY_ATTACK, FLAG_OBFUSCATION,
  FLAG_DYNAMIC_LOADING, FLAG_EXPORTED_SURFACE
"""

from __future__ import annotations

from typing import Any

# Permission combos that strongly imply a behavior. Each entry:
#   (frozenset of required dangerous perms, flag, weight, human label)
SUSPICIOUS_COMBOS: list[tuple[frozenset, str, int, str]] = [
    (frozenset({"RECEIVE_SMS", "INTERNET"}), "FLAG_SMS_THEFT", 30,
     "Intercepts incoming SMS and has network access (OTP exfiltration)"),
    (frozenset({"READ_SMS", "INTERNET"}), "FLAG_SMS_THEFT", 25,
     "Reads SMS inbox and can upload it"),
    (frozenset({"BIND_DEVICE_ADMIN", "READ_CONTACTS"}), "FLAG_DEVICE_ADMIN_ABUSE", 25,
     "Requests device-admin alongside contact access"),
    (frozenset({"SYSTEM_ALERT_WINDOW", "INTERNET"}), "FLAG_OVERLAY_ATTACK", 25,
     "Can draw overlays over other apps (phishing/banking overlay)"),
    (frozenset({"BIND_ACCESSIBILITY_SERVICE", "INTERNET"}), "FLAG_SPYWARE", 30,
     "Accessibility service + network (keylogging / UI scraping)"),
    (frozenset({"RECORD_AUDIO", "INTERNET"}), "FLAG_SPYWARE", 20,
     "Records audio and can transmit it"),
    (frozenset({"READ_CONTACTS", "INTERNET"}), "FLAG_SPYWARE", 15,
     "Harvests contacts and has network access"),
    (frozenset({"ACCESS_FINE_LOCATION", "INTERNET"}), "FLAG_SPYWARE", 12,
     "Tracks precise location and can transmit it"),
    (frozenset({"GET_ACCOUNTS", "INTERNET"}), "FLAG_CREDENTIAL_STEALING", 18,
     "Enumerates device accounts with network access"),
    (frozenset({"REQUEST_INSTALL_PACKAGES", "INTERNET"}), "FLAG_DROPPER", 22,
     "Can download and install further packages (dropper)"),
]

# INTERNET on its own is benign; INTERNET + a hardcoded public IP is a C2 hint.
C2_PERMS = {"INTERNET"}


def analyze(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return a rule-based threat seed for the given APK metadata."""
    perms = set(metadata.get("permissions_dangerous", [])) | set(metadata.get("permissions", []))
    flags: dict[str, str] = {}     # flag -> evidence
    score = 0
    combos: list[str] = []
    code_requests: list[str] = []

    # ── Suspicious permission combinations ──
    for required, flag, weight, label in SUSPICIOUS_COMBOS:
        if required.issubset(perms):
            combos.append("+".join(sorted(required)))
            score += weight
            flags.setdefault(flag, label)

    # ── Hardcoded C2 endpoints ──
    ips = metadata.get("ips", [])
    urls = metadata.get("urls", [])
    if ips and (C2_PERMS & perms):
        score += 25
        flags["FLAG_C2"] = f"Hardcoded public IP(s) with INTERNET: {', '.join(ips[:3])}"
    elif ips:
        score += 10
        flags.setdefault("FLAG_C2", f"Hardcoded public IP(s): {', '.join(ips[:3])}")

    # ── Exported attack surface ──
    exported = metadata.get("exported_components", [])
    unguarded = [c for c in exported if not c.get("permission")]
    if unguarded:
        score += min(20, 5 * len(unguarded))
        names = ", ".join(c["name"].rsplit(".", 1)[-1] for c in unguarded[:4])
        flags["FLAG_EXPORTED_SURFACE"] = f"Exported components without permission guard: {names}"
        # Stage 2 should review the receivers/services that handle sensitive intents.
        for c in unguarded:
            if c["type"] in ("receiver", "service"):
                code_requests.append(c["name"])

    # ── SMS receiver entry points get their handler requested for Stage 2 ──
    if {"RECEIVE_SMS", "READ_SMS"} & perms:
        for c in exported:
            if c["type"] == "receiver":
                code_requests.append(c["name"])

    # ── Raw dangerous-permission pressure ──
    dangerous = metadata.get("permissions_dangerous", [])
    score += min(15, len(dangerous) * 2)

    # ── Normalize + derive level ──
    score = max(0, min(100, score))
    level = threat_level(score)

    # De-dup code requests, cap to keep the LLM context tight.
    seen: set[str] = set()
    deduped = [c for c in code_requests if not (c in seen or seen.add(c))][:6]

    return {
        "threat_score": score,
        "threat_level": level,
        "flags": list(flags.keys()),
        "evidence": [{"flag": k, "detail": v} for k, v in flags.items()],
        "suspicious_combos": sorted(set(combos)),
        "code_requests": deduped,
        "dangerous_permission_count": len(dangerous),
        "exported_component_count": len(exported),
    }


def threat_level(score: int) -> str:
    if score >= 70:
        return "THREAT_HIGH"
    if score >= 40:
        return "THREAT_MEDIUM"
    if score >= 15:
        return "THREAT_LOW"
    return "THREAT_BENIGN"
