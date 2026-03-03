import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "8577304548:AAGmtneLEePzi99UF7746hndDrWtnQiCCJo"


# ---------------- DATABASE ----------------

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    name TEXT,
    status INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime TEXT,
    text TEXT
)
""")

conn.commit()


CATEGORIES = {
    "products": "🛒 Продукты",
    "meds": "💊 Медикаменты",
    "chem": "🧴 Бытовая химия",
    "home": "🏠 Для дома",
    "wishes": "💭 Хотелки",
    "travel": "✈️ Куда поехать",
}


# ---------------- ДОСТУП (первые 2 пользователя) ----------------

def register_user(user_id):
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]

    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    exists = cursor.fetchone()

    if exists:
        return True

    if count < 2:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return True

    return False


# ---------------- ГЛАВНОЕ МЕНЮ ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not register_user(user_id):
        await update.message.reply_text("⛔ Доступ закрыт")
        return

    keyboard = [[InlineKeyboardButton("📅 Дела по дате", callback_data="tasks")]]

    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=key)])

    await update.message.reply_text(
        "🏠 Home Sync 3.0",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- ПОКАЗ КАТЕГОРИИ ----------------

async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data

    if category == "tasks":
        await query.edit_message_text(
            "Введите дату и время:\nПример: 26.02.2026 18:30"
        )
        context.user_data["awaiting_datetime"] = True
        return

    cursor.execute("SELECT id, name, status FROM items WHERE category=?", (category,))
    items = cursor.fetchall()

    text = CATEGORIES.get(category, "Список") + ":\n\n"
    keyboard = []

    for item_id, name, status in items:
        mark = "✅" if status else "❌"
        text += f"{mark} {name}\n"

        keyboard.append([
            InlineKeyboardButton(
                name,
                callback_data=f"toggle_{item_id}_{category}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Добавить", callback_data=f"add_{category}")
    ])

    keyboard.append([
        InlineKeyboardButton("⬅ Назад", callback_data="back")
    ])

    await query.edit_message_text(
        text if items else "Список пуст.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- ПЕРЕКЛЮЧЕНИЕ СТАТУСА ----------------

async def toggle_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, item_id, category = query.data.split("_")
    item_id = int(item_id)

    cursor.execute("SELECT status FROM items WHERE id=?", (item_id,))
    status = cursor.fetchone()[0]
    new_status = 0 if status else 1

    cursor.execute("UPDATE items SET status=? WHERE id=?", (new_status, item_id))
    conn.commit()

    await show_category(update, context)


# ---------------- КНОПКА ДОБАВИТЬ ----------------

async def add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data.split("_")[1]
    context.user_data["adding_category"] = category

    await query.edit_message_text("Введите название:")


# ---------------- ОБРАБОТКА ТЕКСТА ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Добавление даты
    if context.user_data.get("awaiting_datetime"):
        context.user_data["task_datetime"] = update.message.text
        context.user_data["awaiting_datetime"] = False
        context.user_data["awaiting_task"] = True
        await update.message.reply_text("Введите текст задачи:")
        return

    # Добавление задачи
    if context.user_data.get("awaiting_task"):
        dt_str = context.user_data["task_datetime"]
        text = update.message.text

        cursor.execute(
            "INSERT INTO tasks (datetime, text) VALUES (?, ?)",
            (dt_str, text),
        )
        conn.commit()

        try:
            dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
            context.job_queue.run_once(
                send_reminder,
                when=dt,
                data=text,
            )
        except:
            pass

        context.user_data["awaiting_task"] = False
        await update.message.reply_text("✅ Задача добавлена")
        return

    # Добавление элемента
    if context.user_data.get("adding_category"):
        category = context.user_data["adding_category"]
        name = update.message.text

        cursor.execute(
            "INSERT INTO items (category, name) VALUES (?, ?)",
            (category, name),
        )
        conn.commit()

        context.user_data["adding_category"] = None
        await update.message.reply_text("✅ Добавлено")
        return


# ---------------- НАПОМИНАНИЕ ----------------

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    for user in users:
        await context.bot.send_message(
            chat_id=user[0],
            text=f"🔔 Напоминание: {context.job.data}",
        )


# ---------------- НАЗАД ----------------

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)


# ---------------- ЗАПУСК ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

# ВАЖНО: сначала конкретные
app.add_handler(CallbackQueryHandler(toggle_item, pattern="^toggle_"))
app.add_handler(CallbackQueryHandler(add_item, pattern="^add_"))
app.add_handler(CallbackQueryHandler(back, pattern="^back$"))

# потом общий
app.add_handler(CallbackQueryHandler(show_category))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
