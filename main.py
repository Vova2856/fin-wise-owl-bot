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
from sqlalchemy.orm import Session # Змінено: імпортуємо Session напряму, не створюємо engine тут
from datetime import datetime

# Import the new ai module (assuming it's in a 'handlers' directory)
import handlers.ai as ai
import handlers.settings as settings

# Import your database and transactions modules
from database import init_db, User, Transaction, Budget, Goal, engine, Session as DBSession # Імпорт Session як DBSession, щоб уникнути конфлікту імен з telegram.ext
import handlers.transactions as db_transactions # Перейменовуємо для уникнення конфлікту

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
# Додаємо нові стани для додавання транзакції
ADD_TRANSACTION_TYPE, ADD_TRANSACTION_AMOUNT, ADD_TRANSACTION_CATEGORY, ADD_TRANSACTION_DESCRIPTION = range(5, 9) # Продовжуємо з 5
BUDGET_MENU, ADDING_EXPENSE, SETTING_BUDGET, AI_SESSION, GOAL_MENU = range(5) # Старі константи

# Ініціалізація бази даних при запуску бота (один раз)
# ВИДАЛЕНО ручне створення таблиць за допомогою sql_text
# Тепер це робиться через database.py -> init_db()
init_db()

# Клавіатури
def build_main_keyboard():
    keyboard = [
        [KeyboardButton("💰 Бюджет"), KeyboardButton("🤖 AI Поради")],
        [KeyboardButton("🎯 Цілі"), KeyboardButton("📊 Аналіз")],
        [KeyboardButton("➕ Транзакція"), KeyboardButton("⚙ Налаштування")]
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

# Команди
async def cmd_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code

    # Перевіряємо або створюємо користувача в БД
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

# --- ФУНКЦІОНАЛ ТРАНЗАКЦІЙ ---

async def handle_transaction_start(update: Update, context: CallbackContext):
    """Початок процесу додавання транзакції: запитуємо тип."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    language_code = update.effective_user.language_code
    await db_transactions.get_or_create_user(user_id, username, first_name, last_name, language_code) # Ensure user exists

    await update.message.reply_text(
        "➕ <b>Яку транзакцію ви хочете додати?</b>",
        reply_markup=build_transaction_type_keyboard(),
        parse_mode="HTML"
    )
    return ADD_TRANSACTION_TYPE

async def get_transaction_type(update: Update, context: CallbackContext):
    """Отримуємо тип транзакції (дохід/витрата)."""
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
    """Отримуємо суму транзакції."""
    try:
        amount = float(update.message.text.replace(',', '.')) # Дозволяємо кому як десятковий роздільник
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
    """Отримуємо категорію транзакції."""
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
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

# Скасування розмови
async def cancel_conversation(update: Update, context: CallbackContext):
    # Очищаємо всі тимчасові дані користувача, якщо вони є
    context.user_data.clear()
    await update.message.reply_text(
        "Дію скасовано. Головне меню:",
        reply_markup=build_main_keyboard()
    )
    return ConversationHandler.END

# --- Інші обробники ---
async def handle_settings(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "⚙ <b>Налаштування</b>\nТут ви можете налаштувати свій профіль\n\n"
        "Доступні опції:\n"
        "🔸 Змінити валюту\n"
        "🔸 Налаштувати сповіщення\n"
        "🔸 Експорт даних",
        parse_mode="HTML"
    )

# AI Поради
async def handle_ai_advice(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💡 Напишіть ваше запитання про фінанси:",
        reply_markup=build_ai_keyboard()
    )
    return AI_SESSION

# Бюджет - ConversationHandler
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

# Оновлено для використання ORM:
async def add_expense_start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Введіть витрату у форматі:\n<code>100 їжа</code> або <code>200 транспорт обід</code>\n"
        "Або напишіть 'скасувати' для повернення",
        parse_mode="HTML"
    )
    return ADDING_EXPENSE

# Оновлено для використання ORM:
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
# Оновлено для використання ORM:
async def show_statistics(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        # Отримуємо всі транзакції для розрахунку статистики
        transactions_list = await db_transactions.get_transactions(user_id, limit=9999) # Отримати всі для статистики

        if not transactions_list:
            await update.message.reply_text(
                "📭 У вас ще немає транзакцій.",
                reply_markup=build_budget_keyboard()
            )
            return BUDGET_MENU

        # Розділяємо на доходи та витрати для більш точного балансу
        total_income = sum(t.amount for t in transactions_list if t.type == 'income')
        total_expense = sum(t.amount for t in transactions_list if t.type == 'expense')
        
        # Розраховуємо загальний баланс за допомогою функції
        current_balance = await db_transactions.get_balance(user_id)

        # Статистика витрат за категоріями для поточного місяця
        monthly_expenses_by_category = {}
        current_month_str = datetime.now().strftime("%Y-%m")

        for t in transactions_list:
            # Перевіряємо, чи транзакція належить до поточного місяця і є витратою
            if t.date.strftime("%Y-%m") == current_month_str and t.type == 'expense':
                monthly_expenses_by_category[t.category] = monthly_expenses_by_category.get(t.category, 0.0) + t.amount
        
        # Сортуємо категорії за витратами
        sorted_categories = sorted(monthly_expenses_by_category.items(), key=lambda item: item[1], reverse=True)
        total_monthly_expense = sum(monthly_expenses_by_category.values())

        message = "📊 <b>Ваша фінансова статистика:</b>\n\n"
        message += f"💰 <b>Поточний баланс:</b> {current_balance:.2f} грн\n"
        message += f"⬆️ <b>Всього доходів:</b> {total_income:.2f} грн\n"
        message += f"⬇️ <b>Всього витрат:</b> {total_expense:.2f} грн\n\n"
        
        if sorted_categories:
            message += f"<b>Витрати за {datetime.now().strftime('%B %Y').capitalize()}:</b>\n"
            message += f"💵 <b>Загальні витрати цього місяця:</b> {total_monthly_expense:.2f} грн\n\n"
            message += "<b>За категоріями цього місяця:</b>\n"
            for category, amount in sorted_categories:
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

# Оновлено для використання ORM:
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

# Оновлено для використання ORM:
async def handle_budget_settings(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        user_input = update.message.text
        
        if user_input.lower() == 'скасувати' or user_input.lower() == '/cancel':
            await cancel_conversation(update, context)
            return ConversationHandler.END
            
        if user_input.lower() == '/list':
            session = DBSession() # Використовуємо DBSession з database.py
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
        # Шукаємо існуючий бюджет або створюємо новий
        budget = session.query(Budget).filter_by(user_id=user_id, category=category).first()
        if budget:
            budget.limit = limit
            session.add(budget) # Оновлюємо існуючий
            action_msg = "оновлено"
        else:
            budget = Budget(user_id=user_id, category=category, limit=limit)
            session.add(budget) # Додаємо новий
            action_msg = "встановлено"

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

# Обробник цілей (оновлено для використання ORM)
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

# Оновлено для використання ORM:
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
            # Розрахунок місячної суми лише якщо термін у місяцях встановлений і позитивний
            monthly = (goal.target_amount - goal.current_amount) / goal.months if goal.months and goal.months > 0 else 0
            
            response += (
                f"🆔 <b>ID:</b> {goal.id}\n"
                f"📌 <b>Назва:</b> {goal.name}\n"
                f"💵 <b>Ціль:</b> {goal.target_amount} грн\n"
                f"💰 <b>Накопичено:</b> {goal.current_amount} грн ({progress:.1f}%)\n"
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
        "<code>Назва Сума Місяці [Опис]</code>\n\n" # Додано [Опис] для ясності
        "Наприклад: <code>Ноутбук 25000 6 для роботи</code>",
        parse_mode="HTML"
    )
    context.user_data['next_state'] = GOAL_MENU # Повертаємось в меню цілей після успішної операції
    return "WAITING_GOAL_CREATE"

# Оновлено для використання ORM:
async def goal_create(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        args = update.message.text.split()
        if len(args) < 3:
            await update.message.reply_text(
                "❌ Неправильний формат. Використовуйте: Назва Сума Місяці [Опис]",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU

        # Парсинг: останні два - сума та місяці, решта - назва і можливий опис
        try:
            months = int(args[-1])
            target_amount = float(args[-2])
            name_and_desc_parts = args[:-2]
            name = ' '.join(name_and_desc_parts) # Припускаємо, що все до суми/місяців - це назва+опис

            # Якщо опис має бути окремим полем, і він останній
            # Це дуже складно парсити без чіткого роздільника.
            # Якщо ви хочете "Назва Сума Місяці Опис", то логіка має бути такою:
            # name = ' '.join(args[0:-3])
            # target_amount = float(args[-3])
            # months = int(args[-2])
            # description = args[-1] if len(args) > 3 else None
            
            # Для простоти, згідно з вашим прикладом, "для роботи" йде в назву.
            # Якщо "description" має бути окремим, то треба змінити модель та підхід.
            # Наразі, description у моделі `Goal` є, але ми його не парсимо окремо.
            # Щоб парсити опис окремо, треба змінити промпт і логіку.
            # Наприклад: "Ноутбук 25000 6 #для_роботи" або "Ноутбук,25000,6,для роботи"
            # Або, якщо опис йде останнім і може містити пробіли:
            # name = " ".join(args[:-3]) # Якщо опис завжди останній
            # target_amount = float(args[-3])
            # months = int(args[-2])
            # description = args[-1] if len(args) > 3 else None
            # Або, якщо опис - це все, що після 3-го аргументу:
            # name = args[0]
            # target_amount = float(args[1])
            # months = int(args[2])
            # description = " ".join(args[3:]) if len(args) > 3 else None

            # З огляду на ваш попередній приклад "Ноутбук 25000 6 для роботи",
            # де "для роботи" є частиною назви, залишаємо так:
            # name = ' '.join(args[:-2])
            # target_amount = float(args[-2])
            # months = int(args[-1])
            # description = None # Опис не парситься окремо, або частина назви
            
            # Якщо опис має бути окремо, і він може бути багатослівним,
            # найкраще мати чіткий роздільник або фіксовану кількість полів.
            # Давайте зробимо опис опціональним і останнім:
            if len(args) >= 4: # Якщо є опис
                name = ' '.join(args[:-3])
                target_amount = float(args[-3])
                months = int(args[-2])
                description = args[-1]
            else: # Без опису
                name = ' '.join(args[:-2])
                target_amount = float(args[-2])
                months = int(args[-1])
                description = None

        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Помилка у форматі даних. Перевірте, що сума та місяці - числа.\n"
                "Використовуйте: <code>Назва Сума Місяці [Опис]</code>",
                parse_mode="HTML",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU
            
        session = DBSession()
        goal = Goal(
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            months=months,
            created_at=datetime.now().date(), # Використовуємо .date() для поля Date
            description=description
        )
        session.add(goal)
        session.commit()
        session.close()

        reply_text = (
            f"✅ Ціль <b>'{name}'</b> створена!\n"
            f"💵 Сума: <b>{target_amount}</b> грн\n"
            f"📅 Термін: <b>{months}</b> місяців"
        )
        if description:
            reply_text += f"\n📝 Опис: {description}"
            
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

# Оновлено для використання ORM:
async def goal_add_prompt(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💰 Введіть ID цілі та суму для додавання у форматі:\n"
        "<code>ID Сума</code>\n\n"
        "Наприклад: <code>3 1500</code>",
        parse_mode="HTML"
    )
    return "WAITING_GOAL_ADD"

# Оновлено для використання ORM:
async def goal_add(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    session = DBSession()
    try:
        args = update.message.text.split()
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Неправильний формат. Використовуйте: ID Сума",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU

        goal_id = int(args[0])
        amount = float(args[1])
        if amount <= 0:
            await update.message.reply_text("Сума для додавання має бути позитивною.", reply_markup=build_goals_keyboard())
            return GOAL_MENU

        goal = session.query(Goal).filter_by(id=goal_id, user_id=user_id).first()

        if not goal:
            await update.message.reply_text(
                "❌ Ціль не знайдена",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU

        new_amount = goal.current_amount + amount
        
        # Додаємо транзакцію типу "income" (або інший, який ви вирішите для внесків у цілі)
        await db_transactions.add_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type='goal_deposit', # Або 'income'
            category=f"Ціль: {goal.name}", # Категорія для цілі
            description=f"Внесок у ціль '{goal.name}'"
        )

        if new_amount > goal.target_amount:
            # Якщо додана сума перевищує ціль, встановлюємо її на цільову
            overflow_amount = new_amount - goal.target_amount
            goal.current_amount = goal.target_amount
            session.add(goal)
            session.commit()
            await update.message.reply_text(
                f"✅ Додано <b>{amount - overflow_amount:.2f}</b> грн до цілі <b>'{goal.name}'</b>! Ціль досягнута!\n"
                f"🎉 Ви успішно накопичили {goal.target_amount} грн. Залишок {overflow_amount:.2f} грн не було додано.",
                parse_mode="HTML",
                reply_markup=build_goals_keyboard()
            )
            return GOAL_MENU
            
        goal.current_amount = new_amount
        session.add(goal)
        session.commit()

        remaining = goal.target_amount - new_amount
        await update.message.reply_text(
            f"✅ Додано <b>{amount}</b> грн до цілі <b>'{goal.name}'</b>!\n"
            f"💰 Залишилось зібрати: <b>{remaining:.2f}</b> грн",
            parse_mode="HTML",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU

    except ValueError:
        await update.message.reply_text(
            "❌ Помилка у форматі даних. Перевірте, що ID та сума - числа",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU
    except Exception as e:
        logger.error(f"Помилка при додаванні до цілі: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при додаванні коштів",
            reply_markup=build_goals_keyboard()
        )
        return GOAL_MENU
    finally:
        session.close()

# Оновлено для використання ORM:
async def goal_delete_prompt(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ Введіть ID цілі для видалення:\n"
        "<code>ID</code>\n\n"
        "Наприклад: <code>2</code>",
        parse_mode="HTML"
    )
    return "WAITING_GOAL_DELETE"

# Оновлено для використання ORM:
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

# Оновлено для використання ORM:
async def handle_analytics(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        # Отримуємо всі транзакції для повного аналізу
        all_transactions = await db_transactions.get_transactions(user_id, limit=99999) # Великий ліміт для всіх

        if not all_transactions:
            await update.message.reply_text(
                "📭 У вас ще немає транзакцій для аналітики.",
                reply_markup=build_main_keyboard()
            )
            return ConversationHandler.END

        # Розрахунок загального балансу за допомогою функції
        current_balance = await db_transactions.get_balance(user_id)

        # Статистика витрат за категоріями (за весь період або за обраний)
        spending_by_category = {}
        for t in all_transactions:
            if t.type == 'expense': # Тільки витрати для аналітики витрат
                spending_by_category[t.category] = spending_by_category.get(t.category, 0.0) + t.amount

        sorted_categories = sorted(spending_by_category.items(), key=lambda item: item[1], reverse=True)
        total_overall_expense = sum(spending_by_category.values())

        # Розрахунок середньомісячних витрат
        months_data = {} # { "YYYY-MM": total_expense_for_month }
        for t in all_transactions:
            if t.type == 'expense' and t.date: # Перевірка t.date на наявність, якщо це об'єкт datetime
                month_key = t.date.strftime('%Y-%m')
                months_data[month_key] = months_data.get(month_key, 0.0) + t.amount
        
        avg_monthly_expense = sum(months_data.values()) / len(months_data) if months_data else 0

        response = "📊 <b>Фінансова аналітика</b>\n\n"
        response += f"💰 <b>Поточний баланс:</b> {current_balance:.2f} грн\n"
        response += f"⬇️ <b>Загальні витрати (за весь час):</b> {total_overall_expense:.2f} грн\n"
        response += f"📆 <b>Середньомісячні витрати:</b> {avg_monthly_expense:.2f} грн\n\n"
        
        if sorted_categories:
            response += "<b>Топ категорій витрат (за весь час):</b>\n"
            for i, (category, amount) in enumerate(sorted_categories, 1):
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
    # Основні команди
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    
    # Обробники кнопок головного меню
    application.add_handler(MessageHandler(filters.Text(["📊 Аналіз"]), handle_analytics))
    
    settings_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["⚙ Налаштування"]), settings.handle_settings)],
        states={
            settings.SETTINGS_MENU: [
                MessageHandler(filters.Text(["💱 Змінити валюту"]), settings.change_currency_start),
                MessageHandler(filters.Text(["🔔 Сповіщення"]), settings.notification_settings),
                MessageHandler(filters.Text(["📤 Експорт даних"]), settings.data_export),
                MessageHandler(filters.Text(["🔙 На головну"]), settings.cancel_settings)
            ],
            settings.CHANGE_CURRENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, settings.change_currency)
            ],
            settings.NOTIFICATION_SETTINGS: [
                MessageHandler(filters.Text(["🔙 На головну"]), settings.cancel_settings)
            ],
            settings.DATA_EXPORT: [
                MessageHandler(filters.Text(["🔙 На головну"]), settings.cancel_settings)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", settings.cancel_settings),
            MessageHandler(filters.Text(["🔙 На головну"]), settings.cancel_settings)
        ]
    )
    application.add_handler(settings_handler)
    
    
    # Додано ConversationHandler для "➕ Транзакція"
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

    # Обробник цілей
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
            "WAITING_GOAL_ADD": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, goal_add)
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
        entry_points=[
            MessageHandler(filters.Text(["🤖 AI Поради"]), handle_ai_advice),
            CommandHandler("advice", handle_ai_advice)
        ],
        states={
            AI_SESSION: [
                # Use a lambda to pass the required arguments to ai.handle_ai_question
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