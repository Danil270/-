import logging
import json
import os
import time
import signal
import sys
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "0"))
DB_FILE    = os.environ.get("DB_FILE", "data.json")

# ── States ───────────────────────────────────────────────────────────────────
(
    MAIN_MENU,
    # Account management
    ADD_ACCOUNT_NAME,
    # Client management
    SELECT_ACCOUNT_FOR_CLIENT, ADD_CLIENT_NAME, ADD_CLIENT_PHONE,
    ADD_CLIENT_INFO, ADD_CLIENT_TASKS,
    # Edit client
    EDIT_CLIENT_MENU, EDIT_CLIENT_NAME, EDIT_CLIENT_PHONE,
    EDIT_CLIENT_INFO, ADD_CLIENT_TASK, DELETE_CLIENT_TASK,
    # Admin
    ADMIN_MENU, ADMIN_WRITE_MSG, BROADCAST_MSG,
    # Edit client via button flow
    EDIT_SELECT_ACCOUNT, EDIT_SELECT_CLIENT, EDIT_FIELD_VALUE,
) = range(19)

# ── DB helpers ────────────────────────────────────────────────────────────────
def load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(db: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(db: dict, uid: int) -> dict:
    key = str(uid)
    if key not in db:
        db[key] = {
            "id": uid,
            "username": "",
            "full_name": "",
            "accounts": [],
            "registered_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
    db[key]["last_active"] = datetime.now().isoformat()
    if "accounts" not in db[key]:
        db[key]["accounts"] = []
    return db[key]

# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup(
        [
            ["📋 Мой блокнот"],
            ["👤 Добавить аккаунт", "➕ Добавить клиента"],
            ["✏️ Редактировать клиента"],
            ["🗑 Удалить аккаунт"],
        ],
        resize_keyboard=True,
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        [["👥 Все пользователи"], ["✉️ Написать менеджеру"], ["📢 Рассылка"]],
        resize_keyboard=True,
    )

def back_kb():
    return ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = load_db()
    u = get_user(db, user.id)
    u["username"]  = user.username or ""
    u["full_name"] = user.full_name or ""
    save_db(db)

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            "👑 Добро пожаловать, Админ!\n\nВыберите действие:",
            reply_markup=admin_kb(),
        )
        return ADMIN_MENU

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Это твой блокнот для работы с клиентами.\n\n"
        "• Создай аккаунт (например «Миша» или «Саша»)\n"
        "• Добавляй клиентов к каждому аккаунту\n"
        "• Веди заметки и задачи по каждому клиенту\n\n"
        "Выбери действие 👇",
        reply_markup=main_kb(),
    )
    return MAIN_MENU

# ═════════════════════════════════════════════════════════════════════════════
# NOTEBOOK
# ═════════════════════════════════════════════════════════════════════════════
async def show_notebook(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    accounts = u.get("accounts", [])

    if not accounts:
        await update.message.reply_text(
            "📓 Блокнот пуст.\n\nДобавь аккаунт кнопкой «👤 Добавить аккаунт».",
            reply_markup=main_kb(),
        )
        return MAIN_MENU

    lines = ["📓 *Твой блокнот*\n"]
    for ai, acc in enumerate(accounts):
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"👤 *Аккаунт: {acc['name']}*")
        clients = acc.get("clients", [])
        if not clients:
            lines.append("  _(клиентов нет)_")
        else:
            for ci, cl in enumerate(clients):
                lines.append(f"\n  📌 *Клиент {ci+1}: {cl.get('name','—')}*")
                lines.append(f"  📞 Телефон: {cl.get('phone','—')}")
                lines.append(f"  ℹ️ Инфо: {cl.get('info','—')}")
                tasks = cl.get("tasks", [])
                if tasks:
                    lines.append("  📋 Задачи:")
                    for ti, t in enumerate(tasks):
                        icon = "✅" if t.get("done") else "⬜"
                        lines.append(f"    {icon} {ti+1}. {t['text']}")
                else:
                    lines.append("  📋 Задачи: —")
        lines.append("")

    text = "\n".join(lines)

    if len(text) <= 4096:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb())
    else:
        chunks = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > 4000:
                chunks.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            chunks.append(current)
        for i, chunk in enumerate(chunks):
            kb = main_kb() if i == len(chunks) - 1 else None
            await update.message.reply_text(chunk, parse_mode="Markdown", reply_markup=kb)

    return MAIN_MENU

