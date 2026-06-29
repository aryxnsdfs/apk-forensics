# ═══════════════════════════════════════════════════════════════════
# SWARM-OS A100 TRAINING PIPELINE — Maximum Performance
# ═══════════════════════════════════════════════════════════════════
# Hardware Target: A100 80GB VRAM (Colab/Lambda/RunPod)
# Estimated Time:  ~6-8 hours total
#   Stage 1 (SFT):  ~15-20 minutes  (45 golden examples, 3 epochs)
#   Stage 2 (GRPO): ~4-6 hours      (2000+ prompts, 4 completions each)
#   Stage 3 (DPO):  ~20-30 minutes  (45+ preference pairs, 3 epochs)
#   Merge & GGUF:   ~5 minutes
#
# Prerequisites:
#   pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
#   pip install trl datasets jsonlines peft accelerate bitsandbytes
#
# Usage:
#   python train.py --stage all        # Full 3-stage pipeline (~6-8 hours)
#   python train.py --stage sft        # Stage 1 only
#   python train.py --stage grpo       # Stage 2 only
#   python train.py --stage dpo        # Stage 3 only
#   python train.py --stage merge      # Merge LoRA + export GGUF
# ═══════════════════════════════════════════════════════════════════

import os
import re
import sys
import json
import time
import argparse
import logging
import requests
from datetime import datetime, timedelta

import torch

# ── Logging Setup ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("training_log.txt", mode="a", encoding="utf-8"),
    ]
)
log = logging.getLogger("swarm-train")

# ── Constants ─────────────────────────────────────────────────────
MODEL_ID       = "unsloth/llama-3.1-8b-instruct-bnb-4bit"
MAX_SEQ_LEN    = 2048
LORA_R         = 32              # Higher rank for A100 (more capacity)
LORA_ALPHA     = 64
LORA_DROPOUT   = 0.05
OUTPUT_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swarm-os-trained")

# Paths
SPLITS_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset", "splits")
SFT_TRAIN_PATH = os.path.join(SPLITS_DIR, "sft_train.jsonl")
SFT_EVAL_PATH  = os.path.join(SPLITS_DIR, "sft_eval.jsonl")
GRPO_PATH      = os.path.join(SPLITS_DIR, "grpo_prompts.jsonl")
DPO_PATH       = os.path.join(SPLITS_DIR, "dpo_pairs.jsonl")

# Checkpoint dirs
SFT_CKPT       = os.path.join(OUTPUT_DIR, "stage1-sft")
GRPO_CKPT      = os.path.join(OUTPUT_DIR, "stage2-grpo")
DPO_CKPT       = os.path.join(OUTPUT_DIR, "stage3-dpo")
FINAL_MERGED   = os.path.join(OUTPUT_DIR, "final-merged")


def print_banner(stage_name: str, details: dict):
    log.info("=" * 64)
    log.info(f"  {stage_name}")
    log.info("=" * 64)
    for k, v in details.items():
        log.info(f"  {k}: {v}")
    log.info("-" * 64)


def get_vram_info():
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        props = torch.cuda.get_device_properties(0)
        total_vram = getattr(props, "total_memory", getattr(props, "total_mem", 0))
        total = total_vram / 1024**3
        return f"{allocated:.1f}GB / {reserved:.1f}GB reserved / {total:.1f}GB total"
    return "CUDA not available"


def load_jsonl(path):
    import jsonlines
    with jsonlines.open(path) as reader:
        return list(reader)


