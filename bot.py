 import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    datetime TEXT,
    text TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    category TEXT,
    name TEXT,
    status INTEGER DEFAULT 0
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


# ---------------- НАПОМИНАНИЕ ----------------

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        chat_id=job.data["user_id"],
        text=f"🔔 Напоминание:\n{job.data['text']}"
    )


def schedule_existing_tasks(app):
    cursor.execute("SELECT id, user_id, datetime, text FROM tasks")
    tasks = cursor.fetchall()

    for task_id, user_id, dt_str, text in tasks:
        try:
            dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
            if dt > datetime.now():
                app.job_queue.run_once(
                    send_reminder,
                    when=dt,
                    data={"user_id": user_id, "text": text}
                )
        except:
            pass


# ---------------- ГЛАВНОЕ МЕНЮ ----------------

async def main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📅 Дела по дате", callback_data="show_by_date")],
        [InlineKeyboardButton("📆 Дела на месяц", callback_data="show_month")],
        [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")]
    ]

    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=key)])

    text = "🏠 Home Sync 5.0"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)


# ---------------- ДОБАВЛЕНИЕ ЗАДАЧИ ----------------

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["add_task_date"] = True
    await update.callback_query.edit_message_text(
        "Введите дату и время:\n03.03.2026 18:30"
    )


# ---------------- ОБРАБОТКА ТЕКСТА ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # 1. Добавление задачи — ввод даты
    if context.user_data.get("add_task_date"):
        try:
            datetime.strptime(text, "%d.%m.%Y %H:%M")
            context.user_data["task_dt"] = text
            context.user_data["add_task_date"] = False
            context.user_data["add_task_text"] = True
            await update.message.reply_text("Введите текст задачи:")
        except:
            await update.message.reply_text("Неверный формат.")
        return

    # 2. Добавление задачи — ввод текста
    if context.user_data.get("add_task_text"):
        dt_str = context.user_data["task_dt"]

        cursor.execute(
            "INSERT INTO tasks (user_id, datetime, text) VALUES (?, ?, ?)",
            (user_id, dt_str, text)
        )
        conn.commit()

        dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        if dt > datetime.now():
            context.job_queue.run_once(
                send_reminder,
                when=dt,
                data={"user_id": user_id, "text": text}
            )

        context.user_data.clear()
        await update.message.reply_text("✅ Задача добавлена")
        await main_menu(update, context)
        return

    # 3. Показ задач по дате
    if context.user_data.get("await_date"):
        cursor.execute(
            "SELECT datetime, text FROM tasks WHERE user_id=? AND datetime LIKE ?",
            (user_id, f"{text}%")
        )
        tasks = cursor.fetchall()

        if not tasks:
            await update.message.reply_text("Нет задач.")
        else:
            message = f"📅 Дела на {text}:\n\n"
            for dt, task in tasks:
                time = dt.split(" ")[1]
                message += f"🕒 {time} — {task}\n"
            await update.message.reply_text(message)

        context.user_data.clear()
        await main_menu(update, context)
        return

    # 4. Показ задач на месяц
    if context.user_data.get("await_month"):
        try:
            datetime.strptime(text, "%m.%Y")
        except:
            await update.message.reply_text("Формат: 03.2026")
            return

        cursor.execute(
            "SELECT datetime, text FROM tasks WHERE user_id=? AND datetime LIKE ?",
            (user_id, f"%.{text}%")
        )
        tasks = cursor.fetchall()

        if not tasks:
            await update.message.reply_text("Нет задач.")
        else:
            message = f"📆 Дела за {text}:\n\n"
            for dt, task in tasks:
                message += f"{dt} — {task}\n"
            await update.message.reply_text(message)

        context.user_data.clear()
        await main_menu(update, context)


# ---------------- CALLBACK ROUTER ----------------

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "add_task":
        await add_task(update, context)

    elif data == "show_by_date":
        context.user_data["await_date"] = True
        await query.edit_message_text("Введите дату:\n03.03.2026")

    elif data == "show_month":
        context.user_data["await_month"] = True
        await query.edit_message_text("Введите месяц:\n03.2026")

    elif data in CATEGORIES:
        category = data
        user_id = query.from_user.id

        cursor.execute(
            "SELECT id, name, status FROM items WHERE user_id=? AND category=?",
            (user_id, category)
        )
        items = cursor.fetchall()

        text = CATEGORIES[category] + ":\n\n"
        for _, name, status in items:
            mark = "✅" if status else "❌"
            text += f"{mark} {name}\n"

        await query.edit_message_text(text if items else "Список пуст.")
    else:
        await main_menu(update, context)


# ---------------- ЗАПУСК ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

schedule_existing_tasks(app)

app.run_polling()