# ═════════════════════════════════════════════════════════════════════════════
# ADD ACCOUNT
# ═════════════════════════════════════════════════════════════════════════════
async def add_account_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введи название аккаунта (например: «Миша», «Саша», «Работа»):",
        reply_markup=back_kb(),
    )
    return ADD_ACCOUNT_NAME

async def add_account_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Попробуй снова:")
        return ADD_ACCOUNT_NAME
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    u["accounts"].append({"name": name, "clients": []})
    save_db(db)
    await update.message.reply_text(
        f"✅ Аккаунт *{name}* создан!\n\nТеперь добавь клиентов через «➕ Добавить клиента».",
        parse_mode="Markdown",
        reply_markup=main_kb(),
    )
    return MAIN_MENU

# ═════════════════════════════════════════════════════════════════════════════
# DELETE ACCOUNT
# ═════════════════════════════════════════════════════════════════════════════
async def delete_account_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    accounts = u.get("accounts", [])
    if not accounts:
        await update.message.reply_text("Аккаунтов нет.", reply_markup=main_kb())
        return MAIN_MENU
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🗑 {acc['name']}", callback_data=f"delacc_{ai}")]
        for ai, acc in enumerate(accounts)
    ])
    await update.message.reply_text("Какой аккаунт удалить? (вместе со всеми клиентами)", reply_markup=kb)
    return MAIN_MENU

# ═════════════════════════════════════════════════════════════════════════════
# ADD CLIENT — step by step
# ═════════════════════════════════════════════════════════════════════════════
async def add_client_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    accounts = u.get("accounts", [])
    if not accounts:
        await update.message.reply_text(
            "Сначала создай аккаунт кнопкой «👤 Добавить аккаунт».",
            reply_markup=main_kb(),
        )
        return MAIN_MENU
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 {acc['name']}", callback_data=f"selaccount_{ai}")]
        for ai, acc in enumerate(accounts)
    ])
    await update.message.reply_text("К какому аккаунту добавить клиента?", reply_markup=kb)
    return SELECT_ACCOUNT_FOR_CLIENT

async def client_account_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ai = int(q.data.split("_")[1])
    ctx.user_data["new_client_account_idx"] = ai
    ctx.user_data["new_client"] = {}
    await q.message.reply_text("Введи имя клиента:", reply_markup=back_kb())
    return ADD_CLIENT_NAME

async def add_client_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        ctx.user_data.clear()
        return MAIN_MENU
    ctx.user_data["new_client"]["name"] = update.message.text.strip()
    await update.message.reply_text("Введи номер телефона (или напиши «-» если нет):", reply_markup=back_kb())
    return ADD_CLIENT_PHONE

async def add_client_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        ctx.user_data.clear()
        return MAIN_MENU
    val = update.message.text.strip()
    ctx.user_data["new_client"]["phone"] = "" if val == "-" else val
    await update.message.reply_text("Введи информацию о клиенте (или «-»):", reply_markup=back_kb())
    return ADD_CLIENT_INFO

async def add_client_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        ctx.user_data.clear()
        return MAIN_MENU
    val = update.message.text.strip()
    ctx.user_data["new_client"]["info"] = "" if val == "-" else val
    await update.message.reply_text(
        "Введи задачи по клиенту — *каждую с новой строки*.\n"
        "Или напиши «-» если задач пока нет:",
        parse_mode="Markdown",
        reply_markup=back_kb(),
    )
    return ADD_CLIENT_TASKS

async def add_client_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        ctx.user_data.clear()
        return MAIN_MENU
    val = update.message.text.strip()
    if val == "-":
        tasks = []
    else:
        tasks = [
            {"text": line.strip(), "done": False, "created_at": datetime.now().isoformat()}
            for line in val.splitlines() if line.strip()
        ]
    ctx.user_data["new_client"]["tasks"] = tasks

    db  = load_db()
    u   = get_user(db, update.effective_user.id)
    ai  = ctx.user_data.get("new_client_account_idx", 0)
    cl  = ctx.user_data["new_client"]
    if ai < len(u["accounts"]):
        u["accounts"][ai]["clients"].append(cl)
        save_db(db)
        acc_name = u["accounts"][ai]["name"]
        await update.message.reply_text(
            f"✅ Клиент *{cl['name']}* добавлен в аккаунт *{acc_name}*!\n\n"
            "Нажми «📋 Мой блокнот» чтобы посмотреть.",
            parse_mode="Markdown",
            reply_markup=main_kb(),
        )
    else:
        await update.message.reply_text("Ошибка: аккаунт не найден.", reply_markup=main_kb())

    ctx.user_data.clear()
    return MAIN_MENU

