import os
import sqlite3
import calendar
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

ALLOWED_USERS = [482418773,443835005]
TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "data.db"
DATE_FMT = "%d.%m.%Y"

LISTS = {
    "products": "🛒 Продукты",
    "meds": "💊 Медикаменты",
    "chem": "🧴 Бытовая химия",
    "home": "🏠 Полезности",
    "wishes": "⭐ Хотелки",
    "places": "✈️ Поездки",
}
LIST_NAME_TO_KEY = {v: k for k, v in LISTS.items()}

MONTHS_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["📅 Дела", "➕ Добавить дело"],
        ["🛒 Продукты", "💊 Медикаменты"],
        ["🧴 Бытовая химия", "🏠 Полезности"],
        ["⭐ Хотелки", "✈️ Поездки"],
    ],
    resize_keyboard=True,
)


# ---------- DB ----------

def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


conn = get_conn()


def init_db():
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_text TEXT NOT NULL,
        date_iso TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tasks_date_iso
    ON tasks (date_iso)
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS list_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_key TEXT NOT NULL,
        name TEXT NOT NULL,
        is_checked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_list_unique_name
    ON list_items (list_key, name)
    """)

    conn.commit()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, DATE_FMT)


def date_to_iso(date_str: str) -> str:
    return parse_date(date_str).strftime("%Y-%m-%d")


def split_multiline_items(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


# ---------- TASKS ----------

def add_task(date_text: str, text: str):
    text = text.strip()
    if not text:
        return

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (date_text, date_iso, text, created_at)
        VALUES (?, ?, ?, ?)
    """, (date_text, date_to_iso(date_text), text, now_str()))
    conn.commit()


def get_tasks_for_date(date_text: str):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, text
        FROM tasks
        WHERE date_text = ?
        ORDER BY id
    """, (date_text,))
    return cur.fetchall()


def get_task(task_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, text
        FROM tasks
        WHERE id = ?
    """, (task_id,))
    return cur.fetchone()


def delete_task(task_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


def get_tasks_for_week():
    today = datetime.now().date()
    end_date = today + timedelta(days=6)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, text
        FROM tasks
        WHERE date_iso BETWEEN ? AND ?
        ORDER BY date_iso, id
    """, (
        today.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    ))
    return cur.fetchall()


def get_all_tasks():
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, text
        FROM tasks
        ORDER BY date_iso, id
    """)
    return cur.fetchall()


# ---------- LISTS ----------

def get_list_items(list_key: str):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, list_key, name, is_checked
        FROM list_items
        WHERE list_key = ?
        ORDER BY LOWER(name), id
    """, (list_key,))
    return cur.fetchall()


def get_list_item(item_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, list_key, name, is_checked
        FROM list_items
        WHERE id = ?
    """, (item_id,))
    return cur.fetchone()


def add_list_items(list_key: str, names: list[str]):
    cur = conn.cursor()
    for name in names:
        clean_name = name.strip()
        if not clean_name:
            continue
        cur.execute("""
            INSERT OR IGNORE INTO list_items (list_key, name, is_checked, created_at)
            VALUES (?, ?, 0, ?)
        """, (list_key, clean_name, now_str()))
    conn.commit()


def toggle_list_item(item_id: int):
    cur = conn.cursor()
    cur.execute("""
        UPDATE list_items
        SET is_checked = CASE WHEN is_checked = 1 THEN 0 ELSE 1 END
        WHERE id = ?
    """, (item_id,))
    conn.commit()


def delete_list_item(item_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM list_items WHERE id = ?", (item_id,))
    conn.commit()


# ---------- RENDER ----------

def build_tasks_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Выбрать дату", callback_data="tasks_pick_date")],
        [InlineKeyboardButton("📆 На неделю", callback_data="tasks_week")],
        [InlineKeyboardButton("📋 Все дела", callback_data="tasks_all")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")],
    ])


