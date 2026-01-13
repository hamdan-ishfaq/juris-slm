#!/usr/bin/env bash
set -euo pipefail

# This script downloads the small adapter folder (juris_local_proof)
# and optionally the big base model (NOT recommended to track in git).
#
# Options:
#  - Uses kaggle CLI if available and dataset exists (recommended since you uploaded it).
#  - If HF_TOKEN is set, will try to pull files via huggingface_hub.

OUT_DIR="juris_local_proof"
mkdir -p "$OUT_DIR"

# 1) Kaggle dataset option (make sure ~/.kaggle/kaggle.json present)
if command -v kaggle >/dev/null 2>&1; then
  echo "Attempting to download jur is_local_proof from Kaggle..."
  # dataset id you used: hamdanishfaq/juris-local-proof
  kaggle datasets download -d hamdanishfaq/juris-local-proof -p /tmp/juris_download --unzip
  # move files into OUT_DIR
  if [ -d /tmp/juris_download/juris_local_proof ]; then
    rsync -av --progress /tmp/juris_download/juris_local_proof/ "$OUT_DIR/"
    echo "Kaggle dataset downloaded to $OUT_DIR/"
    exit 0
  else
    echo "Kaggle dataset not found at expected path, falling through..."
  fi
fi

# 2) Hugging Face option (requires HF_TOKEN env var)
if [ -n "${HF_TOKEN:-}" ]; then
  echo "Using huggingface_hub to download adapter files..."
  python - <<'PY'
from huggingface_hub import hf_hub_download
import os, sys
repo_id = "hamdanishfaq/juris-local-proof"  # adjust if different
files = ["adapter_model.safetensors","adapter_config.json","tokenizer.json",
         "tokenizer_config.json","tokenizer.model","added_tokens.json",
         "special_tokens_map.json","chat_template.jinja","README.md"]
out_dir = "juris_local_proof"
os.makedirs(out_dir, exist_ok=True)
for f in files:
    try:
        print("Downloading:", f)
        p = hf_hub_download(repo_id=repo_id, filename=f, repo_type="dataset", token=os.environ.get("HF_TOKEN"))
        # move or copy to out_dir
        import shutil
        shutil.copy(p, os.path.join(out_dir, f))
    except Exception as e:
        print("Failed to download", f, e)
PY
  echo "Hugging Face download attempted. Check $OUT_DIR"
  exit 0
fi

echo "No download method succeeded. Please:
  - Install kaggle CLI and `kaggle datasets download -d hamdanishfaq/juris-local-proof`, or
  - Set HF_TOKEN and host the adapters/tokenizer on Hugging Face."
exit 1
