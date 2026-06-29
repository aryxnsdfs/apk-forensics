---
title: VaultAgent
emoji: "\U0001F6E1"
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: true
suggested_hardware: t4-small
---

<div align="center">

# 🛡️ VaultAgent

### Offline, Air-Gapped Android Malware Forensic Platform

**Static APK analysis · Multi-agent forensic reasoning · Threat scoring · Root Cause Analysis · Attack-path graphs**

No cloud APIs · No internet dependency · Everything runs locally

</div>

---

## What it is

VaultAgent analyzes Android `.apk` files for malware **entirely offline**. You upload an
APK; it is parsed locally with [Androguard](https://github.com/androguard/androguard) (pure
Python, no JDK), compressed into a lightweight JSON, and reasoned over by a sequential swarm
of local LLM agents. The output is a threat score, a malware-family classification, an
evidence-backed Root Cause Analysis (RCA), a visual attack-path graph, and a
machine-readable verdict — with **zero data leaving the machine**.

VaultAgent is a domain re-pivot of the **Swarm-OS** multi-agent engine. The local quantized
GGUF model, the GRPO/SFT/DPO training pipeline, the FastAPI + WebSocket backend, the
causal-DAG → RCA engine, and the React/Vite dashboard are all **reused unchanged** — only the
problem domain moved from infrastructure troubleshooting to APK malware forensics.

---

## Pipeline

```
APK upload
   │
   ▼
APK Extractor (Androguard)  ──►  compact JSON metadata  +  lazy smali access
   │
   ▼
Stage 1 · Static Analyst      manifest · permissions · exported components · URLs · IPs
   │                          → flags dangerous perms + suspicious combos
   │                          → requests only the code worth reviewing
   ▼
Stage 2 · Reverse Engineer    requested smali ONLY (never the whole APK)
   │                          → OTP/SMS theft · credential theft · exfiltration
   │                          → obfuscation · dynamic loading · C2 comms
   ▼
Stage 3 · Chief Security Officer   threat score · malware family · indicators
   │                               → evidence · RCA · recommended mitigation
   ▼
Attack-path DAG  +  Dashboard report  (structured JSON  +  human-readable RCA)
```

The LLM **never reads the full APK**. The extractor emits a compact metadata JSON, and the
Reverse Engineer pulls only the specific methods the Static Analyst flagged — keeping the
model's context tight and inference cheap on low-end hardware.

---

## Multi-agent design

VaultAgent keeps Swarm-OS's orchestrator, spawn/dismiss machinery, System-Prompt Integrity
Gate, and per-agent model routing. The internal agent **keys** are preserved so all backend
wiring keeps working; only the personas changed:

| Internal key | Persona | Responsibility |
|---|---|---|
| `COMMANDER` | **Chief Security Officer** | final verdict, threat approval, RCA generation |
| `DETECTIVE` | **Static Analyst** | manifest, permissions, services, receivers, URLs, IPs |
| `CODER` | **Reverse Engineer** | smali/Java intent, OTP/credential/C2/obfuscation detection |
| `THREAT_INTEL` | **Threat Intel** *(optional)* | offline signature + malware-family match |

Agents hand off sequentially and emit compact machine-to-machine (M2M) tags, e.g.:

```
THREAT_HIGH | FLAG_SMS_THEFT | FLAG_CREDENTIAL_STEALING | FLAG_C2 | ETA_10s
```

When the Chief Security Officer and Static Analyst disagree, the orchestrator's
disagreement-detection forks the causal graph and forces a structured resolution — reused
directly from the original engine.

---

## Flag vocabulary & threat levels

Shared across the heuristics, the agents, and the GRPO reward function:

`FLAG_SMS_THEFT` · `FLAG_CREDENTIAL_STEALING` · `FLAG_C2` · `FLAG_SPYWARE` ·
`FLAG_DEVICE_ADMIN_ABUSE` · `FLAG_OVERLAY_ATTACK` · `FLAG_OBFUSCATION` ·
`FLAG_DYNAMIC_LOADING` · `FLAG_EXPORTED_SURFACE` · `FLAG_DROPPER`

Threat levels: `THREAT_BENIGN` < `THREAT_LOW` < `THREAT_MEDIUM` < `THREAT_HIGH` (score 0–100).

---

## Agent output schemas

**Stage 1 — Static Analyst**
```json
{ "stage": "static", "package": "com.x.flash",
  "permissions_dangerous": ["RECEIVE_SMS", "INTERNET"],
  "exported_components": [{ "type": "receiver", "name": ".SmsRx", "permission": null }],
  "suspicious_combos": ["INTERNET+RECEIVE_SMS"], "urls": [], "ips": ["192.0.2.10"],
  "code_requests": ["com.x.flash.SmsRx"], "flags": ["FLAG_SMS_THEFT", "FLAG_C2"] }
```

**Stage 2 — Reverse Engineer**
```json
{ "stage": "reverse", "behaviors": ["otp_interception", "data_exfiltration"],
  "evidence": [{ "flag": "FLAG_C2", "where": "SmsRx.onReceive", "detail": "POST to 192.0.2.10/gate" }],
  "obfuscation": false, "flags": ["FLAG_SMS_THEFT", "FLAG_C2"] }
```

