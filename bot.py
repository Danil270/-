import logging
import json
import os
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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

# ── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "0"))   # ваш Telegram user_id
DB_FILE    = os.environ.get("DB_FILE", "data.json") # on fly.io → /data/data.json

# ── Conversation states ──────────────────────────────────────────────────────
(
    MAIN_MENU,
    EDIT_NAME, EDIT_PHONE, EDIT_TASKS, ADD_TASK, DELETE_TASK,
    ADMIN_MENU, ADMIN_VIEW_USER, ADMIN_WRITE_SELECT, ADMIN_WRITE_MSG,
    BROADCAST_MSG,
) = range(11)

# ── Database helpers ─────────────────────────────────────────────────────────
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
            "phone": "",
            "tasks": [],
            "registered_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
    db[key]["last_active"] = datetime.now().isoformat()
    return db[key]

# ── Keyboards ────────────────────────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup(
        [["📋 Мой блокнот"], ["✏️ Редактировать данные"], ["📋 Мои задачи"]],
        resize_keyboard=True,
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        [["👥 Все пользователи"], ["✉️ Написать менеджеру"], ["📢 Рассылка"]],
        resize_keyboard=True,
    )

def back_kb():
    return ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)

# ── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = load_db()
    u = get_user(db, user.id)
    u["username"]  = user.username or ""
    u["full_name"] = user.full_name or ""
    save_db(db)

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👑 Добро пожаловать, Админ!\n\nВыберите действие:",
            reply_markup=admin_kb(),
        )
        return ADMIN_MENU

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Здесь ты можешь вести свой личный блокнот:\n"
        "• Сохранять контактные данные\n"
        "• Вести список задач\n\n"
        "Выбери действие в меню 👇",
        reply_markup=main_kb(),
    )
    return MAIN_MENU

# ─────────────────────────────────────────────────────────────────────────────
# USER SECTION
# ─────────────────────────────────────────────────────────────────────────────

async def show_notebook(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    tasks_text = ""
    if u["tasks"]:
        tasks_text = "\n\n📋 *Задачи:*\n" + "\n".join(
            f"  {'✅' if t.get('done') else '⬜'} {i+1}. {t['text']}"
            for i, t in enumerate(u["tasks"])
        )
    else:
        tasks_text = "\n\n📋 *Задачи:* пусто"

    text = (
        f"📓 *Твой блокнот*\n\n"
        f"👤 *Имя:* {u['full_name'] or '—'}\n"
        f"📞 *Телефон:* {u['phone'] or '—'}"
        f"{tasks_text}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb())
    return MAIN_MENU

async def edit_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Изменить имя",    callback_data="edit_name")],
        [InlineKeyboardButton("📞 Изменить телефон", callback_data="edit_phone")],
        [InlineKeyboardButton("➕ Добавить задачу",  callback_data="add_task")],
        [InlineKeyboardButton("🗑 Удалить задачу",   callback_data="del_task")],
    ])
    await update.message.reply_text("Что хочешь изменить?", reply_markup=kb)
    return MAIN_MENU

