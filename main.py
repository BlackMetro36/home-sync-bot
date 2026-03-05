import os
import json
from datetime import datetime, timedelta, time
import calendar
import pytz

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)

# === Конфигурация из переменных окружения ===
TOKEN = os.environ.get('TOKEN')
USER_IDS_STR = os.environ.get('USER_IDS', '')
USER_IDS = [uid.strip() for uid in USER_IDS_STR.split(',') if uid.strip()]

TIMEZONE_NAME = os.environ.get('TIMEZONE', 'Europe/Moscow')
tz = pytz.timezone(TIMEZONE_NAME)

if not TOKEN:
    raise ValueError("TOKEN не задан в переменных окружения")
if not USER_IDS:
    print("Внимание: USER_IDS пустой → бот будет доступен всем пользователям!")

# Маппинг русских названий категорий → ключи в JSON
categories_ru_to_en = {
    "Продукты": "products",
    "Медикаменты": "medications",
    "Полезности": "utilities",
    "Бытовaя химия": "house_chem",
    "Хотелки": "wish",
    "Поездки": "trips",
}
categories_en_to_ru = {v: k for k, v in categories_ru_to_en.items()}

# Клавиатура основного меню
main_keyboard = [
    [KeyboardButton("Добавить дело"), KeyboardButton("Дела")],
    [KeyboardButton("Продукты"), KeyboardButton("Медикаменты")],
    [KeyboardButton("Полезности"), KeyboardButton("Бытовaя химия")],
    [KeyboardButton("Хотелки"), KeyboardButton("Поездки")],
]
main_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)


def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default = {
            "tasks": {},
            "products": [],
            "medications": [],
            "utilities": [],
            "house_chem": [],
            "wish": [],
            "trips": [],
        }
        save_data(default)
        return default


def save_data(data):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.message.reply_text(f"Ваш ID: {user_id}")

    if user_id not in USER_IDS and USER_IDS:
        await update.message.reply_text("Доступ запрещён. Обратитесь к владельцу бота.")
        return

    await update.message.reply_text("Добро пожаловать!", reply_markup=main_markup)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in USER_IDS and USER_IDS:
        return

    text = update.message.text.strip()
    user_data = context.user_data

    # Добавление элемента в категорию
    if text in categories_ru_to_en:
        cat_en = categories_ru_to_en[text]
        await show_list(update, context, cat_en)
        return

    # Состояния ввода
    if 'state' in user_data:
        state = user_data['state']

        if state == 'add_task_text':
            date_str = user_data.get('task_date')
            if not date_str:
                await update.message.reply_text("Ошибка: дата не выбрана.")
                del user_data['state']
                return

            data = load_data()
            if date_str not in data['tasks']:
                data['tasks'][date_str] = []
            data['tasks'][date_str].append(text)
            save_data(data)

            del user_data['state']
            del user_data['task_date']
            await update.message.reply_text(f"Дело добавлено на {date_str}")
            return

        if state == 'add_item':
            cat = user_data.get('category')
            if not cat:
                await update.message.reply_text("Ошибка: категория не выбрана.")
                del user_data['state']
                return

            data = load_data()
            data[cat].append(text)
            save_data(data)

            del user_data['state']
            del user_data['category']
            await show_list(update, context, cat)
            return

    # Основные команды
    if text == "Добавить дело":
        await add_task_start(update, context)
        return

    if text == "Дела":
        await show_tasks_menu(update, context)
        return


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_en: str):
    data = load_data()
    items = data.get(cat_en, [])
    title = categories_en_to_ru.get(cat_en, cat_en)
    msg = f"{title}:\n" + ("\n".join(f"• {item}" for item in items) if items else "Пусто")

    keyboard = [
        [InlineKeyboardButton("Добавить", callback_data=f"add {cat_en}")],
        [InlineKeyboardButton("Удалить", callback_data=f"remove_menu {cat_en}")],
    ]

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ── Календарь ────────────────────────────────────────────────────────────────

def create_calendar(year: int, month: int):
    markup = []

    # Кнопки переключения месяца
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    markup.append([
        InlineKeyboardButton("«", callback_data=f"cal-prev {prev_year} {prev_month}"),
        InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton("»", callback_data=f"cal-next {next_year} {next_month}"),
    ])

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    markup.append([InlineKeyboardButton(d, callback_data="ignore") for d in week_days])

    # Дни месяца
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(str(day), callback_data=f"cal-day {date_str}"))
        markup.append(row)

    return InlineKeyboardMarkup(markup)


async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'add_task_date'
    now = datetime.now(tz)
    await update.message.reply_text(
        "Выберите дату для дела:",
        reply_markup=create_calendar(now.year, now.month)
    )


