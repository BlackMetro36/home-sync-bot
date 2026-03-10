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

TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = [482418773, 443835005]

DB_FILE = "data.db"
DATE_FMT = "%d.%m.%Y"
TIME_FMT = "%H:%M"

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
        time_text TEXT NOT NULL DEFAULT '09:00',
        datetime_iso TEXT NOT NULL,
        text TEXT NOT NULL,
        created_by INTEGER,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tasks_date_iso
    ON tasks (date_iso)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tasks_datetime_iso
    ON tasks (datetime_iso)
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

    cur.execute("PRAGMA table_info(tasks)")
    columns = [row["name"] for row in cur.fetchall()]

    if "time_text" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN time_text TEXT NOT NULL DEFAULT '09:00'")
    if "datetime_iso" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN datetime_iso TEXT NOT NULL DEFAULT ''")
    if "created_by" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN created_by INTEGER")

    cur.execute("""
        UPDATE tasks
        SET datetime_iso = date_iso || 'T' || COALESCE(time_text, '09:00') || ':00'
        WHERE datetime_iso = ''
    """)

    conn.commit()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, DATE_FMT)


def date_to_iso(date_str: str) -> str:
    return parse_date(date_str).strftime("%Y-%m-%d")


def make_datetime_iso(date_text: str, time_text: str) -> str:
    dt = datetime.strptime(f"{date_text} {time_text}", f"{DATE_FMT} {TIME_FMT}")
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def split_multiline_items(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def is_allowed(chat_id: int) -> bool:
    return chat_id in ALLOWED_USERS


def get_user_name(chat_id: int) -> str:
    if chat_id == ALLOWED_USERS[0]:
        return "Первый участник"
    if len(ALLOWED_USERS) > 1 and chat_id == ALLOWED_USERS[1]:
        return "Второй участник"
    return "Кто-то"


# ---------- TASKS ----------

def add_task(date_text: str, time_text: str, text: str, created_by: int | None = None):
    text = text.strip()
    if not text:
        return None

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (date_text, date_iso, time_text, datetime_iso, text, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        date_text,
        date_to_iso(date_text),
        time_text,
        make_datetime_iso(date_text, time_text),
        text,
        created_by,
        now_str(),
    ))
    conn.commit()
    return cur.lastrowid


def get_task(task_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE id = ?
    """, (task_id,))
    return cur.fetchone()


def update_task_text(task_id: int, new_text: str):
    new_text = new_text.strip()
    if not new_text:
        return

    cur = conn.cursor()
    cur.execute("""
        UPDATE tasks
        SET text = ?
        WHERE id = ?
    """, (new_text, task_id))
    conn.commit()


def delete_task(task_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


def get_tasks_for_date(date_text: str):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE date_text = ?
        ORDER BY time_text, id
    """, (date_text,))
    return cur.fetchall()


def get_tasks_for_week():
    today = datetime.now().date()
    end_date = today + timedelta(days=6)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE date_iso BETWEEN ? AND ?
        ORDER BY date_iso, time_text, id
    """, (
        today.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    ))
    return cur.fetchall()


def get_all_tasks_future():
    cur = conn.cursor()
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE datetime_iso >= ?
        ORDER BY date_iso, time_text, id
    """, (now_iso,))
    return cur.fetchall()


def get_future_tasks():
    cur = conn.cursor()
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cur.execute("""
        SELECT id, date_text, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE datetime_iso > ?
        ORDER BY datetime_iso
    """, (now_iso,))
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


# ---------- REMINDERS ----------

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    task_id = job_data["task_id"]

    task = get_task(task_id)
    if not task:
        return

    date_text = task["date_text"]
    time_text = task["time_text"]
    task_text = task["text"]

    for chat_id in ALLOWED_USERS:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏰ Напоминание\n{date_text} {time_text}\n• {task_text}"
            )
        except Exception:
            pass


def schedule_task_reminder(app, task_id: int, datetime_iso: str):
    dt = datetime.strptime(datetime_iso, "%Y-%m-%dT%H:%M:%S")
    if dt <= datetime.now():
        return

    job_name = f"task_{task_id}"
    old_jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in old_jobs:
        job.schedule_removal()

    app.job_queue.run_once(
        reminder_job,
        when=dt,
        data={"task_id": task_id},
        name=job_name,
    )