# ═════════════════════════════════════════════════════════════════════════════
# ✏️ РЕДАКТИРОВАТЬ КЛИЕНТА — новый flow через кнопку в главном меню
# ═════════════════════════════════════════════════════════════════════════════
async def edit_client_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: показываем список аккаунтов кнопками"""
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    accounts = u.get("accounts", [])

    if not accounts:
        await update.message.reply_text("Аккаунтов нет. Сначала создай аккаунт.", reply_markup=main_kb())
        return MAIN_MENU

    # Проверяем, есть ли хоть один клиент
    has_clients = any(acc.get("clients") for acc in accounts)
    if not has_clients:
        await update.message.reply_text("Клиентов ещё нет. Сначала добавь клиента.", reply_markup=main_kb())
        return MAIN_MENU

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 {acc['name']} ({len(acc.get('clients',[]))} кл.)",
                              callback_data=f"editacc_{ai}")]
        for ai, acc in enumerate(accounts)
        if acc.get("clients")
    ])
    await update.message.reply_text("Выбери аккаунт:", reply_markup=kb)
    return EDIT_SELECT_ACCOUNT

async def edit_select_account_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: показываем клиентов выбранного аккаунта кнопками"""
    q = update.callback_query
    await q.answer()
    ai = int(q.data.split("_")[1])
    ctx.user_data["edit_ai"] = ai

    db = load_db()
    u  = get_user(db, q.from_user.id)
    try:
        acc = u["accounts"][ai]
    except IndexError:
        await q.message.reply_text("Ошибка: аккаунт не найден.", reply_markup=main_kb())
        return MAIN_MENU

    clients = acc.get("clients", [])
    if not clients:
        await q.message.reply_text("В этом аккаунте нет клиентов.", reply_markup=main_kb())
        return MAIN_MENU

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📌 {cl.get('name','—')}", callback_data=f"editcl_{ai}_{ci}")]
        for ci, cl in enumerate(clients)
    ])
    await q.message.reply_text(f"Выбери клиента из аккаунта «{acc['name']}»:", reply_markup=kb)
    return EDIT_SELECT_CLIENT

async def edit_select_client_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: показываем карточку клиента с кнопками изменить поля"""
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    ai, ci = int(parts[1]), int(parts[2])
    ctx.user_data["edit_ai"] = ai
    ctx.user_data["edit_ci"] = ci

    db = load_db()
    u  = get_user(db, q.from_user.id)
    try:
        acc = u["accounts"][ai]
        cl  = acc["clients"][ci]
    except (IndexError, KeyError):
        await q.message.reply_text("Ошибка: клиент не найден.", reply_markup=main_kb())
        return MAIN_MENU

    text = (
        f"✏️ *Редактирование клиента*\n\n"
        f"👤 Аккаунт: {acc['name']}\n"
        f"📌 Имя: {cl.get('name','—')}\n"
        f"📞 Телефон: {cl.get('phone','—')}\n"
        f"ℹ️ Инфо: {cl.get('info','—')}\n\n"
        f"Выбери что изменить:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Изменить имя",     callback_data=f"chfield_{ai}_{ci}_name"),
         InlineKeyboardButton("📞 Изменить телефон", callback_data=f"chfield_{ai}_{ci}_phone")],
        [InlineKeyboardButton("ℹ️ Изменить инфо",    callback_data=f"chfield_{ai}_{ci}_info")],
        [InlineKeyboardButton("🔙 Назад к списку",   callback_data=f"editacc_{ai}")],
    ])
    await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return EDIT_SELECT_CLIENT

async def edit_choose_field_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Шаг 4: пользователь нажал «Изменить имя/телефон/инфо»"""
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    ai, ci, field = int(parts[1]), int(parts[2]), parts[3]
    ctx.user_data["edit_ai"]    = ai
    ctx.user_data["edit_ci"]    = ci
    ctx.user_data["edit_field"] = field

    field_names = {"name": "имя", "phone": "телефон", "info": "информацию"}
    await q.message.reply_text(
        f"Введи новое {field_names.get(field, field)} клиента:\n\n"
        f"_(или нажми «🔙 Назад» чтобы отменить)_",
        parse_mode="Markdown",
        reply_markup=back_kb(),
    )
    return EDIT_FIELD_VALUE

