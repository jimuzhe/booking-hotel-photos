#!/usr/bin/env bash
# booking-hotel-photos 入口脚本
# 用法: bash run.sh [download.py 参数]
# 示例: bash run.sh -q "大阪" --hotels 3 --headless
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"
exec python3 src/download.py "$@"