def remove_task_reminder(app, task_id: int):
    job_name = f"task_{task_id}"
    old_jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in old_jobs:
        job.schedule_removal()


def reschedule_all_tasks(app):
    for task in get_future_tasks():
        schedule_task_reminder(app, task["id"], task["datetime_iso"])


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
        lines.append(f"{idx}. [{task['time_text']}] {task['text']}")
    return "\n".join(lines)


def build_date_tasks_keyboard(date_text: str, tasks) -> InlineKeyboardMarkup:
    rows = []

    for idx, task in enumerate(tasks, 1):
        short_text = f"{task['time_text']} {task['text']}"
        short_text = short_text[:20] + ("…" if len(short_text) > 20 else "")
        rows.append([
            InlineKeyboardButton(
                f"{idx}. {short_text}",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                "✏️",
                callback_data=f"edit_task|date|{task['id']}",
            ),
            InlineKeyboardButton(
                "❌",
                callback_data=f"delete_task|date|{task['id']}",
            ),
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
        lines.append(f"• [{task['time_text']}] {task['text']}")
    return "\n".join(lines)


def build_week_tasks_keyboard(tasks) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        short_text = f"{task['date_text']} {task['time_text']}"
        rows.append([
            InlineKeyboardButton(short_text, callback_data="noop"),
            InlineKeyboardButton("✏️", callback_data=f"edit_task|week|{task['id']}"),
            InlineKeyboardButton("❌", callback_data=f"delete_task|week|{task['id']}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")])
    return InlineKeyboardMarkup(rows)


def render_all_tasks(tasks) -> str:
    if not tasks:
        return "📋 Все дела\n\nДел нет."

    lines = ["📋 Все дела", ""]
    for task in tasks:
        lines.append(f"{task['date_text']} [{task['time_text']}] — {task['text']}")
    return "\n".join(lines)


def build_all_tasks_keyboard(tasks) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        short_text = f"{task['date_text']} {task['time_text']}"
        rows.append([
            InlineKeyboardButton(short_text, callback_data="noop"),
            InlineKeyboardButton("✏️", callback_data=f"edit_task|all|{task['id']}"),
            InlineKeyboardButton("❌", callback_data=f"delete_task|all|{task['id']}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")])
    return InlineKeyboardMarkup(rows)


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


def build_time_picker(date_text: str) -> InlineKeyboardMarkup:
    rows = []
    row = []

    for hour in range(5, 24):
        t = f"{hour:02d}:00"
        row.append(
            InlineKeyboardButton(
                t,
                callback_data=f"pick_time|{date_text}|{t}"
            )
        )

        if len(row) == 4:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton(
            "🕒 Ввести вручную",
            callback_data=f"manual_time|{date_text}"
        )
    ])

    rows.append([
        InlineKeyboardButton("⬅️ К дате", callback_data="tasks_pick_date")
    ])

    return InlineKeyboardMarkup(rows)


# ---------- HELPERS ----------

async def notify_other_user(
    context: ContextTypes.DEFAULT_TYPE,
    actor_chat_id: int,
    text: str
):
    for chat_id in ALLOWED_USERS:
        if chat_id != actor_chat_id:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                pass


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
    if not is_allowed(update.effective_chat.id):
        await update.message.reply_text("⛔ Нет доступа")
        return

    context.user_data.clear()
    await show_main_menu(update)


async def open_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_allowed(query.message.chat_id):
        return

    context.user_data.clear()
    await edit_or_send_message(query, "📅 Раздел дел", build_tasks_menu())


async def open_lists_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_allowed(query.message.chat_id):
        return

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


async def open_time_picker(update: Update, date_text: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["task_date"] = date_text
    await edit_or_send_message(query, f"Выберите время для {date_text}", build_time_picker(date_text))


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
    context.user_data["task_date"] = date_text
    await edit_or_send_message(query, f"Выберите время для {date_text}", build_time_picker(date_text))


async def show_week_tasks(update: Update):
    query = update.callback_query
    await query.answer()
    tasks = get_tasks_for_week()
    await edit_or_send_message(query, render_week_tasks(tasks), build_week_tasks_keyboard(tasks))


async def show_all_tasks(update: Update):
    query = update.callback_query
    await query.answer()
    tasks = get_all_tasks_future()
    await edit_or_send_message(query, render_all_tasks(tasks), build_all_tasks_keyboard(tasks))


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
        f"✍️ Отправь новые элементы для списка:\n{LISTS[list_key]}\n\nМожно несколько строками."
    )
    context.user_data["temp_prompt_message_id"] = prompt.message_id