**Stage 3 — Chief Security Officer (final verdict)**
```json
{ "stage": "verdict", "threat_score": 88, "threat_level": "THREAT_HIGH",
  "malware_family": "SMS-Stealer", "indicators": ["FLAG_SMS_THEFT", "FLAG_C2"],
  "evidence": ["SmsRx forwards OTP codes to a hardcoded C2"],
  "rca": "Root cause: exported SMS receiver + INTERNET enables OTP exfiltration to C2.",
  "mitigation": ["Uninstall the application", "Revoke the dangerous permissions",
                 "Block the hardcoded C2 endpoints", "Rotate OTP-protected credentials"],
  "eta": "ETA_10s" }
```

Attack-path DAG node types: `error` (malicious indicator) · `escalation` · `fix`
(mitigation) · `resolution` (verdict) · `fork` (agent disagreement).

---

## Repository layout

```
backend/
  engine/
    apk_extractor.py     Androguard wrapper → compact JSON; lazy smali fetch
    apk_features.py      rule-based threat seed: dangerous perms, suspicious combos, C2 hints
    rewards.py           forensic reward methods (flags, evidence, family, schema)
    causal_graph.py      attack-path DAG + RCA markdown (reused unchanged)
  agents/orchestrator.py repurposed SYSTEM_PROMPTS + integrity-gate probes
  schemas/forensic.py    Static / Reverse / Verdict pydantic + JSON schemas
  model/                 local GGUF inference + config (unchanged)
  main.py                POST /api/analyze pipeline + malware DEMO_MODE storyline
swarm_openenv_env/
  tasks.py, graders.py   malware OpenEnv tasks + flag-scoring rubrics
dataset/
  synthetic/gen_scenarios.py   generates 130 synthetic forensic scenarios
  splits/                      generated SFT/GRPO/DPO jsonl (gitignored)
train.py                 SFT → GRPO → DPO → merge/GGUF (loops intact; reward swapped)
frontend/src/            React dashboard (Vite) — agent relabels + APK upload control
VAULTAGENT.md            condensed design notes
```

---

## Quick start

```bash
# 1. Install (Androguard is pure-Python, no Java needed)
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# 2. (Optional) regenerate the synthetic training scenarios
python dataset/synthetic/gen_scenarios.py     # → dataset/splits/*.jsonl (130 scenarios)

# 3. Run the backend (FastAPI + WebSocket on :8000)
cd backend && uvicorn main:app --port 8000

# 4. Run the dashboard (Vite dev server on :5173)
cd frontend && npm run dev
```

Analyze an APK — via the dashboard **"Upload APK for Malware Analysis"** button, or the API:

```bash
curl -F file=@samples/your.apk http://localhost:8000/api/analyze
```

Results stream live to the dashboard over the existing WebSocket: agent chat, attack-path
DAG, reward feed, threat metrics, and the final RCA report.

---

## Running modes

| Mode | Behavior |
|---|---|
| **Local GGUF model** (LM Studio / llama.cpp on `:1234`) | Agents produce real reasoning from the local quantized model. |
| **Heuristic stub** (no model loaded) | Deterministic rule-based scoring still populates the full dashboard. |
| **`DEMO_MODE = True`** (in `backend/main.py`) | Scripted malware-analysis storyline — for demos with no model loaded. |

Every mode is fully offline. No request ever leaves the machine.

---

## Training (offline RL)

The three-stage pipeline in `train.py` — SFT cold-start → GRPO reinforcement → DPO preference
alignment → LoRA merge + GGUF export — is unchanged. Only the **reward function** was
rewritten for the malware domain:

**Rewards** correct permission→behavior reasoning, OTP/credential/C2 detection,
evidence-backed conclusions, correct family, and valid machine-readable JSON.
**Penalizes** hallucinated permissions (not in the scenario manifest), wrong
classification, and missed obvious indicators.

Ground truth is embedded per prompt as a `GROUND_TRUTH:{...}` block by the scenario
generator, so live inference and training share the exact same scoring logic.

```bash
python train.py --stage sft      # cold-start on ideal forensic reports
python train.py --stage grpo     # RL with the forensic reward
python train.py --stage dpo      # prefer evidence-backed over lazy verdicts
python train.py --stage merge    # merge LoRA → 16-bit → Q4_K_M GGUF
```

Model stack (unchanged): local GGUF · LoRA fine-tuning · 4-bit quantization · GRPO.

---

## Design principles

- **Offline & air-gapped** — Androguard, the GGUF model, and training all run locally.
- **Low compute** — the LLM sees compact JSON + targeted snippets, never the raw APK.
- **Modular** — extractor, heuristics, agents, schemas, and reward are independent units.
- **Reuse over rewrite** — the GRPO loops, model inference, and Vite/React config are intact.

---

## Status

**Backbone + stubs.** Real Androguard extraction and heuristic scoring are live; agent
reasoning uses the local model when available and falls back to deterministic stubs
otherwise. Deferred: real Drebin-215 / CIC-AndMal2017 / CIC-MalDroid2020 dataset loaders,
optional apktool/JDK decompilation, and a full LLM retraining run.

> Authorized security research / defensive use only. Analyze only APKs you have the right to inspect.
