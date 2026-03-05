from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "8577304548:AAGmtneLEePzi99UF7746hndDrWtnQiCCJo"

tasks = {}
products = []
meds = []
chem = []
wishlist = []
places = []

user_state = {}

main_menu = ReplyKeyboardMarkup(
    [
        ["📅 Добавить дело", "📋 Посмотреть дела"],
        ["🛒 Продукты", "💊 Аптечка"],
        ["🧴 Бытовая химия"],
        ["⭐ Хотелки", "🌍 Куда поехать"],
    ],
    resize_keyboard=True,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 HomeBot готов!", reply_markup=main_menu)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    user_id = update.message.from_user.id

    if text == "📅 Добавить дело":
        user_state[user_id] = "add_date"
        await update.message.reply_text("Введи дату (например 12.03)")
        return

    if user_state.get(user_id) == "add_date":
        user_state[user_id] = ("add_task", text)
        await update.message.reply_text("Теперь напиши дело")
        return

    if isinstance(user_state.get(user_id), tuple):
        state, date = user_state[user_id]
        if state == "add_task":
            tasks.setdefault(date, []).append(text)
            user_state[user_id] = None
            await update.message.reply_text("✅ Дело добавлено", reply_markup=main_menu)
            return

    if text == "📋 Посмотреть дела":
        user_state[user_id] = "show_date"
        await update.message.reply_text("Введи дату")
        return

    if user_state.get(user_id) == "show_date":
        date = text
        user_state[user_id] = None

        if date in tasks:
            result = "\n".join(tasks[date])
            await update.message.reply_text(f"📅 {date}\n\n{result}", reply_markup=main_menu)
        else:
            await update.message.reply_text("Дел нет", reply_markup=main_menu)
        return

    if text == "🛒 Продукты":
        user_state[user_id] = "add_product"
        await update.message.reply_text("Напиши продукт")
        return

    if user_state.get(user_id) == "add_product":
        products.append(text)
        user_state[user_id] = None
        await update.message.reply_text("✅ Добавлено", reply_markup=main_menu)
        return

    if text == "💊 Аптечка":
        user_state[user_id] = "add_med"
        await update.message.reply_text("Напиши лекарство")
        return

    if user_state.get(user_id) == "add_med":
        meds.append(text)
        user_state[user_id] = None
        await update.message.reply_text("✅ Добавлено", reply_markup=main_menu)
        return

    if text == "🧴 Бытовая химия":
        user_state[user_id] = "add_chem"
        await update.message.reply_text("Напиши средство")
        return

    if user_state.get(user_id) == "add_chem":
        chem.append(text)
        user_state[user_id] = None
        await update.message.reply_text("✅ Добавлено", reply_markup=main_menu)
        return

    if text == "⭐ Хотелки":
        user_state[user_id] = "add_wish"
        await update.message.reply_text("Что хотите купить?")
        return

    if user_state.get(user_id) == "add_wish":
        wishlist.append(text)
        user_state[user_id] = None
        await update.message.reply_text("⭐ Добавлено", reply_markup=main_menu)
        return

    if text == "🌍 Куда поехать":
        user_state[user_id] = "add_place"
        await update.message.reply_text("Куда хотите поехать?")
        return

    if user_state.get(user_id) == "add_place":
        places.append(text)
        user_state[user_id] = None
        await update.message.reply_text("🌍 Добавлено", reply_markup=main_menu)
        return


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

app.run_polling()
