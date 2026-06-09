# 📱 Telegram Блокнот-Бот

Бот с личным блокнотом для каждого пользователя и панелью администратора.

---

## 🚀 Деплой на Fly.io

### Шаг 1 — Создай бота в Telegram

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Напиши `/newbot`
3. Придумай имя и username (должен оканчиваться на `bot`)
4. Скопируй **токен** — выглядит так: `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx`

---

### Шаг 2 — Узнай свой Telegram ID

1. Открой [@userinfobot](https://t.me/userinfobot) и напиши `/start`
2. Скопируй своё `Id` (просто цифры, например `123456789`)

---

### Шаг 3 — Установи flyctl

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

---

### Шаг 4 — Войди в аккаунт

```bash
fly auth login
```

---

### Шаг 5 — Создай приложение и том для данных

```bash
# В папке с проектом:
fly launch --name telegram-bot --region fra --no-deploy

# Создай persistent volume (хранит data.json между перезапусками)
fly volumes create bot_data --region fra --size 1
```

> Если имя `telegram-bot` уже занято, выбери любое уникальное.

---

### Шаг 6 — Установи секреты

```bash
fly secrets set BOT_TOKEN="твой_токен_от_BotFather"
fly secrets set ADMIN_ID="твой_telegram_id"
```

---

### Шаг 7 — Задеплой

```bash
fly deploy
```

Бот запустится автоматически! Проверь логи:

```bash
fly logs
```

---

## 🔄 Обновление бота

После изменений в коде просто:

```bash
fly deploy
```

---

## 🔧 Локальный запуск (для теста на ПК)

```bash
pip install -r requirements.txt
export BOT_TOKEN="твой_токен"
export ADMIN_ID="твой_id"
python bot.py
```

На Windows вместо `export` используй:
```cmd
set BOT_TOKEN=твой_токен
set ADMIN_ID=твой_id
python bot.py
```

---

## 👤 Что умеет пользователь

| Действие | Описание |
|---|---|
| 📋 Мой блокнот | Просмотр всех своих данных |
| ✏️ Редактировать данные | Изменить имя, телефон, задачи |
| 📋 Мои задачи | Список задач с отметкой выполнения |

---

## 👑 Что умеет админ

| Действие | Описание |
|---|---|
| 👥 Все пользователи | Список всех, нажми на любого — увидишь его блокнот |
| ✉️ Написать менеджеру | Выбери пользователя и напиши ему прямо из бота |
| 📢 Рассылка | Отправить сообщение сразу всем |

---

## 📁 Структура файлов

```
tg_bot/
├── bot.py            # Основной код бота
├── requirements.txt  # Зависимости Python
├── Dockerfile        # Образ для fly.io
├── fly.toml          # Конфиг fly.io
└── README.md
```
