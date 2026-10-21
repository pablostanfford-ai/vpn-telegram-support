# 🚀 Запуск на VPS — пошаговая инструкция

Рассчитана на **Ubuntu 22.04 / 24.04** (Debian 12 тоже подойдёт). От вас потребуется:
- VPS с публичным IP (любой, от ~2 CPU/1 ГБ RAM хватит);
- домен, у которого **A-запись** указывает на IP сервера (Telegram требует HTTPS, а значит домен обязателен);
- 15–20 минут времени.

---

## Шаг 0. Подключитесь к серверу

```bash
ssh root@ВАШ_IP
```

Дальше все команды выполняются на сервере. Если вы не под root, добавьте `sudo` перед командами установки.

Обновите систему и поставьте нужные пакеты:

```bash
apt update && apt upgrade -y
apt install -y git python3 python3-venv python3-pip nginx certbot python3-certbot-nginx ufw
```

> В Ubuntu 24.04 venv ставится отдельно: `apt install -y python3.12-venv`

---

## Шаг 1. Загрузите проект на сервер

**Вариант А — из Git-репозитория** (если ваш код лежит в GitHub/GitLab):

```bash
cd /opt
git clone https://github.com/ВАШ_ЛОГИН/ВАШ_РЕПО.git vpn-support
# если проект в папке внутри репо:
# cp -r ВАШ_РЕПО/vpn-support /opt/vpn-support && rm -rf ВАШ_РЕПО
```

**Вариант Б — скопировать файлы с компьютера** (откройте терминал на своём ПК, не на сервере):

```bash
scp -r vpn-support root@ВАШ_IP:/opt/
```

Итог: проект лежит в `/opt/vpn-support`.

---

## Шаг 2. Создайте пользователя и виртуальное окружение

Не запускаем бота от root — создадим отдельного пользователя:

```bash
adduser --disabled-password --gecos "" vpnsupport
mkdir -p /opt/vpn-support-data
chown -R vpnsupport:vpnsupport /opt/vpn-support /opt/vpn-support-data

su - vpnsupport
cd /opt/vpn-support
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
exit   # вернуться к root
```

---

## Шаг 3. Настройте `.env`

```bash
cp /opt/vpn-support/.env.example /opt/vpn-support/.env
nano /opt/vpn-support/.env
```

Заполните:

| Переменная | Что вписать |
|---|---|
| `BOT_TOKEN` | токен от **@BotFather** (`/newbot`) |
| `ADMIN_ID` | ваш числовой Telegram ID (узнать у **@userinfobot**) |
| `APP_SECRET` | сгенерируйте: `openssl rand -hex 32` (выполнить в другом терминале) |
| `WEB_APP_URL` | `https://ваш-домен.ru` — **без слэша на конце** |
| `PORT` | `8000` (можно оставить как есть) |

Сохраните в nano: `Ctrl+O`, Enter, `Ctrl+X`. Затем:

```bash
chown vpnsupport:vpnsupport /opt/vpn-support/.env
chmod 600 /opt/vpn-support/.env
```

---

## Шаг 4. Домен и HTTPS (обязательно для Mini App)

1. В панели регистратора/хостинга добавьте **A-запись**: `ваш-домен.ru → ВАШ_IP`
   (и при желании `www`). Подождите 5–30 минут, проверьте: `ping ваш-домен.ru`.

2. Первичный конфиг nginx:

```bash
cat > /etc/nginx/sites-available/vpn-support <<'EOF'
server {
    listen 80;
    server_name ваш-домен.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/vpn-support /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

3. Получите бесплатный сертификат Let's Encrypt (certbot сам перевпишет nginx на HTTPS):

```bash
certbot --nginx -d ваш-домен.ru --redirect -m ваш@email.ru --agree-tos
```

Проверка: откройте в браузере `https://ваш-домен.ru` — должна быть заглушка/форма мини-приложения (пока без Telegram), без ошибок сертификата.

