import os
import json
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import gspread
from google.oauth2.service_account import Credentials

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
    
    def init_gsheets(self):
        """Ініціалізація Google Sheets"""
        try:
            service_account_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
            creds = Credentials.from_service_account_info(
                service_account_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            client = gspread.authorize(creds)
            
            # Відкриваємо таблицю для продуктів
            self.products_sheet = client.open("kitchen_products").sheet1
            
            # Створюємо заголовки, якщо таблиця порожня
            if len(self.products_sheet.get_all_values()) == 0:
                self.products_sheet.append_row([
                    "user_id", "name", "quantity", "unit", "expiry_date", "added_date"
                ])
            
            logger.info("✅ З'єднання з Google Sheets успішне")
        except Exception as e:
            logger.error(f"❌ Помилка з'єднання з Google Sheets: {e}")
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
    
    def parse_product_message(self, message_text):
        """Розпізнавання продуктів через ChatLLM"""
        system_prompt = """
        Ти - асистент для розпізнавання продуктів харчування з повідомлень користувача.
        Твоє завдання - витягти інформацію про продукти та повернути її у форматі JSON.
        
        Формат відповіді:
        {
            "products": [
                {
                    "name": "назва продукту",
                    "quantity": число,
                    "unit": "одиниця виміру (кг, л, шт, г, мл)",
                    "expiry_days": кількість днів до закінчення терміну (якщо вказано, інакше null)
                }
            ]
        }
        
        Приклади:
        "купив 1 л молока" -> {"products": [{"name": "молоко", "quantity": 1, "unit": "л", "expiry_days": 5}]}
        "взяв 200г масла і 6 яєць" -> {"products": [{"name": "масло", "quantity": 200, "unit": "г", "expiry_days": 30}, {"name": "яйця", "quantity": 6, "unit": "шт", "expiry_days": 21}]}
        
        Якщо в повідомленні немає продуктів, поверни: {"products": []}
        """
        
        response = self.call_chatllm_api(message_text, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error(f"Не вдалося розпарсити JSON: {response}")
        return {"products": []}
    
    def add_products_to_sheets(self, products_data, user_id):
        """Додавання продуктів до Google Sheets"""
        if not self.products_sheet:
            logger.error("Google Sheets не підключено")
            return []
        
        added_products = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            for product in products_data.get('products', []):
                expiry_date = ""
                if product.get('expiry_days'):
                    expiry_date = (datetime.now() + timedelta(days=product['expiry_days'])).strftime("%Y-%m-%d")
                
                # Додаємо рядок до таблиці
                self.products_sheet.append_row([
                    str(user_id),
                    product['name'],
                    str(product['quantity']),
                    product['unit'],
                    expiry_date,
                    current_time
                ])
                
                added_products.append(f"{product['quantity']} {product['unit']} {product['name']}")
                logger.info(f"Додано продукт: {product['name']} для користувача {user_id}")
        
        except Exception as e:
            logger.error(f"Помилка додавання продуктів до Sheets: {e}")
            return []
        
        return added_products
    
    def get_user_products_from_sheets(self, user_id):
        """Отримання продуктів користувача з Google Sheets"""
        if not self.products_sheet:
            logger.error("Google Sheets не підключено")
            return []
        
        try:
            # Отримуємо всі дані з таблиці
            all_records = self.products_sheet.get_all_records()
            
            # Фільтруємо продукти для конкретного користувача
            user_products = []
            for record in all_records:
                if str(record.get('user_id', '')) == str(user_id):
                    user_products.append([
                        record.get('name', ''),
                        record.get('quantity', ''),
                        record.get('unit', ''),
                        record.get('expiry_date', '')
                    ])
            
            # Сортуємо за датою закінчення терміну
            user_products.sort(key=lambda x: x[3] if x[3] else '9999-12-31')
            return user_products
        
        except Exception as e:
            logger.error(f"Помилка отримання продуктів з Sheets: {e}")
            return []

# Ініціалізація бота
kitchen_bot = KitchenBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_message = """
🍳 Привіт! Я твій кухонний асистент!

Що я вмію:
📦 Додавати продукти: "купив 1л молока", "взяв 200г масла"
📋 Показувати твої продукти: /products
🍽️ Пропонувати рецепти: /recipes
📊 Аналізувати що можна приготувати: /suggest

Просто напиши мені про продукти, які ти купив або маєш!

🔄 Тепер всі дані зберігаються в Google Sheets!
    """
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка звичайних повідомлень"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Показуємо, що бот "думає"
    await update.message.reply_text("🤔 Аналізую твоє повідомлення...")
    
    # Розпізнаємо продукти через ChatLLM
    products_data = kitchen_bot.parse_product_message(message_text)
    
    if products_data.get('products'):
        # Додаємо продукти до Google Sheets
        added_products = kitchen_bot.add_products_to_sheets(products_data, user_id)
        
        if added_products:
            response = f"✅ Додав до твоєї кухні (Google Sheets):\n" + "\n".join([f"• {product}" for product in added_products])
        else:
            response = "❌ Не вдалося додати продукти. Перевір підключення до Google Sheets."
    else:
        # Якщо продуктів не знайдено, відповідаємо через ChatLLM
        system_prompt = """
        Ти - дружній кухонний асистент. Користувач написав повідомлення, але в ньому немає інформації про продукти.
        Відповідай коротко і дружньо, пропонуй допомогу з кухонними справами.
        Пиши українською мовою.
        """
        
        ai_response = kitchen_bot.call_chatllm_api(message_text, system_prompt)
        response = ai_response if ai_response else "Вибач, не зрозумів. Спробуй написати про продукти, які ти купив або маєш."
    
    await update.message.reply_text(response)

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /products - показати продукти користувача з Google Sheets"""
    user_id = update.effective_user.id
    products = kitchen_bot.get_user_products_from_sheets(user_id)
    
    if not products:
        await update.message.reply_text("📦 Твоя кухня порожня! Додай продукти, написавши про них.")
        return
    
    response = "📦 Твої продукти (з Google Sheets):\n\n"
    for name, quantity, unit, expiry_date in products:
        expiry_info = ""
        if expiry_date:
            try:
                expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                days_left = (expiry_date_obj - datetime.now().date()).days
                if days_left < 0:
                    expiry_info = " ⚠️ прострочено"
                elif days_left <= 3:
                    expiry_info = f" ⚠️ закінчується через {days_left} дн."
                else:
                    expiry_info = f" (до {expiry_date})"
            except ValueError:
                expiry_info = f" (до {expiry_date})"
        
        response += f"• {quantity} {unit} {name}{expiry_info}\n"
    
    await update.message.reply_text(response)

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
    
    # Створення додатку
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    logger.info("Бот запущено з Google Sheets!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
