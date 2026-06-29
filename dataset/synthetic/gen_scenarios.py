"""
VaultAgent synthetic scenario generator — high-signal forensic training data.

Produces diverse, evidence-backed Android malware forensic scenarios and writes
the four JSONL splits that the training pipeline consumes, in the exact formats it
expects:

  dataset/splits/sft_train.jsonl    {"text": <prompt + full 3-stage ideal report>}
  dataset/splits/sft_eval.jsonl     {"text": ...}
  dataset/splits/grpo_prompts.jsonl {"prompt": <prompt incl. GROUND_TRUTH block>}
  dataset/splits/dpo_pairs.jsonl    {"prompt", "chosen", "rejected"}

Quality features that make this "best of the best" for a small local model:
  * 12 malware archetypes + benign controls + HARD negatives (scary-but-justified
    permission so the model learns NOT to over-flag).
  * Real smali snippets per behavior so the Reverse Engineer stage trains on code.
  * Hardcoded C2 IPs/URLs and obfuscation markers as concrete evidence.
  * Randomized package names, app labels, benign permission noise, and C2 endpoints
    so the model generalizes instead of memorizing.
  * SFT targets teach the FULL pipeline: Static JSON → Reverse JSON → Verdict JSON.
  * Every GRPO prompt embeds GROUND_TRUTH:{...} parsed by train.production_reward.

Run:  python dataset/synthetic/gen_scenarios.py [--count 360]
"""

from __future__ import annotations

import argparse
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SPLITS = os.path.abspath(os.path.join(HERE, "..", "splits"))

# ── randomized vocab for generalization ──
APP_NAMES = [
    "Flashlight Pro", "QR Scanner", "Battery Saver", "Photo Editor", "PDF Reader",
    "Weather Now", "Wallpaper HD", "Voice Recorder", "File Manager", "Music Player",
    "Step Counter", "Notes Plus", "Calculator+", "VPN Lite", "Cleaner Max",
    "Game Booster", "Call Recorder", "Screen Mirror", "Fast Charger", "Translate Go",
]
BENIGN_NOISE = [
    "ACCESS_NETWORK_STATE", "VIBRATE", "WAKE_LOCK", "FOREGROUND_SERVICE",
    "RECEIVE_BOOT_COMPLETED", "POST_NOTIFICATIONS", "BLUETOOTH",
]
C2_HOSTS = ["192.0.2.10", "198.51.100.7", "203.0.113.55", "192.0.2.200", "198.51.100.99",
            "203.0.113.12", "192.0.2.77", "198.51.100.231"]
C2_PATHS = ["/gate", "/api/upload", "/c2/poll", "/bot/report", "/track", "/x.php"]

# ── smali snippet templates keyed by behavior ──
SMALI = {
    "sms_intercept": (
        ".method public onReceive(Landroid/content/Context;Landroid/content/Intent;)V\n"
        "    invoke-static {p2}, Landroid/provider/Telephony$Sms$Intents;->getMessagesFromIntent(...)\n"
        "    invoke-virtual {v0}, Landroid/telephony/SmsMessage;->getMessageBody()Ljava/lang/String;\n"
        "    # forward SMS body over HTTP\n"
        "    invoke-virtual {vHttp, vBody}, Lcom/x/Net;->post(Ljava/lang/String;)V\n"
        ".end method"
    ),
    "overlay": (
        ".method private showFakeLogin()V\n"
        "    new-instance v0, Landroid/view/WindowManager$LayoutParams;\n"
        "    const v1, 0x7f7  # TYPE_APPLICATION_OVERLAY\n"
        "    invoke-virtual {vWM, vView, v0}, Landroid/view/WindowManager;->addView(...)\n"
        "    # capture typed credentials and exfiltrate\n"
        ".end method"
    ),
    "accessibility": (
        ".method public onAccessibilityEvent(Landroid/view/accessibility/AccessibilityEvent;)V\n"
        "    invoke-virtual {p1}, ...;->getSource()Landroid/view/accessibility/AccessibilityNodeInfo;\n"
        "    invoke-virtual {vNode}, ...;->getText()Ljava/lang/CharSequence;  # scrape UI text\n"
        ".end method"
    ),
    "exfil": (
        ".method private uploadContacts()V\n"
        "    invoke-virtual {vCR, vUri}, Landroid/content/ContentResolver;->query(...)\n"
        "    invoke-virtual {vHttp, vJson}, Lcom/x/Net;->post(Ljava/lang/String;)V\n"
        ".end method"
    ),
    "dropper": (
        ".method private installPayload()V\n"
        "    invoke-virtual {vDl, vUrl}, Lcom/x/Dl;->download(Ljava/lang/String;)Ljava/io/File;\n"
        "    const-string v1, \"application/vnd.android.package-archive\"\n"
        "    invoke-virtual {vIntent}, Landroid/content/Intent;->setDataAndType(...)\n"
        ".end method"
    ),
    "obfuscation": (
        ".method private decrypt([B)[B\n"
        "    # XOR + base64 string deobfuscation at runtime\n"
        "    invoke-static {vEnc}, Landroid/util/Base64;->decode([BI)[B\n"
        "    invoke-static {vDec}, Ldalvik/system/DexClassLoader;-><init>(...)  # dynamic load\n"
        ".end method"
    ),
    "benign": (
        ".method public onCreate(Landroid/os/Bundle;)V\n"
        "    invoke-super {p0, p1}, Landroidx/appcompat/app/AppCompatActivity;->onCreate(...)\n"
        "    const v0, 0x7f0b001c\n"
        "    invoke-virtual {p0, v0}, ...;->setContentView(I)V\n"
        ".end method"
    ),
}