def load_model_and_tokenizer(checkpoint_path=None):
    from unsloth import FastLanguageModel

    model_path = checkpoint_path if checkpoint_path and os.path.exists(checkpoint_path) else MODEL_ID
    log.info(f"Loading model from: {model_path}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_path,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=True,
        dtype=None,
    )

    if not checkpoint_path or not os.path.exists(checkpoint_path):
        model = FastLanguageModel.get_peft_model(
            model,
            r=LORA_R,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_alpha=LORA_ALPHA,
            lora_dropout=LORA_DROPOUT,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    log.info(f"Trainable: {trainable:,} / {total:,} ({trainable/total*100:.2f}%)")
    log.info(f"VRAM after load: {get_vram_info()}")
    return model, tokenizer


# ═══════════════════════════════════════════════════════════════════
# STAGE 1: SFT — Cold Start
# ═══════════════════════════════════════════════════════════════════
def run_stage_1_sft():
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    if not os.path.exists(SFT_TRAIN_PATH):
        log.error(f"Missing {SFT_TRAIN_PATH}. Run: python dataset/build_training_splits.py")
        sys.exit(1)

    sft_train = load_jsonl(SFT_TRAIN_PATH)
    sft_eval = load_jsonl(SFT_EVAL_PATH)

    print_banner("STAGE 1: SFT — Cold Start Fine-Tuning", {
        "Train": len(sft_train), "Eval": len(sft_eval),
        "Model": MODEL_ID, "LoRA r": LORA_R,
        "Epochs": 3, "Effective batch": "4 × 4 = 16",
        "Max seq": MAX_SEQ_LEN,
    })

    model, tokenizer = load_model_and_tokenizer()
    train_ds = Dataset.from_list(sft_train)
    eval_ds = Dataset.from_list(sft_eval)

    config = SFTConfig(
        output_dir=SFT_CKPT,
        num_train_epochs=3,
        per_device_train_batch_size=4,        # A100 can handle batch=4
        gradient_accumulation_steps=4,         # Effective batch = 16
        per_device_eval_batch_size=4,
        learning_rate=2e-4,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        fp16=False,
        bf16=True,                             # A100 native bf16
        max_seq_length=MAX_SEQ_LEN,
        dataset_text_field="text",
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=20,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        optim="adamw_8bit",
        seed=42,
    )

    trainer = SFTTrainer(
        model=model, args=config,
        train_dataset=train_ds, eval_dataset=eval_ds,
        tokenizer=tokenizer,
    )

    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0

    model.save_pretrained(SFT_CKPT)
    tokenizer.save_pretrained(SFT_CKPT)
    log.info(f"Stage 1 complete in {elapsed/60:.1f}m. Saved: {SFT_CKPT}")

    del model, trainer
    torch.cuda.empty_cache()
    return SFT_CKPT


# ═══════════════════════════════════════════════════════════════════
# STAGE 2: GRPO — Reinforcement Learning
# ═══════════════════════════════════════════════════════════════════
def production_reward(completions, prompts, **kwargs):
    """
    VaultAgent forensic reward (offline APK malware analysis).

    Shapes the model toward evidence-backed malware reports. Reward signal is
    derived purely from the completion text + the scenario ground truth embedded
    in each prompt — no Docker, no network, fully offline.

    Rewards:  correct flag detection, evidence-backed conclusions, correct family,
              valid JSON, correct threat level.
    Penalizes: hallucinated permissions (not in the scenario manifest), wrong
              classification, missing obvious indicators, malformed output.

    Ground truth is read from kwargs['expected'] when the trainer supplies it, or
    parsed from a `GROUND_TRUTH:{...}` block appended to the prompt by the dataset
    generator. Each GROUND_TRUTH carries: flags[], permissions[], family,
    threat_level.
    """
    import json as _json

    FLAG_RE = re.compile(r"FLAG_[A-Z_]+")
    PERM_RE = re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b")  # SCREAMING_SNAKE tokens (perm-ish)
    LEVELS = ("THREAT_BENIGN", "THREAT_LOW", "THREAT_MEDIUM", "THREAT_HIGH")

    expected_list = kwargs.get("expected")

    def ground_truth_for(idx, prompt):
        if expected_list and idx < len(expected_list):
            return expected_list[idx] or {}
        m = re.search(r"GROUND_TRUTH:\s*(\{.*\})", prompt or "", re.DOTALL)
        if m:
            try:
                return _json.loads(m.group(1))
            except Exception:
                return {}
        return {}

    rewards = []
    for i, completion in enumerate(completions):
        prompt = prompts[i] if i < len(prompts) else ""
        gt = ground_truth_for(i, prompt)
        gt_flags = set(gt.get("flags", []))
        gt_perms = {p.rsplit(".", 1)[-1] for p in gt.get("permissions", [])}
        gt_family = (gt.get("family") or "").lower()
        gt_level = (gt.get("threat_level") or "").upper()

        text = completion or ""
        upper = text.upper()
        score = 0.0

        # ── Valid JSON object present? ──
        json_ok = False
        jm = re.search(r"\{.*\}", text, re.DOTALL)
        parsed = {}
        if jm:
            try:
                parsed = _json.loads(jm.group(0))
                json_ok = True
                score += 0.10
            except Exception:
                json_ok = False
        if not json_ok:
            score -= 0.20

        # ── Flag detection ──
        pred_flags = set(FLAG_RE.findall(upper))
        if gt_flags:
            correct = pred_flags & gt_flags
            missed = gt_flags - pred_flags
            spurious = pred_flags - gt_flags
            score += min(0.30 * len(correct), 0.90)
            score -= 0.40 * len(missed)
            score -= 0.15 * len(spurious)

        # ── Hallucinated permissions: SCREAMING_SNAKE perm tokens cited but not
        #    in the scenario manifest (ignore flags + level + M2M control words). ──
        if gt_perms:
            ignore = gt_flags | set(LEVELS) | {"FLAG", "THREAT", "ETA", "VERDICT",
                                              "STATIC", "REVERSE", "INTEL", "RCA",
                                              "GROUND_TRUTH", "JSON"}
            cited = {t for t in PERM_RE.findall(upper)
                     if not t.startswith("FLAG_") and not t.startswith("THREAT_")
                     and not t.startswith("ETA") and t not in ignore}
            # only count tokens that look like android permissions referenced in prompt
            manifest_universe = gt_perms | {p.rsplit(".", 1)[-1]
                                            for p in re.findall(r"[A-Z_]{4,}", prompt or "")}
            hallucinated = {c for c in cited
                            if c in _ANDROID_PERMS and c not in manifest_universe}
            score -= 0.60 * len(hallucinated)

        # ── Family classification ──
        if gt_family:
            if gt_family in text.lower():
                score += 0.25
            elif parsed.get("malware_family", "").lower() not in ("", "unknown"):
                score -= 0.50  # asserted a wrong family

        # ── Threat level agreement ──
        if gt_level:
            pred_level = next((lvl for lvl in LEVELS if lvl in upper), None)
            if pred_level == gt_level:
                score += 0.15
            elif pred_level:
                score -= 0.25

        # ── Evidence-backed: references a class/method/permission location ──
        if re.search(r"(onReceive|\.smali|class|method|permission|component)", text, re.IGNORECASE):
            score += 0.10

        # ── Length guards ──
        if len(text) < 30:
            score -= 0.30

        rewards.append(max(-1.0, min(1.0, round(score, 2))))

    return rewards


# Minimal offline Android permission lexicon for hallucination detection in the
# reward function (suffix form). Kept small and dependency-free on purpose.
_ANDROID_PERMS = {
    "READ_SMS", "RECEIVE_SMS", "SEND_SMS", "WRITE_SMS", "READ_CONTACTS",
    "WRITE_CONTACTS", "READ_CALL_LOG", "WRITE_CALL_LOG", "RECORD_AUDIO", "CAMERA",
    "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "ACCESS_BACKGROUND_LOCATION",
    "READ_PHONE_STATE", "CALL_PHONE", "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE",
    "MANAGE_EXTERNAL_STORAGE", "BIND_DEVICE_ADMIN", "BIND_ACCESSIBILITY_SERVICE",
    "SYSTEM_ALERT_WINDOW", "REQUEST_INSTALL_PACKAGES", "GET_ACCOUNTS", "INTERNET",
    "QUERY_ALL_PACKAGES", "PACKAGE_USAGE_STATS", "USE_FINGERPRINT",
}


def run_stage_2_grpo():
    from datasets import Dataset
    from trl import GRPOConfig, GRPOTrainer

    if not os.path.exists(GRPO_PATH):
        log.error(f"Missing {GRPO_PATH}.")
        sys.exit(1)

    sft_path = SFT_CKPT if os.path.exists(SFT_CKPT) else None
    grpo_data = load_jsonl(GRPO_PATH)

    print_banner("STAGE 2: GRPO — Reinforcement Learning", {
        "Prompts": len(grpo_data),
        "Base": sft_path or MODEL_ID,
        "Epochs": 1, "Effective batch": "2 × 4 = 8",
        "Completions/prompt": 8,
        "Max completion len": 768,
        "Est. time": "4-6 hours on A100",
    })

    model, tokenizer = load_model_and_tokenizer(sft_path)

    prompts_list = [{"prompt": item["prompt"]} for item in grpo_data]
    grpo_dataset = Dataset.from_list(prompts_list)

    config = GRPOConfig(
        output_dir=GRPO_CKPT,
        num_train_epochs=1,
        per_device_train_batch_size=2,        # A100 can handle batch=2 for RL
        gradient_accumulation_steps=4,         # Effective batch = 8
        learning_rate=5e-6,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        fp16=False,
        bf16=True,
        max_completion_length=768,             # Longer than RTX 3060 version
        num_generations=8,                     # 8 completions per prompt (requires strong variance for GRPO)
        logging_steps=10,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=5,
        report_to="none",
        optim="adamw_8bit",
        seed=42,
        max_grad_norm=0.5,
    )

    trainer = GRPOTrainer(
        model=model, args=config,
        train_dataset=grpo_dataset,
        tokenizer=tokenizer,
        reward_funcs=production_reward,
    )

    t0 = time.time()
    log.info(f"GRPO started: {datetime.now().strftime('%H:%M:%S')}")
    log.info(f"Estimated finish: {(datetime.now() + timedelta(hours=5)).strftime('%H:%M:%S')}")

    trainer.train()
    elapsed = time.time() - t0

    model.save_pretrained(GRPO_CKPT)
    tokenizer.save_pretrained(GRPO_CKPT)
    log.info(f"Stage 2 complete in {elapsed/3600:.1f}h. Saved: {GRPO_CKPT}")

    del model, trainer
    torch.cuda.empty_cache()
    return GRPO_CKPT


# ═══════════════════════════════════════════════════════════════════
# STAGE 3: DPO — Preference Alignment
# ═══════════════════════════════════════════════════════════════════
def run_stage_3_dpo():
    from datasets import Dataset
    from trl import DPOConfig, DPOTrainer

    if not os.path.exists(DPO_PATH):
        log.error(f"Missing {DPO_PATH}.")
        sys.exit(1)

    grpo_path = GRPO_CKPT if os.path.exists(GRPO_CKPT) else None
    sft_path = SFT_CKPT if os.path.exists(SFT_CKPT) else None
    base_path = grpo_path or sft_path
    dpo_data = load_jsonl(DPO_PATH)

    print_banner("STAGE 3: DPO — Preference Alignment", {
        "Pairs": len(dpo_data),
        "Base": base_path or MODEL_ID,
        "Epochs": 3, "Effective batch": "2 × 4 = 8",
        "Beta": 0.1,
    })

    model, tokenizer = load_model_and_tokenizer(base_path)
    dpo_dataset = Dataset.from_list(dpo_data)

    config = DPOConfig(
        output_dir=DPO_CKPT,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=5e-7,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        fp16=False,
        bf16=True,
        max_length=MAX_SEQ_LEN,
        max_prompt_length=512,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        optim="adamw_8bit",
        beta=0.1,
        seed=42,
    )

    trainer = DPOTrainer(
        model=model, args=config,
        train_dataset=dpo_dataset,
        tokenizer=tokenizer,
    )

    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0

    model.save_pretrained(DPO_CKPT)
    tokenizer.save_pretrained(DPO_CKPT)
    log.info(f"Stage 3 complete in {elapsed/60:.1f}m. Saved: {DPO_CKPT}")

    del model, trainer
    torch.cuda.empty_cache()
    return DPO_CKPT


# ═══════════════════════════════════════════════════════════════════
# MERGE & EXPORT
# ═══════════════════════════════════════════════════════════════════
def merge_and_export():
    from unsloth import FastLanguageModel

    ckpt = DPO_CKPT if os.path.exists(DPO_CKPT) else (
           GRPO_CKPT if os.path.exists(GRPO_CKPT) else SFT_CKPT)

    if not os.path.exists(ckpt):
        log.error("No checkpoint found to merge!")
        return

    log.info(f"Merging from: {ckpt}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=ckpt, max_seq_length=MAX_SEQ_LEN, load_in_4bit=True,
    )

    os.makedirs(FINAL_MERGED, exist_ok=True)
    model.save_pretrained_merged(FINAL_MERGED, tokenizer, save_method="merged_16bit")
    log.info(f"Merged 16-bit model: {FINAL_MERGED}")

    try:
        gguf_dir = os.path.join(OUTPUT_DIR, "gguf")
        os.makedirs(gguf_dir, exist_ok=True)
        model.save_pretrained_gguf(gguf_dir, tokenizer, quantization_method="q4_k_m")
        log.info(f"GGUF Q4_K_M: {gguf_dir}")
    except Exception as e:
        log.warning(f"GGUF export skipped: {e}")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Swarm-OS A100 Training Pipeline")
    parser.add_argument("--stage", type=str, default="all",
                        choices=["all", "sft", "grpo", "dpo", "merge"])
    args = parser.parse_args()

    log.info("=" * 64)
    log.info("  SWARM-OS A100 TRAINING PIPELINE")
    log.info(f"  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
    log.info(f"  VRAM: {get_vram_info()}")
    log.info(f"  Stage: {args.stage}")
    log.info(f"  Output: {OUTPUT_DIR}")
    log.info(f"  Started: {datetime.now()}")
    log.info("=" * 64)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    t0 = time.time()

    if args.stage in ("all", "sft"):
        run_stage_1_sft()
    if args.stage in ("all", "grpo"):
        run_stage_2_grpo()
    if args.stage in ("all", "dpo"):
        run_stage_3_dpo()
    if args.stage in ("all", "merge"):
        merge_and_export()

    total = time.time() - t0
    log.info("=" * 64)
    log.info(f"  COMPLETE — {total/3600:.1f} hours")
    log.info(f"  Output: {OUTPUT_DIR}")
    log.info("=" * 64)


if __name__ == "__main__":
    main()
