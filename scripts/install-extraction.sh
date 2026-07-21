#!/usr/bin/env bash
# install-extraction.sh — add the heavy on-screen-OCR stack (easyocr → torch) to the
# conda env, using CPU-ONLY torch wheels (this machine has no NVIDIA GPU).
#
# Everything else (transcript via faster-whisper, AI vision via claude-cli) is already
# torch-free and installed by `pip install -e ".[cpu]"`. Run THIS only when you want
# on-screen text (OCR) extraction and accept slow CPU inference.
#
#   bash scripts/install-extraction.sh
#
# Idempotent: re-running just verifies/upgrades. Set REELS_ENV to target a different
# conda env (default: reels-scrap).
set -euo pipefail

ENV_NAME="${REELS_ENV:-reels-scrap}"
CONDA_BASE="$(conda info --base 2>/dev/null || echo "$HOME/miniforge3")"
PY="$CONDA_BASE/envs/$ENV_NAME/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "✗ conda env '$ENV_NAME' not found at $PY" >&2
  echo "  create it first:  mamba env create -f environment.yml" >&2
  exit 1
fi

echo "→ target: $PY"
if "$PY" -c "import torch" 2>/dev/null; then
  echo "✓ torch already present: $("$PY" -c 'import torch; print(torch.__version__)')"
else
  echo "→ installing CPU-only torch + torchvision (no CUDA; ~200MB not multi-GB)…"
  # CPU wheel index keeps this off the multi-GB CUDA build.
  "$PY" -m pip install --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision
fi

echo "→ installing easyocr (OCR)…"
"$PY" -m pip install "easyocr>=1.7"

echo "→ verifying…"
"$PY" - <<'PYEOF'
import torch, easyocr  # noqa: F401
print(f"✓ torch {torch.__version__} (cuda={torch.cuda.is_available()}) + easyocr ready")
print("  enable OCR: set extract.ocr=true in config-deep.yaml, then `reels-scrap run -c config-deep.yaml`")
PYEOF