# ── archetypes: family, perms, flags, level, components, behaviors, smali keys ──
ARCHETYPES = [
    dict(family="SMS-Stealer", level="THREAT_HIGH",
         perms=["RECEIVE_SMS", "READ_SMS", "INTERNET"],
         flags=["FLAG_SMS_THEFT", "FLAG_C2"],
         comps=[("receiver", ".SmsRx")], c2=True, smali=["sms_intercept"],
         behaviors=["otp_interception", "data_exfiltration"],
         note="Intercepts SMS in SmsRx.onReceive and POSTs OTP codes to a hardcoded C2."),
    dict(family="Banking-Overlay", level="THREAT_HIGH",
         perms=["SYSTEM_ALERT_WINDOW", "INTERNET", "READ_PHONE_STATE"],
         flags=["FLAG_OVERLAY_ATTACK", "FLAG_CREDENTIAL_STEALING", "FLAG_C2"],
         comps=[("service", ".OverlayService")], c2=True, smali=["overlay"],
         behaviors=["credential_theft", "overlay_phishing"],
         note="Draws a fake bank login overlay and exfiltrates typed credentials."),
    dict(family="Accessibility-Trojan", level="THREAT_HIGH",
         perms=["BIND_ACCESSIBILITY_SERVICE", "INTERNET", "SYSTEM_ALERT_WINDOW"],
         flags=["FLAG_SPYWARE", "FLAG_CREDENTIAL_STEALING", "FLAG_OBFUSCATION", "FLAG_C2"],
         comps=[("service", ".A11yService")], c2=True, smali=["accessibility", "obfuscation"],
         behaviors=["keylogging", "ui_scraping", "obfuscation"],
         note="Abuses accessibility service to scrape UI text/keystrokes; payload obfuscated."),
    dict(family="Stalkerware", level="THREAT_HIGH",
         perms=["RECORD_AUDIO", "ACCESS_FINE_LOCATION", "READ_CONTACTS", "INTERNET"],
         flags=["FLAG_SPYWARE", "FLAG_C2"],
         comps=[("service", ".TrackerService")], c2=True, smali=["exfil"],
         behaviors=["audio_capture", "location_tracking", "data_exfiltration"],
         note="Records audio, tracks GPS, harvests contacts and uploads to a remote server."),
    dict(family="Dropper", level="THREAT_MEDIUM",
         perms=["REQUEST_INSTALL_PACKAGES", "INTERNET", "WRITE_EXTERNAL_STORAGE"],
         flags=["FLAG_DROPPER", "FLAG_DYNAMIC_LOADING"],
         comps=[("receiver", ".UpdateRx")], c2=True, smali=["dropper", "obfuscation"],
         behaviors=["payload_download", "dynamic_loading"],
         note="Downloads a secondary payload and installs it via REQUEST_INSTALL_PACKAGES."),
    dict(family="Device-Admin-Abuser", level="THREAT_MEDIUM",
         perms=["BIND_DEVICE_ADMIN", "READ_CONTACTS", "INTERNET"],
         flags=["FLAG_DEVICE_ADMIN_ABUSE", "FLAG_SPYWARE"],
         comps=[("receiver", ".AdminRx")], c2=False, smali=["exfil"],
         behaviors=["persistence", "data_exfiltration"],
         note="Requests device-admin to resist removal while harvesting contacts."),
    dict(family="Spyware", level="THREAT_MEDIUM",
         perms=["READ_CONTACTS", "ACCESS_FINE_LOCATION", "INTERNET"],
         flags=["FLAG_SPYWARE"],
         comps=[("service", ".SyncService")], c2=False, smali=["exfil"],
         behaviors=["data_exfiltration"],
         note="Harvests contacts and precise location with network access."),
    dict(family="Adware", level="THREAT_LOW",
         perms=["INTERNET", "ACCESS_NETWORK_STATE"],
         flags=["FLAG_EXPORTED_SURFACE"],
         comps=[("activity", ".AdActivity")], c2=False, smali=["benign"],
         behaviors=["aggressive_ads"],
         note="Aggressive ad SDK with an exported activity but no exfiltration."),
    # ── benign controls ──
    dict(family="Unknown", level="THREAT_BENIGN",
         perms=["INTERNET", "VIBRATE", "ACCESS_NETWORK_STATE"],
         flags=[], comps=[("activity", ".MainActivity")], c2=False, smali=["benign"],
         behaviors=[], note="Legitimate utility app. No dangerous combination."),
    dict(family="Unknown", level="THREAT_BENIGN",
         perms=["CAMERA", "INTERNET"],
         flags=[], comps=[("activity", ".ScanActivity")], c2=False, smali=["benign"],
         behaviors=[], note="QR scanner: CAMERA is justified by core function; no exfiltration."),
    # ── HARD negatives: one scary permission but justified, must stay LOW/BENIGN ──
    dict(family="Unknown", level="THREAT_LOW",
         perms=["ACCESS_FINE_LOCATION", "INTERNET"],
         flags=[], comps=[("activity", ".MapActivity")], c2=False, smali=["benign"],
         behaviors=[], note="Weather/maps app: location justified, no contacts/SMS, no C2."),
    dict(family="Unknown", level="THREAT_LOW",
         perms=["RECORD_AUDIO"],
         flags=[], comps=[("activity", ".RecActivity")], c2=False, smali=["benign"],
         behaviors=[], note="Voice recorder: RECORD_AUDIO justified, NO INTERNET so cannot exfiltrate."),
]


