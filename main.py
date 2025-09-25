import os
import json
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import gspread
from google.oauth2.service_account import Credentials

# Імпортуємо нові модулі
from database import KitchenDatabase
from kitchen_core import add_product, remove_product, list_products

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHATLLM_API_KEY = os.getenv('CHATLLM_API_KEY')
CHATLLM_API_URL = "https://routellm.abacus.ai/v1/chat/completions"

class KitchenBot:
    def __init__(self):
        self.init_gsheets()
        # Ініціалізуємо нову базу даних
        self.db = KitchenDatabase()
    
    def init_gsheets(self):
        """Ініціалізація Google Sheets (старий код для сумісності)"""
        try:
            logger.info("🔄 Починаю ініціалізацію Google Sheets...")
            
            creds_env = os.environ.get("GOOGLE_CREDENTIALS")
            if not creds_env:
                logger.error("❌ Змінна GOOGLE_CREDENTIALS не знайдена в Railway!")
                self.products_sheet = None
                return
            
            logger.info("✅ GOOGLE_CREDENTIALS знайдено")
            
            service_account_info = json.loads(creds_env)
            logger.info(f"✅ JSON розпарсено. Project ID: {service_account_info.get('project_id')}")
            
            creds = Credentials.from_service_account_info(
                service_account_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            logger.info("✅ Креденшіали створено")
            
            client = gspread.authorize(creds)
            logger.info("✅ Авторизація в gspread пройшла")
            
            logger.info("🔄 Намагаюсь відкрити таблицю 'kitchen_products'...")
            self.products_sheet = client.open("kitchen_products").sheet1
            logger.info("✅ Таблиця 'kitchen_products' відкрита успішно")
            
            if len(self.products_sheet.get_all_values()) == 0:
                logger.info("🔄 Таблиця порожня, додаю заголовки...")
                self.products_sheet.append_row([
                    "user_id", "product_name", "quantity", "unit", "expiry_date", "added_date"
                ])
                logger.info("✅ Заголовки додано")
            
            logger.info("🎉 З'єднання з Google Sheets повністю успішне!")
            
        except Exception as e:
            logger.error(f"❌ Детальна помилка з'єднання з Google Sheets: {e}")
            logger.error(f"❌ Тип помилки: {type(e).__name__}")
            self.products_sheet = None
    
    def call_chatllm_api(self, prompt, system_message=""):
        """Виклик ChatLLM API"""
        headers = {
            'Authorization': f'Bearer {CHATLLM_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(CHATLLM_API_URL, headers=headers, json=data)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Помилка ChatLLM API: {e}")
            return None
    
    def parse_action_and_product(self, message_text):
        """Розпізнавання дії (додати/відняти) та продукту через ChatLLM"""
        system_prompt = """
        Ти - асистент для розпізнавання дій з продуктами харчування.
        Твоє завдання - визначити, що хоче зробити користувач: додати чи відняти продукт.
        
        Формат відповіді (JSON):
        {
            "action": "add" або "remove",
            "product_name": "назва продукту",
            "quantity": число,
            "unit": "одиниця виміру (кг, л, шт, г, мл)",
            "confidence": 0.9
        }

        Ключові слова для "remove" (відняти):
        - з'їв, зїв, з'їла, зїла
        - витратив, використав
        - приготував з цього
        - відняти, мінус

        Ключові слова для "add" (додати):
        - купив, додав, поклав
        - привіз, отримав
        - плюс, додати

        Приклади:
        "я з'їв 250 грам сирників" -> {"action": "remove", "product_name": "сирники", "quantity": 250, "unit": "г", "confidence": 0.9}
        "купив 1 літр молока" -> {"action": "add", "product_name": "молоко", "quantity": 1, "unit": "л", "confidence": 0.9}
        
        Якщо не можеш визначити дію, поверни: {"action": "unknown", "confidence": 0.0}
        """
        
        response = self.call_chatllm_api(message_text, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error(f"Не вдалося розпарсити JSON: {response}")
        return {"action": "unknown", "confidence": 0.0}

# Ініціалізація бота
kitchen_bot = KitchenBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_message = """
🍳 Привіт! Я твій розумний кухонний асистент!

Що я вмію:
📦 Розумію твої повідомлення:
   • "купив 1л молока" → додам до списку
   • "з'їв 250г сирників" → відніму зі списку
   • "що у мене є?" → покажу всі продукти

📋 Команди:
   • /products - показати всі продукти
   • /test_add - тест додавання
   • /test_remove - тест віднімання

🤖 Тепер я розумію, коли ти щось додаєш, а коли з'їдаєш!
    """
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка звичайних повідомлень з новою логікою"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    await update.message.reply_text("🤔 Аналізую твоє повідомлення...")
    
    # Використовуємо нову функцію розпізнавання дій
    action_data = kitchen_bot.parse_action_and_product(message_text)
    
    if action_data["action"] == "add":
        result = add_product(
            user_id, 
            action_data["product_name"], 
            action_data["quantity"], 
            action_data["unit"]
        )
        await update.message.reply_text(result)
        
    elif action_data["action"] == "remove":
        result = remove_product(
            user_id, 
            action_data["product_name"], 
            action_data["quantity"], 
            action_data["unit"]
        )
        await update.message.reply_text(result)
        
    else:
        # Якщо не зрозуміли дію - загальна відповідь
        system_prompt = """
        Ти - дружній кухонний асистент. Користувач написав повідомлення, але я не зрозумів, що він хоче зробити.
        Відповідай коротко і дружньо, пропонуй допомогу з кухонними справами.
        Пиши українською мовою.
        """
        
        ai_response = kitchen_bot.call_chatllm_api(message_text, system_prompt)
        response = ai_response if ai_response else "Вибач, не зрозумів. Спробуй написати 'купив молоко' або 'з'їв хліб'."
        await update.message.reply_text(response)

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /products - показати продукти через нові функції"""
    user_id = update.effective_user.id
    products = list_products(user_id)
    
    if not products:
        await update.message.reply_text("📦 Твоя кухня порожня! Додай продукти, написавши про них.")
        return
    
    response = "📦 Твої продукти:\n\n"
    for product in products:
        expiry_info = ""
        if product.get('expiry_date'):
            expiry_info = f" (до {product['expiry_date']})"
        
        response += f"• {product['quantity']}{product['unit']} {product['product_name']}{expiry_info}\n"
    
    await update.message.reply_text(response)

async def test_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестова команда для додавання"""
    user_id = update.effective_user.id
    result = add_product(user_id, "тестовий продукт", 100, "г")
    await update.message.reply_text(f"🧪 Тест додавання:\n{result}")

async def test_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестова команда для віднімання"""
    user_id = update.effective_user.id
    result = remove_product(user_id, "тестовий продукт", 50, "г")
    await update.message.reply_text(f"🧪 Тест віднімання:\n{result}")

def main():
    """Запуск бота"""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не встановлено!")
        return
    
    if not CHATLLM_API_KEY:
        logger.error("CHATLLM_API_KEY не встановлено!")
        return
    
    if not os.getenv('GOOGLE_CREDENTIALS'):
        logger.error("GOOGLE_CREDENTIALS не встановлено!")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(CommandHandler("test_add", test_add))
    application.add_handler(CommandHandler("test_remove", test_remove))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🤖 Розумний кухонний бот запущено з новими функціями!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
