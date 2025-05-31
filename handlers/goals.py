from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text as sql_text
from datetime import datetime
import os

# Підключення до бази даних
DB_URL = os.getenv("DB_URL", "sqlite:///finance_bot.db")
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

# Створення таблиці цілей (якщо ще не існує)
with engine.connect() as conn:
    conn.execute(sql_text("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        current_amount REAL DEFAULT 0,
        months INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """))
    conn.commit()

goals_router = Router()

@goals_router.message(Command("goal"))
async def goal_menu(message: types.Message):
    await message.answer(
        "🎯 Управління цілями:\n"
        "/goal_create [назва] [сума] [місяці] - нова ціль\n"
        "/goal_list - мої цілі\n"
        "/goal_add [id] [сума] - додати кошти до цілі\n"
        "/goal_delete [id] - видалити ціль"
    )

@goals_router.message(Command("goal_create"))
async def goal_create(message: types.Message):
    try:
        args = message.text.split()[1:]
        if len(args) < 3:
            await message.answer("❌ Неправильний формат. Використовуйте: /goal_create [назва] [сума] [місяці]")
            return

        name = ' '.join(args[:-2])
        target_amount = float(args[-2])
        months = int(args[-1])

        session = Session()
        session.execute(
            sql_text("""
                INSERT INTO goals (user_id, name, target_amount, months, created_at)
                VALUES (:user_id, :name, :target_amount, :months, :created_at)
            """),
            {
                "user_id": message.from_user.id,
                "name": name,
                "target_amount": target_amount,
                "months": months,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
        session.commit()

        await message.answer(f"✅ Ціль '{name}' створена!\n"
                           f"💵 Сума: {target_amount} грн\n"
                           f"📅 Термін: {months} місяців")

    except ValueError:
        await message.answer("❌ Помилка у форматі даних. Перевірте, що сума та місяці - числа")
    except Exception as e:
        await message.answer("❌ Сталася помилка при створенні цілі")
        print(f"Error creating goal: {e}")

@goals_router.message(Command("goal_list"))
async def goal_list(message: types.Message):
    try:
        session = Session()
        goals = session.execute(
            sql_text("SELECT id, name, target_amount, current_amount, months FROM goals WHERE user_id = :user_id"),
            {"user_id": message.from_user.id}
        ).fetchall()

        if not goals:
            await message.answer("📭 У вас ще немає цілей")
            return

        response = "🎯 Ваші цілі:\n\n"
        for goal in goals:
            progress = (goal.current_amount / goal.target_amount) * 100
            monthly = (goal.target_amount - goal.current_amount) / goal.months
            response += (
                f"🆔 ID: {goal.id}\n"
                f"📌 Назва: {goal.name}\n"
                f"💵 Ціль: {goal.target_amount} грн\n"
                f"💰 Накопичено: {goal.current_amount} грн ({progress:.1f}%)\n"
                f"📅 Місячна сума: ~{monthly:.2f} грн\n"
                f"------------------------\n"
            )

        await message.answer(response)

    except Exception as e:
        await message.answer("❌ Сталася помилка при отриманні списку цілей")
        print(f"Error listing goals: {e}")

@goals_router.message(Command("goal_add"))
async def goal_add(message: types.Message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            await message.answer("❌ Неправильний формат. Використовуйте: /goal_add [id] [сума]")
            return

        goal_id = int(args[0])
        amount = float(args[1])

        session = Session()
        # Перевіряємо, чи існує ціль
        goal = session.execute(
            sql_text("SELECT id, target_amount, current_amount FROM goals WHERE id = :id AND user_id = :user_id"),
            {"id": goal_id, "user_id": message.from_user.id}
        ).fetchone()

        if not goal:
            await message.answer("❌ Ціль не знайдена")
            return

        new_amount = goal.current_amount + amount
        if new_amount > goal.target_amount:
            await message.answer(f"⚠️ Сума перевищує цільову! Максимально можна додати {goal.target_amount - goal.current_amount} грн")
            return

        session.execute(
            sql_text("UPDATE goals SET current_amount = :amount WHERE id = :id"),
            {"amount": new_amount, "id": goal_id}
        )
        session.commit()

        remaining = goal.target_amount - new_amount
        await message.answer(f"✅ Додано {amount} грн до цілі!\n"
                           f"💰 Залишилось зібрати: {remaining:.2f} грн")

    except ValueError:
        await message.answer("❌ Помилка у форматі даних. Перевірте, що ID та сума - числа")
    except Exception as e:
        await message.answer("❌ Сталася помилка при додаванні коштів")
        print(f"Error adding to goal: {e}")

@goals_router.message(Command("goal_delete"))
async def goal_delete(message: types.Message):
    try:
        args = message.text.split()[1:]
        if not args:
            await message.answer("❌ Неправильний формат. Використовуйте: /goal_delete [id]")
            return

        goal_id = int(args[0])

        session = Session()
        # Перевіряємо, чи існує ціль
        goal = session.execute(
            sql_text("SELECT name FROM goals WHERE id = :id AND user_id = :user_id"),
            {"id": goal_id, "user_id": message.from_user.id}
        ).fetchone()

        if not goal:
            await message.answer("❌ Ціль не знайдена")
            return

        session.execute(
            sql_text("DELETE FROM goals WHERE id = :id"),
            {"id": goal_id}
        )
        session.commit()

        await message.answer(f"✅ Ціль '{goal.name}' видалена!")

    except ValueError:
        await message.answer("❌ Помилка у форматі даних. ID має бути числом")
    except Exception as e:
        await message.answer("❌ Сталася помилка при видаленні цілі")
        print(f"Error deleting goal: {e}")