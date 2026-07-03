"""
Canonical machine-readable schemas for VaultAgent agent outputs.

Three sequential stages, each with a pydantic model + a lenient validator that
tolerates partial LLM output and returns a normalized dict. The GRPO reward
function and the dashboard both depend on this shared vocabulary.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

THREAT_LEVELS = ("THREAT_BENIGN", "THREAT_LOW", "THREAT_MEDIUM", "THREAT_HIGH")

# Shared flag vocabulary across heuristics, agents, and the reward function.
FLAG_VOCAB = {
    "FLAG_SMS_THEFT",
    "FLAG_CREDENTIAL_STEALING",
    "FLAG_C2",
    "FLAG_SPYWARE",
    "FLAG_DEVICE_ADMIN_ABUSE",
    "FLAG_OVERLAY_ATTACK",
    "FLAG_OBFUSCATION",
    "FLAG_DYNAMIC_LOADING",
    "FLAG_EXPORTED_SURFACE",
    "FLAG_DROPPER",
    "FLAG_SMS_INTERCEPT_SUSPECT",
}


# ── Stage 1: Static Analyst ──────────────────────────────────────────────
class ExportedComponent(BaseModel):
    type: str
    name: str
    permission: Optional[str] = None


class StaticAnalystReport(BaseModel):
    stage: str = "static"
    package: Optional[str] = None
    permissions_dangerous: list[str] = Field(default_factory=list)
    exported_components: list[ExportedComponent] = Field(default_factory=list)
    suspicious_combos: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    ips: list[str] = Field(default_factory=list)
    code_requests: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


# ── Stage 2: Reverse Engineer ────────────────────────────────────────────
class Evidence(BaseModel):
    flag: str
    where: str = ""
    detail: str = ""


class ReverseEngineerReport(BaseModel):
    stage: str = "reverse"
    behaviors: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    obfuscation: bool = False
    flags: list[str] = Field(default_factory=list)


# ── Stage 3: Chief Security Officer ──────────────────────────────────────
class VerdictReport(BaseModel):
    stage: str = "verdict"
    threat_score: int = 0
    threat_level: str = "THREAT_BENIGN"
    malware_family: str = "Unknown"
    indicators: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    rca: str = ""
    impact: list[str] = Field(default_factory=list)
    mitigation: list[str] = Field(default_factory=list)
    eta: str = "ETA_10s"


# ── Lenient validators (tolerate partial / messy LLM output) ─────────────
def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def validate_static(data: dict) -> dict:
    try:
        return StaticAnalystReport(**(data or {})).model_dump()
    except Exception:
        d = data or {}
        return StaticAnalystReport(
            package=d.get("package"),
            permissions_dangerous=_as_list(d.get("permissions_dangerous")),
            suspicious_combos=_as_list(d.get("suspicious_combos")),
            urls=_as_list(d.get("urls")),
            ips=_as_list(d.get("ips")),
            code_requests=_as_list(d.get("code_requests")),
            flags=[f for f in _as_list(d.get("flags")) if isinstance(f, str)],
        ).model_dump()


def validate_reverse(data: dict) -> dict:
    try:
        return ReverseEngineerReport(**(data or {})).model_dump()
    except Exception:
        d = data or {}
        ev = []
        for e in _as_list(d.get("evidence")):
            if isinstance(e, dict):
                ev.append(Evidence(flag=e.get("flag", ""), where=e.get("where", ""),
                                   detail=e.get("detail", "")).model_dump())
        return ReverseEngineerReport(
            behaviors=_as_list(d.get("behaviors")),
            evidence=ev,
            obfuscation=bool(d.get("obfuscation", False)),
            flags=[f for f in _as_list(d.get("flags")) if isinstance(f, str)],
        ).model_dump()


def validate_verdict(data: dict) -> dict:
    try:
        return coerce_verdict(VerdictReport(**(data or {})).model_dump())
    except Exception:
        d = data or {}
        return coerce_verdict(VerdictReport(
            threat_score=int(d.get("threat_score", 0) or 0),
            threat_level=str(d.get("threat_level", "THREAT_BENIGN")),
            malware_family=str(d.get("malware_family", "Unknown")),
            indicators=_as_list(d.get("indicators")),
            evidence=_as_list(d.get("evidence")),
            rca=str(d.get("rca", "")),
            impact=_as_list(d.get("impact")),
            mitigation=_as_list(d.get("mitigation")),
            eta=str(d.get("eta", "ETA_10s")),
        ).model_dump())


def coerce_verdict(v: dict) -> dict:
    """Clamp score to 0-100 and keep level consistent with score."""
    score = max(0, min(100, int(v.get("threat_score", 0) or 0)))
    level = v.get("threat_level") or "THREAT_BENIGN"
    if level not in THREAT_LEVELS:
        level = (
            "THREAT_HIGH" if score >= 70
            else "THREAT_MEDIUM" if score >= 40
            else "THREAT_LOW" if score >= 15
            else "THREAT_BENIGN"
        )
    v["threat_score"] = score
    v["threat_level"] = level
    return v
