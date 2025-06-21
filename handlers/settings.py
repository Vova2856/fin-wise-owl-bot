from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext, ConversationHandler
from database import Session as DBSession, User
import logging

logger = logging.getLogger(__name__)

SETTINGS_MENU, CHANGE_CURRENCY, NOTIFICATION_SETTINGS, DATA_EXPORT = range(4)

def build_settings_keyboard():
    keyboard = [
        ["💱 Змінити валюту", "🔔 Сповіщення"],
        ["📤 Експорт даних", "🔙 На головну"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def handle_settings(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "⚙ <b>Налаштування</b>\n\nОберіть опцію:",
        reply_markup=build_settings_keyboard(),
        parse_mode="HTML"
    )
    return SETTINGS_MENU

async def change_currency_start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "💱 <b>Змінити валюту</b>\n\n"
        "Введіть код валюти (наприклад, USD, EUR, UAH):\n\n"
        "Доступні валюти:\n"
        "🇺🇦 UAH - Гривня\n"
        "🇺🇸 USD - Долар США\n"
        "🇪🇺 EUR - Євро\n"
        "🇬🇧 GBP - Фунт стерлінгів",
        parse_mode="HTML"
    )
    return CHANGE_CURRENCY

async def change_currency(update: Update, context: CallbackContext):
    currency = update.message.text.upper().strip()
    valid_currencies = ["UAH", "USD", "EUR", "GBP"]
    
    if currency not in valid_currencies:
        await update.message.reply_text(
            "❌ Невірний код валюти. Будь ласка, введіть один з доступних кодів: UAH, USD, EUR, GBP"
        )
        return CHANGE_CURRENCY
    
    user_id = update.effective_user.id
    session = DBSession()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.currency = currency
            session.commit()
            await update.message.reply_text(
                f"✅ Валюта змінена на {currency}",
                reply_markup=build_settings_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Користувача не знайдено",
                reply_markup=build_settings_keyboard()
            )
        return SETTINGS_MENU
    except Exception as e:
        logger.error(f"Помилка при зміні валюти: {e}")
        await update.message.reply_text(
            "❌ Сталася помилка при зміні валюти",
            reply_markup=build_settings_keyboard()
        )
        return SETTINGS_MENU
    finally:
        session.close()

async def notification_settings(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🔔 <b>Налаштування сповіщень</b>\n\n"
        "Оберіть тип сповіщень:\n"
        "🕘 Щоденний звіт\n"
        "💸 Попередження про перевитрати\n"
        "🏁 Сповіщення про досягнення цілей",
        parse_mode="HTML",
        reply_markup=build_settings_keyboard()
    )
    return NOTIFICATION_SETTINGS

async def data_export(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📤 <b>Експорт даних</b>\n\n"
        "Оберіть формат експорту:\n"
        "📝 CSV\n"
        "📊 Excel\n"
        "📄 PDF",
        parse_mode="HTML",
        reply_markup=build_settings_keyboard()
    )
    return DATA_EXPORT

async def cancel_settings(update: Update, context: CallbackContext):
    from main import build_main_keyboard
    await update.message.reply_text(
        "Головне меню:",
        reply_markup=build_main_keyboard()
    )
    return ConversationHandler.END