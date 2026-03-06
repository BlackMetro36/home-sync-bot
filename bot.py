import os
import json
import datetime
import calendar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

ALLOWED_USERS = [482418773,443835005]
TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "data.json"

CATEGORIES = {
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


data = load()


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


async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user_id=update.effective_chat.id

    if user_id not in data["users"]:
        data["users"].append(user_id)
        save(data)

    await update.message.reply_text(
    "🏠 Домашний планер",
    reply_markup=menu()
    )


def show_list(cat):

    items=data[cat]

    if not items:
        return "Список пуст"

    return "\n".join([f"{i+1}. {v}" for i,v in enumerate(items)])


async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):

    q=update.callback_query
    await q.answer()

    cmd=q.data


    if cmd in CATEGORIES:

        text=show_list(cmd)

        kb=[
        [InlineKeyboardButton("➕ Добавить",callback_data=f"add_{cmd}")],
        [InlineKeyboardButton("❌ Удалить",callback_data=f"del_{cmd}")],
        [InlineKeyboardButton("⬅️ Назад",callback_data="home")]
        ]

        await q.message.reply_text(
        f"{CATEGORIES[cmd]}\n\n{text}",
        reply_markup=InlineKeyboardMarkup(kb)
        )


    elif cmd=="home":

        await q.message.reply_text("Меню",reply_markup=menu())


    elif cmd=="tasks":

        kb=[
        [InlineKeyboardButton("📆 Неделя",callback_data="week")],
        [InlineKeyboardButton("📋 Все",callback_data="all_tasks")],
        [InlineKeyboardButton("⬅️ Назад",callback_data="home")]
        ]

        await q.message.reply_text("Дела",reply_markup=InlineKeyboardMarkup(kb))


    elif cmd=="week":

        today=datetime.date.today()
        txt=""

        for i in range(7):

            d=(today+datetime.timedelta(days=i)).isoformat()

            if d in data["tasks"]:
                for t in data["tasks"][d]:
                    txt+=f"{d} — {t}\n"

        if txt=="":
            txt="Нет дел"

        await q.message.reply_text(txt)


    elif cmd=="all_tasks":

        txt=""

        for d in sorted(data["tasks"]):
            for t in data["tasks"][d]:
                txt+=f"{d} — {t}\n"

        if txt=="":
            txt="Нет дел"

        await q.message.reply_text(txt)


    elif cmd=="add_task":

        year=datetime.date.today().year

        kb=[]

        for y in range(year,year+3):
            kb.append([InlineKeyboardButton(str(y),callback_data=f"year_{y}")])

        await q.message.reply_text(
        "Выберите год",
        reply_markup=InlineKeyboardMarkup(kb)
        )


    elif cmd.startswith("year_"):

        year=int(cmd.split("_")[1])
        context.user_data["year"]=year

        kb=[]

        for m in range(1,13):
            kb.append([InlineKeyboardButton(str(m),callback_data=f"month_{m}")])

        await q.message.reply_text(
        "Выберите месяц",
        reply_markup=InlineKeyboardMarkup(kb)
        )


    elif cmd.startswith("month_"):

        month=int(cmd.split("_")[1])
        year=context.user_data["year"]

        context.user_data["month"]=month

        days=calendar.monthrange(year,month)[1]

        kb=[]
        row=[]

        for d in range(1,days+1):

            row.append(InlineKeyboardButton(str(d),callback_data=f"day_{d}"))

            if len(row)==7:
                kb.append(row)
                row=[]

        if row:
            kb.append(row)

        await q.message.reply_text(
        "Выберите день",
        reply_markup=InlineKeyboardMarkup(kb)
        )


    elif cmd.startswith("day_"):

        day=int(cmd.split("_")[1])
        year=context.user_data["year"]
        month=context.user_data["month"]

        date=datetime.date(year,month,day).isoformat()

        context.user_data["mode"]="task"
        context.user_data["date"]=date

        await q.message.reply_text("Введите дело")


    elif cmd.startswith("add_"):

        cat=cmd.replace("add_","")

        context.user_data["mode"]=cat

        await q.message.reply_text("Введите текст")


    elif cmd.startswith("del_"):

        cat=cmd.replace("del_","")

        items=data[cat]

        if not items:

            await q.message.reply_text("Список пуст")
            return

        kb=[]

        for i,v in enumerate(items):
            kb.append([InlineKeyboardButton(v,callback_data=f"remove_{cat}_{i}")])

        await q.message.reply_text(
        "Что удалить?",
        reply_markup=InlineKeyboardMarkup(kb)
        )


    elif cmd.startswith("remove_"):

        _,cat,i=cmd.split("_")

        data[cat].pop(int(i))

        save(data)

        text=show_list(cat)

        await q.message.reply_text(
        f"Удалено\n\n{text}",
        reply_markup=menu()
        )


async def text(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if "mode" not in context.user_data:
        return

    mode=context.user_data["mode"]

    msgs=update.message.text.split("\n")


    if mode=="task":

        date=context.user_data.get("date")

        if date not in data["tasks"]:
            data["tasks"][date]=[]

        for m in msgs:
            if m.strip():
                data["tasks"][date].append(m.strip())

        save(data)

        context.user_data.clear()

        await update.message.reply_text(
        "Дело добавлено",
        reply_markup=menu()
        )

        return


    for m in msgs:
        if m.strip():
            data[mode].append(m.strip())

    save(data)

    context.user_data.clear()

    text_list=show_list(mode)

    await update.message.reply_text(
    f"Добавлено\n\n{text_list}",
    reply_markup=menu()
    )


async def notify(context:ContextTypes.DEFAULT_TYPE):

    today=datetime.date.today().isoformat()

    if today not in data["tasks"]:
        return

    text="📅 Дела на сегодня:\n"

    for t in data["tasks"][today]:
        text+=f"- {t}\n"

    for u in data["users"]:
        await context.bot.send_message(u,text)


def main():

    app=ApplicationBuilder().token(TOKEN).build()

    job_queue=app.job_queue

    job_queue.run_daily(
    notify,
    time=datetime.time(hour=6,minute=0)
    )

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT,text))

    print("Bot started")

    app.bot.delete_webhook(drop_pending_updates=True)

    app.run_polling()


main()