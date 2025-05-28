from aiogram import Router, types
from aiogram.filters import Command
from database import Session, Goal

goals_router = Router()

@goals_router.message(Command("goal"))
async def goal_menu(message: types.Message):
    await message.answer(
        "🎯 Управління цілями:\n"
        "/goal_create [назва] [сума] [місяці] - нова ціль\n"
        "/goal_list - мої цілі"
    )