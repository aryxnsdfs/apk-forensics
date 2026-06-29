"""
Build a REAL, Androguard-parseable test APK fully offline — no Android SDK, no
network. Encodes a minimal binary AndroidManifest.xml (AXML) describing a fake
'SMS-Stealer' style app and zips it into an .apk.

Usage:  python samples/make_test_apk.py
Output: samples/test-sms-stealer.apk
"""

from __future__ import annotations

import os
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ANDROID_NS = "http://schemas.android.com/apk/res/android"

# ── manifest we want to encode ──
PACKAGE = "com.vaultagent.testsms"
PERMISSIONS = [
    "android.permission.RECEIVE_SMS",
    "android.permission.READ_SMS",
    "android.permission.INTERNET",
]
RECEIVER = ".SmsRx"
SMS_ACTION = "android.provider.Telephony.SMS_RECEIVED"


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
        # UTF-8 string pool (flags = UTF8_FLAG 0x100)
        offsets = []
        data = bytearray()
        for s in self.strings:
            offsets.append(len(data))
            b = s.encode("utf-8")
            n = len(b)
            # utf16 len then utf8 len (single byte each for <128)
            data += bytes([min(len(s), 0x7F), min(n, 0x7F)])
            data += b
            data += b"\x00"
        # pad string data to 4 bytes
        while len(data) % 4:
            data.append(0)

        string_count = len(self.strings)
        header_size = 28
        offsets_size = 4 * string_count
        strings_start = header_size + offsets_size
        chunk_size = strings_start + len(data)

        out = bytearray()
        out += struct.pack("<HH", 0x0001, header_size)      # type=STRING_POOL, headerSize
        out += struct.pack("<I", chunk_size)
        out += struct.pack("<I", string_count)
        out += struct.pack("<I", 0)                          # styleCount
        out += struct.pack("<I", 0x00000100)                 # flags = UTF8
        out += struct.pack("<I", strings_start)
        out += struct.pack("<I", 0)                          # stylesStart
        for off in offsets:
            out += struct.pack("<I", off)
        out += data
        return bytes(out)


def res_value_string(idx: int) -> bytes:
    # Res_value{ size=8, res0=0, dataType=STRING(0x03), data=idx }
    return struct.pack("<HBBI", 8, 0, 0x03, idx)


def start_namespace(prefix, uri) -> bytes:
    body = struct.pack("<II", prefix, uri)              # prefix, uri (string indices)
    return chunk(0x0100, 0x10, body)


def end_namespace(prefix, uri) -> bytes:
    body = struct.pack("<II", prefix, uri)
    return chunk(0x0101, 0x10, body)


def chunk(ctype, header_size, body) -> bytes:
    # generic: lineNo + comment(-1) live in the "header" for XML nodes
    line_comment = struct.pack("<iI", 1, 0xFFFFFFFF)
    size = 8 + len(line_comment) + len(body)
    return struct.pack("<HHI", ctype, header_size, size) + line_comment + body


def start_element(ns_idx, name_idx, attrs: list[tuple[int, int, int]]) -> bytes:
    # attrs: list of (ns_idx, name_idx, value_string_idx)
    body = bytearray()
    body += struct.pack("<iI", ns_idx, name_idx)        # ns, name
    body += struct.pack("<HH", 0x14, 0x14)              # attributeStart, attributeSize
    body += struct.pack("<H", len(attrs))               # attributeCount
    body += struct.pack("<HHH", 0, 0, 0)               # id, class, style index (none)
    for a_ns, a_name, a_val in attrs:
        body += struct.pack("<iI", a_ns, a_name)        # attr ns, name
        body += struct.pack("<i", a_val)                # rawValue = string idx
        body += res_value_string(a_val)                 # typed value (string)
    return chunk(0x0102, 0x10, body)


def end_element(ns_idx, name_idx) -> bytes:
    body = struct.pack("<iI", ns_idx, name_idx)
    return chunk(0x0103, 0x10, body)


def build_axml() -> bytes:
    sp = StringPool()
    # order does not matter; pool resolves by index
    s_android = sp.add("android")
    s_ns = sp.add(ANDROID_NS)
    s_manifest = sp.add("manifest")
    s_package = sp.add("package")
    s_pkg_val = sp.add(PACKAGE)
    s_uses = sp.add("uses-permission")
    s_name = sp.add("name")
    s_app = sp.add("application")
    s_receiver = sp.add("receiver")
    s_rx_val = sp.add(RECEIVER)
    s_exported = sp.add("exported")
    s_true = sp.add("true")
    s_intent = sp.add("intent-filter")
    s_action = sp.add("action")
    s_action_val = sp.add(SMS_ACTION)
    perm_idx = [sp.add(p) for p in PERMISSIONS]

    nodes = bytearray()
    nodes += start_namespace(s_android, s_ns)

    # <manifest package="...">  (package attr has NO namespace -> ns = -1)
    nodes += start_element(-1, s_manifest, [(-1, s_package, s_pkg_val)])

    # <uses-permission android:name="..."/>
    for p in perm_idx:
        nodes += start_element(-1, s_uses, [(s_ns, s_name, p)])
        nodes += end_element(-1, s_uses)

    # <application>
    nodes += start_element(-1, s_app, [])
    # <receiver android:name=".SmsRx" android:exported="true">
    nodes += start_element(-1, s_receiver, [
        (s_ns, s_name, s_rx_val),
        (s_ns, s_exported, s_true),
    ])
    # <intent-filter><action android:name="SMS_RECEIVED"/></intent-filter>
    nodes += start_element(-1, s_intent, [])
    nodes += start_element(-1, s_action, [(s_ns, s_name, s_action_val)])
    nodes += end_element(-1, s_action)
    nodes += end_element(-1, s_intent)
    nodes += end_element(-1, s_receiver)
    nodes += end_element(-1, s_app)

    nodes += end_element(-1, s_manifest)
    nodes += end_namespace(s_android, s_ns)

    pool = sp.encode()
    body = pool + nodes
    total = 8 + len(body)
    header = struct.pack("<HHI", 0x0003, 8, total)      # RES_XML_TYPE
    return header + body


def main():
    axml = build_axml()
    out = os.path.join(HERE, "test-sms-stealer.apk")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("AndroidManifest.xml", axml)
        # minimal placeholder so it looks like an app archive
        z.writestr("resources.arsc", b"\x02\x00\x0c\x00\x00\x00\x00\x00")
        z.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n\r\n")
    print("wrote", out, f"({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
