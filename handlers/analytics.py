from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy.sql import text as sql_text
from datetime import datetime, timedelta
from database import Session
import matplotlib.pyplot as plt
import io
import os
import logging

# Налаштування логування
logger = logging.getLogger(__name__)

analytics_router = Router()

def build_analytics_keyboard():
    keyboard = [
        [types.KeyboardButton(text="📅 За місяць"), types.KeyboardButton(text="📆 За тиждень")],
        [types.KeyboardButton(text="📊 Топ категорій"), types.KeyboardButton(text="📈 Графік витрат")],
        [types.KeyboardButton(text="🔍 Детальний аналіз"), types.KeyboardButton(text="🔙 На головну")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@analytics_router.message(Command("analytics"))
@analytics_router.message(lambda message: message.text == "📊 Аналіз")
async def analytics_menu(message: types.Message):
    try:
        await message.answer(
            "📊 <b>Розділ аналітики</b>\nОберіть тип звіту:",
            reply_markup=build_analytics_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in analytics_menu: {e}")
        await message.answer("❌ Сталася помилка при відкритті аналітики")

async def generate_monthly_report(user_id: int):
    try:
        session = Session()
        current_month = datetime.now().strftime("%Y-%m")
        
        transactions = session.execute(
            sql_text("""
                SELECT category, SUM(amount) as total 
                FROM transactions 
                WHERE user_id = :user_id AND strftime('%Y-%m', date) = :month 
                GROUP BY category
                ORDER BY total DESC
            """),
            {"user_id": user_id, "month": current_month}
        ).fetchall()

        if not transactions:
            return "📭 У вас ще немає витрат за цей місяць."

        total = sum(t.total for t in transactions)
        report = f"📅 <b>Витрати за {current_month}:</b>\n\n"
        report += f"💵 <b>Загалом:</b> {total:.2f} грн\n\n"
        report += "<b>Розподіл по категоріям:</b>\n"
        
        for t in transactions:
            percentage = (t.total / total) * 100
            report += f"▪ {t.category.capitalize()}: {t.total:.2f} грн ({percentage:.1f}%)\n"

        # Порівняння з попереднім місяцем
        prev_month = datetime.now().replace(day=1) - timedelta(days=1)
        prev_month_str = prev_month.strftime("%Y-%m")
        prev_total = session.execute(
            sql_text("""
                SELECT SUM(amount) as total 
                FROM transactions 
                WHERE user_id = :user_id AND strftime('%Y-%m', date) = :month
            """),
            {"user_id": user_id, "month": prev_month_str}
        ).fetchone().total or 0

        if prev_total:
            diff = total - prev_total
            if diff > 0:
                trend = f"📈 <b>+{abs(diff):.2f} грн</b> vs {prev_month_str}"
            elif diff < 0:
                trend = f"📉 <b>-{abs(diff):.2f} грн</b> vs {prev_month_str}"
            else:
                trend = f"📊 <b>Без змін</b> vs {prev_month_str}"
            
            report += f"\n{trend}"

        return report

    except Exception as e:
        logger.error(f"Error generating monthly report: {e}")
        return "❌ Помилка при формуванні звіту за місяць"

async def generate_weekly_report(user_id: int):
    try:
        session = Session()
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        
        transactions = session.execute(
            sql_text("""
                SELECT category, SUM(amount) as total 
                FROM transactions 
                WHERE user_id = :user_id AND date >= :week_start 
                GROUP BY category
                ORDER BY total DESC
            """),
            {"user_id": user_id, "week_start": week_start}
        ).fetchall()

        if not transactions:
            return "📭 У вас ще немає витрат за цей тиждень."

        total = sum(t.total for t in transactions)
        report = f"📆 <b>Витрати за тиждень (з {week_start}):</b>\n\n"
        report += f"💵 <b>Загалом:</b> {total:.2f} грн\n\n"
        report += "<b>Розподіл по категоріям:</b>\n"
        
        for t in transactions:
            percentage = (t.total / total) * 100
            report += f"▪ {t.category.capitalize()}: {t.total:.2f} грн ({percentage:.1f}%)\n"

        # Додаткові метрики
        avg_daily = total / (today.weekday() + 1)
        report += f"\n📌 <b>Середньоденні витрати:</b> {avg_daily:.2f} грн"

        return report

    except Exception as e:
        logger.error(f"Error generating weekly report: {e}")
        return "❌ Помилка при формуванні звіту за тиждень"

async def generate_category_report(user_id: int):
    try:
        session = Session()
        
        categories = session.execute(
            sql_text("""
                SELECT category, SUM(amount) as total 
                FROM transactions 
                WHERE user_id = :user_id 
                GROUP BY category
                ORDER BY total DESC
                LIMIT 10
            """),
            {"user_id": user_id}
        ).fetchall()

        if not categories:
            return "📭 У вас ще немає витрат за жодною категорією."

        total_all = session.execute(
            sql_text("SELECT SUM(amount) FROM transactions WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchone()[0] or 0

        report = "📊 <b>Топ-10 категорій за весь час:</b>\n\n"
        
        for i, cat in enumerate(categories, 1):
            percentage = (cat.total / total_all) * 100
            report += f"{i}. {cat.category.capitalize()}: {cat.total:.2f} грн ({percentage:.1f}%)\n"

        report += f"\n💳 <b>Всього витрачено:</b> {total_all:.2f} грн"
        return report

    except Exception as e:
        logger.error(f"Error generating category report: {e}")
        return "❌ Помилка при формуванні звіту по категоріям"

async def generate_expenses_chart(user_id: int):
    try:
        session = Session()
        
        months_data = session.execute(
            sql_text("""
                SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
                FROM transactions
                WHERE user_id = :user_id
                GROUP BY month
                ORDER BY month DESC
                LIMIT 6
            """),
            {"user_id": user_id}
        ).fetchall()

        if not months_data or len(months_data) < 2:
            return None

        months = [m.month[-2:] + '/' + m.month[2:4] for m in reversed(months_data)]
        amounts = [m.total for m in reversed(months_data)]

        plt.style.use('seaborn')
        fig, ax = plt.subplots(figsize=(10, 6))
        
        bars = ax.bar(months, amounts, color=['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#607D8B'])
        
        ax.set_title('Динаміка витрат по місяцям', pad=20, fontsize=14, fontweight='bold')
        ax.set_xlabel('Місяць', labelpad=10)
        ax.set_ylabel('Сума (грн)', labelpad=10)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Додаємо значення на стовпці
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f}',
                    ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=80, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer

    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return None

async def generate_detailed_analysis(user_id: int):
    try:
        session = Session()
        
        # Отримуємо дані для аналізу
        total_spent = session.execute(
            sql_text("SELECT SUM(amount) FROM transactions WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchone()[0] or 0

        avg_monthly = session.execute(
            sql_text("""
                SELECT AVG(month_total) FROM (
                    SELECT strftime('%Y-%m', date) as month, SUM(amount) as month_total
                    FROM transactions
                    WHERE user_id = :user_id
                    GROUP BY month
                )
            """),
            {"user_id": user_id}
        ).fetchone()[0] or 0

        most_expensive_category = session.execute(
            sql_text("""
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE user_id = :user_id
                GROUP BY category
                ORDER BY total DESC
                LIMIT 1
            """),
            {"user_id": user_id}
        ).fetchone()

        analysis = "🔍 <b>Детальний фінансовий аналіз:</b>\n\n"
        analysis += f"💸 <b>Всього витрачено:</b> {total_spent:.2f} грн\n"
        analysis += f"📆 <b>Середньомісячні витрати:</b> {avg_monthly:.2f} грн\n"
        
        if most_expensive_category:
            analysis += f"🏆 <b>Найвитратніша категорія:</b> {most_expensive_category[0].capitalize()} ({most_expensive_category[1]:.2f} грн)\n"
        
        # Рекомендації на основі даних
        if avg_monthly > 15000:
            analysis += "\n💡 <b>Рекомендація:</b> Ваші витрати вище середнього. Рекомендуємо переглянути бюджет."
        elif avg_monthly < 5000:
            analysis += "\n💡 <b>Рекомендація:</b> Ви добре контролюєте витрати! Продовжуйте в тому ж дусі."
        else:
            analysis += "\n💡 <b>Рекомендація:</b> Ваші витрати на оптимальному рівні."

        return analysis

    except Exception as e:
        logger.error(f"Error generating detailed analysis: {e}")
        return "❌ Помилка при формуванні детального аналізу"

@analytics_router.message(lambda message: message.text == "📅 За місяць")
async def monthly_report(message: types.Message):
    report = await generate_monthly_report(message.from_user.id)
    await message.answer(report, parse_mode="HTML", reply_markup=build_analytics_keyboard())

@analytics_router.message(lambda message: message.text == "📆 За тиждень")
async def weekly_report(message: types.Message):
    report = await generate_weekly_report(message.from_user.id)
    await message.answer(report, parse_mode="HTML", reply_markup=build_analytics_keyboard())

@analytics_router.message(lambda message: message.text == "📊 Топ категорій")
async def categories_report(message: types.Message):
    report = await generate_category_report(message.from_user.id)
    await message.answer(report, parse_mode="HTML", reply_markup=build_analytics_keyboard())

@analytics_router.message(lambda message: message.text == "📈 Графік витрат")
async def expenses_chart(message: types.Message):
    chart = await generate_expenses_chart(message.from_user.id)
    if chart:
        await message.answer_photo(
            photo=chart,
            caption="📈 <b>Динаміка ваших витрат</b>",
            parse_mode="HTML",
            reply_markup=build_analytics_keyboard()
        )
    else:
        await message.answer(
            "📭 Недостатньо даних для побудови графіка. Потрібно щонайменше 2 місяці даних.",
            reply_markup=build_analytics_keyboard()
        )

@analytics_router.message(lambda message: message.text == "🔍 Детальний аналіз")
async def detailed_analysis(message: types.Message):
    analysis = await generate_detailed_analysis(message.from_user.id)
    await message.answer(analysis, parse_mode="HTML", reply_markup=build_analytics_keyboard())

@analytics_router.message(lambda message: message.text == "🔙 На головну")
async def back_to_main(message: types.Message):
    from main import build_main_keyboard
    await message.answer("Повертаємось до головного меню", reply_markup=build_main_keyboard())