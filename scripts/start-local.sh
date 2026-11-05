#!/bin/bash
# Запускать из обычного Терминала macOS. Токен читается только из .env.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v cloudflared >/dev/null 2>&1; then
  echo 'Сначала установи Cloudflare Tunnel: brew install cloudflared'
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo 'Создан .env. Вставь токен после BOT_TOKEN= и запусти скрипт повторно.'
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
PYTHON=.venv/bin/python

# Проверяем наличие токена до установки пакетов, не выводя его в терминал.
"$PYTHON" - <<'PY'
from pathlib import Path

values = {}
for line in Path('.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('\"\x27')
if not values.get('BOT_TOKEN'):
    raise SystemExit('Вставь токен бота после BOT_TOKEN= в .env и сохрани файл.')
PY

if ! "$PYTHON" -c 'import aiogram, aiohttp, dotenv, pig_tamagotchi' 2>/dev/null; then
  "$PYTHON" -m pip install -e .
fi

mkdir -p data
TUNNEL_LOG="$PWD/data/cloudflared.log"
TUNNEL_PID=''
BOT_PID=''
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$BOT_PID" ]; then kill "$BOT_PID" 2>/dev/null || true; fi
  if [ -n "$TUNNEL_PID" ]; then kill "$TUNNEL_PID" 2>/dev/null || true; fi
  if [ -n "$BOT_PID" ]; then wait "$BOT_PID" 2>/dev/null || true; fi
  if [ -n "$TUNNEL_PID" ]; then wait "$TUNNEL_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

PORT=${PORT:-8080}
echo 'Получаю временный HTTPS-адрес…'
cloudflared tunnel --url "http://127.0.0.1:$PORT" \
  --protocol "${TUNNEL_PROTOCOL:-http2}" --no-autoupdate >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
WEBAPP_URL=''
TUNNEL_READY=false
for ((attempt = 0; attempt < 90; attempt++)); do
  WEBAPP_URL=$("$PYTHON" - "$TUNNEL_LOG" <<'PY'
import re
import sys
from pathlib import Path

urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', Path(sys.argv[1]).read_text())
print(urls[0] if urls else '')
PY
)
  if [ -n "$WEBAPP_URL" ] && grep -q 'Registered tunnel connection' "$TUNNEL_LOG"; then
    TUNNEL_READY=true
    break
  fi
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    cat "$TUNNEL_LOG"
    exit 1
  fi
  sleep 1
done

if [ "$TUNNEL_READY" != true ]; then
  echo 'Туннель не подключился к Cloudflare. Проверь подключение к интернету.'
  echo "Журнал ошибок: $TUNNEL_LOG"
  cat "$TUNNEL_LOG"
  exit 1
fi

# Переменные процесса имеют приоритет над .env: адрес всегда актуальный.
export WEBAPP_URL PORT
export DEMO_MODE=false HOST=127.0.0.1
echo 'Туннель подключён к Cloudflare.'
echo "Адрес мини-приложения: $WEBAPP_URL"
echo 'Запускаю бота. После запуска отправь ему /start в Telegram.'
echo 'Оставь Терминал открытым. Для остановки нажми Ctrl+C.'
"$PYTHON" -m pig_tamagotchi &
BOT_PID=$!
while kill -0 "$BOT_PID" 2>/dev/null; do
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "Туннель завершился. Журнал: $TUNNEL_LOG"
    tail -n 20 "$TUNNEL_LOG"
    exit 1
  fi
  sleep 2
done
wait "$BOT_PID"
