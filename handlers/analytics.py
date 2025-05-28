from aiogram import Router, types
from database import Session, Transaction
from datetime import datetime

analytics_router = Router()

@analytics_router.message()
async def show_analytics(message: types.Message):
    if message.text != "📈 Аналіз витрат":
        return  # Ігноруємо всі повідомлення, крім потрібного тексту

    session = Session()
    transactions = session.query(Transaction).filter(
        Transaction.user_id == message.from_user.id,
        Transaction.date.like(f"{datetime.now().strftime('%Y-%m')}%")
    ).all()

    if not transactions:
        await message.answer("📭 Немає даних за цей місяць!")
        return

    total = sum(t.amount for t in transactions)
    categories = {t.category: sum(t.amount for t in transactions if t.category == t.category) for t in transactions}
    
    report = "📊 Ваші витрати за місяць:\n"
    for cat, amount in categories.items():
        report += f"▪ {cat}: {amount} грн ({round(amount/total*100)}%)\n"
    
    await message.answer(report)