async def edit_save_field(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Шаг 5: сохраняем новое значение и показываем обновлённую карточку"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        ctx.user_data.clear()
        return MAIN_MENU

    new_val = update.message.text.strip()
    ai    = ctx.user_data.get("edit_ai", 0)
    ci    = ctx.user_data.get("edit_ci", 0)
    field = ctx.user_data.get("edit_field", "name")

    db = load_db()
    u  = get_user(db, update.effective_user.id)
    try:
        cl = u["accounts"][ai]["clients"][ci]
        cl[field] = new_val
        save_db(db)

        acc_name = u["accounts"][ai]["name"]
        field_names = {"name": "Имя", "phone": "Телефон", "info": "Информация"}

        # Показываем обновлённую карточку
        text = (
            f"✅ *{field_names.get(field, field)} обновлено!*\n\n"
            f"👤 Аккаунт: {acc_name}\n"
            f"📌 Имя: {cl.get('name','—')}\n"
            f"📞 Телефон: {cl.get('phone','—')}\n"
            f"ℹ️ Инфо: {cl.get('info','—')}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить имя",     callback_data=f"chfield_{ai}_{ci}_name"),
             InlineKeyboardButton("📞 Изменить телефон", callback_data=f"chfield_{ai}_{ci}_phone")],
            [InlineKeyboardButton("ℹ️ Изменить инфо",    callback_data=f"chfield_{ai}_{ci}_info")],
            [InlineKeyboardButton("🏠 В главное меню",   callback_data="goto_main")],
        ])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    except (IndexError, KeyError):
        await update.message.reply_text("Ошибка при сохранении.", reply_markup=main_kb())
        ctx.user_data.clear()
        return MAIN_MENU

    return EDIT_SELECT_CLIENT