def rand_pkg(name: str, idx: int) -> str:
    base = name.split()[0].lower()
    return f"com.{base}.{random.choice(['app','lite','pro','go'])}{idx}"


def make_metadata(arc: dict, idx: int) -> dict:
    name = random.choice(APP_NAMES)
    pkg = rand_pkg(name, idx)
    perms = list(arc["perms"])
    # add 0-2 benign noise permissions for realism
    for _ in range(random.randint(0, 2)):
        p = random.choice(BENIGN_NOISE)
        if p not in perms:
            perms.append(p)
    random.shuffle(perms)
    ips, urls = [], []
    if arc["c2"]:
        host = random.choice(C2_HOSTS)
        ips = [host]
        urls = [f"http://{host}{random.choice(C2_PATHS)}"]
    return {
        "package": pkg,
        "app_label": name,
        "permissions": perms,
        "exported_components": [{"type": t, "name": pkg + n} for t, n in arc["comps"]],
        "ips": ips,
        "urls": urls,
        "smali": "\n\n".join(SMALI[k] for k in arc["smali"]),
    }


def score_for(level: str) -> int:
    return {"THREAT_HIGH": random.randint(82, 95),
            "THREAT_MEDIUM": random.randint(50, 68),
            "THREAT_LOW": random.randint(16, 30),
            "THREAT_BENIGN": random.randint(2, 10)}[level]


def dangerous(perms: list[str]) -> list[str]:
    DANGER = {"RECEIVE_SMS", "READ_SMS", "SEND_SMS", "READ_CONTACTS", "RECORD_AUDIO",
              "CAMERA", "ACCESS_FINE_LOCATION", "READ_PHONE_STATE", "BIND_DEVICE_ADMIN",
              "BIND_ACCESSIBILITY_SERVICE", "SYSTEM_ALERT_WINDOW", "REQUEST_INSTALL_PACKAGES",
              "WRITE_EXTERNAL_STORAGE", "GET_ACCOUNTS"}
    return [p for p in perms if p in DANGER]


def build_prompt(meta: dict, with_ground_truth: bool, arc: dict) -> str:
    perms = ", ".join(meta["permissions"])
    comps = "; ".join(f"{c['type']}={c['name'].rsplit('.',1)[-1]} (exported)"
                      for c in meta["exported_components"])
    ips = ", ".join(meta["ips"]) or "none"
    p = (
        "You are the VaultAgent malware forensics swarm. Analyze this APK and output "
        "three JSON objects: a Static report, a Reverse-engineering report, and a final "
        "Verdict, then one M2M line.\n\n"
        f"APP: {meta['app_label']}\nPACKAGE: {meta['package']}\n"
        f"PERMISSIONS: {perms}\nEXPORTED_COMPONENTS: {comps}\n"
        f"HARDCODED_IPS: {ips}\n\nREQUESTED_CODE:\n{meta['smali']}\n"
    )
    if with_ground_truth:
        gt = {"flags": arc["flags"], "permissions": arc["perms"],
              "family": arc["family"], "threat_level": arc["level"]}
        p += "\nGROUND_TRUTH: " + json.dumps(gt)
    return p


