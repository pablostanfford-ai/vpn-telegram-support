# VPN Support — Telegram Mini App для техподдержки

Мини-приложение + aiogram-бот + веб-панель оператора для приёма и решения
технических обращений по VPN.

## Возможности

- 🆘 Клиент создаёт тикет через Telegram Mini App (устройство, тема, описание),
  отправка защищена валидацией `initData` (HMAC-SHA256)
- 💬 Переписка: сообщения клиента падают в тикет, админ отвечает командами
  `/msg T-XXXXX текст`, либо прямо из веб-панели
- 🗂️ Панель оператора `/admin`: список тикетов с фильтрами по статусам,
  живой чат, перевод статусов «открыт → в работу → решён»
- 🤖 Уведомления о новых тикетах админу в личку бота
- 💾 Хранилище — SQLite (одним файлом)

## Структура

```
vpn-support/          # всё приложение
├── bot/              # aiogram-бот, БД, FastAPI-сервер
├── web/              # mini app (index.html) и панель (admin.html)
├── README.md         # подробная документация проекта
├── DEPLOY-VPS.md     # пошаговый деплой на VPS (Ubuntu/Debian, nginx, HTTPS, systemd)
└── .env.example      # шаблон конфигурации
PUBLISH.md            # как опубликовать этот репозиторий на GitHub
LICENSE               # MIT
```

## Быстрый старт

```bash
cd vpn-support
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # заполнить BOT_TOKEN, ADMIN_ID, APP_SECRET
uvicorn bot.web_server:app --host 0.0.0.0 --port 8000 &
python -m bot.main
```

Полная инструкция по серверу: [vpn-support/DEPLOY-VPS.md](vpn-support/DEPLOY-VPS.md).
Публикация на GitHub: [PUBLISH.md](PUBLISH.md).

## Лицензия

MIT — см. [LICENSE](LICENSE).