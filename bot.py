import json
import os
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "data.json"

CATEGORIES = {
    "products": "🛒 Продукты",
    "meds": "💊 Медикаменты",
    "chem": "🧴 Бытовая химия",
    "useful": "🏠 Полезности",
    "wishes": "⭐ Хотелки",
    "trips": "✈️ Поездки"
}

def load():
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE,"w") as f:
        json.dump(data,f)

data = load()

def main_menu():

    return InlineKeyboardMarkup([

        [InlineKeyboardButton("📅 Дела",callback_data="tasks")],
        [InlineKeyboardButton("➕ Добавить дело",callback_data="add_task")],

        [InlineKeyboardButton("🛒 Продукты",callback_data="products"),
         InlineKeyboardButton("💊 Медикаменты",callback_data="meds")],

        [InlineKeyboardButton("🧴 Бытовая химия",callback_data="chem"),
         InlineKeyboardButton("🏠 Полезности",callback_data="useful")],

        [InlineKeyboardButton("⭐ Хотелки",callback_data="wishes"),
         InlineKeyboardButton("✈️ Поездки",callback_data="trips")]

    ])

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🏠 Home Planner",
        reply_markup=main_menu()
    )

async def menu(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    cmd = query.data

    if cmd in CATEGORIES:

        items = data[cmd]

        text = "\n".join(items) if items else "Список пуст"

        keyboard = [

            [InlineKeyboardButton("➕ Добавить",callback_data=f"add_{cmd}")],
            [InlineKeyboardButton("❌ Удалить",callback_data=f"remove_{cmd}")]

        ]

        await query.message.reply_text(text,reply_markup=InlineKeyboardMarkup(keyboard))

    if cmd == "tasks":

        keyboard=[

            [InlineKeyboardButton("📆 На неделю",callback_data="week_tasks")],
            [InlineKeyboardButton("📅 Все дела",callback_data="all_tasks")]

        ]

        await query.message.reply_text(
            "Выберите",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def add(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    cmd=query.data.replace("add_","")

    context.user_data["add"]=cmd

    if cmd=="task":

        await query.message.reply_text("Введите дату YYYY-MM-DD")

        context.user_data["step"]="date"

    else:

        await query.message.reply_text("Введите текст")

async def text(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if "add" not in context.user_data:
        return

    cmd=context.user_data["add"]

    txt=update.message.text

    if cmd=="task":

        if context.user_data.get("step")=="date":

            context.user_data["date"]=txt
            context.user_data["step"]="task"

            await update.message.reply_text("Введите дело")

            return

        date=context.user_data["date"]

        if date not in data["tasks"]:
            data["tasks"][date]=[]

        data["tasks"][date].append(txt)

        save(data)

        context.user_data.clear()

        await update.message.reply_text("Дело добавлено",reply_markup=main_menu())

        return

    data[cmd].append(txt)

    save(data)

    context.user_data.clear()

    await update.message.reply_text("Добавлено",reply_markup=main_menu())

async def week(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    today=datetime.date.today()

    out=""

    for i in range(7):

        d=(today+datetime.timedelta(days=i)).isoformat()

        if d in data["tasks"]:

            for t in data["tasks"][d]:
                out+=f"{d} - {t}\n"

    if not out:
        out="Нет дел"

    await query.message.reply_text(out)

async def notify(context:ContextTypes.DEFAULT_TYPE):

    today=datetime.date.today().isoformat()

    if today not in data["tasks"]:
        return

    text="📅 Дела на сегодня:\n"

    for t in data["tasks"][today]:
        text+=f"- {t}\n"

    for chat_id in context.application.chat_data:

        await context.bot.send_message(chat_id,text)

def main():

    app=ApplicationBuilder().token(TOKEN).build()

    scheduler=AsyncIOScheduler()

    scheduler.add_job(
        notify,
        "cron",
        hour=6,
        minute=0,
        args=[app]
    )

    scheduler.start()

    app.add_handler(CommandHandler("start",start))

    app.add_handler(CallbackQueryHandler(add,pattern="add_"))

    app.add_handler(CallbackQueryHandler(week,pattern="week_tasks"))

    app.add_handler(CallbackQueryHandler(menu))

    app.add_handler(MessageHandler(filters.TEXT,text))

    print("Bot started")

    app.run_polling()

main()