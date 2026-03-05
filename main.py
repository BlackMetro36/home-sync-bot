import os
import json
from datetime import datetime, timedelta
import calendar
import pytz

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

TOKEN = os.environ['TOKEN']
USER_IDS = os.environ['USER_IDS'].split(',')
TIMEZONE = os.environ.get('TIMEZONE', 'Europe/Moscow')
tz = pytz.timezone(TIMEZONE)

categories_ru_to_en = {
    "Продукты": "products",
    "Медикаменты": "medications",
    "Полезности": "utilities",
    "Бытовaя химия": "house_chem",
    "Хотелки": "wish",
    "Поездки": "trips",
}
categories_en_to_ru = {v: k for k, v in categories_ru_to_en.items()}

def load_data():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"tasks": {}, "products": [], "medications": [], "utilities": [], "house_chem": [], "wish": [], "trips": []}

def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f)

keyboard = [
    [KeyboardButton("Добавить дело"), KeyboardButton("Дела")],
    [KeyboardButton("Продукты"), KeyboardButton("Медикаменты")],
    [KeyboardButton("Полезности"), KeyboardButton("Бытовaя химия")],
    [KeyboardButton("Хотелки"), KeyboardButton("Поездки")],
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    await update.message.reply_text(f"Ваш ID: {user_id}")
    if user_id not in USER_IDS:
        await update.message.reply_text("Доступ запрещен.")
        return
    await update.message.reply_text("Добро пожаловать!", reply_markup=markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in USER_IDS:
        return
    text = update.message.text
    user_data = context.user_data
    if 'state' in user_data:
        state = user_data['state']
        if state == 'add_task_text':
            date = user_data['task_date']
            data = load_data()
            if date not in data['tasks']:
                data['tasks'][date] = []
            data['tasks'][date].append(text)
            save_data(data)
            del user_data['state']
            del user_data['task_date']
            await update.message.reply_text(f"Дело добавлено на {date}")
            return
        elif state == 'add_item':
            cat = user_data['category']
            data = load_data()
            data[cat].append(text)
            save_data(data)
            del user_data['state']
            del user_data['category']
            await show_list(update, context, cat)
            return
    if text in categories_ru_to_en:
        cat_en = categories_ru_to_en[text]
        await show_list(update, context, cat_en)
        return
    if text == "Добавить дело":
        await add_task_start(update, context)
        return
    if text == "Дела":
        await show_tasks_menu(update, context)
        return

async def show_list(update, context, cat_en):
    data = load_data()
    items = data[cat_en]
    msg = categories_en_to_ru[cat_en] + ":\n" + ("\n".join(items) if items else "Пусто")
    keyboard = [
        [InlineKeyboardButton("Добавить", callback_data=f"add {cat_en}")],
        [InlineKeyboardButton("Удалить", callback_data=f"remove_menu {cat_en}")],
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_task_start(update, context):
    context.user_data['state'] = 'add_task_date'
    now = datetime.now(tz)
    year = now.year
    month = now.month
    await update.message.reply_text("Выберите дату:", reply_markup=create_calendar(year, month))

def create_calendar(year, month):
    markup = []
    prev_m = month - 1
    prev_y = year
    if prev_m == 0:
        prev_m = 12
        prev_y -= 1
    next_m = month + 1
    next_y = year
    if next_m == 13:
        next_m = 1
        next_y += 1
    row = [
        InlineKeyboardButton("<", callback_data=f"cal-prev {prev_y} {prev_m}"),
        InlineKeyboardButton(f"{month}/{year}", callback_data="ignore"),
        InlineKeyboardButton(">", callback_data=f"cal-next {next_y} {next_m}"),
    ]
    markup.append(row)
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    markup.append([InlineKeyboardButton(d, callback_data="ignore") for d in week_days])
    month_cal = calendar.monthcalendar(year, month)
    for week in month_cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"cal-day {year}-{month:02d}-{day:02d}"))
        markup.append(row)
    return InlineKeyboardMarkup(markup)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_data = context.user_data
    await query.answer()
    if data == "ignore":
        return
    if data.startswith("cal-prev "):
        _, y, m = data.split()
        y, m = int(y), int(m)
        await query.edit_message_reply_markup(reply_markup=create_calendar(y, m))
        return
    if data.startswith("cal-next "):
        _, y, m = data.split()
        y, m = int(y), int(m)
        await query.edit_message_reply_markup(reply_markup=create_calendar(y, m))
        return
    if data.startswith("cal-day "):
        _, date = data.split()
        state = user_data.get('state')
        if state == 'add_task_date':
            user_data['task_date'] = date
            user_data['state'] = 'add_task_text'
            await query.edit_message_text("Введите дело:")
        elif state == 'select_date_for_tasks':
            await show_tasks_for_date(query, date)
            del user_data['state']
        elif state == 'select_date_for_remove':
            await show_remove_tasks(query, date)
            del user_data['state']
        return
    if data.startswith("add "):
        _, cat = data.split()
        user_data['state'] = 'add_item'
        user_data['category'] = cat
        await query.edit_message_text("Введите элемент для добавления:")
        return
    if data.startswith("remove_menu "):
        _, cat = data.split()
        await show_remove_menu(query, cat)
        return
    if data.startswith("remove_item "):
        _, cat, index = data.split()
        data_d = load_data()
        del data_d[cat][int(index)]
        save_data(data_d)
        await show_remove_menu(query, cat)
        return
    if data == "tasks_week":
        await show_week_tasks(query)
        return
    if data == "tasks_all":
        await show_all_tasks(query)
        return
    if data == "tasks_date":
        user_data['state'] = 'select_date_for_tasks'
        now = datetime.now(tz)
        await query.edit_message_text("Выберите дату:", reply_markup=create_calendar(now.year, now.month))
        return
    if data == "tasks_remove":
        user_data['state'] = 'select_date_for_remove'
        now = datetime.now(tz)
        await query.edit_message_text("Выберите дату для удаления дела:", reply_markup=create_calendar(now.year, now.month))
        return
    if data.startswith("remove_task "):
        _, date, index = data.split()
        data_d = load_data()
        del data_d['tasks'][date][int(index)]
        if not data_d['tasks'][date]:
            del data_d['tasks'][date]
        save_data(data_d)
        await show_remove_tasks(query, date)
        return

async def show_tasks_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("На неделю", callback_data="tasks_week")],
        [InlineKeyboardButton("Все дела", callback_data="tasks_all")],
        [InlineKeyboardButton("Дела на дату", callback_data="tasks_date")],
        [InlineKeyboardButton("Удалить дело", callback_data="tasks_remove")],
    ]
    await update.message.reply_text("Дела:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_week_tasks(query):
    data = load_data()
    now = datetime.now(tz)
    msg = "Дела на неделю:\n"
    has_tasks = False
    for i in range(7):
        date = (now + timedelta(days=i)).strftime("%Y-%m-%d")
        if date in data['tasks']:
            msg += f"{date}:\n" + "\n".join(f"- {t}" for t in data['tasks'][date]) + "\n"
            has_tasks = True
    if not has_tasks:
        msg += "Нет дел."
    await query.edit_message_text(msg)

async def show_all_tasks(query):
    data = load_data()
    tasks = data['tasks']
    if not tasks:
        await query.edit_message_text("Нет дел.")
        return
    sorted_dates = sorted(tasks.keys())
    msg = "Все дела:\n"
    for date in sorted_dates:
        msg += f"{date}:\n" + "\n".join(f"- {t}" for t in tasks[date]) + "\n"
    await query.edit_message_text(msg)

async def show_tasks_for_date(query, date):
    data = load_data()
    tasks = data['tasks'].get(date, [])
    msg = f"Дела на {date}:\n" + ("\n".join(f"- {t}" for t in tasks) if tasks else "Нет дел.")
    await query.edit_message_text(msg)

async def show_remove_menu(query, cat):
    data = load_data()
    items = data[cat]
    if not items:
        await query.edit_message_text("Список пуст.")
        return
    keyboard = []
    for i, item in enumerate(items):
        keyboard.append([InlineKeyboardButton(item, callback_data=f"remove_item {cat} {i}")])
    msg = "Выберите для удаления:"
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_remove_tasks(query, date):
    data = load_data()
    tasks = data['tasks'].get(date, [])
    if not tasks:
        await query.edit_message_text(f"Нет дел на {date}.")
        return
    keyboard = []
    for i, task in enumerate(tasks):
        keyboard.append([InlineKeyboardButton(task, callback_data=f"remove_task {date} {i}")])
    msg = f"Выберите дело для удаления на {date}:"
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def send_daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now(tz)
    date = now.strftime("%Y-%m-%d")
    tasks = data['tasks'].get(date, [])
    msg = f"Дела на сегодня ({date}):\n" + ("\n".join(f"- {t}" for t in tasks) if tasks else "Нет дел.")
    for user_id in USER_IDS:
        await context.bot.send_message(user_id, msg)

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.job_queue.run_daily(send_daily_tasks, datetime.time(hour=6, minute=0, tzinfo=tz), days=(0, 1, 2, 3, 4, 5, 6))
    application.run_polling()

if __name__ == '__main__':
    main()