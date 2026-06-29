# ═══════════════════════════════════════════════════════════════════════════
#  VaultAgent — Cloud Training Pipeline  (Colab / RunPod / Lambda / Vast.ai)
# ═══════════════════════════════════════════════════════════════════════════
#  Fine-tunes a local 8B model into an offline Android-malware forensic analyst:
#    Stage 1  SFT   — cold-start on full 3-stage ideal reports
#    Stage 2  GRPO  — RL with the forensic reward (train.production_reward)
#    Stage 3  DPO   — prefer evidence-backed verdicts over lazy ones
#    Export         — merge LoRA → 16-bit → GGUF (q4_k_m / q5_k_m / q8_0)
#
#  Reuses the SAME reward function the live inference path uses (single source of
#  truth in train.py), so training and serving agree. The trained GGUF runs fully
#  offline behind backend/model/inference.py — no cloud at inference.
#
#  ── One-cell cloud bootstrap (paste at top of a fresh Colab/RunPod cell) ──
#    !pip install -q "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
#    !pip install -q trl peft datasets jsonlines accelerate bitsandbytes
#    !git clone https://github.com/aryxnsdfs/apk-forensics && cd apk-forensics && \
#        python dataset/synthetic/gen_scenarios.py --count 360 && \
#        python train_cloud.py --stage all --push-gguf
#
#  ── Local / single GPU ──
#    python dataset/synthetic/gen_scenarios.py --count 360
#    python train_cloud.py --stage all
#
#  Hardware:
#    A100/H100 80GB → bf16, batch 4, 8 generations/prompt   (full quality, ~5-7h)
#    A10/4090 24GB  → fp16, batch 1-2, 4 generations/prompt  (auto-detected)
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(os.path.join(ROOT, "train_cloud.log"), mode="a", encoding="utf-8")],
)
log = logging.getLogger("vaultagent-train")

# ── Config (override via CLI / env) ──────────────────────────────────────────
DEFAULT_MODEL = os.getenv("VA_MODEL", "unsloth/llama-3.1-8b-instruct-bnb-4bit")
MAX_SEQ_LEN = int(os.getenv("VA_MAXSEQ", "2048"))
OUTPUT_DIR = os.path.join(ROOT, os.getenv("VA_OUTDIR", "vaultagent-trained"))
SPLITS_DIR = os.path.join(ROOT, "dataset", "splits")

SFT_TRAIN = os.path.join(SPLITS_DIR, "sft_train.jsonl")
SFT_EVAL = os.path.join(SPLITS_DIR, "sft_eval.jsonl")
GRPO_DATA = os.path.join(SPLITS_DIR, "grpo_prompts.jsonl")
DPO_DATA = os.path.join(SPLITS_DIR, "dpo_pairs.jsonl")

SFT_CKPT = os.path.join(OUTPUT_DIR, "stage1-sft")
GRPO_CKPT = os.path.join(OUTPUT_DIR, "stage2-grpo")
DPO_CKPT = os.path.join(OUTPUT_DIR, "stage3-dpo")
MERGED_DIR = os.path.join(OUTPUT_DIR, "final-merged")
GGUF_DIR = os.path.join(OUTPUT_DIR, "gguf")
REWARD_LOG = os.path.join(OUTPUT_DIR, "grpo_reward_log.jsonl")


# ── Hardware autodetect ──────────────────────────────────────────────────────
def detect_hardware():
    import torch
    if not torch.cuda.is_available():
        log.warning("No CUDA GPU detected — training will be extremely slow on CPU.")
        return dict(bf16=False, fp16=False, batch=1, accum=8, gens=2, vram_gb=0, name="cpu")
    name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_mem / 1024**3
    bf16 = torch.cuda.is_bf16_supported()
    big = vram_gb >= 70
    cfg = dict(
        bf16=bf16, fp16=not bf16,
        batch=4 if big else (2 if vram_gb >= 20 else 1),
        accum=4 if big else 8,
        gens=8 if big else 4,
        vram_gb=round(vram_gb, 1), name=name,
    )
    log.info("GPU: %s | VRAM %.1fGB | bf16=%s | batch=%d accum=%d gens/prompt=%d",
             name, vram_gb, bf16, cfg["batch"], cfg["accum"], cfg["gens"])
    return cfg


def ensure_data():
    if os.path.exists(GRPO_DATA) and os.path.exists(SFT_TRAIN):
        return
    log.info("Splits missing — generating synthetic forensic data...")
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "dataset", "synthetic", "gen_scenarios.py"),
                    "--count", os.getenv("VA_COUNT", "360")], check=True)


def load_jsonl(path):
    import jsonlines
    with jsonlines.open(path) as r:
        return list(r)