async def tasks_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    if not u["tasks"]:
        await update.message.reply_text("Список задач пуст. Добавь через «Редактировать данные».", reply_markup=main_kb())
        return MAIN_MENU

    kb_rows = []
    for i, t in enumerate(u["tasks"]):
        icon = "✅" if t.get("done") else "⬜"
        kb_rows.append([InlineKeyboardButton(f"{icon} {t['text']}", callback_data=f"toggle_{i}")])

    await update.message.reply_text(
        "📋 *Твои задачи*\nНажми на задачу чтобы отметить выполненной:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )
    return MAIN_MENU

# Inline callback handlers
async def inline_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    if data == "edit_name":
        await q.message.reply_text("Введи своё имя:", reply_markup=back_kb())
        ctx.user_data["editing"] = "name"
        return EDIT_NAME

    if data == "edit_phone":
        await q.message.reply_text("Введи номер телефона:", reply_markup=back_kb())
        ctx.user_data["editing"] = "phone"
        return EDIT_PHONE

    if data == "add_task":
        await q.message.reply_text("Введи текст задачи:", reply_markup=back_kb())
        return ADD_TASK

    if data == "del_task":
        db = load_db()
        u  = get_user(db, q.from_user.id)
        if not u["tasks"]:
            await q.message.reply_text("Задач нет.", reply_markup=main_kb())
            return MAIN_MENU
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🗑 {t['text']}", callback_data=f"deltask_{i}")]
            for i, t in enumerate(u["tasks"])
        ])
        await q.message.reply_text("Какую задачу удалить?", reply_markup=kb)
        return DELETE_TASK

    if data.startswith("toggle_"):
        idx = int(data.split("_")[1])
        db  = load_db()
        u   = get_user(db, q.from_user.id)
        if idx < len(u["tasks"]):
            u["tasks"][idx]["done"] = not u["tasks"][idx].get("done", False)
            save_db(db)
            await q.edit_message_text(
                "✅ Статус обновлён!\n\nОткрой «Мой блокнот» чтобы увидеть изменения."
            )
        return MAIN_MENU

    if data.startswith("deltask_"):
        idx = int(data.split("_")[1])
        db  = load_db()
        u   = get_user(db, q.from_user.id)
        if idx < len(u["tasks"]):
            removed = u["tasks"].pop(idx)
            save_db(db)
            await q.edit_message_text(f"🗑 Задача «{removed['text']}» удалена.")
        return MAIN_MENU

    # ── Admin inline callbacks ──
    if data.startswith("viewuser_"):
        uid = int(data.split("_")[1])
        db  = load_db()
        u   = db.get(str(uid), {})
        tasks_text = "\n".join(
            f"  {'✅' if t.get('done') else '⬜'} {t['text']}" for t in u.get("tasks", [])
        ) or "  —"
        text = (
            f"👤 *{u.get('full_name','—')}* (@{u.get('username','—')})\n"
            f"🆔 ID: `{uid}`\n"
            f"📞 Телефон: {u.get('phone','—')}\n"
            f"🕐 Последняя активность: {u.get('last_active','—')[:16]}\n\n"
            f"📋 Задачи:\n{tasks_text}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✉️ Написать", callback_data=f"msguser_{uid}")
        ]])
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return ADMIN_MENU

    if data.startswith("msguser_"):
        ctx.user_data["target_uid"] = int(data.split("_")[1])
        await q.message.reply_text("Введи сообщение для этого менеджера:", reply_markup=back_kb())
        return ADMIN_WRITE_MSG

    return MAIN_MENU

async def save_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    u["full_name"] = update.message.text.strip()
    save_db(db)
    await update.message.reply_text(f"✅ Имя сохранено: *{u['full_name']}*", parse_mode="Markdown", reply_markup=main_kb())
    return MAIN_MENU

async def save_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    u["phone"] = update.message.text.strip()
    save_db(db)
    await update.message.reply_text(f"✅ Телефон сохранён: *{u['phone']}*", parse_mode="Markdown", reply_markup=main_kb())
    return MAIN_MENU

async def save_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return MAIN_MENU
    db = load_db()
    u  = get_user(db, update.effective_user.id)
    task_text = update.message.text.strip()
    u["tasks"].append({"text": task_text, "done": False, "created_at": datetime.now().isoformat()})
    save_db(db)
    await update.message.reply_text(f"✅ Задача добавлена: *{task_text}*", parse_mode="Markdown", reply_markup=main_kb())
    return MAIN_MENU

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN SECTION
# ─────────────────────────────────────────────────────────────────────────────

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

    kb_rows = []
    for u in users:
        label = f"✉️ {u.get('full_name') or u.get('username') or str(u['id'])}"
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"msguser_{u['id']}")])

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
        await update.message.reply_text(f"❌ Ошибка при отправке: {e}", reply_markup=admin_kb())

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

# ── Fallback ─────────────────────────────────────────────────────────────────
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
                MessageHandler(filters.Regex("^📋 Мой блокнот$"),          show_notebook),
                MessageHandler(filters.Regex("^✏️ Редактировать данные$"), edit_menu),
                MessageHandler(filters.Regex("^📋 Мои задачи$"),           tasks_menu),
                CallbackQueryHandler(inline_handler),
            ],
            EDIT_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, save_name)],
            EDIT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_phone)],
            ADD_TASK:   [MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)],
            DELETE_TASK:[CallbackQueryHandler(inline_handler)],
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
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