def build_lists_menu() -> InlineKeyboardMarkup:
    rows = []
    for key, title in LISTS.items():
        rows.append([InlineKeyboardButton(title, callback_data=f"open_list|{key}")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def render_list_text(list_key: str, items) -> str:
    title = LISTS[list_key]
    if not items:
        return f"{title}\n\nСписок пуст."
    lines = [title, ""]
    for item in items:
        icon = "✅" if item["is_checked"] else "⬜"
        lines.append(f"{icon} {item['name']}")
    return "\n".join(lines)


def build_list_keyboard(list_key: str, items) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        icon = "✅" if item["is_checked"] else "⬜"
        rows.append([
            InlineKeyboardButton(
                f"{icon} {item['name']}",
                callback_data=f"toggle_item|{item['id']}",
            ),
            InlineKeyboardButton(
                "❌",
                callback_data=f"delete_item|{item['id']}",
            ),
        ])

    rows.append([InlineKeyboardButton("➕ Добавить", callback_data=f"add_item|{list_key}")])
    rows.append([InlineKeyboardButton("⬅️ К спискам", callback_data="open_lists_menu")])
    return InlineKeyboardMarkup(rows)


def render_tasks_for_date(date_text: str, tasks) -> str:
    if not tasks:
        return f"📅 {date_text}\n\nДел нет."

    lines = [f"📅 {date_text}", ""]
    for idx, task in enumerate(tasks, 1):
        lines.append(f"{idx}. {task['text']}")
    return "\n".join(lines)


def build_date_tasks_keyboard(date_text: str, tasks) -> InlineKeyboardMarkup:
    rows = []

    for idx, task in enumerate(tasks, 1):
        short_text = task["text"][:24] + ("…" if len(task["text"]) > 24 else "")
        rows.append([
            InlineKeyboardButton(f"{idx}. {short_text}", callback_data="noop"),
            InlineKeyboardButton("❌", callback_data=f"delete_task|{task['id']}"),
        ])

    rows.append([InlineKeyboardButton("➕ Добавить дело на эту дату", callback_data=f"add_task_for|{date_text}")])
    rows.append([InlineKeyboardButton("📅 Выбрать другую дату", callback_data="tasks_pick_date")])
    rows.append([InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")])
    return InlineKeyboardMarkup(rows)


def render_week_tasks(tasks) -> str:
    if not tasks:
        return "📆 Ближайшие 7 дней\n\nДел нет."

    lines = ["📆 Ближайшие 7 дней", ""]
    current_date = None
    for task in tasks:
        if current_date != task["date_text"]:
            if current_date is not None:
                lines.append("")
            current_date = task["date_text"]
            lines.append(current_date)
        lines.append(f"• {task['text']}")
    return "\n".join(lines)


def render_all_tasks(tasks) -> str:
    if not tasks:
        return "📋 Все дела\n\nДел нет."

    lines = ["📋 Все дела", ""]
    for task in tasks:
        lines.append(f"{task['date_text']} — {task['text']}")
    return "\n".join(lines)


def build_year_picker(mode: str, start_year: int | None = None) -> InlineKeyboardMarkup:
    current_year = datetime.now().year
    start_year = start_year or current_year

    years = [start_year + i for i in range(6)]
    rows = []

    row = []
    for year in years:
        row.append(InlineKeyboardButton(str(year), callback_data=f"pick_year|{mode}|{year}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton("◀️", callback_data=f"shift_years|{mode}|{start_year - 6}"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
        InlineKeyboardButton("▶️", callback_data=f"shift_years|{mode}|{start_year + 6}"),
    ])
    return InlineKeyboardMarkup(rows)


def build_month_picker(mode: str, year: int) -> InlineKeyboardMarkup:
    month_names = [
        "Янв", "Фев", "Мар",
        "Апр", "Май", "Июн",
        "Июл", "Авг", "Сен",
        "Окт", "Ноя", "Дек",
    ]

    rows = []
    row = []
    for i, name in enumerate(month_names, start=1):
        row.append(InlineKeyboardButton(name, callback_data=f"pick_month|{mode}|{year}|{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ К годам", callback_data=f"back_to_years|{mode}")])
    return InlineKeyboardMarkup(rows)


def build_day_picker(mode: str, year: int, month: int) -> InlineKeyboardMarkup:
    cal = calendar.monthcalendar(year, month)
    rows = []

    rows.append([InlineKeyboardButton(f"{MONTHS_RU[month]} {year}", callback_data="noop")])
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    rows.append([InlineKeyboardButton(day, callback_data="noop") for day in weekdays])

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_text = f"{day:02d}.{month:02d}.{year}"
                row.append(InlineKeyboardButton(str(day), callback_data=f"pick_day|{mode}|{date_text}"))
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ К месяцам", callback_data=f"back_to_months|{mode}|{year}")])
    return InlineKeyboardMarkup(rows)


# ---------- HELPERS ----------

async def safe_delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int | None):
    if not message_id:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def show_main_menu(update: Update, text: str = "🏠 Главное меню"):
    if update.message:
        await update.message.reply_text(text, reply_markup=MAIN_MENU)
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(text)
        except Exception:
            pass
        await update.callback_query.message.reply_text(text, reply_markup=MAIN_MENU)


async def edit_or_send_message(query, text: str, reply_markup=None):
    try:
        await query.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup)


# ---------- HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await show_main_menu(update)


async def open_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await edit_or_send_message(query, "📅 Раздел дел", build_tasks_menu())


async def open_lists_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await edit_or_send_message(query, "🛒 Раздел списков", build_lists_menu())


async def show_list_message(message, list_key: str, context: ContextTypes.DEFAULT_TYPE):
    items = get_list_items(list_key)
    sent = await message.reply_text(
        render_list_text(list_key, items),
        reply_markup=build_list_keyboard(list_key, items),
    )
    context.user_data["active_list_message_id"] = sent.message_id
    context.user_data["active_list_key"] = list_key


async def show_list_callback(update: Update, list_key: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    items = get_list_items(list_key)
    context.user_data["active_list_message_id"] = query.message.message_id
    context.user_data["active_list_key"] = list_key
    await edit_or_send_message(query, render_list_text(list_key, items), build_list_keyboard(list_key, items))


async def refresh_list_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, list_key: str):
    message_id = context.user_data.get("active_list_message_id")
    if not message_id:
        return

    items = get_list_items(list_key)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=render_list_text(list_key, items),
            reply_markup=build_list_keyboard(list_key, items),
        )
    except Exception:
        pass


