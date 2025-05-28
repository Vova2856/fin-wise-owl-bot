import logging
import httpx
import asyncio
from telegram import Update
from telegram.ext import CallbackContext
from main import build_main_keyboard, build_ai_keyboard, ConversationHandler, AI_SESSION

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://localhost:9117"
TIMEOUT = 30.0

async def check_ollama_available():
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{OLLAMA_HOST}/api/tags")
            if response.status_code == 200:
                return True
            logger.error(f"Ollama недоступний. Код статусу: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Помилка перевірки Ollama: {str(e)}")
        return False

async def ask_ollama(question: str) -> str:
    try:
        ollama_payload = {
            "model": "llama3:8b",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ти — фінансовий асистент FinWise Owl. "
                        "Надавай чіткі, лаконічні відповіді українською мовою. "
                        "Фокусуйся на фінансових порадах та аналізі."
                    )
                },
                {"role": "user", "content": question}
            ],
            "stream": False,
            "options": {"temperature": 0.7}
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/chat",
                json=ollama_payload
            )
            
            if response.status_code != 200:
                logger.error(f"Помилка Ollama: {response.status_code} - {response.text}")
                return "Не вдалося отримати відповідь від AI. Спробуйте пізніше."
            
            data = response.json()
            if not data.get("message") or not data["message"].get("content"):
                logger.error("Некоректна відповідь від Ollama")
                return "Не вдалося обробити відповідь AI."
            
            return data["message"]["content"]

    except httpx.ReadTimeout:
        logger.error("Таймаут запиту до Ollama")
        return "Час очікування відповіді минув. Будь ласка, сформулюйте коротше запитання."
    except Exception as e:
        logger.error(f"Помилка запиту до Ollama: {str(e)}")
        return "Вибачте, сталася помилка при обробці вашого запиту."

async def handle_ai_question(update: Update, context: CallbackContext):
    try:
        if not await check_ollama_available():
            await update.message.reply_text(
                "🔴 На жаль, AI-сервіс тимчасово недоступний. Спробуйте пізніше.",
                reply_markup=build_main_keyboard()
            )
            return ConversationHandler.END

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        user_question = update.message.text
        if not user_question or len(user_question.strip()) < 3:
            await update.message.reply_text(
                "Будь ласка, введіть коректне запитання (не менше 3 символів).",
                reply_markup=build_ai_keyboard()
            )
            return AI_SESSION

        answer = await ask_ollama(user_question)
        
        # Обрізаємо відповідь, якщо вона занадто довга для Telegram
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n[...]"
        
        await update.message.reply_text(
            f"🤖 FinWise Owl AI:\n\n{answer}",
            reply_markup=build_ai_keyboard()
        )
        return AI_SESSION

    except Exception as e:
        logger.error(f"Критична помилка в обробнику AI: {str(e)}")
        await update.message.reply_text(
            "🔴 Сталася критична помилка. Будь ласка, спробуйте ще раз пізніше.",
            reply_markup=build_main_keyboard()
        )
        return ConversationHandler.END