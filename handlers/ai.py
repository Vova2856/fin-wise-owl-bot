import logging
import httpx
import asyncio
import os
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler

logger = logging.getLogger(__name__)

# Отримуємо OLLAMA_HOST з змінних середовища або використовуємо значення за замовчуванням
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:9117").strip()

# Додаємо перевірку та префікс протоколу, якщо він відсутній
if not OLLAMA_HOST.startswith(("http://", "https://")):
    OLLAMA_HOST = f"http://localhost:9117"

# Видаляємо зайві слеші в кінці URL, якщо вони є
OLLAMA_HOST = OLLAMA_HOST.rstrip('/')

# Збільшений таймаут для запитів (6 хвилин)
TIMEOUT = 360.0

logger.info(f"Використовується OLLAMA_HOST: {OLLAMA_HOST}")

async def check_ollama_available():
    """Перевіряє доступність сервісу Ollama з детальним логуванням."""
    try:
        # Додаємо перевірку на пустий URL
        if not OLLAMA_HOST:
            logger.error("OLLAMA_HOST не встановлено!")
            return False

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Додаємо додаткове логування перед запитом
            logger.info(f"Спроба підключення до Ollama за URL: http://localhost:9117/api/tags")
            
            try:
                response = await client.get(f"http://localhost:9117/api/tags")
                
                # Додаткове логування відповіді
                logger.info(f"Ollama response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info("Ollama доступний та відповідає")
                    return True
                
                logger.error(f"Ollama відповів з кодом {response.status_code}")
                return False
                
            except httpx.ConnectError as ce:
                logger.error(f"Помилка підключення до Ollama: {str(ce)}")
                return False
            except httpx.TimeoutException:
                logger.error("Таймаут при перевірці доступності Ollama")
                return False
                
    except Exception as e:
        logger.error(f"Невідома помилка при перевірці Ollama: {str(e)}", exc_info=True)
        return False

async def ask_ollama(question: str) -> str:
    """Відправляє запит до Ollama AI та повертає відповідь з покращеним обробленням помилок."""
    try:
        # Перевіряємо, чи є запитання
        if not question or not question.strip():
            logger.error("Отримано пусте запитання")
            return "Будь ласка, введіть коректне запитання."

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

        logger.info(f"Відправляємо запит до Ollama: {question[:50]}...")  # Логуємо початок запитання

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{OLLAMA_HOST}/api/chat",
                    json=ollama_payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Ollama повернув код {response.status_code}. Відповідь: {response.text}")
                    return "Не вдалося отримати відповідь від AI. Спробуйте пізніше."
                
                data = response.json()
                
                if not data.get("message") or not data["message"].get("content"):
                    logger.error(f"Некоректна відповідь від Ollama: {data}")
                    return "Не вдалося обробити відповідь AI."
                
                answer = data["message"]["content"]
                logger.info(f"Отримано відповідь довжиною {len(answer)} символів")
                return answer
                
            except httpx.RequestError as re:
                logger.error(f"Помилка запиту до Ollama: {str(re)}")
                return "Помилка підключення до AI сервісу. Спробуйте пізніше."
            except ValueError as ve:
                logger.error(f"Помилка парсингу JSON: {str(ve)}")
                return "Помилка обробки відповіді AI."

    except Exception as e:
        logger.error(f"Критична помилка в ask_ollama: {str(e)}", exc_info=True)
        return "Вибачте, сталася неочікувана помилка при обробці вашого запиту."

async def handle_ai_question(update: Update, context: CallbackContext, build_main_keyboard_func, build_ai_keyboard_func, ai_session_state):
    """Обробляє запитання користувача до AI з покращеним обробленням помилок."""
    try:
        # Перевіряємо, чи є повідомлення та текст
        if not update.message or not update.message.text:
            logger.error("Отримано пусте повідомлення")
            await update.message.reply_text(
                "Будь ласка, введіть коректне запитання.",
                reply_markup=build_ai_keyboard_func()
            )
            return ai_session_state

        user_question = update.message.text.strip()
        
        # Перевірка довжини запитання
        if len(user_question) < 3:
            await update.message.reply_text(
                "Будь ласка, введіть запитання довше (мінімум 3 символи).",
                reply_markup=build_ai_keyboard_func()
            )
            return ai_session_state

        # Відправляємо статус "друкує"
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        # Отримуємо відповідь від Ollama
        answer = await ask_ollama(user_question)
        
        # Обрізаємо занадто довгу відповідь
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n[...]"
            logger.warning("Відповідь було обрізано через обмеження Telegram")
        
        # Відправляємо відповідь
        await update.message.reply_text(
            f"🤖 FinWise Owl AI:\n\n{answer}",
            reply_markup=build_ai_keyboard_func()
        )
        
        return ai_session_state

    except Exception as e:
        logger.error(f"Критична помилка в handle_ai_question: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "🔴 Сталася критична помилка. Будь ласка, спробуйте ще раз пізніше.",
            reply_markup=build_main_keyboard_func()
        )
        return ConversationHandler.END