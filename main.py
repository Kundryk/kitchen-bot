import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHATLLM_API_KEY = os.getenv('CHATLLM_API_KEY')  # Додай це в Railway
CHATLLM_API_URL = "https://routellm.abacus.ai/v1/chat/completions"  # URL для RouteLLM

class KitchenBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Ініціалізація бази даних"""
        conn = sqlite3.connect('kitchen.db')
        cursor = conn.cursor()
        
        # Таблиця продуктів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                expiry_date DATE,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL
            )
        ''')
        
        # Таблиця рецептів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,  -- JSON
                instructions TEXT NOT NULL,
                servings INTEGER DEFAULT 1,
                user_id INTEGER NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблиця вподобань користувача
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                liked_recipes TEXT,  -- JSON список ID рецептів
                disliked_ingredients TEXT,  -- JSON список інгредієнтів
                dietary_restrictions TEXT  -- JSON
            )
        ''')
        
        conn.commit()
        conn.close()
    
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
            "model": "gpt-4o-mini",  # Або інша модель з RouteLLM
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
    
    def add_products_to_db(self, products_data, user_id):
        """Додавання продуктів до бази даних"""
        conn = sqlite3.connect('kitchen.db')
        cursor = conn.cursor()
        
        added_products = []
        for product in products_data.get('products', []):
            expiry_date = None
            if product.get('expiry_days'):
                expiry_date = (datetime.now() + timedelta(days=product['expiry_days'])).date()
            
            cursor.execute('''
                INSERT INTO products (name, quantity, unit, expiry_date, user_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                product['name'],
                product['quantity'],
                product['unit'],
                expiry_date,
                user_id
            ))
            added_products.append(f"{product['quantity']} {product['unit']} {product['name']}")
        
        conn.commit()
        conn.close()
        return added_products
    
    def get_user_products(self, user_id):
        """Отримання продуктів користувача"""
        conn = sqlite3.connect('kitchen.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, quantity, unit, expiry_date
            FROM products
            WHERE user_id = ?
            ORDER BY expiry_date ASC
        ''', (user_id,))
        
        products = cursor.fetchall()
        conn.close()
        return products

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
        # Додаємо продукти до бази
        added_products = kitchen_bot.add_products_to_db(products_data, user_id)
        
        if added_products:
            response = f"✅ Додав до твоєї кухні:\n" + "\n".join([f"• {product}" for product in added_products])
        else:
            response = "❌ Не вдалося додати продукти. Спробуй ще раз."
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
    """Команда /products - показати продукти користувача"""
    user_id = update.effective_user.id
    products = kitchen_bot.get_user_products(user_id)
    
    if not products:
        await update.message.reply_text("📦 Твоя кухня порожня! Додай продукти, написавши про них.")
        return
    
    response = "📦 Твої продукти:\n\n"
    for name, quantity, unit, expiry_date in products:
        expiry_info = ""
        if expiry_date:
            expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            days_left = (expiry_date_obj - datetime.now().date()).days
            if days_left < 0:
                expiry_info = " ⚠️ прострочено"
            elif days_left <= 3:
                expiry_info = f" ⚠️ закінчується через {days_left} дн."
            else:
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
    
    # Створення додатку
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    logger.info("Бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
