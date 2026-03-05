import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from datetime import datetime, timedelta

TOKEN = "8577304548:AAGmtneLEePzi99UF7746hndDrWtnQiCCJo"

DATA_FILE = "data.json"

# создание базы если нет
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({
            "tasks": {},
            "lists": {
                "products": [],
                "meds": [],
                "chem": [],
                "useful": [],
                "wishlist": [],
                "trips": []
            }
        }, f)


def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ------------------- МЕНЮ -------------------

def main_menu():
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("📅 Дела", callback_data="tasks"),
        InlineKeyboardButton("🛒 Списки", callback_data="lists")
    )

    markup.add(
        InlineKeyboardButton("➕ Добавить дело", callback_data="add_task")
    )

    return markup


@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(msg.chat.id, "Главное меню", reply_markup=main_menu())


# ------------------- ДЕЛА -------------------

@bot.callback_query_handler(func=lambda c: c.data == "tasks")
def tasks_menu(call):

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("📅 Выбрать дату", callback_data="pick_date")
    )

    markup.add(
        InlineKeyboardButton("📆 На неделю", callback_data="week_tasks")
    )

    markup.add(
        InlineKeyboardButton("📋 Все дела", callback_data="all_tasks")
    )

    markup.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back")
    )

    bot.edit_message_text(
        "📅 Дела",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


# ------------------- ДЕЛА НА НЕДЕЛЮ -------------------

@bot.callback_query_handler(func=lambda c: c.data == "week_tasks")
def week_tasks(call):

    data = load_data()

    today = datetime.today()

    text = "📆 Ближайшие 7 дней\n\n"

    for i in range(7):

        d = today + timedelta(days=i)
        key = d.strftime("%d.%m.%Y")

        if key in data["tasks"]:

            text += f"{key}\n"

            for t in data["tasks"][key]:
                text += f"• {t}\n"

            text += "\n"

    bot.send_message(call.message.chat.id, text)


# ------------------- ВСЕ ДЕЛА -------------------

@bot.callback_query_handler(func=lambda c: c.data == "all_tasks")
def all_tasks(call):

    data = load_data()

    text = "📋 Все дела\n\n"

    for date in sorted(data["tasks"]):

        for t in data["tasks"][date]:

            text += f"{date} — {t}\n"

    bot.send_message(call.message.chat.id, text)


# ------------------- СПИСКИ -------------------

@bot.callback_query_handler(func=lambda c: c.data == "lists")
def lists(call):

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("🛒 Продукты", callback_data="products"),
        InlineKeyboardButton("💊 Медикаменты", callback_data="meds")
    )

    markup.add(
        InlineKeyboardButton("🧴 Бытовая химия", callback_data="chem")
    )

    markup.add(
        InlineKeyboardButton("🏠 Полезности", callback_data="useful")
    )

    markup.add(
        InlineKeyboardButton("⭐ Хотелки", callback_data="wishlist")
    )

    markup.add(
        InlineKeyboardButton("✈️ Поездки", callback_data="trips")
    )

    markup.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back")
    )

    bot.edit_message_text(
        "🛒 Списки",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


# ------------------- ПОКАЗ СПИСКА -------------------

def show_list(chat_id, name):

    data = load_data()

    items = data["lists"][name]

    markup = InlineKeyboardMarkup()

    text = ""

    for i, item in enumerate(items):

        icon = "✅" if item["done"] else "⬜"

        markup.add(
            InlineKeyboardButton(
                f"{icon} {item['name']}",
                callback_data=f"toggle_{name}_{i}"
            )
        )

        text += f"{icon} {item['name']}\n"

    markup.add(
        InlineKeyboardButton("➕ Добавить", callback_data=f"add_{name}")
    )

    markup.add(
        InlineKeyboardButton("❌ Удалить", callback_data=f"del_{name}")
    )

    bot.send_message(chat_id, text or "Пусто", reply_markup=markup)


# ------------------- ОТКРЫТЬ СПИСОК -------------------

@bot.callback_query_handler(func=lambda c: c.data in ["products","meds","chem","useful","wishlist","trips"])
def open_list(call):

    show_list(call.message.chat.id, call.data)


# ------------------- ПЕРЕКЛЮЧЕНИЕ ГАЛОЧКИ -------------------

@bot.callback_query_handler(func=lambda c: c.data.startswith("toggle"))
def toggle(call):

    _, name, i = call.data.split("_")

    data = load_data()

    item = data["lists"][name][int(i)]

    item["done"] = not item["done"]

    save_data(data)

    show_list(call.message.chat.id, name)


# ------------------- ДОБАВИТЬ -------------------

@bot.callback_query_handler(func=lambda c: c.data.startswith("add_"))
def add_item(call):

    name = call.data.split("_")[1]

    msg = bot.send_message(call.message.chat.id, "Напиши название")

    bot.register_next_step_handler(msg, save_item, name)


def save_item(msg, name):

    data = load_data()

    data["lists"][name].append({
        "name": msg.text,
        "done": False
    })

    save_data(data)

    show_list(msg.chat.id, name)


# ------------------- УДАЛИТЬ -------------------

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_item(call):

    name = call.data.split("_")[1]

    msg = bot.send_message(call.message.chat.id, "Напиши номер элемента")

    bot.register_next_step_handler(msg, remove_item, name)


def remove_item(msg, name):

    data = load_data()

    i = int(msg.text) - 1

    if i < len(data["lists"][name]):
        data["lists"][name].pop(i)

    save_data(data)

    show_list(msg.chat.id, name)


# ------------------- НАЗАД -------------------

@bot.callback_query_handler(func=lambda c: c.data == "back")
def back(call):

    bot.edit_message_text(
        "Главное меню",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu()
    )


bot.infinity_polling()