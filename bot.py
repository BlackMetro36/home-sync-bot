import os
import json
import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ALLOWED_USERS = [482418773,443835005]
TOKEN=os.getenv("BOT_TOKEN")
DATA_FILE="data.json"

CATEGORIES={
"products":"🛒 Продукты",
"meds":"💊 Медикаменты",
"chem":"🧴 Химия",
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

    [InlineKeyboardButton("➕ Добавить дело",callback_data="task_menu")],

    [InlineKeyboardButton("🛒 Продукты",callback_data="products"),
     InlineKeyboardButton("💊 Медикаменты",callback_data="meds")],

    [InlineKeyboardButton("🧴 Химия",callback_data="chem"),
     InlineKeyboardButton("🏠 Полезности",callback_data="useful")],

    [InlineKeyboardButton("⭐ Хотелки",callback_data="wishes"),
     InlineKeyboardButton("✈️ Поездки",callback_data="trips")]

    ])

def task_dates():

    today=datetime.date.today()

    kb=[

    [InlineKeyboardButton("Сегодня",callback_data=f"date_{today}")],
    [InlineKeyboardButton("Завтра",callback_data=f"date_{today+datetime.timedelta(days=1)}")],
    [InlineKeyboardButton("+2 дня",callback_data=f"date_{today+datetime.timedelta(days=2)}")],
    [InlineKeyboardButton("+3 дня",callback_data=f"date_{today+datetime.timedelta(days=3)}")],
    [InlineKeyboardButton("+7 дней",callback_data=f"date_{today+datetime.timedelta(days=7)}")],
    [InlineKeyboardButton("⬅️ Назад",callback_data="home")]

    ]

    return InlineKeyboardMarkup(kb)

def list_text(cat):

    items=sorted(data[cat])

    if not items:
        return f"{CATEGORIES[cat]}\n\nСписок пуст"

    txt="\n".join([f"{i+1}. {v}" for i,v in enumerate(items)])

    return f"{CATEGORIES[cat]}\n\n{txt}"

def tasks_keyboard():

    kb=[]

    for d in sorted(data["tasks"]):

        for i,t in enumerate(data["tasks"][d]):

            mark="☑" if t["done"] else "☐"

            kb.append([
            InlineKeyboardButton(
            f"{mark} {t['text']} ({d})",
            callback_data=f"done_{d}_{i}"
            )
            ])

    kb.append([InlineKeyboardButton("⬅️ Назад",callback_data="home")])

    return InlineKeyboardMarkup(kb)

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

    q=update.callback_query
    await q.answer()

    cmd=q.data

    if cmd in CATEGORIES:

        await q.message.reply_text(
        list_text(cmd),
        reply_markup=InlineKeyboardMarkup([

        [InlineKeyboardButton("➕ Добавить",callback_data=f"add_{cmd}")],
        [InlineKeyboardButton("❌ Удалить",callback_data=f"del_{cmd}")],
        [InlineKeyboardButton("⬅️ Назад",callback_data="home")]

        ])
        )

    elif cmd=="home":

        await q.message.reply_text("Меню",reply_markup=menu())

    elif cmd=="tasks":

        if not data["tasks"]:
            await q.message.reply_text("Нет задач")
            return

        await q.message.reply_text(
        "Нажмите чтобы отметить выполнение",
        reply_markup=tasks_keyboard()
        )

    elif cmd=="task_menu":

        await q.message.reply_text(
        "Выберите дату",
        reply_markup=task_dates()
        )

    elif cmd.startswith("date_"):

        date=cmd.replace("date_","")

        context.user_data["mode"]="task"
        context.user_data["date"]=date

        await q.message.reply_text(
        f"Введите задачу на {date}"
        )

    elif cmd.startswith("done_"):

        _,date,i=cmd.split("_")

        task=data["tasks"][date][int(i)]

        task["done"]=not task["done"]

        save(data)

        await q.message.reply_text(
        "Обновлено",
        reply_markup=tasks_keyboard()
        )

    elif cmd.startswith("add_"):

        context.user_data["mode"]=cmd.replace("add_","")

        await q.message.reply_text("Введите текст")

    elif cmd.startswith("del_"):

        cat=cmd.replace("del_","")

        kb=[]

        for i,v in enumerate(data[cat]):

            kb.append([
            InlineKeyboardButton(
            v,
            callback_data=f"remove_{cat}_{i}"
            )
            ])

        await q.message.reply_text(
        "Что удалить?",
        reply_markup=InlineKeyboardMarkup(kb)
        )

    elif cmd.startswith("remove_"):

        _,cat,i=cmd.split("_")

        data[cat].pop(int(i))

        save(data)

        await q.message.reply_text("Удалено")
        await q.message.reply_text(list_text(cat))
        await q.message.reply_text("Меню",reply_markup=menu())

async def text(update:Update,context:ContextTypes.DEFAULT_TYPE):

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

            if not item:
                continue

            repeat=None

            if "|" in item:

                item,repeat=item.split("|")
                repeat=repeat.strip()

            data["tasks"][date].append({

            "text":item.strip(),
            "done":False,
            "repeat":repeat,
            "user":update.effective_chat.first_name

            })

        save(data)

        context.user_data.clear()

        await update.message.reply_text("Задача добавлена",reply_markup=menu())

        return

    for item in items:

        item=item.strip()

        if item:
            data[mode].append(item)

    save(data)

    await update.message.reply_text(list_text(mode))

    context.user_data.clear()

    await update.message.reply_text("Меню",reply_markup=menu())

async def notify(context:ContextTypes.DEFAULT_TYPE):

    today=datetime.date.today().isoformat()

    if today not in data["tasks"]:
        return

    text="📅 Дела на сегодня\n\n"

    for t in data["tasks"][today]:

        mark="☑" if t["done"] else "☐"

        text+=f"{mark} {t['text']}\n"

    for u in data["users"]:

        await context.bot.send_message(u,text)

def main():

    app=ApplicationBuilder().token(TOKEN).build()

    job_queue=app.job_queue

    job_queue.run_daily(notify,time=datetime.time(hour=8))
    job_queue.run_daily(notify,time=datetime.time(hour=20))

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT,text))

    print("Bot started")

    app.run_polling()

main()