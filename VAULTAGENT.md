# VaultAgent — Offline Android Malware Forensic Platform

VaultAgent repurposes the **Swarm-OS** multi-agent infrastructure into a fully
**offline / air-gapped** static APK malware analysis engine. No cloud APIs, no
internet dependency — the local quantized GGUF model, the GRPO training pipeline,
and the React dashboard are all reused. Only the *domain* changed: from
infrastructure/Docker troubleshooting to Android malware forensics.

> The original Swarm-OS GRPO training loops, model-inference logic, and Vite/React
> config are intentionally preserved. See [BLOG.md](BLOG.md) / [README.md](README.md)
> for the original system.

## Pipeline

```
APK upload → Androguard extract → compact JSON metadata
  → Stage 1  Static Analyst    (DETECTIVE)  manifest, permissions, components, URLs/IPs
  → Stage 2  Reverse Engineer  (CODER)      requested smali only: OTP/credential/C2/obfuscation
  → Stage 3  Chief Security Officer (COMMANDER)  threat score + family + RCA + mitigation
  → Attack-path DAG → Dashboard report (JSON + human-readable RCA)
```

The LLM never reads the whole APK — the extractor emits a lightweight JSON and the
Reverse Engineer fetches only the specific methods the Static Analyst flagged.

## Agent mapping (keys preserved for backend wiring)

| Swarm-OS key | VaultAgent persona | Responsibility |
|---|---|---|
| `COMMANDER` | Chief Security Officer | final verdict, threat approval, RCA |
| `DETECTIVE` | Static Analyst | manifest / permissions / components / URLs / IPs |
| `CODER` | Reverse Engineer | smali behavior: OTP, credential theft, C2, obfuscation |
| `THREAT_INTEL` | Threat Intel (optional) | offline signature + family match |

## Key files

- [backend/engine/apk_extractor.py](backend/engine/apk_extractor.py) — Androguard → JSON, lazy smali access
- [backend/engine/apk_features.py](backend/engine/apk_features.py) — rule-based threat seed + flag vocabulary
- [backend/schemas/forensic.py](backend/schemas/forensic.py) — Static / Reverse / Verdict JSON schemas
- [backend/agents/orchestrator.py](backend/agents/orchestrator.py) — repurposed `SYSTEM_PROMPTS`
- [backend/engine/rewards.py](backend/engine/rewards.py) — forensic reward methods
- [backend/main.py](backend/main.py) — `POST /api/analyze` pipeline + malware DEMO_MODE storyline
- [swarm_openenv_env/tasks.py](swarm_openenv_env/tasks.py) — malware OpenEnv tasks
- [train.py](train.py) — `production_reward` rewritten for malware (loops untouched)
- [dataset/synthetic/gen_scenarios.py](dataset/synthetic/gen_scenarios.py) — 130 synthetic scenarios

## Flag vocabulary

`FLAG_SMS_THEFT` · `FLAG_CREDENTIAL_STEALING` · `FLAG_C2` · `FLAG_SPYWARE` ·
`FLAG_DEVICE_ADMIN_ABUSE` · `FLAG_OVERLAY_ATTACK` · `FLAG_OBFUSCATION` ·
`FLAG_DYNAMIC_LOADING` · `FLAG_EXPORTED_SURFACE` · `FLAG_DROPPER`

Threat levels: `THREAT_BENIGN` < `THREAT_LOW` < `THREAT_MEDIUM` < `THREAT_HIGH`.

## Run

```bash
pip install -r backend/requirements.txt          # includes androguard (pure-Python)
python dataset/synthetic/gen_scenarios.py         # → dataset/splits/*.jsonl (130 scenarios)

# Backend
cd backend && uvicorn main:app --port 8000
# Frontend
cd frontend && npm install && npm run dev

# Analyze an APK (also available via the dashboard "Upload APK" button)
curl -F file=@samples/test.apk http://localhost:8000/api/analyze
```

`DEMO_MODE=True` (in [backend/main.py](backend/main.py)) plays a scripted malware
storyline with no LLM loaded. With a local GGUF model served on `:1234`
(LM Studio / llama.cpp), agents produce real reasoning; otherwise the heuristic
stub keeps the dashboard populated.

## Training (offline)

The GRPO/SFT/DPO pipeline in [train.py](train.py) is unchanged except the reward.
`production_reward` rewards correct flag detection, evidence-backed conclusions,
correct family, and valid JSON; it penalizes hallucinated permissions (not in the
scenario manifest), wrong classification, and missed indicators. Ground truth is
embedded per-prompt as a `GROUND_TRUTH:{...}` block by the scenario generator.

## Status

Backbone + stubs: real Androguard extraction and heuristic scoring; agent
reasoning uses the local model when available, deterministic stubs otherwise.
Deferred: real Drebin/CIC dataset loaders, apktool/JDK, a full LLM retraining run.
