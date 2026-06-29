"""
APK Extractor — VaultAgent static-analysis front end.

Replaces the old Docker code-execution sandbox. Instead of *running* code, we
*parse* an uploaded APK fully offline with Androguard and emit a lightweight JSON
metadata representation. The LLM agents never read the whole APK — they receive
this compact JSON plus, on demand, individual smali method snippets fetched lazily
via `ApkExtractor.get_method_smali`.

Air-gapped: Androguard is pure-Python and needs no network or JDK.

If Androguard is not installed, `extract()` still returns a well-formed (empty)
metadata dict with `available=False` so the rest of the backbone keeps working
in stub mode.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger("swarm-os.apk")

# ── Androguard is optional at import time so the backend boots without it. ──
try:
    # Androguard logs verbosely via loguru — quiet it so our pipeline output stays clean.
    try:
        from loguru import logger as _loguru_logger
        _loguru_logger.disable("androguard")
    except Exception:
        pass

    from androguard.misc import AnalyzeAPK  # type: ignore

    ANDROGUARD_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    AnalyzeAPK = None  # type: ignore
    ANDROGUARD_AVAILABLE = False
    logger.warning("Androguard unavailable (%s). APK extraction runs in stub mode.", exc)


# Android "dangerous" / high-signal permission set used to flag risky requests
# without an LLM. Short suffixes (android.permission.X -> X).
DANGEROUS_PERMISSIONS = {
    "READ_SMS", "RECEIVE_SMS", "SEND_SMS", "WRITE_SMS",
    "READ_CONTACTS", "WRITE_CONTACTS",
    "READ_CALL_LOG", "WRITE_CALL_LOG", "PROCESS_OUTGOING_CALLS",
    "RECORD_AUDIO", "CAMERA",
    "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "ACCESS_BACKGROUND_LOCATION",
    "READ_PHONE_STATE", "READ_PHONE_NUMBERS", "CALL_PHONE",
    "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "MANAGE_EXTERNAL_STORAGE",
    "BIND_DEVICE_ADMIN", "BIND_ACCESSIBILITY_SERVICE", "SYSTEM_ALERT_WINDOW",
    "REQUEST_INSTALL_PACKAGES", "GET_ACCOUNTS", "USE_FINGERPRINT",
    "QUERY_ALL_PACKAGES", "PACKAGE_USAGE_STATS", "REQUEST_IGNORE_BATTERY_OPTIMIZATIONS",
}

# Regexes for network indicators harvested from decoded strings / resources.
_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
# Private/loopback ranges are noise, not C2.
_PRIVATE_IP_RE = re.compile(r"^(?:0\.|127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.)")


def _short_perm(perm: str) -> str:
    """android.permission.RECEIVE_SMS -> RECEIVE_SMS."""
    return perm.rsplit(".", 1)[-1] if perm else perm


class ApkExtractor:
    """
    Lazy wrapper around an Androguard analysis. `metadata` is the compact JSON
    handed to the agents; `get_method_smali` fetches code only when an agent asks.
    """

    def __init__(self, apk_path: str):
        self.apk_path = apk_path
        self.apk = None
        self.dvms: list = []
        self.analysis = None
        self.metadata: dict[str, Any] = {}

    # ── Parsing ──────────────────────────────────────────────────────────
    def parse(self) -> dict[str, Any]:
        if not os.path.exists(self.apk_path):
            raise FileNotFoundError(self.apk_path)

        size_bytes = os.path.getsize(self.apk_path)

        if not ANDROGUARD_AVAILABLE:
            self.metadata = self._empty_metadata(size_bytes, reason="androguard_missing")
            return self.metadata

        try:
            self.apk, self.dvms, self.analysis = AnalyzeAPK(self.apk_path)
        except Exception as exc:
            logger.exception("Androguard failed to analyze %s", self.apk_path)
            self.metadata = self._empty_metadata(size_bytes, reason=f"parse_error:{exc}")
            return self.metadata

        self.metadata = self._build_metadata(size_bytes)
        return self.metadata

    def _empty_metadata(self, size_bytes: int, reason: str) -> dict[str, Any]:
        return {
            "available": False,
            "reason": reason,
            "apk_path": self.apk_path,
            "apk_size_bytes": size_bytes,
            "apk_size_kb": round(size_bytes / 1024, 1),
            "package": None,
            "version_name": None,
            "min_sdk": None,
            "target_sdk": None,
            "permissions": [],
            "permissions_dangerous": [],
            "activities": [],
            "services": [],
            "receivers": [],
            "providers": [],
            "exported_components": [],
            "intent_filters": [],
            "urls": [],
            "ips": [],
            "domains": [],
            "file_count": 0,
            "dex_count": 0,
            "strings_sampled": 0,
        }

    def _build_metadata(self, size_bytes: int) -> dict[str, Any]:
        apk = self.apk
        permissions = [p for p in (apk.get_permissions() or [])]
        dangerous = sorted({_short_perm(p) for p in permissions if _short_perm(p) in DANGEROUS_PERMISSIONS})

        exported = self._exported_components()
        urls, ips, domains = self._network_indicators()

        try:
            files = apk.get_files()
        except Exception:
            files = []

        meta = {
            "available": True,
            "reason": None,
            "apk_path": self.apk_path,
            "apk_size_bytes": size_bytes,
            "apk_size_kb": round(size_bytes / 1024, 1),
            "package": apk.get_package(),
            "version_name": apk.get_androidversion_name(),
            "version_code": apk.get_androidversion_code(),
            "min_sdk": _to_int(apk.get_min_sdk_version()),
            "target_sdk": _to_int(apk.get_target_sdk_version()),
            "main_activity": apk.get_main_activity(),
            "permissions": [_short_perm(p) for p in permissions],
            "permissions_dangerous": dangerous,
            "activities": _safe_list(apk.get_activities),
            "services": _safe_list(apk.get_services),
            "receivers": _safe_list(apk.get_receivers),
            "providers": _safe_list(apk.get_providers),
            "exported_components": exported,
            "intent_filters": self._intent_filters(),
            "urls": urls,
            "ips": ips,
            "domains": domains,
            "file_count": len(files),
            "dex_count": len(self.dvms),
            "strings_sampled": self._string_sample_count,
        }
        return meta

    def _exported_components(self) -> list[dict[str, Any]]:
        """Components reachable by other apps — a common attack surface."""
        out: list[dict[str, Any]] = []
        apk = self.apk
        for kind, getter in (
            ("activity", apk.get_activities),
            ("service", apk.get_services),
            ("receiver", apk.get_receivers),
            ("provider", apk.get_providers),
        ):
            for name in _safe_list(getter):
                try:
                    exported = apk.get_element(_manifest_tag(kind), "exported", name=name)
                    perm = apk.get_element(_manifest_tag(kind), "permission", name=name)
                except Exception:
                    exported, perm = None, None
                is_exported = str(exported).lower() == "true"
                # Heuristic: a component with intent filters but no explicit
                # exported flag is implicitly exported on older targets.
                if is_exported or (exported is None and self._has_intent_filter(name)):
                    out.append({
                        "type": kind,
                        "name": name,
                        "permission": perm or None,
                        "explicit": is_exported,
                    })
        return out

    def _has_intent_filter(self, comp_name: str) -> bool:
        return any(f.get("component") == comp_name for f in self._intent_filters())

    _intent_filter_cache: Optional[list[dict[str, Any]]] = None

    def _intent_filters(self) -> list[dict[str, Any]]:
        if self._intent_filter_cache is not None:
            return self._intent_filter_cache
        filters: list[dict[str, Any]] = []
        try:
            # androguard exposes intent filters per component type
            raw = self.apk.get_intent_filters  # method
        except Exception:
            raw = None
        if raw:
            for kind in ("activity", "service", "receiver"):
                for comp in _safe_list(getattr(self.apk, f"get_{kind_plural(kind)}")):
                    try:
                        info = self.apk.get_intent_filters(kind, comp)
                    except Exception:
                        info = None
                    if info:
                        filters.append({
                            "component": comp,
                            "type": kind,
                            "actions": list(info.get("action", [])),
                            "categories": list(info.get("category", [])),
                        })
        self._intent_filter_cache = filters
        return filters

    _string_sample_count = 0

    def _network_indicators(self) -> tuple[list[str], list[str], list[str]]:
        """Harvest URLs / public IPs / domains from decoded DEX strings."""
        urls: set[str] = set()
        ips: set[str] = set()
        sampled = 0
        if self.analysis is not None:
            try:
                for s in self.analysis.get_strings():
                    val = s.get_value() if hasattr(s, "get_value") else str(s)
                    if not val:
                        continue
                    sampled += 1
                    for m in _URL_RE.findall(val):
                        urls.add(m.strip().rstrip(".,)"))
                    for m in _IP_RE.findall(val):
                        if not _PRIVATE_IP_RE.match(m):
                            ips.add(m)
            except Exception:
                logger.debug("string harvest failed", exc_info=True)
        self._string_sample_count = sampled

        domains: set[str] = set()
        for u in urls:
            m = re.match(r"https?://([^/:]+)", u, re.IGNORECASE)
            if m:
                domains.add(m.group(1).lower())

        return sorted(urls)[:200], sorted(ips)[:100], sorted(domains)[:100]

    # ── Lazy code access for Stage 2 (Reverse Engineer) ──────────────────
    def get_method_smali(self, class_name: str, method_name: str = "") -> str:
        """
        Return decoded smali/bytecode for a single class (optionally one method).
        Agents call this ONLY for components flagged in Stage 1, so the model
        never ingests the full APK.
        """
        if self.analysis is None:
            return ""
        snippets: list[str] = []
        try:
            target = _to_smali_class(class_name)
            for m in self.analysis.get_methods():
                mobj = m.get_method()
                if mobj is None:
                    continue
                if target not in str(mobj.get_class_name()):
                    continue
                if method_name and method_name not in str(mobj.get_name()):
                    continue
                try:
                    snippets.append(mobj.get_source() or "")
                except Exception:
                    try:
                        snippets.append("\n".join(str(i) for i in mobj.get_instructions()))
                    except Exception:
                        continue
                if len(snippets) >= 8:
                    break
        except Exception:
            logger.debug("smali fetch failed for %s", class_name, exc_info=True)
        return "\n\n".join(s for s in snippets if s)[:8000]


def _to_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_list(getter) -> list[str]:
    try:
        return list(getter() or [])
    except Exception:
        return []


def _manifest_tag(kind: str) -> str:
    return {"activity": "activity", "service": "service",
            "receiver": "receiver", "provider": "provider"}[kind]


def kind_plural(kind: str) -> str:
    return {"activity": "activities", "service": "services",
            "receiver": "receivers", "provider": "providers"}[kind]


def _to_smali_class(class_name: str) -> str:
    """com.x.SmsRx -> Lcom/x/SmsRx; (best-effort match substring)."""
    if class_name.startswith("L") and class_name.endswith(";"):
        return class_name
    return "L" + class_name.replace(".", "/")


def extract(apk_path: str) -> dict[str, Any]:
    """Convenience: parse and return compact metadata JSON."""
    return ApkExtractor(apk_path).parse()
