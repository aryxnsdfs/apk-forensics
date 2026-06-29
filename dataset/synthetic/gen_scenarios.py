"""
VaultAgent synthetic scenario generator.

Produces 100-150 offline Android malware forensic scenarios and writes the four
JSONL splits that train.py already loads, in the exact formats it expects:

  dataset/splits/sft_train.jsonl    {"text": <prompt + ideal JSON answer>}
  dataset/splits/sft_eval.jsonl     {"text": ...}
  dataset/splits/grpo_prompts.jsonl {"prompt": <prompt incl. GROUND_TRUTH block>}
  dataset/splits/dpo_pairs.jsonl    {"prompt", "chosen", "rejected"}

Every scenario embeds a GROUND_TRUTH:{...} block the GRPO reward function parses
(see train.production_reward). No network, no real APKs — fully synthetic.

Run:  python dataset/synthetic/gen_scenarios.py
"""

from __future__ import annotations

import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SPLITS = os.path.abspath(os.path.join(HERE, "..", "splits"))

random.seed(1337)

# ── Malware archetypes: (family, perms, flags, level, behavior blurb) ──
ARCHETYPES = [
    {
        "family": "SMS-Stealer",
        "perms": ["RECEIVE_SMS", "READ_SMS", "INTERNET"],
        "flags": ["FLAG_SMS_THEFT", "FLAG_C2"],
        "level": "THREAT_HIGH",
        "components": [("receiver", ".SmsRx")],
        "ips": ["192.0.2.10"],
        "behavior": "Intercepts incoming SMS in SmsRx.onReceive and POSTs OTP codes to a hardcoded C2.",
    },
    {
        "family": "Banking-Overlay",
        "perms": ["SYSTEM_ALERT_WINDOW", "INTERNET", "READ_PHONE_STATE"],
        "flags": ["FLAG_OVERLAY_ATTACK", "FLAG_CREDENTIAL_STEALING"],
        "level": "THREAT_HIGH",
        "components": [("service", ".OverlayService")],
        "ips": ["198.51.100.7"],
        "behavior": "Draws a fake login overlay over banking apps and exfiltrates typed credentials.",
    },
    {
        "family": "Spyware-Stalkerware",
        "perms": ["RECORD_AUDIO", "ACCESS_FINE_LOCATION", "READ_CONTACTS", "INTERNET"],
        "flags": ["FLAG_SPYWARE", "FLAG_C2"],
        "level": "THREAT_HIGH",
        "components": [("service", ".TrackerService")],
        "ips": ["203.0.113.55"],
        "behavior": "Records audio, tracks GPS, harvests contacts and uploads to a remote server.",
    },
    {
        "family": "Accessibility-Trojan",
        "perms": ["BIND_ACCESSIBILITY_SERVICE", "INTERNET", "SYSTEM_ALERT_WINDOW"],
        "flags": ["FLAG_SPYWARE", "FLAG_OVERLAY_ATTACK", "FLAG_CREDENTIAL_STEALING"],
        "level": "THREAT_HIGH",
        "components": [("service", ".A11yService")],
        "ips": ["192.0.2.200"],
        "behavior": "Abuses accessibility service to scrape UI text and capture keystrokes.",
    },
    {
        "family": "Dropper",
        "perms": ["REQUEST_INSTALL_PACKAGES", "INTERNET", "WRITE_EXTERNAL_STORAGE"],
        "flags": ["FLAG_DROPPER", "FLAG_DYNAMIC_LOADING"],
        "level": "THREAT_MEDIUM",
        "components": [("receiver", ".UpdateRx")],
        "ips": ["198.51.100.99"],
        "behavior": "Downloads a secondary payload and installs it via REQUEST_INSTALL_PACKAGES.",
    },
    {
        "family": "Device-Admin-Abuser",
        "perms": ["BIND_DEVICE_ADMIN", "READ_CONTACTS", "INTERNET"],
        "flags": ["FLAG_DEVICE_ADMIN_ABUSE", "FLAG_SPYWARE"],
        "level": "THREAT_MEDIUM",
        "components": [("receiver", ".AdminRx")],
        "ips": [],
        "behavior": "Requests device-admin to resist removal while harvesting contacts.",
    },
    {
        "family": "Adware",
        "perms": ["INTERNET", "ACCESS_NETWORK_STATE"],
        "flags": ["FLAG_EXPORTED_SURFACE"],
        "level": "THREAT_LOW",
        "components": [("activity", ".AdActivity")],
        "ips": [],
        "behavior": "Aggressive ad SDK with an exported activity but no exfiltration.",
    },
    {
        "family": "Unknown",  # benign control
        "perms": ["INTERNET", "VIBRATE", "ACCESS_NETWORK_STATE"],
        "flags": [],
        "level": "THREAT_BENIGN",
        "components": [("activity", ".MainActivity")],
        "ips": [],
        "behavior": "Legitimate flashlight/utility app. No dangerous combination present.",
    },
]

