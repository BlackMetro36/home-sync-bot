import json
import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

TOKEN = "8577304548:AAGmtneLEePzi99UF7746hndDrWtnQiCCJo"

DATA_FILE = "data.json"

MENU = [
    ["📅 Дела"],
    ["➕ Добавить дело"],
    ["🛒 Продукты", "💊 Медикаменты"],
    ["🧴 Бытовая химия", "🏠 Полезности"],
    ["⭐ Хотелки", "✈️ Поездки"]
]

lists_map = {
    "🛒 Продукты": "products",
    "💊 Медикаменты": "meds",
    "🧴 Бытовая химия": "chem",
    "🏠 Полезности": "home",
    "⭐ Хотелки": "wishes",
    "✈️ Поездки": "places"
}


def load_data():

    if not os.path.exists(DATA_FILE):

        data = {
            "tasks": {},
            "products": {},
            "meds": {},
            "chem": {},
            "home": {},
            "wishes": {},
            "places": {}
        }

        with open(DATA_FILE, "w") as f:
            json.dump(data, f)

    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def build_list_keyboard(items):

    keyboard = []

    for name, state in items.items():

        icon = "✅" if state else "⬜"

        keyboard.append([
            InlineKeyboardButton(f"{icon} {name}", callback_data=f"toggle|{name}"),
            InlineKeyboardButton("❌", callback_data=f"delete|{name}")
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Добавить", callback_data="add")
    ])

    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = ReplyKeyboardMarkup(MENU, resize_keyboard=True)

    await update.message.reply_text(
        "🏠 Главное меню",
        reply_markup=keyboard
    )


async def show_list(update, context, list_key, title):

    data = load_data()

    items = data[list_key]

    keyboard = build_list_keyboard(items)

    await update.message.reply_text(
        title,
        reply_markup=keyboard
    )


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    data = load_data()


    if text in lists_map:

        key = lists_map[text]

        context.user_data["current_list"] = key
        context.user_data["list_title"] = text

        await show_list(update, context, key, text)

        return


    if text == "➕ Добавить дело":

        context.user_data["mode"] = "add_task"

        await update.message.reply_text(
            "Напиши:\n\n2026-03-10 Купить торт"
        )

        return


    if context.user_data.get("mode") == "add_task":

        try:

            date, task = text.split(" ", 1)

            if date not in data["tasks"]:
                data["tasks"][date] = []

            data["tasks"][date].append(task)

            save_data(data)

            context.user_data["mode"] = None

            await update.message.reply_text("✅ Дело добавлено")

            await start(update, context)

        except:

            await update.message.reply_text("Формат:\n2026-03-10 Купить торт")

        return


    if text == "📅 Дела":

        context.user_data["mode"] = "show_tasks"

        await update.message.reply_text(
            "Введите дату\n\n2026-03-10"
        )

        return


    if context.user_data.get("mode") == "show_tasks":

        tasks = data["tasks"].get(text)

        if not tasks:

            await update.message.reply_text("Дел нет")

        else:

            msg = f"📅 {text}\n\n"

            for t in tasks:
                msg += f"• {t}\n"

            await update.message.reply_text(msg)

        context.user_data["mode"] = None

        await start(update, context)

        return


    if context.user_data.get("mode") == "add_item":

        key = context.user_data["current_list"]

        data[key][text] = False

        save_data(data)

        context.user_data["mode"] = None

        await show_list(
            update,
            context,
            key,
            context.user_data["list_title"]
        )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = load_data()

    key = context.user_data.get("current_list")

    action, name = None, None

    if "|" in query.data:

        action, name = query.data.split("|")

    else:

        action = query.data


    if action == "add":

        context.user_data["mode"] = "add_item"

        await query.message.reply_text("Введите название")

        return


    if action == "toggle":

        data[key][name] = not data[key][name]

        save_data(data)


    if action == "delete":

        del data[key][name]

        save_data(data)


    items = data[key]

    keyboard = build_list_keyboard(items)

    await query.message.edit_reply_markup(reply_markup=keyboard)


if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    app.add_handler(CallbackQueryHandler(callback))

    print("бот запущен")

    app.run_polling()