def ideal_report(meta: dict, arc: dict) -> str:
    score = score_for(arc["level"])
    static = {
        "stage": "static",
        "package": meta["package"],
        "permissions_dangerous": dangerous(meta["permissions"]),
        "exported_components": [{"type": c["type"], "name": c["name"].rsplit(".", 1)[-1],
                                 "permission": None} for c in meta["exported_components"]],
        "suspicious_combos": _combos(arc),
        "urls": meta["urls"], "ips": meta["ips"],
        "code_requests": [c["name"] for c in meta["exported_components"]],
        "flags": [f for f in arc["flags"] if f != "FLAG_C2"],
    }
    reverse = {
        "stage": "reverse",
        "behaviors": arc["behaviors"],
        "evidence": [{"flag": f, "where": meta["exported_components"][0]["name"].rsplit(".", 1)[-1]
                      if meta["exported_components"] else "code",
                      "detail": arc["note"]} for f in arc["flags"]],
        "obfuscation": "obfuscation" in arc["smali"],
        "flags": arc["flags"],
    }
    verdict = {
        "stage": "verdict", "threat_score": score, "threat_level": arc["level"],
        "malware_family": arc["family"], "indicators": arc["flags"],
        "evidence": [arc["note"]],
        "rca": f"Root cause: {arc['note']}" if arc["flags"] else "No malicious combination detected; benign.",
        "mitigation": (["Uninstall immediately", "Revoke dangerous permissions"]
                       + (["Block the hardcoded C2 endpoints"] if arc["c2"] else []))
                      if arc["flags"] else ["No action required"],
        "eta": "ETA_10s",
    }
    m2m = "VERDICT | {} | {} | {}".format(
        arc["level"], arc["family"], " ".join(arc["flags"]) or "NO_FLAGS")
    return (json.dumps(static) + "\n" + json.dumps(reverse) + "\n"
            + json.dumps(verdict) + "\n" + m2m)


def _combos(arc: dict) -> list[str]:
    perms = set(arc["perms"])
    out = []
    if {"RECEIVE_SMS", "INTERNET"} <= perms or {"READ_SMS", "INTERNET"} <= perms:
        out.append("INTERNET+RECEIVE_SMS")
    if {"SYSTEM_ALERT_WINDOW", "INTERNET"} <= perms:
        out.append("INTERNET+SYSTEM_ALERT_WINDOW")
    if {"BIND_ACCESSIBILITY_SERVICE", "INTERNET"} <= perms:
        out.append("BIND_ACCESSIBILITY_SERVICE+INTERNET")
    return out


def weak_answer(arc: dict) -> str:
    """Deliberately poor answer for DPO 'rejected': wrong level, no evidence, no JSON discipline."""
    return ("This app might be okay. It probably is safe.\n"
            + json.dumps({"stage": "verdict", "threat_score": 5,
                          "threat_level": "THREAT_BENIGN", "malware_family": "Unknown",
                          "indicators": [], "evidence": [], "rca": "Looks fine.",
                          "mitigation": [], "eta": "ETA_10s"}))


def write_jsonl(path: str, rows: list):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=360, help="total scenarios (≥100)")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()
    random.seed(args.seed)

    os.makedirs(SPLITS, exist_ok=True)
    sft, grpo, dpo = [], [], []

    for idx in range(args.count):
        arc = ARCHETYPES[idx % len(ARCHETYPES)]
        meta = make_metadata(arc, idx)
        report = ideal_report(meta, arc)

        sft.append({"text": build_prompt(meta, False, arc) + "\n\nANSWER:\n" + report})
        grpo.append({"prompt": build_prompt(meta, True, arc)})
        dpo.append({"prompt": build_prompt(meta, False, arc),
                    "chosen": report, "rejected": weak_answer(arc)})

    random.shuffle(sft)
    split = max(1, int(len(sft) * 0.1))
    sft_eval, sft_train = sft[:split], sft[split:]

    write_jsonl(os.path.join(SPLITS, "sft_train.jsonl"), sft_train)
    write_jsonl(os.path.join(SPLITS, "sft_eval.jsonl"), sft_eval)
    write_jsonl(os.path.join(SPLITS, "grpo_prompts.jsonl"), grpo)
    write_jsonl(os.path.join(SPLITS, "dpo_pairs.jsonl"), dpo)

    # quick class balance report
    from collections import Counter
    levels = Counter(ARCHETYPES[i % len(ARCHETYPES)]["level"] for i in range(args.count))
    print(f"Wrote splits to {SPLITS}")
    print(f"  sft_train={len(sft_train)} sft_eval={len(sft_eval)} grpo={len(grpo)} dpo={len(dpo)}")
    print(f"  level balance: {dict(levels)}")


if __name__ == "__main__":
    main()
