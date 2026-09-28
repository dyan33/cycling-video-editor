#!/usr/bin/env bash
# 环境引导：创建 skill 自带 venv 并安装依赖（需要 uv）。
# 草稿组装阶段依赖 jianying-editor skill 的 venv，这里顺带检查。
set -e
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "❌ 未找到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  uv venv .venv --quiet
fi
uv pip install --python .venv/bin/python --quiet \
  fitdecode pillow opencv-python-headless pymediainfo pyyaml
echo "✅ skill venv 就绪: $(pwd)/.venv"

JY_ROOT="${JY_SKILL_ROOT:-$HOME/.agents/skills/jianying-editor}"
if [ ! -x "$JY_ROOT/.venv/bin/python" ]; then
  for alt in "$HOME/.zcode/skills/jianying-editor" ".agents/skills/jianying-editor" ".zcode/skills/jianying-editor"; do
    if [ -x "$alt/.venv/bin/python" ]; then JY_ROOT="$alt"; break; fi
  done
fi
if [ -x "$JY_ROOT/.venv/bin/python" ]; then
  echo "✅ jianying-editor venv 就绪: $JY_ROOT/.venv/bin/python"
else
  echo "⚠️ 未找到 jianying-editor 的 venv（build/verify 阶段需要），先按其文档初始化，并可用 JY_SKILL_ROOT 指定路径"
fi
