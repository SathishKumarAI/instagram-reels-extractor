#!/usr/bin/env bash
# System deps for reels-scrap. Run once. Rocky Linux 10 / dnf.
set -euo pipefail

echo "==> Installing system packages (ffmpeg, weasyprint native deps, tesseract optional)"
# ffmpeg: required for audio extraction (whisper) + frame sampling (ocr/vision)
# cairo/pango/gdk-pixbuf: weasyprint PDF rendering
# tesseract: optional OCR fallback if easyocr unavailable
sudo dnf install -y \
  ffmpeg ffmpeg-libs \
  cairo pango gdk-pixbuf2 libffi \
  tesseract \
  || {
    echo "ffmpeg may need RPM Fusion. Enabling..."
    sudo dnf install -y \
      https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-$(rpm -E %rhel).noarch.rpm || true
    sudo dnf install -y ffmpeg ffmpeg-libs
  }

echo "==> Python env via mise + venv"
mise use python@3.12 2>/dev/null || echo "mise not active; using system python3.12"

if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .

echo "==> Done. Activate with: source .venv/bin/activate"
echo "    Set ANTHROPIC_API_KEY in .env if using vision."
echo "    First whisper/easyocr run downloads models (large)."