async def delete_task_callback(update: Update, task_id: int, source: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task = get_task(task_id)
    if not task:
        return

    date_text = task["date_text"]
    time_text = task["time_text"]
    task_text = task["text"]

    delete_task(task_id)
    remove_task_reminder(context.application, task_id)

    actor_chat_id = query.message.chat_id
    actor_name = get_user_name(actor_chat_id)
    await notify_other_user(
        context,
        actor_chat_id,
        f"🗑 {actor_name} удалил дело:\n{date_text} {time_text}\n• {task_text}"
    )

    if source == "date":
        tasks = get_tasks_for_date(date_text)
        context.user_data["active_task_message_id"] = query.message.message_id
        context.user_data["active_task_date"] = date_text
        await edit_or_send_message(query, render_tasks_for_date(date_text, tasks), build_date_tasks_keyboard(date_text, tasks))
        return

    if source == "week":
        tasks = get_tasks_for_week()
        await edit_or_send_message(query, render_week_tasks(tasks), build_week_tasks_keyboard(tasks))
        return

    if source == "all":
        tasks = get_all_tasks_future()
        await edit_or_send_message(query, render_all_tasks(tasks), build_allTasks_keyboard(tasks))
        return


async def edit_task_callback(update: Update, task_id: int, source: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task = get_task(task_id)
    if not task:
        return

    context.user_data["mode"] = "await_task_edit"
    context.user_data["edit_task_id"] = task_id
    context.user_data["edit_task_source"] = source

    prompt = await query.message.reply_text(
        f"✏️ Редактирование дела\n\n"
        f"Дата: {task['date_text']}\n"
        f"Время: {task['time_text']}\n"
        f"Старый текст: {task['text']}\n\n"
        f"Отправь новый текст."
    )
    context.user_data["temp_prompt_message_id"] = prompt.message_id


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if not is_allowed(query.message.chat_id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return

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
            await open_time_picker(update, date_text, context)
            return

    if data.startswith("manual_time|"):
        _, date_text = data.split("|", 1)
        await query.answer()

        context.user_data["mode"] = "await_manual_time"
        context.user_data["task_date"] = date_text

        prompt = await query.message.reply_text(
            f"🕒 Введи время для {date_text} в формате ЧЧ:ММ\n\n"
            f"Например: 14:30"
        )
        context.user_data["temp_prompt_message_id"] = prompt.message_id
        return

    if data.startswith("pick_time|"):
        _, date_text, time_text = data.split("|", 2)
        await query.answer()
        context.user_data["mode"] = "await_task_text"
        context.user_data["task_date"] = date_text
        context.user_data["task_time"] = time_text
        context.user_data["active_task_message_id"] = query.message.message_id
        context.user_data["active_task_date"] = date_text

        prompt = await query.message.reply_text(
            f"✍️ Дата: {date_text}\n⏰ Время: {time_text}\n\n"
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
        _, source, task_id = data.split("|", 2)
        await delete_task_callback(update, int(task_id), source, context)
        return

    if data.startswith("edit_task|"):
        _, source, task_id = data.split("|", 2)
        await edit_task_callback(update, int(task_id), source, context)
        return

    await query.answer("Неизвестная команда")


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_message_id = update.message.message_id

    if not is_allowed(chat_id):
        await update.message.reply_text("⛔ Нет доступа")
        return

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

    if mode == "await_manual_time":
        date_text = context.user_data["task_date"]

        try:
            datetime.strptime(text, TIME_FMT)
        except ValueError:
            await update.message.reply_text("Неверный формат. Пример: 14:30")
            return

        context.user_data["mode"] = "await_task_text"
        context.user_data["task_time"] = text

        prompt_id = context.user_data.get("temp_prompt_message_id")
        context.user_data.pop("temp_prompt_message_id", None)

        await safe_delete_message(context, chat_id, prompt_id)

        prompt = await update.message.reply_text(
            f"✍️ Дата: {date_text}\n⏰ Время: {text}\n\n"
            f"Отправь текст дела.\n"
            f"Можно несколько дел, каждое с новой строки."
        )
        context.user_data["temp_prompt_message_id"] = prompt.message_id

        await safe_delete_message(context, chat_id, user_message_id)
        return

    if mode == "await_task_text":
        date_text = context.user_data["task_date"]
        time_text = context.user_data["task_time"]
        tasks_to_add = split_multiline_items(text)

        created_ids = []
        for task_text in tasks_to_add:
            new_id = add_task(date_text, time_text, task_text, chat_id)
            if new_id:
                created_ids.append(new_id)

        for task_id in created_ids:
            task = get_task(task_id)
            if task:
                schedule_task_reminder(context.application, task_id, task["datetime_iso"])

        await refresh_tasks_message(context, chat_id, date_text)

        if tasks_to_add:
            actor_name = get_user_name(chat_id)
            added_text = "\n".join([f"• {item}" for item in tasks_to_add])
            await notify_other_user(
                context,
                chat_id,
                f"📌 {actor_name} добавил дела на {date_text} {time_text}:\n\n{added_text}"
            )

        prompt_id = context.user_data.get("temp_prompt_message_id")
        context.user_data["mode"] = None
        context.user_data.pop("temp_prompt_message_id", None)

        await safe_delete_message(context, chat_id, prompt_id)
        await safe_delete_message(context, chat_id, user_message_id)
        return

    if mode == "await_task_edit":
        task_id = context.user_data["edit_task_id"]
        source = context.user_data["edit_task_source"]

        task = get_task(task_id)
        if task:
            old_text = task["text"]
            update_task_text(task_id, text)

            updated_task = get_task(task_id)
            actor_name = get_user_name(chat_id)
            await notify_other_user(
                context,
                chat_id,
                f"✏️ {actor_name} изменил дело\n"
                f"{updated_task['date_text']} {updated_task['time_text']}\n\n"
                f"Было:\n• {old_text}\n\n"
                f"Стало:\n• {updated_task['text']}"
            )

            if source == "date":
                await refresh_tasks_message(context, chat_id, updated_task["date_text"])
            elif source == "week":
                tasks = get_tasks_for_week()
                await update.message.reply_text(
                    render_week_tasks(tasks),
                    reply_markup=build_week_tasks_keyboard(tasks),
                )
            elif source == "all":
                tasks = get_all_tasks_future()
                await update.message.reply_text(
                    render_all_tasks(tasks),
                    reply_markup=build_all_tasks_keyboard(tasks),
                )

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
    reschedule_all_tasks(app)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()import os
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

TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = [482418773, 443835005]

DB_FILE = "data.db"
DATE_FMT = "%d.%m.%Y"
TIME_FMT = "%H:%M"

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
        time_text TEXT NOT NULL DEFAULT '09:00',
        datetime_iso TEXT NOT NULL,
        text TEXT NOT NULL,
        created_by INTEGER,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tasks_date_iso
    ON tasks (date_iso)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_tasks_datetime_iso
    ON tasks (datetime_iso)
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

    cur.execute("PRAGMA table_info(tasks)")
    columns = [row["name"] for row in cur.fetchall()]

    if "time_text" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN time_text TEXT NOT NULL DEFAULT '09:00'")
    if "datetime_iso" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN datetime_iso TEXT NOT NULL DEFAULT ''")
    if "created_by" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN created_by INTEGER")

    cur.execute("""
        UPDATE tasks
        SET datetime_iso = date_iso || 'T' || COALESCE(time_text, '09:00') || ':00'
        WHERE datetime_iso = ''
    """)

    conn.commit()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, DATE_FMT)


def date_to_iso(date_str: str) -> str:
    return parse_date(date_str).strftime("%Y-%m-%d")


def make_datetime_iso(date_text: str, time_text: str) -> str:
    dt = datetime.strptime(f"{date_text} {time_text}", f"{DATE_FMT} {TIME_FMT}")
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def split_multiline_items(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def is_allowed(chat_id: int) -> bool:
    return chat_id in ALLOWED_USERS


def get_user_name(chat_id: int) -> str:
    if chat_id == ALLOWED_USERS[0]:
        return "Первый участник"
    if len(ALLOWED_USERS) > 1 and chat_id == ALLOWED_USERS[1]:
        return "Второй участник"
    return "Кто-то"


# ---------- TASKS ----------

def add_task(date_text: str, time_text: str, text: str, created_by: int | None = None):
    text = text.strip()
    if not text:
        return None

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (date_text, date_iso, time_text, datetime_iso, text, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        date_text,
        date_to_iso(date_text),
        time_text,
        make_datetime_iso(date_text, time_text),
        text,
        created_by,
        now_str(),
    ))
    conn.commit()
    return cur.lastrowid


def get_task(task_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE id = ?
    """, (task_id,))
    return cur.fetchone()


def update_task_text(task_id: int, new_text: str):
    new_text = new_text.strip()
    if not new_text:
        return

    cur = conn.cursor()
    cur.execute("""
        UPDATE tasks
        SET text = ?
        WHERE id = ?
    """, (new_text, task_id))
    conn.commit()


def delete_task(task_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


def get_tasks_for_date(date_text: str):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE date_text = ?
        ORDER BY time_text, id
    """, (date_text,))
    return cur.fetchall()


def get_tasks_for_week():
    today = datetime.now().date()
    end_date = today + timedelta(days=6)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE date_iso BETWEEN ? AND ?
        ORDER BY date_iso, time_text, id
    """, (
        today.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    ))
    return cur.fetchall()


def get_all_tasks_future():
    cur = conn.cursor()
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cur.execute("""
        SELECT id, date_text, date_iso, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE datetime_iso >= ?
        ORDER BY date_iso, time_text, id
    """, (now_iso,))
    return cur.fetchall()


def get_future_tasks():
    cur = conn.cursor()
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cur.execute("""
        SELECT id, date_text, time_text, datetime_iso, text, created_by
        FROM tasks
        WHERE datetime_iso > ?
        ORDER BY datetime_iso
    """, (now_iso,))
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


# ---------- REMINDERS ----------

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    task_id = job_data["task_id"]

    task = get_task(task_id)
    if not task:
        return

    date_text = task["date_text"]
    time_text = task["time_text"]
    task_text = task["text"]

    for chat_id in ALLOWED_USERS:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏰ Напоминание\n{date_text} {time_text}\n• {task_text}"
            )
        except Exception:
            pass


def schedule_task_reminder(app, task_id: int, datetime_iso: str):
    dt = datetime.strptime(datetime_iso, "%Y-%m-%dT%H:%M:%S")
    if dt <= datetime.now():
        return

    job_name = f"task_{task_id}"

    old_jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in old_jobs:
        job.schedule_removal()

    app.job_queue.run_once(
        reminder_job,
        when=dt,
        data={"task_id": task_id},
        name=job_name,
    )


def remove_task_reminder(app, task_id: int):
    job_name = f"task_{task_id}"
    old_jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in old_jobs:
        job.schedule_removal()


def reschedule_all_tasks(app):
    for task in get_future_tasks():
        schedule_task_reminder(app, task["id"], task["datetime_iso"])


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
        lines.append(f"{idx}. [{task['time_text']}] {task['text']}")
    return "\n".join(lines)


def build_date_tasks_keyboard(date_text: str, tasks) -> InlineKeyboardMarkup:
    rows = []

    for idx, task in enumerate(tasks, 1):
        short_text = f"{task['time_text']} {task['text']}"
        short_text = short_text[:20] + ("…" if len(short_text) > 20 else "")
        rows.append([
            InlineKeyboardButton(
                f"{idx}. {short_text}",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                "✏️",
                callback_data=f"edit_task|date|{task['id']}",
            ),
            InlineKeyboardButton(
                "❌",
                callback_data=f"delete_task|date|{task['id']}",
            ),
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
        lines.append(f"• [{task['time_text']}] {task['text']}")
    return "\n".join(lines)


def build_week_tasks_keyboard(tasks) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        short_text = f"{task['date_text']} {task['time_text']}"
        rows.append([
            InlineKeyboardButton(short_text, callback_data="noop"),
            InlineKeyboardButton("✏️", callback_data=f"edit_task|week|{task['id']}"),
            InlineKeyboardButton("❌", callback_data=f"delete_task|week|{task['id']}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")])
    return InlineKeyboardMarkup(rows)


def render_all_tasks(tasks) -> str:
    if not tasks:
        return "📋 Все дела\n\nДел нет."

    lines = ["📋 Все дела", ""]
    for task in tasks:
        lines.append(f"{task['date_text']} [{task['time_text']}] — {task['text']}")
    return "\n".join(lines)


def build_all_tasks_keyboard(tasks) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        short_text = f"{task['date_text']} {task['time_text']}"
        rows.append([
            InlineKeyboardButton(short_text, callback_data="noop"),
            InlineKeyboardButton("✏️", callback_data=f"edit_task|all|{task['id']}"),
            InlineKeyboardButton("❌", callback_data=f"delete_task|all|{task['id']}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ К делам", callback_data="open_tasks_menu")])
    return InlineKeyboardMarkup(rows)


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


def build_time_picker(date_text: str) -> InlineKeyboardMarkup:
    times = [
        ["09:00", "12:00", "15:00"],
        ["18:00", "20:00", "22:00"],
    ]
    rows = []
    for row_times in times:
        row = []
        for t in row_times:
            row.append(InlineKeyboardButton(t, callback_data=f"pick_time|{date_text}|{t}"))
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ К дате", callback_data="tasks_pick_date")])
    return InlineKeyboardMarkup(rows)


# ---------- HELPERS ----------

async def notify_other_user(
    context: ContextTypes.DEFAULT_TYPE,
    actor_chat_id: int,
    text: str
):
    for chat_id in ALLOWED_USERS:
        if chat_id != actor_chat_id:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                pass


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
    if not is_allowed(update.effective_chat.id):
        await update.message.reply_text("⛔ Нет доступа")
        return

    context.user_data.clear()
    await show_main_menu(update)


async def open_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_allowed(query.message.chat_id):
        return

    context.user_data.clear()
    await edit_or_send_message(query, "📅 Раздел дел", build_tasks_menu())


async def open_lists_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_allowed(query.message.chat_id):
        return

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


async def open_time_picker(update: Update, date_text: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["task_date"] = date_text
    await edit_or_send_message(query, f"Выберите время для {date_text}", build_time_picker(date_text))


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
    context.user_data["task_date"] = date_text
    await edit_or_send_message(query, f"Выберите время для {date_text}", build_time_picker(date_text))


async def show_week_tasks(update: Update):
    query = update.callback_query
    await query.answer()
    tasks = get_tasks_for_week()
    await edit_or_send_message(query, render_week_tasks(tasks), build_week_tasks_keyboard(tasks))


async def show_all_tasks(update: Update):
    query = update.callback_query
    await query.answer()
    tasks = get_all_tasks_future()
    await edit_or_send_message(query, render_all_tasks(tasks), build_all_tasks_keyboard(tasks))


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
        f"✍️ Отправь новые элементы для списка:\n{LISTS[list_key]}\n\nМожно несколько строками."
    )
    context.user_data["temp_prompt_message_id"] = prompt.message_id


async def delete_task_callback(update: Update, task_id: int, source: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task = get_task(task_id)
    if not task:
        return

    date_text = task["date_text"]
    time_text = task["time_text"]
    task_text = task["text"]

    delete_task(task_id)
    remove_task_reminder(context.application, task_id)

    actor_chat_id = query.message.chat_id
    actor_name = get_user_name(actor_chat_id)
    await notify_other_user(
        context,
        actor_chat_id,
        f"🗑 {actor_name} удалил дело:\n{date_text} {time_text}\n• {task_text}"
    )

    if source == "date":
        tasks = get_tasks_for_date(date_text)
        context.user_data["active_task_message_id"] = query.message.message_id
        context.user_data["active_task_date"] = date_text
        await edit_or_send_message(query, render_tasks_for_date(date_text, tasks), build_date_tasks_keyboard(date_text, tasks))
        return

    if source == "week":
        tasks = get_tasks_for_week()
        await edit_or_send_message(query, render_week_tasks(tasks), build_week_tasks_keyboard(tasks))
        return

    if source == "all":
        tasks = get_all_tasks_future()
        await edit_or_send_message(query, render_all_tasks(tasks), build_all_tasks_keyboard(tasks))
        return


async def edit_task_callback(update: Update, task_id: int, source: str, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task = get_task(task_id)
    if not task:
        return

    context.user_data["mode"] = "await_task_edit"
    context.user_data["edit_task_id"] = task_id
    context.user_data["edit_task_source"] = source

    prompt = await query.message.reply_text(
        f"✏️ Редактирование дела\n\n"
        f"Дата: {task['date_text']}\n"
        f"Время: {task['time_text']}\n"
        f"Старый текст: {task['text']}\n\n"
        f"Отправь новый текст."
    )
    context.user_data["temp_prompt_message_id"] = prompt.message_id


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if not is_allowed(query.message.chat_id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return

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
            await open_time_picker(update, date_text, context)
            return

    if data.startswith("pick_time|"):
        _, date_text, time_text = data.split("|", 2)
        await query.answer()
        context.user_data["mode"] = "await_task_text"
        context.user_data["task_date"] = date_text
        context.user_data["task_time"] = time_text
        context.user_data["active_task_message_id"] = query.message.message_id
        context.user_data["active_task_date"] = date_text

        prompt = await query.message.reply_text(
            f"✍️ Дата: {date_text}\n⏰ Время: {time_text}\n\n"
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
        _, source, task_id = data.split("|", 2)
        await delete_task_callback(update, int(task_id), source, context)
        return

    if data.startswith("edit_task|"):
        _, source, task_id = data.split("|", 2)
        await edit_task_callback(update, int(task_id), source, context)
        return

    await query.answer("Неизвестная команда")


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_message_id = update.message.message_id

    if not is_allowed(chat_id):
        await update.message.reply_text("⛔ Нет доступа")
        return

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
        time_text = context.user_data["task_time"]
        tasks_to_add = split_multiline_items(text)

        created_ids = []
        for task_text in tasks_to_add:
            new_id = add_task(date_text, time_text, task_text, chat_id)
            if new_id:
                created_ids.append(new_id)

        for task_id in created_ids:
            task = get_task(task_id)
            if task:
                schedule_task_reminder(context.application, task_id, task["datetime_iso"])

        await refresh_tasks_message(context, chat_id, date_text)

        if tasks_to_add:
            actor_name = get_user_name(chat_id)
            added_text = "\n".join([f"• {item}" for item in tasks_to_add])
            await notify_other_user(
                context,
                chat_id,
                f"📌 {actor_name} добавил дела на {date_text} {time_text}:\n\n{added_text}"
            )

        prompt_id = context.user_data.get("temp_prompt_message_id")
        context.user_data["mode"] = None
        context.user_data.pop("temp_prompt_message_id", None)

        await safe_delete_message(context, chat_id, prompt_id)
        await safe_delete_message(context, chat_id, user_message_id)
        return

    if mode == "await_task_edit":
        task_id = context.user_data["edit_task_id"]
        source = context.user_data["edit_task_source"]

        task = get_task(task_id)
        if task:
            old_text = task["text"]
            update_task_text(task_id, text)

            updated_task = get_task(task_id)
            actor_name = get_user_name(chat_id)
            await notify_other_user(
                context,
                chat_id,
                f"✏️ {actor_name} изменил дело\n"
                f"{updated_task['date_text']} {updated_task['time_text']}\n\n"
                f"Было:\n• {old_text}\n\n"
                f"Стало:\n• {updated_task['text']}"
            )

            if source == "date":
                await refresh_tasks_message(context, chat_id, updated_task["date_text"])
            elif source == "week":
                tasks = get_tasks_for_week()
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=context.user_data.get("active_task_message_id", update.message.message_id),
                    text=render_week_tasks(tasks),
                    reply_markup=build_week_tasks_keyboard(tasks),
                )
            elif source == "all":
                tasks = get_all_tasks_future()
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=context.user_data.get("active_task_message_id", update.message.message_id),
                    text=render_all_tasks(tasks),
                    reply_markup=build_all_tasks_keyboard(tasks),
                )

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
    reschedule_all_tasks(app)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
