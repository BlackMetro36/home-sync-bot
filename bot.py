import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from datetime import datetime, timedelta

# ─────────────── Инициализация бота ───────────────
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения TOKEN не найдена. Укажи её в настройках Railway.")

bot = telebot.TeleBot(TOKEN)

DATA_FILE = "data.json"

# Создаём файл данных, если его нет
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
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
        }, f, ensure_ascii=False, indent=2)


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────── Главное меню ───────────────
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
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
    bot.send_message(msg.chat.id, "Привет! Вот главное меню:", reply_markup=main_menu())


# ─────────────── Дела ───────────────
@bot.callback_query_handler(func=lambda c: c.data == "tasks")
def tasks_menu(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📅 Выбрать дату", callback_data="pick_date"),
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


@bot.callback_query_handler(func=lambda c: c.data == "week_tasks")
def week_tasks(call):
    data = load_data()
    today = datetime.today()
    text = "📆 Ближайшие 7 дней\n\n"

    for i in range(7):
        d = today + timedelta(days=i)
        key = d.strftime("%d.%m.%Y")
        if key in data["tasks"] and data["tasks"][key]:
            text += f"<b>{key}</b>\n"
            for t in data["tasks"][key]:
                text += f"• {t}\n"
            text += "\n"

    if text == "📆 Ближайшие 7 дней\n\n":
        text += "Пока дел на ближайшую неделю нет."

    bot.send_message(call.message.chat.id, text, parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data == "all_tasks")
def all_tasks(call):
    data = load_data()
    text = "📋 Все дела\n\n"

    if not data["tasks"]:
        text += "Список дел пуст."
    else:
        for date in sorted(data["tasks"]):
            if data["tasks"][date]:
                text += f"<b>{date}</b>\n"
                for t in data["tasks"][date]:
                    text += f"• {t}\n"
                text += "\n"

    bot.send_message(call.message.chat.id, text, parse_mode="HTML")


# ─────────────── Списки ───────────────
@bot.callback_query_handler(func=lambda c: c.data == "lists")
def lists_menu(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🛒 Продукты", callback_data="products"),
        InlineKeyboardButton("💊 Медикаменты", callback_data="meds")
    )
    markup.add(
        InlineKeyboardButton("🧴 Бытовая химия", callback_data="chem"),
        InlineKeyboardButton("🏠 Полезности", callback_data="useful")
    )
    markup.add(
        InlineKeyboardButton("⭐ Хотелки", callback_data="wishlist"),
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


def show_list(chat_id, list_name):
    data = load_data()
    items = data["lists"].get(list_name, [])

    if not items:
        text = "Список пуст."
    else:
        text = ""
        for i, item in enumerate(items, 1):
            icon = "✅" if item.get("done", False) else "⬜"
            text += f"{icon} {item['name']}\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Добавить", callback_data=f"add_{list_name}"))
    if items:
        markup.add(InlineKeyboardButton("✅/⬜ Поменять статус", callback_data=f"toggle_help_{list_name}"))
        markup.add(InlineKeyboardButton("🗑 Удалить элемент", callback_data=f"del_{list_name}"))

    bot.send_message(chat_id, f"<b>{list_name.capitalize()}</b>\n\n{text}", reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data in ["products", "meds", "chem", "useful", "wishlist", "trips"])
def open_list(call):
    show_list(call.message.chat.id, call.data)


@bot.callback_query_handler(func=lambda c: c.data.startswith("toggle_"))
def toggle_item(call):
    try:
        _, list_name, index_str = call.data.split("_", 2)
        index = int(index_str)
    except:
        bot.answer_callback_query(call.id, "Ошибка формата", show_alert=True)
        return

    data = load_data()
    try:
        item = data["lists"][list_name][index]
        item["done"] = not item.get("done", False)
        save_data(data)
        show_list(call.message.chat.id, list_name)
    except (KeyError, IndexError):
        bot.answer_callback_query(call.id, "Элемент не найден", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("add_"))
def add_item_start(call):
    list_name = call.data.split("_", 1)[1]
    msg = bot.send_message(call.message.chat.id, f"Напиши, что добавить в «{list_name}»:")
    bot.register_next_step_handler(msg, lambda m: save_item(m, list_name))


def save_item(message, list_name):
    if not message.text or message.text.strip() == "":
        bot.send_message(message.chat.id, "Пустое название — не добавляем.")
        return

    data = load_data()
    data["lists"][list_name].append({"name": message.text.strip(), "done": False})
    save_data(data)
    show_list(message.chat.id, list_name)


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_item_start(call):
    list_name = call.data.split("_", 1)[1]
    msg = bot.send_message(call.message.chat.id, f"Напиши номер элемента для удаления из «{list_name}» (число):")
    bot.register_next_step_handler(msg, lambda m: remove_item(m, list_name))


def remove_item(message, list_name):
    try:
        idx = int(message.text.strip()) - 1
        if idx < 0:
            raise ValueError
    except:
        bot.send_message(message.chat.id, "Нужно ввести положительное число.")
        return

    data = load_data()
    items = data["lists"][list_name]
    if 0 <= idx < len(items):
        removed = items.pop(idx)
        save_data(data)
        bot.send_message(message.chat.id, f"Удалено: {removed['name']}")
        show_list(message.chat.id, list_name)
    else:
        bot.send_message(message.chat.id, "Такого номера нет.")


@bot.callback_query_handler(func=lambda c: c.data == "back")
def back_to_main(call):
    bot.edit_message_text(
        "Главное меню",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu()
    )


# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling(timeout=15, long_polling_timeout=10)