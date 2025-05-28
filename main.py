import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler
)
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.sql import text as sql_text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Завантаження змінних середовища
load_dotenv()

# Константи для ConversationHandler
BUDGET_MENU, ADDING_EXPENSE, SETTING_BUDGET, AI_SESSION = range(4)

# Підключення до бази даних
DB_URL = os.getenv("DB_URL", "sqlite:///finance_bot.db")
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

# Створення таблиць
with engine.connect() as conn:
    conn.execute(sql_text("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """))
    conn.execute(sql_text("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        "limit" REAL NOT NULL
    )
    """))
    conn.commit()

# Клавіатури
def build_main_keyboard():
    keyboard = [
        [KeyboardButton("💰 Бюджет"), KeyboardButton("🤖 AI Поради")],
        [KeyboardButton("🎯 Цілі"), KeyboardButton("📊 Аналіз")],
        [KeyboardButton("➕ Транзакція"), KeyboardButton("⚙ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_budget_keyboard():
    keyboard = [
        ["➕ Додати витрату", "📊 Статистика"],
        ["⚙ Налаштування бюджету", "❌ Скасувати"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_ai_keyboard():
    keyboard = [[KeyboardButton("❌ Скасувати")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команди
async def cmd_start(update: Update, context: CallbackContext):
    user_first_name = update.effective_user.first_name or "користувачу"
    welcome_msg = f"""🦉 <b>Привіт, {user_first_name}!</b>

Я — <b>FinWise Owl</b>, ваш особистий помічник у світі фінансів."""
    await update.message.reply_text(
        text=welcome_msg,
        reply_markup=build_main_keyboard(),
        parse_mode="HTML"
    )

async def cmd_help(update: Update, context: CallbackContext):
    help_msg = """ℹ️ <b>Довідка:</b>"""
    await update.message.reply_text(help_msg, parse_mode="HTML")

# Обробники кнопок
async def handle_goals(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🎯 <b>Розділ цілей</b>\nТут ви можете керувати своїми фінансовими цілями",
        parse_mode="HTML"
    )

async def handle_analytics(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📊 <b>Розділ аналітики</b>\nТут ви можете переглядати аналітику витрат",
        parse_mode="HTML"
    )

async def handle_transaction(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "➕ <b>Додавання транзакції</b>\nВведіть суму та категорію у форматі: <code>100 їжа</code>",
        parse_mode="HTML"
    )

async def handle_settings(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "⚙ <b>Налаштування</b>\nТут ви можете налаштувати свій профіль",
        parse_mode="HTML"
    )

# AI Поради
async def handle_ai_advice(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💡 Напишіть ваше запитання про фінанси:",
        reply_markup=build_ai_keyboard()
    )
    return AI_SESSION

async def handle_ai_question(update: Update, context: CallbackContext):
    from handlers.ai import handle_ai_question as ai_handler
    return await ai_handler(update, context)

async def cancel_conversation(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Дію скасовано. Головне меню:",
        reply_markup=build_main_keyboard()
    )
    return ConversationHandler.END

# Бюджет - ConversationHandler
async def budget_start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💰 <b>Розділ бюджету</b>\nОберіть дію:",
        reply_markup=build_budget_keyboard(),
        parse_mode="HTML"
    )
    return BUDGET_MENU

async def add_expense_start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Введіть витрату у форматі:\n<code>100 їжа</code> або <code>200 транспорт</code>\n"
        "Або напишіть 'скасувати' для повернення",
        parse_mode="HTML"
    )
    return ADDING_EXPENSE

async def add_expense(update: Update, context: CallbackContext):
    try:
        user_input = update.message.text
        if user_input.lower() == 'скасувати':
            await cancel_conversation(update, context)
            return ConversationHandler.END

        parts = user_input.split()
        if len(parts) < 2:
            raise ValueError("Недостатньо даних")
            
        amount = float(parts[0])
        category = ' '.join(parts[1:]).lower()

        session = Session()
        session.execute(
            sql_text("""
                INSERT INTO transactions (user_id, amount, category, date) 
                VALUES (:user_id, :amount, :category, :date)
            """),
            {
                "user_id": update.effective_user.id,
                "amount": amount,
                "category": category,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
        session.commit()
        
        await update.message.reply_text(
            f"✅ Витрату {amount} грн на '{category}' додано!",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

    except ValueError as e:
        logger.error(f"Помилка при додаванні витрати: {e}")
        await update.message.reply_text(
            "❌ Невірний формат. Введіть, наприклад: <code>100 їжа</code>",
            parse_mode="HTML"
        )
        return ADDING_EXPENSE
    except Exception as e:
        logger.error(f"Неочікувана помилка: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка. Спробуйте ще раз.",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

async def show_statistics(update: Update, context: CallbackContext):
    try:
        session = Session()
        user_id = update.effective_user.id
        current_month = datetime.now().strftime("%Y-%m")
        
        transactions = session.execute(
            sql_text("""
                SELECT category, SUM(amount) as total FROM transactions 
                WHERE user_id = :user_id AND strftime('%Y-%m', date) = :month 
                GROUP BY category
            """),
            {"user_id": user_id, "month": current_month}
        ).fetchall()

        if not transactions:
            await update.message.reply_text(
                "📭 У вас ще немає витрат за цей місяць.",
                reply_markup=build_budget_keyboard()
            )
            return BUDGET_MENU

        total = sum(t.total for t in transactions)
        message = "📊 <b>Ваша статистика за місяць:</b>\n\n"
        message += f"💵 Загальні витрати: {total:.2f} грн\n\n"
        message += "<b>За категоріями:</b>\n"
        
        for t in transactions:
            percentage = (t.total / total) * 100
            message += f"▪ {t.category.capitalize()}: {t.total:.2f} грн ({percentage:.1f}%)\n"

        await update.message.reply_text(
            message,
            reply_markup=build_budget_keyboard(),
            parse_mode="HTML"
        )
        return BUDGET_MENU

    except Exception as e:
        logger.error(f"Помилка при отриманні статистики: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при отриманні статистики.",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

async def budget_settings_start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "⚙ <b>Налаштування бюджету</b>\n\n"
        "Введіть ліміти у форматі:\n<code>категорія ліміт</code>\n"
        "Наприклад: <code>їжа 3000</code>\n\n"
        "Доступні команди:\n"
        "/list - показати поточні ліміти\n"
        "/cancel - скасувати",
        parse_mode="HTML"
    )
    return SETTING_BUDGET

async def handle_budget_settings(update: Update, context: CallbackContext):
    try:
        user_input = update.message.text
        
        if user_input.lower() == 'скасувати':
            await cancel_conversation(update, context)
            return ConversationHandler.END
            
        if user_input.lower() == '/list':
            session = Session()
            budgets = session.execute(
                sql_text("SELECT category, \"limit\" FROM budgets WHERE user_id = :user_id"),
                {"user_id": update.effective_user.id}
            ).fetchall()
            
            if not budgets:
                await update.message.reply_text(
                    "У вас ще немає встановлених лімітів.",
                    reply_markup=build_budget_keyboard()
                )
                return SETTING_BUDGET
                
            message = "📋 <b>Ваші поточні ліміти:</b>\n"
            for budget in budgets:
                message += f"▪ {budget.category}: {budget.limit} грн\n"
                
            await update.message.reply_text(
                message,
                reply_markup=build_budget_keyboard(),
                parse_mode="HTML"
            )
            return SETTING_BUDGET

        category, limit = user_input.split(maxsplit=1)
        limit = float(limit)
        
        session = Session()
        session.execute(
            sql_text("""
                INSERT INTO budgets (user_id, category, "limit") 
                VALUES (:user_id, :category, :limit)
                ON CONFLICT(user_id, category) DO UPDATE SET "limit" = :limit
            """),
            {
                "user_id": update.effective_user.id,
                "category": category.lower(),
                "limit": limit
            }
        )
        session.commit()
        
        await update.message.reply_text(
            f"✅ Ліміт для '{category}' встановлено на {limit} грн",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ Невірний формат. Введіть, наприклад: <code>їжа 3000</code>",
            parse_mode="HTML"
        )
        return SETTING_BUDGET
    except Exception as e:
        logger.error(f"Помилка при налаштуванні бюджету: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка. Спробуйте ще раз.",
            reply_markup=build_budget_keyboard()
        )
        return SETTING_BUDGET

def setup_handlers(application: Application):
    # Основні команди
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    
    # Обробники кнопок головного меню
    application.add_handler(MessageHandler(filters.Text(["🎯 Цілі"]), handle_goals))
    application.add_handler(MessageHandler(filters.Text(["📊 Аналіз"]), handle_analytics))
    application.add_handler(MessageHandler(filters.Text(["➕ Транзакція"]), handle_transaction))
    application.add_handler(MessageHandler(filters.Text(["⚙ Налаштування"]), handle_settings))
    
    # Обробник бюджету
    budget_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text(["💰 Бюджет"]), budget_start),
            CommandHandler("budget", budget_start)
        ],
        states={
            BUDGET_MENU: [
                MessageHandler(filters.Text(["➕ Додати витрату"]), add_expense_start),
                MessageHandler(filters.Text(["📊 Статистика"]), show_statistics),
                MessageHandler(filters.Text(["⚙ Налаштування бюджету"]), budget_settings_start),
                MessageHandler(filters.Text(["❌ Скасувати"]), cancel_conversation)
            ],
            ADDING_EXPENSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense)
            ],
            SETTING_BUDGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_budget_settings),
                CommandHandler("list", handle_budget_settings)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Text(["❌ Скасувати"]), cancel_conversation)
        ]
    )
    application.add_handler(budget_handler)
    
    # Обробник AI
    ai_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["🤖 AI Поради"]), handle_ai_advice)],
        states={
            AI_SESSION: [
                MessageHandler(filters.TEXT & ~filters.Text(["❌ Скасувати"]), handle_ai_question),
                MessageHandler(filters.Text(["❌ Скасувати"]), cancel_conversation)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Text(["❌ Скасувати"]), cancel_conversation)
        ]
    )
    application.add_handler(ai_handler)

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("Не вказано TELEGRAM_TOKEN")
    
    application = Application.builder().token(token).build()
    setup_handlers(application)
    
    logger.info("Бот запускається...")
    application.run_polling()

if __name__ == "__main__":
    main()