from aiogram import Router, types
from aiogram.filters import Command
from ollama import Client
import logging

ai_router = Router()

# Налаштовуємо клієнт для Ollama (ваш порт 9117)
ollama_client = Client(host='http://localhost:9117')

@ai_router.message(Command("ask"))
async def handle_ask_command(message: types.Message):
    # Отримуємо текст після команди /ask
    question = message.text.replace('/ask', '').strip()
    
    if not question:
        await message.answer("Будь ласка, введіть ваш запит після команди /ask")
        return

    try:
        # Відправляємо статус "друкує"
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        # Запит до Ollama з явним вказівником мови
        response = ollama_client.chat(
            model='llama3:8b',
            messages=[
                {
                    'role': 'system',
                    'content': 'Ти фінансовий помічник FinWise Owl. Відповідай українською.'
                },
                {
                    'role': 'user', 
                    'content': question
                }
            ],
            options={'temperature': 0.7}
        )
        
        await message.answer(response['message']['content'])
    except Exception as e:
        logging.error(f"Помилка Ollama: {e}")
        await message.answer("⚠️ Не вдалося отримати відповідь. Спробуйте пізніше.")

# Обробник для питань без команди /ask
@ai_router.message(lambda msg: "заощадити" in msg.text.lower() or "економі" in msg.text.lower())
async def handle_saving_questions(message: types.Message):
    await handle_ask_command(message)
    