# ── Обработчик callback ──────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_data = context.user_data

    await query.answer()

    if data == "ignore":
        return

    # Переключение месяцев в календаре
    if data.startswith("cal-prev "):
        _, y, m = data.split()
        await query.edit_message_reply_markup(reply_markup=create_calendar(int(y), int(m)))
        return

    if data.startswith("cal-next "):
        _, y, m = data.split()
        await query.edit_message_reply_markup(reply_markup=create_calendar(int(y), int(m)))
        return

    # Выбор дня
    if data.startswith("cal-day "):
        _, date_str = data.split(maxsplit=1)

        state = user_data.get('state')

        if state == 'add_task_date':
            user_data['task_date'] = date_str
            user_data['state'] = 'add_task_text'
            await query.edit_message_text(f"Введите текст дела на {date_str}:")

        elif state == 'select_date_for_tasks':
            await show_tasks_for_date(query, date_str)
            user_data.pop('state', None)

        elif state == 'select_date_for_remove':
            await show_remove_tasks(query, date_str)
            user_data.pop('state', None)

        return

    # Добавление / удаление в категориях
    if data.startswith("add "):
        _, cat = data.split(maxsplit=1)
        user_data['state'] = 'add_item'
        user_data['category'] = cat
        await query.edit_message_text("Введите название элемента для добавления:")
        return

    if data.startswith("remove_menu "):
        _, cat = data.split(maxsplit=1)
        await show_remove_menu(query, cat)
        return

    if data.startswith("remove_item "):
        _, cat, idx_str = data.split()
        idx = int(idx_str)
        d = load_data()
        if cat in d and 0 <= idx < len(d[cat]):
            del d[cat][idx]
            save_data(d)
        await show_remove_menu(query, cat)
        return

    # Меню дел
    if data == "tasks_week":
        await show_week_tasks(query)
        return

    if data == "tasks_all":
        await show_all_tasks(query)
        return

    if data == "tasks_date":
        user_data['state'] = 'select_date_for_tasks'
        now = datetime.now(tz)
        await query.edit_message_text(
            "Выберите дату:",
            reply_markup=create_calendar(now.year, now.month)
        )
        return

    if data == "tasks_remove":
        user_data['state'] = 'select_date_for_remove'
        now = datetime.now(tz)
        await query.edit_message_text(
            "Выберите дату для удаления дела:",
            reply_markup=create_calendar(now.year, now.month)
        )
        return

    if data.startswith("remove_task "):
        _, date_str, idx_str = data.split()
        idx = int(idx_str)
        d = load_data()
        if date_str in d['tasks'] and 0 <= idx < len(d['tasks'][date_str]):
            del d['tasks'][date_str][idx]
            if not d['tasks'][date_str]:
                del d['tasks'][date_str]
            save_data(d)
        await show_remove_tasks(query, date_str)
        return


async def show_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    lines = ["Дела на ближайшую неделю:"]

    has = False
    for i in range(7):
        dt = now + timedelta(days=i)
        date_str = dt.strftime("%Y-%m-%d")
        tasks = data['tasks'].get(date_str, [])
        if tasks:
            has = True
            lines.append(f"\n{date_str}:")
            lines.extend(f"  • {t}" for t in tasks)

    if not has:
        lines.append("\nНет запланированных дел.")

    await query.edit_message_text("\n".join(lines))


async def show_all_tasks(query):
    data = load_data()
    tasks = data['tasks']
    if not tasks:
        await query.edit_message_text("Нет запланированных дел.")
        return

    lines = ["Все дела (по датам):"]
    for date_str in sorted(tasks.keys()):
        lines.append(f"\n{date_str}:")
        lines.extend(f"  • {t}" for t in tasks[date_str])

    await query.edit_message_text("\n".join(lines))


async def show_tasks_for_date(query, date_str: str):
    data = load_data()
    tasks = data['tasks'].get(date_str, [])
    msg = f"Дела на {date_str}:\n"
    if tasks:
        msg += "\n".join(f"• {t}" for t in tasks)
    else:
        msg += "Нет дел."
    await query.edit_message_text(msg)


async def show_remove_menu(query, cat: str):
    data = load_data()
    items = data.get(cat, [])
    if not items:
        await query.edit_message_text("В этой категории ничего нет.")
        return

    keyboard = []
    for i, item in enumerate(items):
        keyboard.append([InlineKeyboardButton(item, callback_data=f"remove_item {cat} {i}")])

    await query.edit_message_text("Выберите, что удалить:", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_remove_tasks(query, date_str: str):
    data = load_data()
    tasks = data['tasks'].get(date_str, [])
    if not tasks:
        await query.edit_message_text(f"На {date_str} нет дел для удаления.")
        return

    keyboard = []
    for i, task in enumerate(tasks):
        keyboard.append([InlineKeyboardButton(task, callback_data=f"remove_task {date_str} {i}")])

    await query.edit_message_text(
        f"Выберите дело для удаления на {date_str}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Ежедневное уведомление в 6:00 ───────────────────────────────────────────

async def send_daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    tasks = data['tasks'].get(today, [])

    if not tasks:
        msg = f"Сегодня ({today}) дел нет."
    else:
        msg = f"Дела на сегодня ({today}):\n" + "\n".join(f"• {t}" for t in tasks)

    for uid in USER_IDS:
        try:
            await context.bot.send_message(uid, msg)
        except Exception as e:
            print(f"Не удалось отправить уведомление пользователю {uid}: {e}")


def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Ежедневное уведомление в 6:00 по указанному часовому поясу
    application.job_queue.run_daily(
        callback=send_daily_tasks,
        time=time(hour=6, minute=0, tzinfo=tz),
        days=tuple(range(7)),  # каждый день
    )

    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()