# ═════════════════════════════════════════════════════════════════════════════
# INLINE CALLBACKS (общий обработчик)
# ═════════════════════════════════════════════════════════════════════════════
async def inline_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    # ── Главное меню (кнопка из карточки редактирования) ──
    if data == "goto_main":
        ctx.user_data.clear()
        await q.message.reply_text("Главное меню:", reply_markup=main_kb())
        return MAIN_MENU

    # ── Выбор аккаунта при редактировании (из inline_handler) ──
    if data.startswith("editacc_"):
        ai = int(data.split("_")[1])
        ctx.user_data["edit_ai"] = ai
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            acc = u["accounts"][ai]
        except IndexError:
            await q.message.reply_text("Ошибка.", reply_markup=main_kb())
            return MAIN_MENU
        clients = acc.get("clients", [])
        if not clients:
            await q.message.reply_text("В этом аккаунте нет клиентов.", reply_markup=main_kb())
            return MAIN_MENU
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📌 {cl.get('name','—')}", callback_data=f"editcl_{ai}_{ci}")]
            for ci, cl in enumerate(clients)
        ])
        await q.message.reply_text(f"Выбери клиента из аккаунта «{acc['name']}»:", reply_markup=kb)
        return EDIT_SELECT_CLIENT

    # ── Выбор клиента для редактирования (из inline_handler) ──
    if data.startswith("editcl_"):
        parts = data.split("_")
        ai, ci = int(parts[1]), int(parts[2])
        ctx.user_data["edit_ai"] = ai
        ctx.user_data["edit_ci"] = ci
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            acc = u["accounts"][ai]
            cl  = acc["clients"][ci]
        except (IndexError, KeyError):
            await q.message.reply_text("Ошибка.", reply_markup=main_kb())
            return MAIN_MENU
        text = (
            f"✏️ *Редактирование клиента*\n\n"
            f"👤 Аккаунт: {acc['name']}\n"
            f"📌 Имя: {cl.get('name','—')}\n"
            f"📞 Телефон: {cl.get('phone','—')}\n"
            f"ℹ️ Инфо: {cl.get('info','—')}\n\n"
            f"Выбери что изменить:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить имя",     callback_data=f"chfield_{ai}_{ci}_name"),
             InlineKeyboardButton("📞 Изменить телефон", callback_data=f"chfield_{ai}_{ci}_phone")],
            [InlineKeyboardButton("ℹ️ Изменить инфо",    callback_data=f"chfield_{ai}_{ci}_info")],
            [InlineKeyboardButton("🔙 Назад к списку",   callback_data=f"editacc_{ai}")],
        ])
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return EDIT_SELECT_CLIENT

    # ── Выбор поля для изменения (из inline_handler) ──
    if data.startswith("chfield_"):
        parts = data.split("_")
        ai, ci, field = int(parts[1]), int(parts[2]), parts[3]
        ctx.user_data["edit_ai"]    = ai
        ctx.user_data["edit_ci"]    = ci
        ctx.user_data["edit_field"] = field
        field_names = {"name": "имя", "phone": "телефон", "info": "информацию"}
        await q.message.reply_text(
            f"Введи новое {field_names.get(field, field)} клиента:",
            reply_markup=back_kb(),
        )
        return EDIT_FIELD_VALUE

    # ── Delete account ──
    if data.startswith("delacc_"):
        ai  = int(data.split("_")[1])
        db  = load_db()
        u   = get_user(db, q.from_user.id)
        if ai < len(u["accounts"]):
            removed = u["accounts"].pop(ai)
            save_db(db)
            await q.message.reply_text(
                f"🗑 Аккаунт *{removed['name']}* удалён.",
                parse_mode="Markdown",
                reply_markup=main_kb(),
            )
        return MAIN_MENU

    # ── Account selected for new client ──
    if data.startswith("selaccount_"):
        ai = int(data.split("_")[1])
        ctx.user_data["new_client_account_idx"] = ai
        ctx.user_data["new_client"] = {}
        await q.message.reply_text("Введи имя клиента:", reply_markup=back_kb())
        return ADD_CLIENT_NAME

    # ── View client detail ──
    if data.startswith("viewclient_"):
        _, ai, ci = data.split("_")
        ai, ci = int(ai), int(ci)
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            acc = u["accounts"][ai]
            cl  = acc["clients"][ci]
        except (IndexError, KeyError):
            await q.message.reply_text("Клиент не найден.")
            return MAIN_MENU

        tasks = cl.get("tasks", [])
        tasks_text = "\n".join(
            f"  {'✅' if t.get('done') else '⬜'} {ti+1}. {t['text']}"
            for ti, t in enumerate(tasks)
        ) or "  —"

        text = (
            f"👤 *Аккаунт:* {acc['name']}\n"
            f"📌 *Клиент:* {cl.get('name','—')}\n"
            f"📞 *Телефон:* {cl.get('phone','—')}\n"
            f"ℹ️ *Инфо:* {cl.get('info','—')}\n\n"
            f"📋 *Задачи:*\n{tasks_text}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить имя",    callback_data=f"edn_{ai}_{ci}"),
             InlineKeyboardButton("📞 Изменить телефон", callback_data=f"edp_{ai}_{ci}")],
            [InlineKeyboardButton("ℹ️ Изменить инфо",   callback_data=f"edi_{ai}_{ci}")],
            [InlineKeyboardButton("➕ Добавить задачу",  callback_data=f"addt_{ai}_{ci}"),
             InlineKeyboardButton("🗑 Удалить задачу",   callback_data=f"delt_{ai}_{ci}")],
            [InlineKeyboardButton("🗑 Удалить клиента",  callback_data=f"delcl_{ai}_{ci}")],
            [InlineKeyboardButton("✅ Отметить задачи",  callback_data=f"togglemenu_{ai}_{ci}")],
        ])
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return MAIN_MENU

    # ── Delete client ──
    if data.startswith("delcl_"):
        _, ai, ci = data.split("_")
        ai, ci = int(ai), int(ci)
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            removed = u["accounts"][ai]["clients"].pop(ci)
            save_db(db)
            await q.message.reply_text(f"🗑 Клиент *{removed['name']}* удалён.", parse_mode="Markdown")
        except (IndexError, KeyError):
            await q.message.reply_text("Ошибка.")
        return MAIN_MENU

    # ── Edit client fields (из viewclient) ──
    if data.startswith("edn_"):
        _, ai, ci = data.split("_")
        ctx.user_data["edit_ai"] = int(ai)
        ctx.user_data["edit_ci"] = int(ci)
        ctx.user_data["edit_field"] = "name"
        await q.message.reply_text("Введи новое имя клиента:", reply_markup=back_kb())
        return EDIT_CLIENT_NAME

    if data.startswith("edp_"):
        _, ai, ci = data.split("_")
        ctx.user_data["edit_ai"] = int(ai)
        ctx.user_data["edit_ci"] = int(ci)
        await q.message.reply_text("Введи новый телефон:", reply_markup=back_kb())
        return EDIT_CLIENT_PHONE

    if data.startswith("edi_"):
        _, ai, ci = data.split("_")
        ctx.user_data["edit_ai"] = int(ai)
        ctx.user_data["edit_ci"] = int(ci)
        await q.message.reply_text("Введи новую информацию:", reply_markup=back_kb())
        return EDIT_CLIENT_INFO

    # ── Add task ──
    if data.startswith("addt_"):
        _, ai, ci = data.split("_")
        ctx.user_data["edit_ai"] = int(ai)
        ctx.user_data["edit_ci"] = int(ci)
        await q.message.reply_text("Введи текст задачи:", reply_markup=back_kb())
        return ADD_CLIENT_TASK

    # ── Delete task menu ──
    if data.startswith("delt_"):
        _, ai, ci = data.split("_")
        ai, ci = int(ai), int(ci)
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            tasks = u["accounts"][ai]["clients"][ci].get("tasks", [])
        except (IndexError, KeyError):
            await q.message.reply_text("Ошибка.")
            return MAIN_MENU
        if not tasks:
            await q.message.reply_text("Задач нет.")
            return MAIN_MENU
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🗑 {t['text'][:40]}", callback_data=f"deltask_{ai}_{ci}_{ti}")]
            for ti, t in enumerate(tasks)
        ])
        await q.message.reply_text("Какую задачу удалить?", reply_markup=kb)
        return MAIN_MENU

    if data.startswith("deltask_"):
        parts = data.split("_")
        ai, ci, ti = int(parts[1]), int(parts[2]), int(parts[3])
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            removed = u["accounts"][ai]["clients"][ci]["tasks"].pop(ti)
            save_db(db)
            await q.edit_message_text(f"🗑 Задача «{removed['text']}» удалена.")
        except (IndexError, KeyError):
            await q.message.reply_text("Ошибка.")
        return MAIN_MENU

    # ── Toggle task ──
    if data.startswith("togglemenu_"):
        _, ai, ci = data.split("_")
        ai, ci = int(ai), int(ci)
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            tasks = u["accounts"][ai]["clients"][ci].get("tasks", [])
        except (IndexError, KeyError):
            await q.message.reply_text("Ошибка.")
            return MAIN_MENU
        if not tasks:
            await q.message.reply_text("Задач нет.")
            return MAIN_MENU
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"{'✅' if t.get('done') else '⬜'} {t['text'][:40]}",
                callback_data=f"tog_{ai}_{ci}_{ti}"
            )]
            for ti, t in enumerate(tasks)
        ])
        await q.message.reply_text("Нажми на задачу чтобы отметить:", reply_markup=kb)
        return MAIN_MENU

    if data.startswith("tog_"):
        parts = data.split("_")
        ai, ci, ti = int(parts[1]), int(parts[2]), int(parts[3])
        db = load_db()
        u  = get_user(db, q.from_user.id)
        try:
            task = u["accounts"][ai]["clients"][ci]["tasks"][ti]
            task["done"] = not task.get("done", False)
            save_db(db)
            status = "✅ Выполнена" if task["done"] else "⬜ Не выполнена"
            await q.edit_message_text(f"{status}: «{task['text']}»")
        except (IndexError, KeyError):
            await q.message.reply_text("Ошибка.")
        return MAIN_MENU

    # ── Admin: view user ──
    if data.startswith("viewuser_"):
        uid = int(data.split("_")[1])
        db  = load_db()
        u   = db.get(str(uid), {})
        accounts = u.get("accounts", [])
        lines = [f"👤 *{u.get('full_name','—')}* (@{u.get('username','—')})\n🆔 `{uid}`\n"]
        if not accounts:
            lines.append("_Аккаунтов нет_")
        else:
            for acc in accounts:
                lines.append(f"━━━━ 👤 {acc['name']} ━━━━")
                for ci, cl in enumerate(acc.get("clients", [])):
                    lines.append(f"  📌 Клиент {ci+1}: {cl.get('name','—')}")
                    lines.append(f"  📞 {cl.get('phone','—')}  ℹ️ {cl.get('info','—')}")
        text = "\n".join(lines)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✉️ Написать", callback_data=f"msguser_{uid}")
        ]])
        await q.message.reply_text(text[:4096], parse_mode="Markdown", reply_markup=kb)
        return ADMIN_MENU

    if data.startswith("msguser_"):
        ctx.user_data["target_uid"] = int(data.split("_")[1])
        await q.message.reply_text("Введи сообщение для этого пользователя:", reply_markup=back_kb())
        return ADMIN_WRITE_MSG

    return MAIN_MENU

