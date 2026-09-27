#!/usr/bin/env bash
# Cloudflare Pages build for this backpack's design pages.
# Pages settings: build command `bash cloudflare-build.sh`, output directory `site`.
set -euo pipefail
git fetch --unshallow --quiet 2>/dev/null || true   # full history: "last touched" dates come from git
rm -rf .backpack-kit
git clone --depth 1 --quiet https://github.com/Escape-Backpack/backpack-kit .backpack-kit
PY=$(command -v python3 || command -v python)
"$PY" .backpack-kit/kit.py --project . build