def load_model(hw, checkpoint=None):
    from unsloth import FastLanguageModel
    src = checkpoint if checkpoint and os.path.exists(checkpoint) else DEFAULT_MODEL
    log.info("Loading model: %s", src)
    model, tok = FastLanguageModel.from_pretrained(
        model_name=src, max_seq_length=MAX_SEQ_LEN, load_in_4bit=True, dtype=None,
    )
    if not checkpoint or not os.path.exists(checkpoint):
        model = FastLanguageModel.get_peft_model(
            model, r=32, lora_alpha=64, lora_dropout=0.05,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            bias="none", use_gradient_checkpointing="unsloth", random_state=42,
        )
    return model, tok


# ── Stage 1: SFT ─────────────────────────────────────────────────────────────
def stage_sft(hw):
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    train, ev = load_jsonl(SFT_TRAIN), load_jsonl(SFT_EVAL)
    log.info("SFT: train=%d eval=%d", len(train), len(ev))
    model, tok = load_model(hw)
    cfg = SFTConfig(
        output_dir=SFT_CKPT, num_train_epochs=3,
        per_device_train_batch_size=hw["batch"], gradient_accumulation_steps=hw["accum"],
        per_device_eval_batch_size=hw["batch"], learning_rate=2e-4,
        warmup_ratio=0.1, lr_scheduler_type="cosine",
        bf16=hw["bf16"], fp16=hw["fp16"], max_seq_length=MAX_SEQ_LEN,
        dataset_text_field="text", logging_steps=5, eval_strategy="steps", eval_steps=20,
        save_strategy="epoch", save_total_limit=2, report_to="none",
        optim="adamw_8bit", seed=42,
    )
    tr = SFTTrainer(model=model, args=cfg, train_dataset=Dataset.from_list(train),
                    eval_dataset=Dataset.from_list(ev), tokenizer=tok)
    _run(tr, "SFT", SFT_CKPT, model, tok)
    return SFT_CKPT


# ── Stage 2: GRPO (reuses the forensic reward from train.py) ─────────────────
def stage_grpo(hw):
    from datasets import Dataset
    from trl import GRPOConfig, GRPOTrainer
    from train import production_reward  # single source of truth

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    data = load_jsonl(GRPO_DATA)
    log.info("GRPO: prompts=%d gens/prompt=%d", len(data), hw["gens"])
    base = SFT_CKPT if os.path.exists(SFT_CKPT) else None
    model, tok = load_model(hw, base)

    def logged_reward(completions, prompts, **kw):
        rewards = production_reward(completions, prompts, **kw)
        try:
            with open(REWARD_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "mean": sum(rewards) / max(1, len(rewards)),
                                    "min": min(rewards), "max": max(rewards), "n": len(rewards)}) + "\n")
        except Exception:
            pass
        return rewards

    cfg = GRPOConfig(
        output_dir=GRPO_CKPT, num_train_epochs=1,
        per_device_train_batch_size=hw["batch"], gradient_accumulation_steps=hw["accum"],
        learning_rate=5e-6, warmup_ratio=0.05, lr_scheduler_type="cosine",
        bf16=hw["bf16"], fp16=hw["fp16"], max_completion_length=768,
        num_generations=hw["gens"], logging_steps=10, save_strategy="steps",
        save_steps=200, save_total_limit=5, report_to="none",
        optim="adamw_8bit", seed=42, max_grad_norm=0.5,
    )
    tr = GRPOTrainer(model=model, args=cfg,
                     train_dataset=Dataset.from_list([{"prompt": d["prompt"]} for d in data]),
                     tokenizer=tok, reward_funcs=logged_reward)
    _run(tr, "GRPO", GRPO_CKPT, model, tok)
    return GRPO_CKPT


# ── Stage 3: DPO ─────────────────────────────────────────────────────────────
def stage_dpo(hw):
    from datasets import Dataset
    from trl import DPOConfig, DPOTrainer
    data = load_jsonl(DPO_DATA)
    log.info("DPO: pairs=%d", len(data))
    base = GRPO_CKPT if os.path.exists(GRPO_CKPT) else (SFT_CKPT if os.path.exists(SFT_CKPT) else None)
    model, tok = load_model(hw, base)
    cfg = DPOConfig(
        output_dir=DPO_CKPT, num_train_epochs=3,
        per_device_train_batch_size=hw["batch"], gradient_accumulation_steps=hw["accum"],
        learning_rate=5e-7, warmup_ratio=0.1, lr_scheduler_type="cosine",
        bf16=hw["bf16"], fp16=hw["fp16"], max_length=MAX_SEQ_LEN, max_prompt_length=1024,
        beta=0.1, logging_steps=5, save_strategy="epoch", save_total_limit=2,
        report_to="none", optim="adamw_8bit", seed=42,
    )
    tr = DPOTrainer(model=model, args=cfg, train_dataset=Dataset.from_list(data), tokenizer=tok)
    _run(tr, "DPO", DPO_CKPT, model, tok)
    return DPO_CKPT