# ── Edit client field handlers ────────────────────────────────────────────────
async def edit_client_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    ai = ctx.user_data.get("edit_ai", 0)
    ci = ctx.user_data.get("edit_ci", 0)
    try:
        u["accounts"][ai]["clients"][ci]["name"] = update.message.text.strip()
        save_db(db)
        await update.message.reply_text("✅ Имя клиента обновлено.", reply_markup=main_kb())
    except (IndexError, KeyError):
        await update.message.reply_text("Ошибка.", reply_markup=main_kb())
    return MAIN_MENU

async def edit_client_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    ai = ctx.user_data.get("edit_ai", 0)
    ci = ctx.user_data.get("edit_ci", 0)
    try:
        u["accounts"][ai]["clients"][ci]["phone"] = update.message.text.strip()
        save_db(db)
        await update.message.reply_text("✅ Телефон обновлён.", reply_markup=main_kb())
    except (IndexError, KeyError):
        await update.message.reply_text("Ошибка.", reply_markup=main_kb())
    return MAIN_MENU

async def edit_client_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    ai = ctx.user_data.get("edit_ai", 0)
    ci = ctx.user_data.get("edit_ci", 0)
    try:
        u["accounts"][ai]["clients"][ci]["info"] = update.message.text.strip()
        save_db(db)
        await update.message.reply_text("✅ Информация обновлена.", reply_markup=main_kb())
    except (IndexError, KeyError):
        await update.message.reply_text("Ошибка.", reply_markup=main_kb())
    return MAIN_MENU

