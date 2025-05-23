#!/usr/bin/env bash
set -euo pipefail

echo "🚀  Bootstrapping Conda environment…"

# 1) Make `conda activate` available in this script
CONDA_BASE="$(conda info --base)"
# shellcheck source=/dev/null
source "${CONDA_BASE}/etc/profile.d/conda.sh"

# 2) Create or update your env
ENV_NAME="MageEnv"
if conda env list | grep -qE "^${ENV_NAME}[[:space:]]"; then
  echo "🔄  Updating existing '$ENV_NAME' environment…"
  conda env update --name "$ENV_NAME" --file environment.yml --prune
else
  echo "✨  Creating new '$ENV_NAME' environment…"
  conda env create --name "$ENV_NAME" --file environment.yml
fi

# 3) Activate it
echo "⚡️  Activating '$ENV_NAME'…"
conda activate "$ENV_NAME"

# ────────────────────────────────────────────────────────────────────────────────
# 4) System-level deps: LaTeX standalone & FFmpeg
# ────────────────────────────────────────────────────────────────────────────────

echo "📦  Installing system-level dependencies…"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected macOS…"
    command -v brew >/dev/null 2>&1 || {
      echo "  → Installing Homebrew…"
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    }
    command -v latex >/dev/null 2>&1 || {
      echo "  → Installing MacTeX…"
      brew install --cask mactex
    }
    echo "  → Ensuring standalone package…"
    sudo tlmgr update --self
    sudo tlmgr install standalone
    command -v ffmpeg >/dev/null 2>&1 || {
      echo "  → Installing FFmpeg…"
      brew install ffmpeg
    }

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux…"
    if [ -f /etc/debian_version ]; then
        echo "  → Installing TeX Live & FFmpeg on Debian/Ubuntu…"
        sudo apt-get update
        sudo apt-get install -y texlive-latex-extra texlive-fonts-extra ffmpeg
    elif [ -f /etc/fedora-release ]; then
        echo "  → Installing TeX Live & FFmpeg on Fedora…"
        sudo dnf install -y texlive-standalone texlive-latex ffmpeg
    elif [ -f /etc/arch-release ]; then
        echo "  → Installing TeX Live & FFmpeg on Arch…"
        sudo pacman -Sy --noconfirm texlive-most ffmpeg
    else
        echo "⚠️  Unsupported Linux distro: please install 'texlive-latex-extra' and 'ffmpeg' yourself."
    fi

else
    echo "⚠️  Unsupported OS: please install LaTeX standalone + FFmpeg manually."
fi

# ────────────────────────────────────────────────────────────────────────────────
# 5) Python-level deps via pip (inside the activated Conda env)
# ────────────────────────────────────────────────────────────────────────────────

echo "🐍  Installing Python dependencies (pip)…"
pip install -r requirements.txt

echo "🎉  All dependencies are now installed in Conda env '$ENV_NAME'."