# ── Export: merge + GGUF ─────────────────────────────────────────────────────
def export(push_gguf=False, quants=("q4_k_m",)):
    from unsloth import FastLanguageModel
    ckpt = next((c for c in (DPO_CKPT, GRPO_CKPT, SFT_CKPT) if os.path.exists(c)), None)
    if not ckpt:
        log.error("No checkpoint to export."); return
    log.info("Merging from: %s", ckpt)
    model, tok = FastLanguageModel.from_pretrained(ckpt, max_seq_length=MAX_SEQ_LEN, load_in_4bit=True)
    os.makedirs(MERGED_DIR, exist_ok=True)
    model.save_pretrained_merged(MERGED_DIR, tok, save_method="merged_16bit")
    log.info("Merged 16-bit → %s", MERGED_DIR)
    os.makedirs(GGUF_DIR, exist_ok=True)
    for q in quants:
        try:
            model.save_pretrained_gguf(GGUF_DIR, tok, quantization_method=q)
            log.info("GGUF %s → %s", q, GGUF_DIR)
        except Exception as e:
            log.warning("GGUF %s export skipped: %s", q, e)
    repo = os.getenv("VA_HF_REPO")
    if push_gguf and repo:
        token = os.getenv("HF_TOKEN")
        if not token:
            log.warning("VA_HF_REPO set but HF_TOKEN missing — skipping push."); return
        try:
            model.push_to_hub_gguf(repo, tok, quantization_method=list(quants), token=token)
            log.info("Pushed GGUF to hf.co/%s", repo)
        except Exception as e:
            log.warning("HF push failed: %s", e)


def _run(trainer, name, ckpt, model, tok):
    import torch
    t0 = time.time()
    log.info("%s started %s (ETA varies by GPU)", name, datetime.now().strftime("%H:%M:%S"))
    trainer.train()
    model.save_pretrained(ckpt); tok.save_pretrained(ckpt)
    log.info("%s complete in %.1f min → %s", name, (time.time() - t0) / 60, ckpt)
    del trainer, model
    torch.cuda.empty_cache()


def write_summary(stages):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    summary = {
        "model": DEFAULT_MODEL, "stages_run": stages,
        "checkpoints": {k: os.path.exists(v) for k, v in
                        {"sft": SFT_CKPT, "grpo": GRPO_CKPT, "dpo": DPO_CKPT,
                         "merged": MERGED_DIR, "gguf": GGUF_DIR}.items()},
        "finished": datetime.now().isoformat(),
    }
    with open(os.path.join(OUTPUT_DIR, "training_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    log.info("Summary → %s", os.path.join(OUTPUT_DIR, "training_summary.json"))


def main():
    ap = argparse.ArgumentParser(description="VaultAgent cloud training pipeline")
    ap.add_argument("--stage", default="all", choices=["all", "sft", "grpo", "dpo", "export"])
    ap.add_argument("--push-gguf", action="store_true", help="push GGUF to VA_HF_REPO (needs HF_TOKEN)")
    ap.add_argument("--quants", default="q4_k_m", help="comma list, e.g. q4_k_m,q5_k_m,q8_0")
    args = ap.parse_args()

    import torch
    log.info("=" * 64)
    log.info("  VaultAgent Cloud Training")
    log.info("  GPU: %s", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
    log.info("  Stage: %s | Output: %s", args.stage, OUTPUT_DIR)
    log.info("  Started: %s", datetime.now())
    log.info("=" * 64)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ensure_data()
    hw = detect_hardware()
    quants = tuple(q.strip() for q in args.quants.split(",") if q.strip())

    t0 = time.time()
    ran = []
    if args.stage in ("all", "sft"):
        stage_sft(hw); ran.append("sft")
    if args.stage in ("all", "grpo"):
        stage_grpo(hw); ran.append("grpo")
    if args.stage in ("all", "dpo"):
        stage_dpo(hw); ran.append("dpo")
    if args.stage in ("all", "export"):
        export(push_gguf=args.push_gguf, quants=quants); ran.append("export")

    write_summary(ran)
    log.info("=" * 64)
    log.info("  COMPLETE — %.1f h | stages=%s", (time.time() - t0) / 3600, ran)
    log.info("  GGUF: %s  →  load in backend/model/inference.py for offline inference", GGUF_DIR)
    log.info("=" * 64)


if __name__ == "__main__":
    main()
