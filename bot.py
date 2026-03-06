import json
import calendar
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

ALLOWED_USERS = [482418773,443835005]
TOKEN = "8760347314:AAEH4CFruPml-gkJ7mSJZ_hUorOhWxDJeXM"

DATA_FILE = "tasks.json"


def load_tasks():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_tasks(tasks):
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить дело", callback_data="add")],
        [InlineKeyboardButton("📋 Список дел", callback_data="list")]
    ]

    await update.message.reply_text(
        "Меню:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add":
        now = datetime.now().year

        keyboard = []
        for y in range(now, now + 3):
            keyboard.append([InlineKeyboardButton(str(y), callback_data=f"year_{y}")])

        await query.edit_message_text(
            "Выбери год:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    if query.data == "list":
        tasks = load_tasks()
        user_id = str(query.from_user.id)

        if user_id not in tasks or not tasks[user_id]:
            await query.edit_message_text("Список пуст")
            return

        text = "📋 Твои дела:\n\n"

        keyboard = []

        for i, task in enumerate(tasks[user_id]):
            text += f"{i+1}. {task['text']} — {task['date']}\n"
            keyboard.append(
                [InlineKeyboardButton(f"❌ {task['text']}", callback_data=f"del_{i}")]
            )

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def choose_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    year = int(query.data.split("_")[1])
    context.user_data["year"] = year

    keyboard = []

    for m in range(1, 13):
        keyboard.append(
            [InlineKeyboardButton(calendar.month_name[m], callback_data=f"month_{m}")]
        )

    await query.edit_message_text(
        "Выбери месяц:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def choose_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    month = int(query.data.split("_")[1])
    context.user_data["month"] = month

    year = context.user_data.get("year")

    days = calendar.monthrange(year, month)[1]

    keyboard = []
    row = []

    for d in range(1, days + 1):
        row.append(InlineKeyboardButton(str(d), callback_data=f"day_{d}"))

        if len(row) == 7:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    await query.edit_message_text(
        "Выбери день:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    day = int(query.data.split("_")[1])

    year = context.user_data.get("year")
    month = context.user_data.get("month")

    date = f"{day:02d}.{month:02d}.{year}"

    context.user_data["date"] = date

    await query.edit_message_text(
        f"Дата выбрана: {date}\n\nТеперь отправь текст задачи."
    )


async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    date = context.user_data.get("date")

    if not date:
        await update.message.reply_text("Сначала добавь дело через /start")
        return

    task_text = update.message.text

    tasks = load_tasks()
    user_id = str(update.message.from_user.id)

    if user_id not in tasks:
        tasks[user_id] = []

    tasks[user_id].append({
        "text": task_text,
        "date": date
    })

    save_tasks(tasks)

    context.user_data.clear()

    await update.message.reply_text("✅ Дело добавлено!")


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    index = int(query.data.split("_")[1])

    tasks = load_tasks()
    user_id = str(query.from_user.id)

    if user_id in tasks and len(tasks[user_id]) > index:
        tasks[user_id].pop(index)

    save_tasks(tasks)

    await query.edit_message_text("Удалено ✅")


async def error(update, context):
    print(context.error)


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(menu, pattern="^(add|list)$"))
    app.add_handler(CallbackQueryHandler(choose_year, pattern="^year_"))
    app.add_handler(CallbackQueryHandler(choose_month, pattern="^month_"))
    app.add_handler(CallbackQueryHandler(choose_day, pattern="^day_"))
    app.add_handler(CallbackQueryHandler(delete_task, pattern="^del_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    app.add_error_handler(error)

    print("Bot started")

    def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(menu, pattern="^(add|list)$"))
    app.add_handler(CallbackQueryHandler(choose_year, pattern="^year_"))
    app.add_handler(CallbackQueryHandler(choose_month, pattern="^month_"))
    app.add_handler(CallbackQueryHandler(choose_day, pattern="^day_"))
    app.add_handler(CallbackQueryHandler(delete_task, pattern="^del_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    print("Bot started")

    # СБРОС ВЕБХУКА
    app.bot.delete_webhook(drop_pending_updates=True)

    app.run_polling()


if __name__ == "__main__":
    main()