#!/usr/bin/env bash
# Автозагрузка проекта на ваш GitHub. Использование:
#   GITHUB_USER=ваш_логин GH_TOKEN=github_pat_... ./push-to-github.sh [имя_репо]
set -euo pipefail

: "${GITHUB_USER:?Укажите GITHUB_USER (логин на github.com)}"
: "${GH_TOKEN:?Укажите GH_TOKEN (Personal Access Token с правом repo)}"
REPO="${1:-vpn-telegram-support}"
API="https://api.github.com"
AUTH="Authorization: Bearer ${GH_TOKEN}"

echo "==> Проверка токена..."
LOGIN=$(curl -sf -H "$AUTH" "$API/user" | python3 -c 'import sys,json;print(json.load(sys.stdin)["login"])')
echo "    Авторизован как: ${LOGIN}"

echo "==> Создание репозитория ${GITHUB_USER}/${REPO} (если ещё нет)..."
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH" "$API/repos/${GITHUB_USER}/${REPO}")
if [ "$CODE" = "404" ]; then
  curl -sf -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"name\":\"${REPO}\",\"private\":false,\"description\":\"Telegram Mini App: VPN support tickets with admin panel and bot chat\"}" \
    "$API/user/repos" > /dev/null
  echo "    Репозиторий создан."
else
  echo "    Репозиторий уже существует (HTTP ${CODE})."
fi

echo "==> Push кода..."
cd "$(dirname "$0")"
git init -q
git add -A
git -c user.name="${LOGIN}" -c user.email="${LOGIN}@users.noreply.github.com" \
    commit -qm "VPN Telegram support: mini app, bot, admin panel, deploy docs" || true
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_USER}/${REPO}.git"
git push -q -f origin main
git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO}.git"  # убрать токен из .git/config

echo ""
echo "✅ Готово! https://github.com/${GITHUB_USER}/${REPO}"
