# 🛡️ VPN Support — Telegram Mini App + бот поддержки

Мини-приложение для приёма обращений по техническим вопросам VPN, Telegram-бот
для переписки с клиентами и веб-панель оператора для просмотра тикетов.

## Как это работает

1. **Клиент** открывает бота → жмёт «🆘 Создать тикет» → открывается **Mini App**
   с формой (устройство, тема проблемы, описание). Отправка защищена валидацией
   `initData` (HMAC-SHA256), поэтому тикет нельзя создать «с стороны».
2. **Вы (админ)** получаете уведомление о новом тикете прямо в личку боту.
3. Переписка возможна двумя способами:
   - **В чате бота**: клиент пишет обычные сообщения — они падают в его тикет;
     вы отвечаете командами `/msg T-XXXXX текст`.
   - **В веб-панели** `https://ваш-домен/admin`: список тикетов с фильтрами по
     статусам, живой чат (polling каждые 2.5 сек), кнопки «в работу» / «решён».
4. Клиент может закрыть тикет кнопкой «✅ Проблема решена» или «✖️ Отменить».

Структура проекта:

```
vpn-support/
├── bot/
│   ├── main.py        # aiogram-бот (пользователь + админ команды)
│   ├── web_server.py  # FastAPI: mini app, API тикетов, панель оператора
│   └── db.py          # SQLite: тикеты и сообщения
├── web/
│   ├── index.html     # форма создания тикета (Telegram WebApp)
│   └── admin.html     # панель оператора
├── requirements.txt
├── .env.example
└── DEPLOY-VPS.md    # подробная инструкция по запуску на VPS (Ubuntu + nginx + certbot + systemd)
```

## 🚀 Запуск на VPS

Полная пошаговая инструкция — в **[DEPLOY-VPS.md](DEPLOY-VPS.md)**: установка пакетов,
домен и HTTPS (Let's Encrypt), nginx, firewall, автозапуск через systemd, привязка
Mini App в BotFather, проверка, обновления, бэкапы и разбор частых проблем.

## Установка

```bash
cd vpn-support
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # и заполните значения
python bot/main.py
```

### Настройка Telegram

1. **@BotFather** → `/newbot` → получите токен → в `.env` как `BOT_TOKEN`.
2. Узнайте свой user id (напишите **@userinfobot**) → `ADMIN_ID`.
3. `APP_SECRET` — любая длинная случайная строка (`openssl rand -hex 32`).
4. Разверните сервер на VPS с **HTTPS** (обязательно для Mini App). Пример nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.ru;
    ssl_certificate     /etc/letsencrypt/live/your-domain.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.ru/privkey.pem;
    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
}
```

5. В **.env**: `WEB_APP_URL=https://your-domain.ru`.
6. Запустите `python bot/main.py` (бот и веб-сервер стартуют вместе).
7. **@BotFather** → ваш бот → Bot Settings → Menu Button → *Configure menu button*
   → укажите `https://your-domain.ru` — тогда «🆘 Создать тикет» будет и в меню ввода.

## Команды админа (в чате бота)

| Команда | Действие |
|---|---|
| `/tickets [статус]` | список тикетов (+ счётчики); статус: open/in_progress/closed… |
| `/open <id>` | карточка тикета и последние сообщения |
| `/msg <id> <текст>` | ответить клиенту (доставится ему в чат) |
| `/progress <id>` | взять в работу |
| `/close <id>` | закрыть как решённый |
| `/history <id>` | вся переписка |

Панель оператора: `https://your-domain.ru/admin` — пароль = `ADMIN_PANEL_TOKEN`
(или `APP_SECRET`, если первый не задан).

## Безопасность (перед реальным запуском)

- Панель `/admin` защищена только токеном-паролем — держайте её за HTTPS и
  не публикуйте ссылку; для продакшена добавьте нормальную авторизацию.
- Все запросы из мини-приложения проходят валидацию `initData` — подделать
  пользователя со стороны нельзя.
- База — локальный `tickets.db`; делайте резервные копии.