async def open_year_picker(update: Update, mode: str, start_year: int | None = None):
    query = update.callback_query
    await query.answer()
    await edit_or_send_message(query, "Выберите год", build_year_picker(mode, start_year))


async def open_month_picker(update: Update, mode: str, year: int):
    query = update.callback_query
    await query.answer()
    await edit_or_send_message(query, "Выберите месяц", build_month_picker(mode, year))


async def open_day_picker(update: Update, mode: str, year: int, month: int):
    query = update.callback_query
    await query.answer()
    await edit_or_send_message(query, "Выберите день", build_day_picker(mode, year, month))


async def show_tasks_for_date(update: Update, date_text: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tasks = get_tasks_for_date(date_text)
    context.user_data["active_task_message_id"] = query.message.message_id
    context.user_data["active_task_date"] = date_text
    await edit_or_send_message(query, render_tasks_for_date(date_text, tasks), build_date_tasks_keyboard(date_text, tasks))


async def refresh_tasks_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, date_text: str):
    message_id = context.user_data.get("active_task_message_id")
    if not message_id:
        return

    tasks = get_tasks_for_date(date_text)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=render_tasks_for_date(date_text, tasks),
            reply_markup=build_date_tasks_keyboard(date_text, tasks),
        )
    except Exception:
        pass


