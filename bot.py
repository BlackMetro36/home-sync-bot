import os
import json
import datetime
import calendar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ALLOWED_USERS = [482418773,443835005]
TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "data.json"

CATEGORIES={
"products":"🛒 Продукты",
"meds":"💊 Медикаменты",
"chem":"🧴 Бытовая химия",
"useful":"🏠 Полезности",
"wishes":"⭐ Хотелки",
"trips":"✈️ Поездки"
}

def load():
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE,"w") as f:
        json.dump(data,f,indent=2)

data=load()

def menu():

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

def list_text(cat):

    items=data[cat]

    if not items:
        return f"{CATEGORIES[cat]}\n\nСписок пуст"

    txt="\n".join([f"{i+1}. {v}" for i,v in enumerate(items)])

    return f"{CATEGORIES[cat]}\n\n{txt}"

def category_keyboard(cat):

    return InlineKeyboardMarkup([

    [InlineKeyboardButton("➕ Добавить",callback_data=f"add_{cat}")],
    [InlineKeyboardButton("❌ Удалить",callback_data=f"del_{cat}")],
    [InlineKeyboardButton("⬅️ Назад",callback_data="home")]

    ])

def year_keyboard():

    year=datetime.date.today().year

    return InlineKeyboardMarkup([

    [InlineKeyboardButton(str(year),callback_data=f"year_{year}")],
    [InlineKeyboardButton(str(year+1),callback_data=f"year_{year+1}")],
    [InlineKeyboardButton(str(year+2),callback_data=f"year_{year+2}")],

    [InlineKeyboardButton("⬅️ Назад",callback_data="home")]

    ])

def month_keyboard(year):

    months=[
    "Январь","Февраль","Март","Апрель",
    "Май","Июнь","Июль","Август",
    "Сентябрь","Октябрь","Ноябрь","Декабрь"
    ]

    kb=[]

    for i,m in enumerate(months,1):

        kb.append([
        InlineKeyboardButton(
        m,
        callback_data=f"month_{year}_{i}"
        )
        ])

    kb.append([InlineKeyboardButton("⬅️ Назад",callback_data="add_task")])

    return InlineKeyboardMarkup(kb)

def day_keyboard(year,month):

    days=calendar.monthrange(year,month)[1]

    kb=[]
    row=[]

    for d in range(1,days+1):

        row.append(
        InlineKeyboardButton(
        str(d),
        callback_data=f"day_{year}_{month}_{d}"
        )
        )

        if len(row)==7:
            kb.append(row)
            row=[]

    if row:
        kb.append(row)

    kb.append([
    InlineKeyboardButton(
    "⬅️ Назад",
    callback_data=f"year_{year}"
    )
    ])

    return InlineKeyboardMarkup(kb)

def tasks_text():

    today=datetime.date.today()

    txt="📅 Ближайшие дела\n\n"

    for i in range(7):

        d=(today+datetime.timedelta(days=i)).isoformat()

        if d in data["tasks"]:

            txt+=f"{d}\n"

            for t in data["tasks"][d]:

                txt+=f"- {t}\n"

            txt+="\n"

    if txt=="📅 Ближайшие дела\n\n":
        txt="Нет дел"

    return txt

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user_id=update.effective_chat.id

    if user_id not in data["users"]:
        data["users"].append(user_id)
        save(data)

    await update.message.reply_text(
    "🏠 Домашний планер",
    reply_markup=menu()
    )

async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):

    global data
    data=load()

    q=update.callback_query
    await q.answer()

    cmd=q.data

    if cmd=="home":

        await q.message.edit_text(
        "🏠 Меню",
        reply_markup=menu()
        )

    elif cmd in CATEGORIES:

        await q.message.edit_text(
        list_text(cmd),
        reply_markup=category_keyboard(cmd)
        )

    elif cmd.startswith("add_"):

        context.user_data["mode"]=cmd.replace("add_","")

        await q.message.reply_text("Введите текст")

    elif cmd.startswith("del_"):

        cat=cmd.replace("del_","")

        items=data[cat]

        if not items:

            await q.message.reply_text("Список пуст")
            return

        kb=[]

        for i,v in enumerate(items):

            kb.append([
            InlineKeyboardButton(
            v,
            callback_data=f"remove_{cat}_{i}"
            )
            ])

        await q.message.edit_text(
        "Что удалить?",
        reply_markup=InlineKeyboardMarkup(kb)
        )

    elif cmd.startswith("remove_"):

        _,cat,i=cmd.split("_")

        data[cat].pop(int(i))

        save(data)

        await q.message.edit_text(
        list_text(cat),
        reply_markup=category_keyboard(cat)
        )

    elif cmd=="tasks":

        await q.message.edit_text(
        tasks_text(),
        reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить дело",callback_data="add_task")],
        [InlineKeyboardButton("⬅️ Назад",callback_data="home")]
        ])
        )

    elif cmd=="add_task":

        await q.message.edit_text(
        "Выберите год",
        reply_markup=year_keyboard()
        )

    elif cmd.startswith("year_"):

        year=int(cmd.split("_")[1])

        await q.message.edit_text(
        "Выберите месяц",
        reply_markup=month_keyboard(year)
        )

    elif cmd.startswith("month_"):

        _,year,month=cmd.split("_")

        year=int(year)
        month=int(month)

        await q.message.edit_text(
        "Выберите день",
        reply_markup=day_keyboard(year,month)
        )

    elif cmd.startswith("day_"):

        _,year,month,day=cmd.split("_")

        date=f"{year}-{int(month):02}-{int(day):02}"

        context.user_data["mode"]="task"
        context.user_data["date"]=date

        await q.message.reply_text(
        f"Введите задачу на {date}"
        )

async def text(update:Update,context:ContextTypes.DEFAULT_TYPE):

    global data
    data=load()

    if "mode" not in context.user_data:
        return

    mode=context.user_data["mode"]

    msg=update.message.text

    items=msg.split("\n")

    if mode=="task":

        date=context.user_data["date"]

        if date not in data["tasks"]:
            data["tasks"][date]=[]

        for item in items:

            item=item.strip()

            if item:
                data["tasks"][date].append(item)

        save(data)

        context.user_data.clear()

        await update.message.reply_text("Дело добавлено")

        return

    for item in items:

        item=item.strip()

        if item:
            data[mode].append(item)

    save(data)

    await update.message.reply_text(list_text(mode))

    context.user_data.clear()

async def notify(context:ContextTypes.DEFAULT_TYPE):

    data=load()

    today=datetime.date.today().isoformat()

    if today not in data["tasks"]:
        return

    text="📅 Дела на сегодня\n\n"

    for t in data["tasks"][today]:

        text+=f"- {t}\n"

    for u in data["users"]:

        await context.bot.send_message(u,text)

def main():

    app=ApplicationBuilder().token(TOKEN).build()

    job_queue=app.job_queue

    job_queue.run_daily(
    notify,
    time=datetime.time(hour=8)
    )

    app.add_handler(CommandHandler("start",start))

    app.add_handler(CallbackQueryHandler(buttons))

    app.add_handler(MessageHandler(filters.TEXT,text))

    print("Bot started")

    app.run_polling()

main()