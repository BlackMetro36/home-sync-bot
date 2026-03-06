import os
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)


# ========================
# TOKEN
# ========================

ALLOWED_USERS = [482418773,443835005]
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")


# ========================
# DATABASE
# ========================

conn = sqlite3.connect("planner.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
date TEXT,
task TEXT
)
""")

conn.commit()


# ========================
# MAIN MENU
# ========================

main_keyboard = ReplyKeyboardMarkup(
    [
        ["📅 Дела"],
        ["➕ Добавить дело"]
    ],
    resize_keyboard=True
)


# ========================
# START
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🏠 Домашний планер",
        reply_markup=main_keyboard
    )


# ========================
# ADD TASK
# ========================

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    current_year = datetime.now().year

    keyboard = [
        [
            InlineKeyboardButton(str(current_year), callback_data=f"year_{current_year}"),
            InlineKeyboardButton(str(current_year+1), callback_data=f"year_{current_year+1}")
        ]
    ]

    await update.message.reply_text(
        "Выберите год",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ========================
# YEAR
# ========================

async def choose_month(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    year = query.data.split("_")[1]
    context.user_data["year"] = year

    months = [
        ("Янв",1),("Фев",2),("Мар",3),
        ("Апр",4),("Май",5),("Июн",6),
        ("Июл",7),("Авг",8),("Сен",9),
        ("Окт",10),("Ноя",11),("Дек",12)
    ]

    keyboard = []
    row = []

    for name, num in months:

        row.append(
            InlineKeyboardButton(name, callback_data=f"month_{num}")
        )

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    await query.edit_message_text(
        "Выберите месяц",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ========================
# MONTH
# ========================

async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    month = int(query.data.split("_")[1])
    context.user_data["month"] = month

    keyboard = []
    row = []

    for day in range(1, 32):

        row.append(
            InlineKeyboardButton(str(day), callback_data=f"day_{day}")
        )

        if len(row) == 7:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    await query.edit_message_text(
        "Выберите день",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ========================
# DAY
# ========================

async def choose_day_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    day = int(query.data.split("_")[1])

    year = context.user_data.get("year")
    month = context.user_data.get("month")

    date = f"{year}-{int(month):02}-{day:02}"

    context.user_data["date"] = date

    await query.edit_message_text(
        f"Введите задачу на {date}"
    )


# ========================
# SAVE TASK
# ========================

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "date" not in context.user_data:
        return

    task = update.message.text
    date = context.user_data["date"]
    user_id = update.message.from_user.id

    cursor.execute(
        "INSERT INTO tasks(user_id,date,task) VALUES(?,?,?)",
        (user_id, date, task)
    )

    conn.commit()

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Задача добавлена",
        reply_markup=main_keyboard
    )


# ========================
# SHOW TASKS
# ========================

async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id

    cursor.execute(
        "SELECT date, task FROM tasks WHERE user_id=? ORDER BY date",
        (user_id,)
    )

    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Список дел пуст")
        return

    text = "📅 Ваши задачи:\n\n"

    for r in rows:
        text += f"{r[0]} — {r[1]}\n"

    await update.message.reply_text(text)


# ========================
# TEXT ROUTER
# ========================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "➕ Добавить дело":
        await add_task(update, context)
        return

    if text == "📅 Дела":
        await show_tasks(update, context)
        return

    await save_task(update, context)


# ========================
# MAIN
# ========================

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(choose_month, pattern="year_"))
    app.add_handler(CallbackQueryHandler(choose_day, pattern="month_"))
    app.add_handler(CallbackQueryHandler(choose_day_finish, pattern="day_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":
    main()