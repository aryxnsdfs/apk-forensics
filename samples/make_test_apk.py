"""
Build a SET of REAL, Androguard-parseable test APKs fully offline — no Android
SDK, no network. Each APK encodes a minimal binary AndroidManifest.xml (AXML)
with a different permission/component profile so VaultAgent produces a different
verdict for each.

Usage:  python samples/make_test_apk.py
Output: samples/*.apk  (one per spec below)

These are NOT real malware — they contain no executable payload, only a manifest
that trips the static heuristics. Safe to analyze.
"""

from __future__ import annotations

import os
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ANDROID_NS = "http://schemas.android.com/apk/res/android"


class StringPool:
    def __init__(self):
        self.strings: list[str] = []
        self.index: dict[str, int] = {}

    def add(self, s: str) -> int:
        if s not in self.index:
            self.index[s] = len(self.strings)
            self.strings.append(s)
        return self.index[s]

    def encode(self) -> bytes:
        offsets, data = [], bytearray()
        for s in self.strings:
            offsets.append(len(data))
            b = s.encode("utf-8")
            data += bytes([min(len(s), 0x7F), min(len(b), 0x7F)])
            data += b + b"\x00"
        while len(data) % 4:
            data.append(0)
        count = len(self.strings)
        header_size, offsets_size = 28, 4 * count
        strings_start = header_size + offsets_size
        chunk_size = strings_start + len(data)
        out = bytearray()
        out += struct.pack("<HH", 0x0001, header_size)
        out += struct.pack("<I", chunk_size)
        out += struct.pack("<I", count)
        out += struct.pack("<I", 0)
        out += struct.pack("<I", 0x00000100)  # UTF-8 flag
        out += struct.pack("<I", strings_start)
        out += struct.pack("<I", 0)
        for off in offsets:
            out += struct.pack("<I", off)
        out += data
        return bytes(out)


def _res_string(idx: int) -> bytes:
    return struct.pack("<HBBI", 8, 0, 0x03, idx)


def _chunk(ctype, header_size, body) -> bytes:
    line_comment = struct.pack("<iI", 1, 0xFFFFFFFF)
    size = 8 + len(line_comment) + len(body)
    return struct.pack("<HHI", ctype, header_size, size) + line_comment + body


def _start_ns(prefix, uri):
    return _chunk(0x0100, 0x10, struct.pack("<II", prefix, uri))


def _end_ns(prefix, uri):
    return _chunk(0x0101, 0x10, struct.pack("<II", prefix, uri))


def _start_el(ns_idx, name_idx, attrs):
    body = bytearray()
    body += struct.pack("<iI", ns_idx, name_idx)
    body += struct.pack("<HH", 0x14, 0x14)
    body += struct.pack("<H", len(attrs))
    body += struct.pack("<HHH", 0, 0, 0)
    for a_ns, a_name, a_val in attrs:
        body += struct.pack("<iI", a_ns, a_name)
        body += struct.pack("<i", a_val)
        body += _res_string(a_val)
    return _chunk(0x0102, 0x10, body)


def _end_el(ns_idx, name_idx):
    return _chunk(0x0103, 0x10, struct.pack("<iI", ns_idx, name_idx))