APP_NAMES = [
    "Flashlight Pro", "QR Scanner", "Battery Saver", "Photo Editor", "PDF Reader",
    "Weather Now", "Wallpaper HD", "Voice Recorder", "File Manager", "Music Player",
    "Step Counter", "Notes Plus", "Calculator+", "VPN Lite", "Cleaner Max",
]


def make_metadata(arc: dict, idx: int) -> dict:
    name = random.choice(APP_NAMES)
    pkg = f"com.{name.split()[0].lower()}.app{idx}"
    return {
        "package": pkg,
        "app_label": name,
        "permissions": arc["perms"],
        "exported_components": [{"type": t, "name": pkg + n} for t, n in arc["components"]],
        "ips": arc["ips"],
        "urls": [f"http://{ip}/gate" for ip in arc["ips"]],
    }


def build_prompt(meta: dict, arc: dict, with_ground_truth: bool) -> str:
    perms = ", ".join(meta["permissions"])
    comps = "; ".join(f"{c['type']}={c['name'].rsplit('.',1)[-1]} (exported)"
                      for c in meta["exported_components"])
    ips = ", ".join(meta["ips"]) or "none"
    p = (
        "You are the VaultAgent malware forensics swarm. Analyze this APK metadata "
        "and output a verdict JSON {threat_score, threat_level, malware_family, "
        "indicators[], evidence[], rca, mitigation[]} then an M2M line.\n\n"
        f"APP: {meta['app_label']}\nPACKAGE: {meta['package']}\n"
        f"PERMISSIONS: {perms}\nEXPORTED_COMPONENTS: {comps}\n"
        f"HARDCODED_IPS: {ips}\n\nTASK: Determine malware behavior, threat level, and RCA."
    )
    if with_ground_truth:
        gt = {
            "flags": arc["flags"],
            "permissions": arc["perms"],
            "family": arc["family"],
            "threat_level": arc["level"],
        }
        p += "\n\nGROUND_TRUTH: " + json.dumps(gt)
    return p


def ideal_answer(meta: dict, arc: dict) -> str:
    score = {"THREAT_HIGH": 88, "THREAT_MEDIUM": 55, "THREAT_LOW": 25, "THREAT_BENIGN": 5}[arc["level"]]
    verdict = {
        "stage": "verdict",
        "threat_score": score,
        "threat_level": arc["level"],
        "malware_family": arc["family"],
        "indicators": arc["flags"],
        "evidence": [arc["behavior"]],
        "rca": f"Root cause: {arc['behavior']}",
        "mitigation": (["Uninstall immediately", "Revoke dangerous permissions"]
                       if arc["flags"] else ["No action required"]),
        "eta": "ETA_10s",
    }
    m2m = "VERDICT | {} | {} | {}".format(
        arc["level"], arc["family"], " ".join(arc["flags"]) or "NO_FLAGS")
    return json.dumps(verdict) + "\n" + m2m


def weak_answer(arc: dict) -> str:
    """A deliberately poor answer for DPO 'rejected' — wrong level, no evidence."""
    bad = {
        "stage": "verdict",
        "threat_score": 5,
        "threat_level": "THREAT_BENIGN",
        "malware_family": "Unknown",
        "indicators": [],
        "evidence": [],
        "rca": "Looks fine.",
        "mitigation": [],
        "eta": "ETA_10s",
    }
    return json.dumps(bad)


def write_jsonl(path: str, rows: list):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main():
    os.makedirs(SPLITS, exist_ok=True)
    n_total = 130  # within the 100-150 target
    sft, grpo, dpo = [], [], []

    for idx in range(n_total):
        arc = ARCHETYPES[idx % len(ARCHETYPES)]
        meta = make_metadata(arc, idx)

        # SFT: full prompt + ideal answer concatenated as one text field.
        sft_prompt = build_prompt(meta, arc, with_ground_truth=False)
        sft.append({"text": sft_prompt + "\n\nANSWER:\n" + ideal_answer(meta, arc)})

        # GRPO: prompt only, with GROUND_TRUTH block for the reward function.
        grpo.append({"prompt": build_prompt(meta, arc, with_ground_truth=True)})

        # DPO: chosen (ideal) vs rejected (weak).
        dpo.append({
            "prompt": sft_prompt,
            "chosen": ideal_answer(meta, arc),
            "rejected": weak_answer(arc),
        })

    random.shuffle(sft)
    split = max(1, int(len(sft) * 0.1))
    sft_eval, sft_train = sft[:split], sft[split:]

    write_jsonl(os.path.join(SPLITS, "sft_train.jsonl"), sft_train)
    write_jsonl(os.path.join(SPLITS, "sft_eval.jsonl"), sft_eval)
    write_jsonl(os.path.join(SPLITS, "grpo_prompts.jsonl"), grpo)
    write_jsonl(os.path.join(SPLITS, "dpo_pairs.jsonl"), dpo)

    print(f"Wrote splits to {SPLITS}")
    print(f"  sft_train={len(sft_train)} sft_eval={len(sft_eval)} "
          f"grpo={len(grpo)} dpo={len(dpo)} (total scenarios={n_total})")


if __name__ == "__main__":
    main()
