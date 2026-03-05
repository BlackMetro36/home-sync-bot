import json
import os
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

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
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except:
        return {
            "tasks": {},
            "products": [],
            "meds": [],
            "chem": [],
            "useful": [],
            "wishes": [],
            "trips": []
        }

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
    await update.message.reply_text("🏠 Home Bot",reply_markup=main_menu())

async def menu(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cmd = query.data

    if cmd in CATEGORIES:
        items = data[cmd]
        text = "\n".join(items) if items else "Список пуст"
        keyboard = [[InlineKeyboardButton("➕ Добавить",callback_data=f"add_{cmd}")]]
        await query.message.reply_text(text,reply_markup=InlineKeyboardMarkup(keyboard))

async def text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if context.user_data.get("adding"):
        cat = context.user_data["adding"]
        data[cat].append(text)
        save(data)
        context.user_data["adding"]=None
        await update.message.reply_text("Добавлено",reply_markup=main_menu())

async def add_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat = query.data.replace("add_","")
    context.user_data["adding"]=cat

    await query.message.reply_text("Введите текст")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CallbackQueryHandler(add_handler,pattern="add_"))
app.add_handler(CallbackQueryHandler(menu))
app.add_handler(MessageHandler(filters.TEXT,text_handler))

app.run_polling()