def build_axml(package: str, permissions: list[str], components: list[tuple[str, str]]) -> bytes:
    sp = StringPool()
    s_android = sp.add("android")
    s_ns = sp.add(ANDROID_NS)
    s_manifest = sp.add("manifest")
    s_package = sp.add("package")
    s_pkg_val = sp.add(package)
    s_uses = sp.add("uses-permission")
    s_name = sp.add("name")
    s_app = sp.add("application")
    s_exported = sp.add("exported")
    s_true = sp.add("true")
    perm_idx = [sp.add("android.permission." + p) for p in permissions]
    comp_tags = {t: sp.add(t) for t, _ in components}
    comp_val = [sp.add(package + n) for _, n in components]

    nodes = bytearray()
    nodes += _start_ns(s_android, s_ns)
    nodes += _start_el(-1, s_manifest, [(-1, s_package, s_pkg_val)])
    for p in perm_idx:
        nodes += _start_el(-1, s_uses, [(s_ns, s_name, p)])
        nodes += _end_el(-1, s_uses)
    nodes += _start_el(-1, s_app, [])
    for (ctype, _), cval in zip(components, comp_val):
        tag = comp_tags[ctype]
        nodes += _start_el(-1, tag, [(s_ns, s_name, cval), (s_ns, s_exported, s_true)])
        nodes += _end_el(-1, tag)
    nodes += _end_el(-1, s_app)
    nodes += _end_el(-1, s_manifest)
    nodes += _end_ns(s_android, s_ns)

    body = sp.encode() + nodes
    return struct.pack("<HHI", 0x0003, 8, 8 + len(body)) + body


def write_apk(filename, package, permissions, components, size_kb=0):
    axml = build_axml(package, permissions, components)
    path = os.path.join(HERE, filename)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("AndroidManifest.xml", axml)
        z.writestr("resources.arsc", b"\x02\x00\x0c\x00\x00\x00\x00\x00")
        z.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n\r\n")
        # Distinct, incompressible filler so each sample has a realistic, different
        # on-disk size (mimics classes.dex / resources / native libs).
        if size_kb:
            z.writestr(zipfile.ZipInfo("assets/filler.bin"), os.urandom(size_kb * 1024),
                       compress_type=zipfile.ZIP_STORED)
    return path


# ── 5 distinct samples (+ the original) ──
SPECS = [
    {
        "file": "test-sms-stealer.apk",
        "package": "com.vaultagent.smsstealer",
        "permissions": ["RECEIVE_SMS", "READ_SMS", "INTERNET"],
        "components": [("receiver", ".SmsRx")],
        "size_kb": 48,
        "what": "SMS/OTP Stealer — exported SMS receiver + INTERNET. Steals one-time passcodes.",
    },
    {
        "file": "test-banking-overlay.apk",
        "package": "com.vaultagent.bankoverlay",
        "permissions": ["SYSTEM_ALERT_WINDOW", "INTERNET", "READ_PHONE_STATE"],
        "components": [("service", ".OverlayService")],
        "size_kb": 71,
        "what": "Banking Overlay — draws fake login screens over apps to phish credentials.",
    },
    {
        "file": "test-spyware.apk",
        "package": "com.vaultagent.spyware",
        "permissions": ["RECORD_AUDIO", "ACCESS_FINE_LOCATION", "READ_CONTACTS", "INTERNET"],
        "components": [("service", ".TrackerService")],
        "size_kb": 96,
        "what": "Spyware/Stalkerware — records audio, tracks GPS, harvests contacts.",
    },
    {
        "file": "test-dropper.apk",
        "package": "com.vaultagent.dropper",
        "permissions": ["REQUEST_INSTALL_PACKAGES", "INTERNET", "WRITE_EXTERNAL_STORAGE"],
        "components": [("receiver", ".UpdateRx")],
        "size_kb": 33,
        "what": "Dropper — downloads and installs a second-stage payload.",
    },
    {
        "file": "test-benign.apk",
        "package": "com.vaultagent.flashlight",
        "permissions": ["CAMERA", "INTERNET", "VIBRATE"],
        "components": [("activity", ".MainActivity")],
        "size_kb": 12,
        "what": "Benign flashlight/QR app — CAMERA justified, no dangerous combo. Should score low.",
    },
]


def main():
    print("Building test APKs in", HERE, "\n")
    for spec in SPECS:
        path = write_apk(spec["file"], spec["package"], spec["permissions"],
                         spec["components"], spec.get("size_kb", 0))
        print(f"  {spec['file']:30s} {os.path.getsize(path) // 1024:>4d} KB  — {spec['what']}")
    print("\nUpload any of these via the dashboard to see different verdicts.")


if __name__ == "__main__":
    main()