async def add_client_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    ai = ctx.user_data.get("edit_ai", 0)
    ci = ctx.user_data.get("edit_ci", 0)
    try:
        task_text = update.message.text.strip()
        u["accounts"][ai]["clients"][ci].setdefault("tasks", []).append(
            {"text": task_text, "done": False, "created_at": datetime.now().isoformat()}
        )
        save_db(db)
        await update.message.reply_text(f"✅ Задача добавлена: *{task_text}*", parse_mode="Markdown", reply_markup=main_kb())
    except (IndexError, KeyError):
        await update.message.reply_text("Ошибка.", reply_markup=main_kb())
    return MAIN_MENU

# ═════════════════════════════════════════════════════════════════════════════
# ADMIN SECTION
# ═════════════════════════════════════════════════════════════════════════════
async def admin_all_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    users = [v for k, v in db.items() if v.get("id") != ADMIN_ID]
    if not users:
        await update.message.reply_text("Пользователей пока нет.", reply_markup=admin_kb())
        return ADMIN_MENU
    kb_rows = []
    for u in users:
        label = f"👤 {u.get('full_name') or u.get('username') or str(u['id'])}"
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"viewuser_{u['id']}")])
    await update.message.reply_text(
        f"👥 *Все пользователи* ({len(users)}):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )
    return ADMIN_MENU

async def admin_write_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    users = [v for k, v in db.items() if v.get("id") != ADMIN_ID]
    if not users:
        await update.message.reply_text("Пользователей нет.", reply_markup=admin_kb())
        return ADMIN_MENU
    kb_rows = [
        [InlineKeyboardButton(
            f"✉️ {u.get('full_name') or u.get('username') or str(u['id'])}",
            callback_data=f"msguser_{u['id']}"
        )]
        for u in users
    ]
    await update.message.reply_text("Кому написать?", reply_markup=InlineKeyboardMarkup(kb_rows))
    return ADMIN_MENU

async def admin_send_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ADMIN_MENU
    target_uid = ctx.user_data.get("target_uid")
    if not target_uid:
        await update.message.reply_text("Ошибка: не выбран получатель.", reply_markup=admin_kb())
        return ADMIN_MENU
    try:
        await ctx.bot.send_message(
            chat_id=target_uid,
            text=f"📩 *Сообщение от администратора:*\n\n{update.message.text}",
            parse_mode="Markdown",
        )
        await update.message.reply_text("✅ Сообщение отправлено!", reply_markup=admin_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=admin_kb())
    ctx.user_data.pop("target_uid", None)
    return ADMIN_MENU

async def admin_broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введи текст рассылки для ВСЕХ пользователей:", reply_markup=back_kb())
    return BROADCAST_MSG

async def admin_broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ADMIN_MENU
    db = load_db()
    users = [v for k, v in db.items() if v.get("id") != ADMIN_ID]
    ok, fail = 0, 0
    for u in users:
        try:
            await ctx.bot.send_message(
                chat_id=u["id"],
                text=f"📢 *Объявление:*\n\n{update.message.text}",
                parse_mode="Markdown",
            )
            ok += 1
        except:
            fail += 1
    await update.message.reply_text(
        f"📢 Рассылка завершена!\n✅ Доставлено: {ok}\n❌ Ошибок: {fail}",
        reply_markup=admin_kb(),
    )
    return ADMIN_MENU

# ── Fallback ──────────────────────────────────────────────────────────────────
async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        await update.message.reply_text("Используй кнопки меню.", reply_markup=admin_kb())
        return ADMIN_MENU
    await update.message.reply_text("Используй кнопки меню.", reply_markup=main_kb())
    return MAIN_MENU

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^📋 Мой блокнот$"),           show_notebook),
                MessageHandler(filters.Regex("^👤 Добавить аккаунт$"),      add_account_start),
                MessageHandler(filters.Regex("^➕ Добавить клиента$"),      add_client_start),
                MessageHandler(filters.Regex("^✏️ Редактировать клиента$"), edit_client_start),
                MessageHandler(filters.Regex("^🗑 Удалить аккаунт$"),       delete_account_start),
                CallbackQueryHandler(inline_handler),
            ],
            ADD_ACCOUNT_NAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_save)],
            SELECT_ACCOUNT_FOR_CLIENT: [CallbackQueryHandler(client_account_selected)],
            ADD_CLIENT_NAME:           [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_name)],
            ADD_CLIENT_PHONE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_phone)],
            ADD_CLIENT_INFO:           [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_info)],
            ADD_CLIENT_TASKS:          [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_tasks)],
            EDIT_CLIENT_NAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_client_name)],
            EDIT_CLIENT_PHONE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_client_phone)],
            EDIT_CLIENT_INFO:          [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_client_info)],
            ADD_CLIENT_TASK:           [MessageHandler(filters.TEXT & ~filters.COMMAND, add_client_task)],
            # Новые состояния для редактирования через кнопку меню
            EDIT_SELECT_ACCOUNT: [CallbackQueryHandler(edit_select_account_cb, pattern="^editacc_")],
            EDIT_SELECT_CLIENT:  [
                CallbackQueryHandler(edit_select_client_cb,  pattern="^editcl_"),
                CallbackQueryHandler(edit_choose_field_cb,   pattern="^chfield_"),
                CallbackQueryHandler(inline_handler,         pattern="^(editacc_|goto_main)"),
            ],
            EDIT_FIELD_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_save_field),
            ],
            ADMIN_MENU: [
                MessageHandler(filters.Regex("^👥 Все пользователи$"),   admin_all_users),
                MessageHandler(filters.Regex("^✉️ Написать менеджеру$"), admin_write_select),
                MessageHandler(filters.Regex("^📢 Рассылка$"),           admin_broadcast_start),
                CallbackQueryHandler(inline_handler),
            ],
            ADMIN_WRITE_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_msg)],
            BROADCAST_MSG:   [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.ALL, unknown),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    logger.info("Бот запущен...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

# ── Resilient entry point ─────────────────────────────────────────────────────
def run_forever():
    RETRY_DELAY = 5
    MAX_DELAY   = 60
    delay = RETRY_DELAY
    while True:
        try:
            logger.info("▶ Запуск бота...")
            main()
            logger.warning("main() вернулась, перезапуск через %ds...", delay)
        except KeyboardInterrupt:
            logger.info("Остановлен вручную (Ctrl+C).")
            sys.exit(0)
        except Exception as exc:
            logger.exception("💥 Ошибка: %s. Перезапуск через %ds...", exc, delay)
        time.sleep(delay)
        delay = min(delay * 2, MAX_DELAY)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    run_forever()
