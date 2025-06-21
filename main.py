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
from sqlalchemy.orm import Session
from datetime import datetime
import handlers.ai as ai
import handlers.settings as settings
from database import init_db, User, Transaction, Budget, Goal, engine, Session as DBSession
import handlers.transactions as db_transactions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

ADD_TRANSACTION_TYPE, ADD_TRANSACTION_AMOUNT, ADD_TRANSACTION_CATEGORY, ADD_TRANSACTION_DESCRIPTION = range(5, 9)
ADD_INCOME_AMOUNT, ADD_INCOME_CATEGORY, ADD_INCOME_DESCRIPTION = range(9, 12)
BUDGET_MENU, ADDING_EXPENSE, SETTING_BUDGET, AI_SESSION, GOAL_MENU = range(5)

init_db()

def build_main_keyboard():
    keyboard = [
        [KeyboardButton("➕ Транзакція"), KeyboardButton("💵 Дохід")],
        [KeyboardButton("💰 Бюджет"), KeyboardButton("🤖 AI Поради")],
        [KeyboardButton("🎯 Цілі"), KeyboardButton("📊 Аналіз")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_transaction_type_keyboard():
    keyboard = [
        [KeyboardButton("Дохід"), KeyboardButton("Витрата")],
        [KeyboardButton("❌ Скасувати")]
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

def build_goals_keyboard():
    keyboard = [
        ["📋 Список цілей", "➕ Нова ціль"],
        ["💰 Додати кошти", "❌ Видалити ціль"],
        ["🔙 На головну"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def cmd_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code)

    user_first_name = update.effective_user.first_name or "користувачу"
    welcome_msg = f"""🦉 <b>Привіт, {user_first_name}!</b>

Я — <b>FinWise Owl</b>, ваш особистий помічник у світі фінансів.

🔹 Ведіть облік витрат
🔹 Аналізуйте свої фінанси
🔹 Досягайте цілей
🔹 Отримуйте персоналізовані поради"""
    await update.message.reply_text(
        text=welcome_msg,
        reply_markup=build_main_keyboard(),
        parse_mode="HTML"
    )

async def cmd_help(update: Update, context: CallbackContext):
    help_msg = """ℹ️ <b>Довідка по командам:</b>

<b>Основні команди:</b>
/start - Початок роботи
/help - Довідка
/analytics - Фінансова аналітика

<b>Бюджет:</b>
/budget - Управління бюджетом
/add_expense - Додати витрату

<b>Цілі:</b>
/goals - Управління цілями
/goal_create - Створити нову ціль

<b>AI Поради:</b>
/advice - Отримати фінансові поради"""
    await update.message.reply_text(help_msg, parse_mode="HTML")

async def handle_transaction_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code)

    await update.message.reply_text(
        "➕ <b>Яку транзакцію ви хочете додати?</b>",
        reply_markup=build_transaction_type_keyboard(),
        parse_mode="HTML"
    )
    return ADD_TRANSACTION_TYPE

async def get_transaction_type(update: Update, context: CallbackContext):
    text = update.message.text
    if text.lower() == "дохід":
        context.user_data['transaction_type'] = 'income'
    elif text.lower() == "витрата":
        context.user_data['transaction_type'] = 'expense'
    else:
        await update.message.reply_text("Будь ласка, оберіть 'Дохід' або 'Витрата'.")
        return ADD_TRANSACTION_TYPE

    await update.message.reply_text("Введіть суму транзакції (наприклад, <code>100.50</code>):", parse_mode="HTML")
    return ADD_TRANSACTION_AMOUNT

async def get_transaction_amount(update: Update, context: CallbackContext):
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            await update.message.reply_text("Сума має бути позитивним числом. Спробуйте ще раз.")
            return ADD_TRANSACTION_AMOUNT
        context.user_data['amount'] = amount
        await update.message.reply_text("Введіть категорію (наприклад, <code>Їжа</code>, <code>Зарплата</code>):", parse_mode="HTML")
        return ADD_TRANSACTION_CATEGORY
    except ValueError:
        await update.message.reply_text("Невірний формат суми. Введіть число, наприклад: <code>100</code> або <code>50.75</code>", parse_mode="HTML")
        return ADD_TRANSACTION_AMOUNT

async def get_transaction_category(update: Update, context: CallbackContext):
    category = update.message.text.strip()
    if not category:
        await update.message.reply_text("Категорія не може бути пустою. Спробуйте ще раз.")
        return ADD_TRANSACTION_CATEGORY
    context.user_data['category'] = category
    await update.message.reply_text("Введіть опис транзакції (або 'пропустити', якщо не потрібно):")
    return ADD_TRANSACTION_DESCRIPTION

async def get_transaction_description(update: Update, context: CallbackContext):
    description = update.message.text.strip()
    if description.lower() == 'пропустити':
        description = None

    user_id = update.effective_user.id
    transaction_type = context.user_data['transaction_type']
    amount = context.user_data['amount']
    category = context.user_data['category']

    success = await db_transactions.add_transaction(
        user_id=user_id,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
        description=description
    )

    if success:
        reply_text = f"✅ {transaction_type.capitalize()} {amount} грн на '{category}' додано!"
        if description:
            reply_text += f"\n📝 Опис: {description}"
    else:
        reply_text = "❌ Сталася помилка при додаванні транзакції."

    await update.message.reply_text(reply_text, reply_markup=build_main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# Новий функціонал для додавання доходу
async def income_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code)

    context.user_data['transaction_type'] = 'income'
    await update.message.reply_text(
        "💵 <b>Додавання доходу</b>\n\n"
        "Введіть суму доходу (наприклад, <code>100.50</code>):",
        parse_mode="HTML"
    )
    return ADD_INCOME_AMOUNT

async def get_income_amount(update: Update, context: CallbackContext):
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            await update.message.reply_text("Сума має бути позитивним числом. Спробуйте ще раз.")
            return ADD_INCOME_AMOUNT
        context.user_data['amount'] = amount
        await update.message.reply_text(
            "Введіть категорію доходу (наприклад, <code>Зарплата</code>, <code>Фріланс</code>):",
            parse_mode="HTML"
        )
        return ADD_INCOME_CATEGORY
    except ValueError:
        await update.message.reply_text("Невірний формат суми. Введіть число, наприклад: <code>100</code> або <code>50.75</code>", parse_mode="HTML")
        return ADD_INCOME_AMOUNT

async def get_income_category(update: Update, context: CallbackContext):
    category = update.message.text.strip()
    if not category:
        await update.message.reply_text("Категорія не може бути пустою. Спробуйте ще раз.")
        return ADD_INCOME_CATEGORY
    context.user_data['category'] = category
    await update.message.reply_text("Введіть опис доходу (або 'пропустити', якщо не потрібно):")
    return ADD_INCOME_DESCRIPTION

async def get_income_description(update: Update, context: CallbackContext):
    description = update.message.text.strip()
    if description.lower() == 'пропустити':
        description = None

    user_id = update.effective_user.id
    amount = context.user_data['amount']
    category = context.user_data['category']

    success = await db_transactions.add_transaction(
        user_id=user_id,
        amount=amount,
        transaction_type='income',
        category=category,
        description=description
    )

    if success:
        reply_text = f"✅ Дохід {amount} грн на '{category}' додано!"
        if description:
            reply_text += f"\n📝 Опис: {description}"
    else:
        reply_text = "❌ Сталася помилка при додаванні доходу."

    await update.message.reply_text(reply_text, reply_markup=build_main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: CallbackContext):
    context.user_data.clear()
    await update.message.reply_text(
        "Дію скасовано. Головне меню:",
        reply_markup=build_main_keyboard()
    )
    return ConversationHandler.END

async def handle_settings(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "⚙ <b>Налаштування</b>\nТут ви можете налаштувати свій профіль\n\n"
        "Доступні опції:\n"
        "🔸 Змінити валюту\n"
        "🔸 Налаштувати сповіщення\n"
        "🔸 Експорт даних",
        parse_mode="HTML"
    )

async def handle_ai_advice(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💡 Напишіть ваше запитання про фінанси:",
        reply_markup=build_ai_keyboard()
    )
    return AI_SESSION

async def budget_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code)

    await update.message.reply_text(
        "💰 <b>Розділ бюджету</b>\nОберіть дію:",
        reply_markup=build_budget_keyboard(),
        parse_mode="HTML"
    )
    return BUDGET_MENU

async def add_expense_start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Введіть витрату у форматі:\n<code>100 їжа</code> або <code>200 транспорт обід</code>\n"
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

        parts = user_input.split(maxsplit=2)
        if len(parts) < 2:
            raise ValueError("Недостатньо даних")
            
        amount = float(parts[0].replace(',', '.'))
        category = parts[1].lower()
        description = parts[2] if len(parts) > 2 else None

        success = await db_transactions.add_transaction(
            user_id=update.effective_user.id,
            amount=amount,
            transaction_type='expense',
            category=category,
            description=description
        )
        
        if success:
            reply_text = f"✅ Витрату {amount} грн на '{category}' додано!"
            if description:
                reply_text += f"\n📝 Опис: {description}"
            await update.message.reply_text(reply_text, reply_markup=build_budget_keyboard())
            return BUDGET_MENU
        else:
            await update.message.reply_text("❌ Помилка при додаванні витрати.", reply_markup=build_budget_keyboard())
            return BUDGET_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ Невірний формат. Введіть: <code>100 їжа</code> або <code>200 транспорт обід</code>",
            parse_mode="HTML"
        )
        return ADDING_EXPENSE
    except Exception as e:
        logger.error(f"Помилка: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка. Спробуйте ще раз.",
            reply_markup=build_budget_keyboard()
        )
        return BUDGET_MENU

async def show_statistics(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        transactions_list = await db_transactions.get_transactions(user_id, limit=9999)

        if not transactions_list:
            await update.message.reply_text(
                "📭 У вас ще немає транзакцій.",
                reply_markup=build_budget_keyboard()
            )
            return BUDGET_MENU

        total_income = sum(t.amount for t in transactions_list if t.type == 'income')
        total_expense = sum(t.amount for t in transactions_list if t.type == 'expense')
        current_balance = await db_transactions.get_balance(user_id)

        monthly_expenses_by_category = {}
        monthly_income_by_category = {}
        current_month_str = datetime.now().strftime("%Y-%m")

        for t in transactions_list:
            if t.date.strftime("%Y-%m") == current_month_str:
                if t.type == 'expense':
                    monthly_expenses_by_category[t.category] = monthly_expenses_by_category.get(t.category, 0.0) + t.amount
                elif t.type == 'income':
                    monthly_income_by_category[t.category] = monthly_income_by_category.get(t.category, 0.0) + t.amount
        
        sorted_expense_categories = sorted(monthly_expenses_by_category.items(), key=lambda item: item[1], reverse=True)
        sorted_income_categories = sorted(monthly_income_by_category.items(), key=lambda item: item[1], reverse=True)
        total_monthly_expense = sum(monthly_expenses_by_category.values())
        total_monthly_income = sum(monthly_income_by_category.values())

        message = "📊 <b>Ваша фінансова статистика:</b>\n\n"
        message += f"💰 <b>Поточний баланс:</b> {current_balance:.2f} грн\n"
        message += f"⬆️ <b>Всього доходів:</b> {total_income:.2f} грн\n"
        message += f"⬇️ <b>Всього витрат:</b> {total_expense:.2f} грн\n\n"
        
        if sorted_income_categories:
            message += f"<b>Доходи за {datetime.now().strftime('%B %Y').capitalize()}:</b>\n"
            message += f"💵 <b>Загальні доходи цього місяця:</b> {total_monthly_income:.2f} грн\n\n"
            message += "<b>За категоріями:</b>\n"
            for category, amount in sorted_income_categories:
                message += f"▪ {category.capitalize()}: {amount:.2f} грн\n"
            message += "\n"
        
        if sorted_expense_categories:
            message += f"<b>Витрати за {datetime.now().strftime('%B %Y').capitalize()}:</b>\n"
            message += f"💵 <b>Загальні витрати цього місяця:</b> {total_monthly_expense:.2f} грн\n\n"
            message += "<b>За категоріями:</b>\n"
            for category, amount in sorted_expense_categories:
                percentage = (amount / total_monthly_expense) * 100 if total_monthly_expense > 0 else 0
                message += f"▪ {category.capitalize()}: {amount:.2f} грн ({percentage:.1f}%)\n"
        else:
            message += "📭 У вас ще немає витрат за цей місяць.\n"

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
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code)

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
    user_id = update.effective_user.id
    try:
        user_input = update.message.text
        
        if user_input.lower() == 'скасувати' or user_input.lower() == '/cancel':
            await cancel_conversation(update, context)
            return ConversationHandler.END
            
        if user_input.lower() == '/list':
            session = DBSession()
            budgets = session.query(Budget).filter_by(user_id=user_id).all()
            session.close()
            
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

        parts = user_input.split(maxsplit=1)
        if len(parts) < 2:
            raise ValueError("Невірний формат. Введіть категорію та ліміт.")
        
        category = parts[0].lower()
        limit = float(parts[1])
        
        session = DBSession()
        budget = session.query(Budget).filter_by(user_id=user_id, category=category).first()
        if budget:
            budget.limit = limit
            action_msg = "оновлено"
        else:
            budget = Budget(user_id=user_id, category=category, limit=limit)
            action_msg = "встановлено"
        session.add(budget)
        session.commit()
        session.close()
        
        await update.message.reply_text(
            f"✅ Ліміт для '{category}' {action_msg} на {limit} грн",
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
        return BUDGET_MENU

async def handle_goals(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code)

    await update.message.reply_text(
        "🎯 <b>Розділ цілей</b>\nОберіть дію:",
        reply_markup=build_goals_keyboard(),
        parse_mode="HTML"
    )
    return GOAL_MENU

async def goal_list(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    session = DBSession()
    try:
        goals = session.query(Goal).filter_by(user_id=user_id).all()

        if not goals:
            await update.message.reply_text("📭 У вас ще немає цілей", reply_markup=build_goals_keyboard())
            return GOAL_MENU

        response = "🎯 <b>Ваші цілі:</b>\n\n"
        for goal in goals:
            progress = (goal.current_amount / goal.target_amount) * 100 if goal.target_amount > 0 else 0
            monthly = (goal.target_amount - goal.current_amount) / goal.months if goal.months and goal.months > 0 else 0
            
            response += (
                f"🆔 <b>ID:</b> {goal.id}\n"
                f"📌 <b>Назва:</b> {goal.name}\n"
                f"💵 <b>Ціль:</b> {goal.target_amount} грн\n"
                f"💳 <b>Внесено:</b> {goal.deposits:.2f} грн\n"
                f"💰 <b>Накопичено:</b> {goal.current_amount:.2f} грн ({progress:.1f}%)\n"
            )
            if goal.months and goal.months > 0:
                 response += f"📅 <b>Місячна сума:</b> ~{monthly:.2f} грн\n"
            if goal.description:
                response += f"📝 <b>Опис:</b> {goal.description}\n"
            response += f"------------------------\n"

        await update.message.reply_text(response, parse_mode="HTML", reply_markup=build_goals_keyboard())
        return GOAL_MENU

    except Exception as e:
        logger.error(f"Помилка при отриманні списку цілей: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при отриманні списку цілей.",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU
    finally:
        session.close()

async def goal_create_prompt(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📌 Введіть назву цілі, цільову суму та кількість місяців у форматі:\n"
        "<code>Назва Сума Місяці</code>\n\n"
        "Наприклад: <code>Ноутбук 25000 6</code>",
        parse_mode="HTML"
    )
    context.user_data['next_state'] = GOAL_MENU
    return "WAITING_GOAL_CREATE"

async def goal_create(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    session = DBSession()
    try:
        text = update.message.text.strip()
        tokens = text.split()
        
        if len(tokens) < 3:
            await update.message.reply_text(
                "❌ Неправильний формат. Використовуйте: Назва Сума Місяці",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU
            
        try:
            months = int(tokens[-1])
            target_amount = float(tokens[-2])
            name = ' '.join(tokens[:-2])
            description = None
        except ValueError:
            await update.message.reply_text(
                "❌ Помилка у форматі даних. Перевірте, що сума та місяці - числа.",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU

        if not name:
            await update.message.reply_text("❌ Назва цілі не може бути пустою", reply_markup=build_goals_keyboard())
            return GOAL_MENU

        goal = Goal(
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            months=months,
            created_at=datetime.now().date(),
            description=description,
            deposits=0.0
        )
        session.add(goal)
        session.commit()

        reply_text = (
            f"✅ Ціль <b>'{name}'</b> створена!\n"
            f"💵 Сума: <b>{target_amount}</b> грн\n"
            f"📅 Термін: <b>{months}</b> місяців\n"
            f"💳 Стартовий внесок: <b>0.00</b> грн"
        )
            
        await update.message.reply_text(
            reply_text,
            parse_mode="HTML",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU

    except Exception as e:
        logger.error(f"Помилка при створенні цілі: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при створенні цілі",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU
    finally:
        session.close()

async def goal_add_prompt(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💳 Введіть ID цілі та суму внеску у форматі:\n"
        "<code>ID Сума</code>\n\n"
        "Наприклад: <code>3 1500</code>\n"
        "Щоб побачити список цілей, натисніть /list",
        parse_mode="HTML"
    )
    return "WAITING_DEPOSIT"

async def handle_deposit(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    session = DBSession()
    try:
        args = update.message.text.split()
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Неправильний формат. Використовуйте: ID Сума",
                reply_markup=build_goals_keyboard()
            )
            return "WAITING_DEPOSIT"

        goal_id = int(args[0])
        amount = float(args[1])
        
        if amount <= 0:
            await update.message.reply_text("❌ Сума внеску має бути більше 0", reply_markup=build_goals_keyboard())
            return "WAITING_DEPOSIT"

        goal = session.query(Goal).filter_by(id=goal_id, user_id=user_id).first()

        if not goal:
            await update.message.reply_text(
                "❌ Ціль не знайдена",
                reply_markup=build_goals_keyboard()
            )
            return "WAITING_DEPOSIT"

        # Оновлюємо суми цілі
        goal.deposits += amount
        goal.current_amount += amount
        session.commit()

        # Додаємо транзакцію
        await db_transactions.add_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='goal_deposit',
            category=f"Внесок у ціль: {goal.name}",
            description=f"Додано кошти до цілі '{goal.name}'"
        )

        # Розраховуємо прогрес
        progress = (goal.current_amount / goal.target_amount) * 100
        remaining = goal.target_amount - goal.current_amount
        
        await update.message.reply_text(
            f"✅ Внесено <b>{amount:.2f}</b> грн до цілі <b>'{goal.name}'</b>!\n"
            f"💰 Загальний внесок: <b>{goal.deposits:.2f}</b> грн\n"
            f"📈 Прогрес: <b>{progress:.1f}%</b>\n"
            f"🎯 Залишилось зібрати: <b>{remaining:.2f}</b> грн",
            parse_mode="HTML",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ Помилка у форматі даних. Перевірте, що ID та сума - числа",
            reply_markup=build_goals_keyboard()
        )
        return "WAITING_DEPOSIT"
    except Exception as e:
        logger.error(f"Помилка при внесенні коштів: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при внесенні коштів",
            reply_markup=build_goals_keyboard()
        )
        return "WAITING_DEPOSIT"
    finally:
        session.close()

async def goal_delete_prompt(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ Введіть ID цілі для видалення:\n"
        "<code>ID</code>\n\n"
        "Наприклад: <code>2</code>",
        parse_mode="HTML"
    )
    return "WAITING_GOAL_DELETE"

async def goal_delete(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    session = DBSession()
    try:
        goal_id = int(update.message.text)

        goal = session.query(Goal).filter_by(id=goal_id, user_id=user_id).first()

        if not goal:
            await update.message.reply_text(
                "❌ Ціль не знайдена",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU

        session.delete(goal)
        session.commit()

        await update.message.reply_text(
            f"✅ Ціль <b>'{goal.name}'</b> видалена!",
            parse_mode="HTML",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ Помилка у форматі даних. ID має бути числом",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU
    except Exception as e:
        logger.error(f"Помилка при видаленні цілі: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при видаленні цілі",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU
    finally:
        session.close()

async def handle_analytics(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        all_transactions = await db_transactions.get_transactions(user_id, limit=99999)

        if not all_transactions:
            await update.message.reply_text(
                "📭 У вас ще немає транзакцій для аналітики.",
                reply_markup=build_main_keyboard()
            )
            return ConversationHandler.END

        current_balance = await db_transactions.get_balance(user_id)

        spending_by_category = {}
        income_by_category = {}
        for t in all_transactions:
            if t.type == 'expense':
                spending_by_category[t.category] = spending_by_category.get(t.category, 0.0) + t.amount
            elif t.type == 'income':
                income_by_category[t.category] = income_by_category.get(t.category, 0.0) + t.amount

        sorted_expense_categories = sorted(spending_by_category.items(), key=lambda item: item[1], reverse=True)
        sorted_income_categories = sorted(income_by_category.items(), key=lambda item: item[1], reverse=True)
        total_overall_expense = sum(spending_by_category.values())
        total_overall_income = sum(income_by_category.values())

        months_data = {}
        for t in all_transactions:
            if t.type == 'expense' and t.date:
                month_key = t.date.strftime('%Y-%m')
                months_data[month_key] = months_data.get(month_key, 0.0) + t.amount
        
        avg_monthly_expense = sum(months_data.values()) / len(months_data) if months_data else 0

        response = "📊 <b>Фінансова аналітика</b>\n\n"
        response += f"💰 <b>Поточний баланс:</b> {current_balance:.2f} грн\n"
        response += f"⬆️ <b>Загальні доходи:</b> {total_overall_income:.2f} грн\n"
        response += f"⬇️ <b>Загальні витрати:</b> {total_overall_expense:.2f} грн\n"
        response += f"📆 <b>Середньомісячні витрати:</b> {avg_monthly_expense:.2f} грн\n\n"
        
        if sorted_income_categories:
            response += "<b>Топ категорій доходів:</b>\n"
            for i, (category, amount) in enumerate(sorted_income_categories, 1):
                response += f"{i}. {category.capitalize()}: {amount:.2f} грн\n"
            response += "\n"
        
        if sorted_expense_categories:
            response += "<b>Топ категорій витрат:</b>\n"
            for i, (category, amount) in enumerate(sorted_expense_categories, 1):
                response += f"{i}. {category.capitalize()}: {amount:.2f} грн\n"
        else:
            response += "Немає даних про витрати за категоріями.\n"
        
        await update.message.reply_text(
            response,
            parse_mode="HTML",
            reply_markup=build_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in analytics handler: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при отриманні аналітики",
            reply_markup=build_main_keyboard()
        )

def setup_handlers(application: Application):
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(MessageHandler(filters.Text(["📊 Аналіз"]), handle_analytics))
    
    # Обробник для звичайних транзакцій (доходи та витрати)
    transaction_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["➕ Транзакція"]), handle_transaction_start)],
        states={
            ADD_TRANSACTION_TYPE: [
                MessageHandler(filters.Text(["Дохід", "Витрата"]) & ~filters.COMMAND, get_transaction_type)
            ],
            ADD_TRANSACTION_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_transaction_amount)
            ],
            ADD_TRANSACTION_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_transaction_category)
            ],
            ADD_TRANSACTION_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_transaction_description)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Text(["❌ Скасувати", "🔙 На головну"]), cancel_conversation)
        ]
    )
    application.add_handler(transaction_handler)
    
    # Новий обробник для швидкого додавання доходу
    income_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["💵 Дохід"]), income_start)],
        states={
            ADD_INCOME_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_income_amount)
            ],
            ADD_INCOME_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_income_category)
            ],
            ADD_INCOME_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_income_description)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Text(["❌ Скасувати", "🔙 На головну"]), cancel_conversation)
        ]
    )
    application.add_handler(income_handler)

    goals_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["🎯 Цілі"]), handle_goals)],
        states={
            GOAL_MENU: [
                MessageHandler(filters.Text(["📋 Список цілей"]), goal_list),
                MessageHandler(filters.Text(["➕ Нова ціль"]), goal_create_prompt),
                MessageHandler(filters.Text(["💰 Додати кошти"]), goal_add_prompt),
                MessageHandler(filters.Text(["❌ Видалити ціль"]), goal_delete_prompt),
                MessageHandler(filters.Text(["🔙 На головну"]), cancel_conversation)
            ],
            "WAITING_GOAL_CREATE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_create)
            ],
            "WAITING_DEPOSIT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit),
                CommandHandler("list", goal_list)
            ],
            "WAITING_GOAL_DELETE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_delete)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Text(["🔙 На головну"]), cancel_conversation)
        ]
    )
    application.add_handler(goals_handler)
    
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
    
    ai_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text(["🤖 AI Поради"]), handle_ai_advice),
            CommandHandler("advice", handle_ai_advice)
        ],
        states={
            AI_SESSION: [
                MessageHandler(
                    filters.TEXT & ~filters.Text(["❌ Скасувати"]),
                    lambda update, context: ai.handle_ai_question(
                        update, context, build_main_keyboard, build_ai_keyboard, AI_SESSION
                    )
                ),
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