#!/usr/bin/env bash
# booking-hotel-photos skill 一键安装脚本
# 用法: curl -fsSL <raw-url>/install.sh | bash
#   或: git clone <repo-url> && cd booking-hotel-photos && ./install.sh

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HOME/.claude/skills/booking-hotel-photos"

echo "============================================"
echo "  booking-hotel-photos skill 安装器"
echo "============================================"
echo ""
echo "源码目录: $SKILL_DIR"
echo "安装目标: $TARGET"
echo ""

# 1. 复制 skill 文件
echo "[1/3] 复制 skill 文件..."
rm -rf "$TARGET"
cp -r "$SKILL_DIR" "$TARGET"
echo "  ✓ 已安装到 $TARGET"

# 2. 安装 Python 依赖
echo ""
echo "[2/3] 安装 Python 依赖..."
cd "$TARGET"
if command -v python3 &>/dev/null; then
    python3 -m pip install -r requirements.txt 2>/dev/null
    echo "  ✓ Python 依赖已安装"
else
    echo "  ✗ 未找到 python3，请手动安装: pip3 install -r $TARGET/requirements.txt"
fi

# 3. 安装 Playwright
echo ""
echo "[3/3] 安装 Playwright Chromium..."
if command -v python3 &>/dev/null; then
    python3 -m playwright install chromium 2>/dev/null
    echo "  ✓ Playwright Chromium 已安装"
else
    echo "  ✗ 跳过（需要先安装 python3）"
fi

echo ""
echo "============================================"
echo "  安装完成 ✓"
echo "============================================"
echo ""
echo "使用方式:"
echo "  在 Claude Code 中说:"
echo "    \"帮我爬大阪 3 家酒店的图片\""
echo "    \"下载东京 5 酒店的大图到 ~/Pictures\""
echo ""