> ⚠️ Certbot автоматически настроит автопродление. Проверить: `systemctl list-timers | grep certbot`.

---

## Шаг 5. Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

Приложение слушает только `127.0.0.1:8000` через nginx — наружу порты 8000 открывать не нужно.

---

## Шаг 6. Автозапуск через systemd

```bash
cat > /etc/systemd/system/vpn-support.service <<'EOF'
[Unit]
Description=VPN Support bot + mini app
After=network-online.target

[Service]
Type=simple
User=vpnsupport
WorkingDirectory=/opt/vpn-support
Environment=DB_PATH=/opt/vpn-support-data/tickets.db
ExecStart=/opt/vpn-support/.venv/bin/python bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now vpn-support
```

Полезные команды:

```bash
systemctl status vpn-support      # состояние
journalctl -u vpn-support -f      # живые логи (Ctrl+C — выйти)
systemctl restart vpn-support     # перезапуск после изменений .env
```

> База `tickets.db` лежит в `/opt/vpn-support-data/` (вне кода) — удобно бэкапить и переживать обновления проекта.

---

## Шаг 7. Привяжите Mini App к боту в BotFather

1. **@BotFather** → `/mybots` → ваш бот → **Bot Settings** → **Menu Button** →
   *Configure menu button* → введите URL: `https://ваш-домен.ru`
   (название кнопки, например «🆘 Поддержка»).
2. Теперь у клиентов кнопка мини-приложения появится прямо в поле ввода чата,
   плюс она уже есть в меню бота («🆘 Создать тикет»).

---

## Шаг 8. Проверка

1. Откройте бота в Telegram → нажмите «🆘 Создать тикет» → форма должна открыться внутри Telegram.
2. Отправьте тестовый тикет → вам (ADMIN_ID) придёт уведомление.
3. В чате бота: `/tickets` — увидите список; `/msg T-XXXXX Привет!` — клиент получит ответ.
4. Панель оператора: `https://ваш-домен.ru/admin` → пароль = значение `ADMIN_PANEL_TOKEN`
   (или `APP_SECRET`, если первый не задан). Там живой чат и кнопки статусов.
5. Закройте тикет кнопкой клиента или `/close T-XXXXX`.

---

## Обновление проекта

```bash
cd /opt/vpn-support
sudo -u vpnsupport git pull            # вариант с git (файлы .env и tickets.db не трогаются)
sudo -u vpnsupport .venv/bin/pip install -r requirements.txt
systemctl restart vpn-support
```

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| Mini App не открывается / «Failed too long» | Нет валидного HTTPS или домен не совпадает с `WEB_APP_URL`; проверьте `certbot certificates` и A-запись |
| Ошибка валидации initData | `APP_SECRET` на сервере должен совпадать с тем, что привязан к домену; URL в BotFather и `WEB_APP_URL` должны быть идентичны |
| Тикеты не приходят админу | Неверный `ADMIN_ID` (нужен числовой ID, не @username); смотрите `journalctl -u vpn-support -e` |
| 502 Bad Gateway | Бот не запущен: `systemctl status vpn-support`, затем `journalctl -u vpn-support -n 50` |
| Порт 80 занят другой программой | `ss -ltnp \| grep :80` — остановите конфликтующий сервис или поменяйте конфиг |
| После ребута сервера ничего не работает | Должно работать само (systemd `enable`); проверьте `systemctl is-enabled vpn-support nginx` |

## Бэкапы

```bash
# дамп базы (sqlite может горячо копироваться через .backup):
sudo -u vpnsupport /opt/vpn-support/.venv/bin/python -c "import sqlite3; s=sqlite3.connect('/opt/vpn-support-data/tickets.db'); d=sqlite3.connect('/root/backup-$(date +%F).db'); s.backup(d); d.close()"
```

Копию `.env` храните в надёжном месте — там токен бота.