async def add_task_for_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, date_text: str):
    query = update.callback_query
    await query.answer()
    context.user_data["mode"] = "await_task_text"
    context.user_data["task_date"] = date_text
    context.user_data["active_task_message_id"] = query.message.message_id
    context.user_data["active_task_date"] = date_text

    prompt = await query.message.reply_text(
        f"✍️ Дата выбрана: {date_text}\n\n"
        f"Отправь текст дела.\n"
        f"Можно несколько дел, каждое с новой строки."
    )
    context.user_data["temp_prompt_message_id"] = prompt.message_id


async def show_week_tasks(update: Update):
    query = update.callback_query
    await query.answer()
    tasks = get_tasks_for_week()
    await edit_or_send_message(
        query,
        render_week_tasks(tasks),
        InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")]]),
    )


async def show_all_tasks(update: Update):
    query = update.callback_query
    await query.answer()
    tasks = get_all_tasks()
    await edit_or_send_message(
        query,
        render_all_tasks(tasks),
        InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")]]),
    )


async def toggle_item_callback(update: Update, item_id: int, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item = get_list_item(item_id)
    if not item:
        return

    toggle_list_item(item_id)
    items = get_list_items(item["list_key"])
    context.user_data["active_list_message_id"] = query.message.message_id
    context.user_data["active_list_key"] = item["list_key"]

    await edit_or_send_message(query, render_list_text(item["list_key"], items), build_list_keyboard(item["list_key"], items))


async def delete_item_callback(update: Update, item_id: int, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item = get_list_item(item_id)
    if not item:
        return

    list_key = item["list_key"]
    delete_list_item(item_id)
    items = get_list_items(list_key)
    context.user_data["active_list_message_id"] = query.message.message_id
    context.user_data["active_list_key"] = list_key

    await edit_or_send_message(query, render_list_text(list_key, items), build_list_keyboard(list_key, items))


async def add_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, list_key: str):
    query = update.callback_query
    await query.answer()

    context.user_data["mode"] = "await_list_item"
    context.user_data["list_key"] = list_key
    context.user_data["active_list_message_id"] = query.message.message_id
    context.user_data["active_list_key"] = list_key

    prompt = await query.message.reply_text(
        f"✍️ Отправь новые элементы для списка:\n{LISTS[list_key]}\n\n"
        f"Можно несколько строками, например:\nмолоко\nяйца"
    )
    context.user_data["temp_prompt_message_id"] = prompt.message_id


async def delete_task_callback(update: Update, task_id: int, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task = get_task(task_id)
    if not task:
        return

    date_text = task["date_text"]
    delete_task(task_id)
    tasks = get_tasks_for_date(date_text)
    context.user_data["active_task_message_id"] = query.message.message_id
    context.user_data["active_task_date"] = date_text

    await edit_or_send_message(query, render_tasks_for_date(date_text, tasks), build_date_tasks_keyboard(date_text, tasks))


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "noop":
        await query.answer()
        return

    if data == "open_tasks_menu":
        await open_tasks_menu(update, context)
        return

    if data == "open_lists_menu":
        await open_lists_menu(update, context)
        return

    if data == "back_main":
        await query.answer()
        context.user_data.clear()
        await show_main_menu(update)
        return

    if data == "tasks_pick_date":
        await open_year_picker(update, mode="show")
        return

    if data == "tasks_week":
        await show_week_tasks(update)
        return

    if data == "tasks_all":
        await show_all_tasks(update)
        return

    if data.startswith("shift_years|"):
        _, mode, start_year = data.split("|")
        await open_year_picker(update, mode=mode, start_year=int(start_year))
        return

    if data.startswith("pick_year|"):
        _, mode, year = data.split("|")
        await open_month_picker(update, mode=mode, year=int(year))
        return

    if data.startswith("back_to_years|"):
        _, mode = data.split("|")
        await open_year_picker(update, mode=mode)
        return

    if data.startswith("pick_month|"):
        _, mode, year, month = data.split("|")
        await open_day_picker(update, mode=mode, year=int(year), month=int(month))
        return

    if data.startswith("back_to_months|"):
        _, mode, year = data.split("|")
        await open_month_picker(update, mode=mode, year=int(year))
        return

    if data.startswith("pick_day|"):
        _, mode, date_text = data.split("|", 2)
        await query.answer()

        if mode == "show":
            await show_tasks_for_date(update, date_text, context)
            return

        if mode == "add":
            context.user_data["mode"] = "await_task_text"
            context.user_data["task_date"] = date_text
            context.user_data["active_task_message_id"] = query.message.message_id
            context.user_data["active_task_date"] = date_text

            prompt = await query.message.reply_text(
                f"✍️ Дата выбрана: {date_text}\n\n"
                f"Отправь текст дела.\n"
                f"Можно несколько дел, каждое с новой строки."
            )
            context.user_data["temp_prompt_message_id"] = prompt.message_id
            return

    if data.startswith("add_task_for|"):
        _, date_text = data.split("|", 1)
        await add_task_for_date_callback(update, context, date_text)
        return

    if data.startswith("open_list|"):
        _, list_key = data.split("|", 1)
        await show_list_callback(update, list_key, context)
        return

    if data.startswith("toggle_item|"):
        _, item_id = data.split("|", 1)
        await toggle_item_callback(update, int(item_id), context)
        return

    if data.startswith("delete_item|"):
        _, item_id = data.split("|", 1)
        await delete_item_callback(update, int(item_id), context)
        return

    if data.startswith("add_item|"):
        _, list_key = data.split("|", 1)
        await add_item_callback(update, context, list_key)
        return

    if data.startswith("delete_task|"):
        _, task_id = data.split("|", 1)
        await delete_task_callback(update, int(task_id), context)
        return

    await query.answer("Неизвестная команда")


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_message_id = update.message.message_id

    if text == "📅 Дела":
        context.user_data.clear()
        await update.message.reply_text("📅 Раздел дел", reply_markup=build_tasks_menu())
        return

    if text == "➕ Добавить дело":
        context.user_data.clear()
        current_year = datetime.now().year
        await update.message.reply_text("Выберите год", reply_markup=build_year_picker("add", current_year))
        return

    if text in LIST_NAME_TO_KEY:
        context.user_data.clear()
        await show_list_message(update.message, LIST_NAME_TO_KEY[text], context)
        return

    mode = context.user_data.get("mode")

    if mode == "await_list_item":
        list_key = context.user_data["list_key"]
        items_to_add = split_multiline_items(text)

        if items_to_add:
            add_list_items(list_key, items_to_add)

        await refresh_list_message(context, chat_id, list_key)

        prompt_id = context.user_data.get("temp_prompt_message_id")
        context.user_data["mode"] = None
        context.user_data.pop("temp_prompt_message_id", None)

        await safe_delete_message(context, chat_id, prompt_id)
        await safe_delete_message(context, chat_id, user_message_id)
        return

    if mode == "await_task_text":
        date_text = context.user_data["task_date"]
        tasks_to_add = split_multiline_items(text)

        for task_text in tasks_to_add:
            add_task(date_text, task_text)

        await refresh_tasks_message(context, chat_id, date_text)

        prompt_id = context.user_data.get("temp_prompt_message_id")
        context.user_data["mode"] = None
        context.user_data.pop("temp_prompt_message_id", None)

        await safe_delete_message(context, chat_id, prompt_id)
        await safe_delete_message(context, chat_id, user_message_id)
        return

    await update.message.reply_text("Выбери действие из меню ниже.", reply_markup=MAIN_MENU)


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не найден в переменных окружения")

    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()