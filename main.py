import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Функція для команди /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Відправляє привітання коли користувач натискає /start"""
    user = update.effective_user
    await update.message.reply_html(
        f"Привіт, {user.mention_html()}! 👋\n\n"
        f"Я твій персональний кухонний помічник! 🍳\n\n"
        f"Що я вмію:\n"
        f"• Допомагати з продуктами на кухні\n"
        f"• Аналізувати рецепти\n"
        f"• Пропонувати що приготувати\n\n"
        f"Напиши мені що-небудь, і я спробую допомогти!"
    )

# Функція для обробки звичайних повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробляє всі текстові повідомлення"""
    user_message = update.message.text
    user_name = update.effective_user.first_name
    
    # Поки що просто відповідаємо, що отримали повідомлення
    await update.message.reply_text(
        f"Привіт, {user_name}! 😊\n\n"
        f"Ти написав: '{user_message}'\n\n"
        f"Поки що я вчуся розуміти твої повідомлення. "
        f"Скоро я стану розумнішим і зможу допомагати з кухнею! 🚀"
    )

def main() -> None:
    """Запускає бота"""
    # Отримуємо токен з змінних середовища (для безпеки)
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не знайдено! Додай його в змінні середовища.")
        return
    
    # Створюємо додаток
    application = Application.builder().token(token).build()
    
    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаємо бота
    logger.info("Бот запущений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
    