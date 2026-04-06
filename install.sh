#!/usr/bin/env bash
# pdf2skills 一键安装脚本
# 用法：在 pdf2skills 项目根目录执行 ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_NAME="pdf2skills"

echo "=== pdf2skills Installer ==="
echo ""

# 1. 检查 Python 版本
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.11+."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo "ERROR: Python 3.11+ required, found $PY_VERSION"
    exit 1
fi
echo "[OK] Python $PY_VERSION"

# 2. 创建虚拟环境
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "[..] Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi
echo "[OK] Virtual environment"

# 3. 安装依赖
echo "[..] Installing dependencies..."
source "$SCRIPT_DIR/.venv/bin/activate"
pip install -q -e "$SCRIPT_DIR[dev]" 2>/dev/null
python -m spacy download en_core_web_sm -q 2>/dev/null
echo "[OK] Dependencies installed"

# 4. 运行测试验证
echo "[..] Running tests..."
if python -m pytest "$SCRIPT_DIR/tests/" -q 2>/dev/null; then
    echo "[OK] All tests passed"
else
    echo "[WARN] Some tests failed, but installation can continue"
fi

# 5. 安装 Skill 到目标运行环境
echo ""
echo "Where to install the skill?"
echo "  1) Project-level  (.claude/skills/ in current directory)"
echo "  2) User-level     (~/.claude/skills/ for all projects)"
echo "  3) Skip (I'll install manually)"
echo ""
read -rp "Choose [1/2/3]: " choice

case "$choice" in
    1)
        DEST="$(pwd)/.claude/skills/$SKILL_NAME"
        ;;
    2)
        DEST="$HOME/.claude/skills/$SKILL_NAME"
        ;;
    3)
        echo ""
        echo "=== Installation Complete ==="
        echo ""
        echo "To install the skill manually, copy:"
        echo "  $SCRIPT_DIR/skills/pdf2skills"
        echo ""
        echo "into a skill directory recognized by your target agent runtime."
        exit 0
        ;;
    *)
        echo "Invalid choice, skipping skill install."
        exit 0
        ;;
 esac

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -r "$SCRIPT_DIR/skills/$SKILL_NAME" "$DEST"

echo "[OK] Skill installed to $DEST"
echo ""
echo "=== Installation Complete ==="
echo ""
echo "Configure your target runtime to load the installed skill from that directory."
echo ""
echo "Optional: configure LLM provider for better PDF parsing:"
echo "  mkdir -p $SCRIPT_DIR/.pdf2skills"
echo "  cp $SCRIPT_DIR/.env.example $SCRIPT_DIR/.pdf2skills/.env"
echo "  # Edit .pdf2skills/.env with your API keys"
