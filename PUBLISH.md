# Публикация проекта на GitHub

Инструкция рассчитана на первый публикацию этого репозитория. Все команды — из
корня проекта (там, где лежит папка `vpn-support/`).

## 1. Убедись, что в истории нет секретов

В репозиторий уже добавлены `.gitignore` (исключает `.env`, базу `tickets.db`,
кэш Python). Проверь, что настоящий `BOT_TOKEN` / `APP_SECRET` нигде не
закоммичены:

```bash
git ls-files | grep -E "\.env$|\.db$"   # ничего не должно вывести
grep -rn "BOT_TOKEN=" vpn-support --include="*.py"
```

Если секрет всё же попал в коммит — удали его из истории через
`git filter-repo` или создай новый репозиторий с чистой историей, и обязательно
**отзови скомпрометированный токен** у @BotFather (`/revoke`).

## 2. Создай репозиторий на GitHub

1. Зайди на https://github.com/new
2. Имя, например: `vpn-telegram-support`
3. **Private** — если планируешь хранить здесь приватную конфигурацию, иначе Public
4. Не ставь галочку «Add a README» (он уже есть) → **Create repository**

Или через CLI ([gh](https://cli.github.com/)):

```bash
gh repo create vpn-telegram-support --private --source=. --push
# и готово — можно пропустить шаг 3
```

## 3. Настрой git (если ещё не настроен)

```bash
git config --global user.name  "Твоё Имя"
git config --global user.email "твой@email.ru"
```

## 4. Добавь удалённый репозиторий и запушь

Подставь своё имя пользователя и название репо:

```bash
git remote add origin https://github.com/<username>/vpn-telegram-support.git
git branch -M main
git push -u origin main
```

Для публичного репозитория GitHub спросит логин и **Personal Access Token**
(пароль от аккаунта не подходит). Получить: Settings → Developer settings →
Personal access tokens → Fine-grained token с правом *Contents: Read & write*.
Либо настрой SSH-ключ и используй адрес `git@github.com:<username>/<repo>.git`.

## 5. Проверь

Открой `https://github.com/<username>/vpn-telegram-support` — должны быть видны:
`README.md`, `LICENSE`, `PUBLISH.md`, папка `vpn-support/` со всем кодом,
`.env.example` (но не `.env`).

## 6. Дальнейшие изменения

```bash
git add -A
git commit -m "что изменил"
git push
```

На VPS обновления подтягиваются командой `git pull` (см. `vpn-support/DEPLOY-VPS.md`,
раздел «Обновления»).

## 7. (Опционально) Сделай проект красивым для других

- Добавь описание: репозиторий → About → Edit: «Telegram Mini App + bot for VPN tech support»
- Теги: `telegram`, `mini-app`, `aiogram`, `fastapi`, `support`, `vpn`
- Если проект публичный — в README можно добавить скриншоты панели `/admin` и мини-аппа.
