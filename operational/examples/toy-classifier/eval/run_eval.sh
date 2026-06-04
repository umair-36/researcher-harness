#!/usr/bin/env bash
set -euo pipefail
TARGET_REPO="${1:-target/repo}"
python3 "$TARGET_REPO/train.py"
