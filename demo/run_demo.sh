#!/usr/bin/env bash
# run_demo.sh —— 一键复现「动作层」演示
#
# 做三件事：
#   1. 起一个本地静态服务，托管 mock_form/index.html（假的建计划表单）
#   2. 用调试端口起一个无头浏览器
#   3. 跑 fill_form.py，通过 CDP 自动走完 6 步并逐步截屏
#
# 依赖：python3 + websocket-client / pillow；本机 Chrome 或 Edge
# 用法：bash run_demo.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

PY="${PY:-python}"
PORT_HTTP="${PORT_HTTP:-8899}"
PORT_CDP="${PORT_CDP:-9344}"

# 找一个可用的浏览器
BROWSER="${BROWSER:-}"
if [ -z "$BROWSER" ]; then
  for c in \
    "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
    "/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "$(command -v google-chrome || true)" \
    "$(command -v chromium || true)"; do
    [ -x "$c" ] && BROWSER="$c" && break
  done
fi
[ -z "$BROWSER" ] && { echo "未找到 Chrome/Edge，请用 BROWSER=... 指定"; exit 1; }
echo "浏览器: $BROWSER"

PROF="$(mktemp -d)"

"$PY" -m http.server "$PORT_HTTP" --bind 127.0.0.1 --directory mock_form >/dev/null 2>&1 &
SRV=$!
"$BROWSER" --headless=new --remote-debugging-port="$PORT_CDP" --remote-allow-origins='*' \
  --user-data-dir="$PROF" --no-first-run --no-default-browser-check \
  --disable-gpu --no-proxy-server >/dev/null 2>&1 &
CHR=$!
trap 'kill $CHR $SRV 2>/dev/null || true; rm -rf "$PROF"' EXIT

sleep 6
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="127.0.0.1,localhost"

rm -rf shots && mkdir -p shots
"$PY" fill_form.py --port "$PORT_CDP" --url "http://127.0.0.1:$PORT_HTTP/index.html" --shots shots

echo
echo "生成展示图…"
"$PY" make_assets.py --shots shots --out .
echo
echo "完成。截图在 shots/，动图在 demo.gif"
