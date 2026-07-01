"""
Download the trained VaultAgent LoRA adapter from Hugging Face and place it
where train_cloud.py's --stage export expects it, so you can merge + build a
local GGUF without re-running SFT/GRPO.

Usage:
  python download_checkpoint.py                     # grabs GRPO stage (best)
  python download_checkpoint.py --stage sft          # grabs SFT stage instead
  python download_checkpoint.py --repo aryxn323/vaultagent
"""

import argparse
import os

from huggingface_hub import snapshot_download

ROOT = os.path.dirname(os.path.abspath(__file__))

STAGE_DIRS = {"sft": "stage1-sft", "grpo": "stage2-grpo"}
LOCAL_DIRS = {"sft": "stage1-sft", "grpo": "stage2-grpo"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="aryxn323/vaultagent")
    ap.add_argument("--stage", default="grpo", choices=["sft", "grpo"])
    args = ap.parse_args()

    remote_dir = STAGE_DIRS[args.stage]
    local_dir = os.path.join(ROOT, "vaultagent-trained", LOCAL_DIRS[args.stage])
    os.makedirs(local_dir, exist_ok=True)

    print(f"Downloading {args.repo}:{remote_dir}/  ->  {local_dir}")
    # Only the top-level adapter files — skip checkpoint-*/ subfolders
    # (those carry optimizer.pt / scheduler.pt state we don't need for merging).
    snapshot_download(
        repo_id=args.repo,
        repo_type="model",
        local_dir=local_dir,
        allow_patterns=[f"{remote_dir}/*"],
        local_dir_use_symlinks=False,
    )

    # snapshot_download preserves the repo's folder structure under local_dir,
    # i.e. files land in local_dir/<remote_dir>/... — flatten one level up.
    nested = os.path.join(local_dir, remote_dir)
    if os.path.isdir(nested):
        for name in os.listdir(nested):
            src = os.path.join(nested, name)
            dst = os.path.join(local_dir, name)
            if not os.path.exists(dst):
                os.replace(src, dst)
        os.rmdir(nested)

    files = os.listdir(local_dir)
    print(f"Done. {len(files)} files in {local_dir}:")
    for f in sorted(files):
        print(" -", f)


if __name__ == "__main__":
    main()
