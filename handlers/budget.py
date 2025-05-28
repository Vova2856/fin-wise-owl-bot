from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler
)
from datetime import datetime
import logging
from database import Session, Transaction, Budget  # Припускаючи, що у вас є такі моделі

logger = logging.getLogger(__name__)

# Стани для ConversationHandler
BUDGET_MENU, ADDING_EXPENSE, SETTING_BUDGET, VIEWING_STATS = range(4)

def build_budget_keyboard():
    """Створює клавіатуру для бюджету"""
    keyboard = [
        ["➕ Додати витрату", "📊 Статистика"],
        ["⚙ Налаштування бюджету", "❌ Скасувати"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def budget_start(update: Update, context: CallbackContext) -> int:
    """Початок роботи з бюджетом"""
    await update.message.reply_text(
        "💰 <b>Розділ бюджету</b>\n"
        "Оберіть дію:",
        reply_markup=build_budget_keyboard(),
        parse_mode="HTML"
    )
    return BUDGET_MENU

async def add_expense_start(update: Update, context: CallbackContext) -> int:
    """Початок додавання витрати"""
    await update.message.reply_text(
        "Введіть витрату у форматі:\n"
        "<code>100 їжа</code> або <code>200 транспорт</code>\n"
        "Або напишіть 'скасувати' для повернення",
        parse_mode="HTML"
    )
    return ADDING_EXPENSE

async def add_expense(update: Update, context: CallbackContext) -> int:
    """Обробка додавання витрати"""
    try:
        text = update.message.text
        if text.lower() == 'скасувати':
            await update.message.reply_text(
                "Дію скасовано",
                reply_markup=build_budget_keyboard()
            )
            return BUDGET_MENU

        amount, *category_parts = text.split()
        amount = float(amount)
        category = ' '.join(category_parts).lower()

        # Збереження витрати в базу даних
        session = Session()
        transaction = Transaction(
            user_id=update.effective_user.id,
            amount=amount,
            category=category,
            date=datetime.now()
        )
        session.add(transaction)
        session.commit()
        
        await update.message.reply_text(
            f"✅ Витрату {amount} грн на '{category}' додано!",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

    except ValueError:
        await update.message.reply_text(
            "Невірний формат. Введіть, наприклад: <code>100 їжа</code>",
            parse_mode="HTML"
        )
        return ADDING_EXPENSE

async def show_statistics(update: Update, context: CallbackContext) -> int:
    """Показ статистики витрат"""
    try:
        session = Session()
        user_id = update.effective_user.id
        
        # Отримання транзакцій за поточний місяць
        current_month = datetime.now().strftime("%Y-%m")
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.date.like(f"{current_month}%")
        ).all()

        if not transactions:
            await update.message.reply_text(
                "📭 У вас ще немає витрат за цей місяць.",
                reply_markup=build_budget_keyboard()
            )
            return BUDGET_MENU

        # Розрахунок статистики
        total = sum(t.amount for t in transactions)
        categories = {}
        for t in transactions:
            categories[t.category] = categories.get(t.category, 0) + t.amount

        # Формування повідомлення
        message = "📊 <b>Ваша статистика за місяць:</b>\n\n"
        message += f"💵 Загальні витрати: {total:.2f} грн\n\n"
        message += "<b>За категоріями:</b>\n"
        
        for category, amount in categories.items():
            percentage = (amount / total) * 100
            message += f"▪ {category.capitalize()}: {amount:.2f} грн ({percentage:.1f}%)\n"

        await update.message.reply_text(
            message,
            reply_markup=build_budget_keyboard(),
            parse_mode="HTML"
        )
        return BUDGET_MENU

    except Exception as e:
        logger.error(f"Помилка при отриманні статистики: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при отриманні статистики. Спробуйте пізніше.",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

async def budget_settings_start(update: Update, context: CallbackContext) -> int:
    """Початок налаштування бюджету"""
    await update.message.reply_text(
        "⚙ <b>Налаштування бюджету</b>\n\n"
        "Введіть ліміти у форматі:\n"
        "<code>категорія ліміт</code>\n"
        "Наприклад: <code>їжа 3000</code>\n\n"
        "Доступні команди:\n"
        "/list - показати поточні ліміти\n"
        "/cancel - скасувати",
        parse_mode="HTML"
    )
    return SETTING_BUDGET

async def handle_budget_settings(update: Update, context: CallbackContext) -> int:
    """Обробка налаштувань бюджету"""
    try:
        text = update.message.text
        
        if text.lower() == '/cancel':
            await update.message.reply_text(
                "Налаштування бюджету скасовано",
                reply_markup=build_budget_keyboard()
            )
            return BUDGET_MENU
            
        if text.lower() == '/list':
            session = Session()
            budgets = session.query(Budget).filter(
                Budget.user_id == update.effective_user.id
            ).all()
            
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

        # Обробка встановлення ліміту
        category, limit = text.split(maxsplit=1)
        limit = float(limit)
        
        session = Session()
        budget = session.query(Budget).filter(
            Budget.user_id == update.effective_user.id,
            Budget.category == category.lower()
        ).first()
        
        if budget:
            budget.limit = limit
        else:
            budget = Budget(
                user_id=update.effective_user.id,
                category=category.lower(),
                limit=limit
            )
            session.add(budget)
        
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

async def cancel_budget(update: Update, context: CallbackContext) -> int:
    """Скасування роботи з бюджетом"""
    from main import build_main_keyboard
    await update.message.reply_text(
        "Роботу з бюджетом завершено. Що бажаєте зробити?",
        reply_markup=build_main_keyboard()
    )
    return ConversationHandler.END

def setup(application: Application) -> None:
    """Налаштування обробників бюджету"""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text(["💰 Бюджет"]), budget_start),
            CommandHandler("budget", budget_start)
        ],
        states={
            BUDGET_MENU: [
                MessageHandler(filters.Text(["➕ Додати витрату"]), add_expense_start),
                MessageHandler(filters.Text(["📊 Статистика"]), show_statistics),
                MessageHandler(filters.Text(["⚙ Налаштування бюджету"]), budget_settings_start),
                MessageHandler(filters.Text(["❌ Скасувати"]), cancel_budget)
            ],
            ADDING_EXPENSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense)
            ],
            SETTING_BUDGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_budget_settings),
                CommandHandler("list", handle_budget_settings),
                CommandHandler("cancel", cancel_budget)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Text(["❌ Скасувати"]), cancel_budget),
            CommandHandler("cancel", cancel_budget)
        ]
    )
    application.add_handler(conv_handler)