#!/usr/bin/env bash
# 一键安装 booking-hotel-photos skill 所需依赖
# 用法: bash setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== booking-hotel-photos 依赖安装 ==="
echo "目录: $ROOT"
echo ""

# 1. Python 依赖
echo "[1/2] 安装 Python 依赖..."
python3 -m pip install -r "$ROOT/requirements.txt"
echo "  ✓ Python 依赖完成"
echo ""

# 2. Playwright Chromium
echo "[2/2] 安装 Playwright Chromium（首次约 1–2 分钟）..."
python3 -m playwright install chromium
echo "  ✓ Playwright Chromium 完成"
echo ""

# 3. 自检
echo "自检..."
python3 -c "import playwright, requests; print('  ✓ deps ok')"
echo ""
echo "=== 安装完成 ==="
echo "运行示例: python3 src/download.py -q \"大阪\" --hotels 3 --headless"
