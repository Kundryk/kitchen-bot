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
                    "user_id", "name", "quantity", "unit", "expiry_date", "added_date"
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
    
    def determine_product_category(self, product_name, context=""):
        """Визначення категорії продукту через AI"""
        system_prompt = """
        Ти - експерт з кухонних продуктів. Визнач категорію продукту:
        
        Категорії:
        1. "freezer_raw" - сирі продукти, які зберігаються в морозилці (м'ясо, риба, овочі заморожені)
        2. "freezer_ready" - готові страви в морозилці (вареники, котлети, готові обіди)
        3. "regular" - звичайні продукти (крупи, консерви, молочні продукти, хліб)
        
        Поверни ТІЛЬКИ одне слово: freezer_raw, freezer_ready або regular
        
        Приклади:
        "фарш" -> freezer_raw
        "вареники" -> freezer_ready
        "молоко" -> regular
        "заморожені овочі" -> freezer_raw
        "готові котлети" -> freezer_ready
        """
        
        prompt = f"Продукт: {product_name}"
        if context:
            prompt += f"\nКонтекст: {context}"
        
        response = self.call_chatllm_api(prompt, system_prompt)
        if response and response.strip().lower() in ['freezer_raw', 'freezer_ready', 'regular']:
            return response.strip().lower()
        return 'regular'  # за замовчуванням
    
    def parse_product_message(self, message_text):
        """Розпізнавання продуктів через ChatLLM з визначенням категорій"""
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
                    "expiry_days": кількість днів до закінчення терміну (якщо вказано, інакше null),
                    "context": "додатковий контекст (заморожений, готовий, свіжий тощо)"
                }
            ]
        }

        ВАЖЛИВО: Для складних кількостей типу "4 по 400г" або "2 банки по 500мл":
        - Перемножуй кількість на вагу однієї одиниці
        - "4 по 400г" = 1600г
        - "2 банки по 500мл" = 1000мл
        - "4 банки помідорів по 400г" = 1600г
        
        Приклади:
        "купив 1 л молока" -> {"products": [{"name": "молоко", "quantity": 1, "unit": "л", "expiry_days": 5, "context": "свіже"}]}
        "заморозив 500г фаршу" -> {"products": [{"name": "фарш", "quantity": 500, "unit": "г", "expiry_days": null, "context": "заморожений"}]}
        "приготував вареники, заморозив" -> {"products": [{"name": "вареники", "quantity": 1, "unit": "порція", "expiry_days": null, "context": "готові заморожені"}]}
        
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
        """Додавання продуктів до Google Sheets з автоматичним визначенням категорій"""
        if not self.products_sheet:
            logger.error("Google Sheets не підключено")
            return []
        
        added_products = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            for product in products_data.get('products', []):
                # Визначаємо категорію продукту
                category = self.determine_product_category(
                    product['name'], 
                    product.get('context', '')
                )
                
                # Формуємо назву з префіксом
                if category == 'freezer_raw':
                    product_name = f"[МОРОЗИЛКА] {product['name']}"
                    expiry_days = 90  # 3 місяці для сирих заморожених
                elif category == 'freezer_ready':
                    product_name = f"[МОРОЗИЛКА-ГОТОВЕ] {product['name']}"
                    expiry_days = 60  # 2 місяці для готових заморожених
                else:
                    product_name = product['name']
                    # Визначаємо термін для звичайних продуктів
                    if product.get('expiry_days'):
                        expiry_days = product['expiry_days']
                    else:
                        expiry_days = self.get_default_expiry_days(product['name'])
                
                expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
                
                # Додаємо рядок до таблиці
                self.products_sheet.append_row([
                    str(user_id),
                    product_name,
                    str(product['quantity']),
                    product['unit'],
                    expiry_date,
                    current_time
                ])
                
                added_products.append(f"{product['quantity']} {product['unit']} {product_name}")
                logger.info(f"Додано продукт: {product_name} (категорія: {category}) для користувача {user_id}")
        
        except Exception as e:
            logger.error(f"Помилка додавання продуктів до Sheets: {e}")
            return []
        
        return added_products
    
    def get_default_expiry_days(self, product_name):
        """Визначення стандартного терміну придатності"""
        name_lower = product_name.lower()
        
        if any(word in name_lower for word in ['молоко', 'яйця', 'масло', 'сир', 'кефір', 'йогурт']):
            return 7
        elif any(word in name_lower for word in ['м\'ясо', 'фарш', 'філе', 'сосиски']):
            return 5
        elif any(word in name_lower for word in ['хліб', 'булка', 'батон']):
            return 3
        elif any(word in name_lower for word in ['банани', 'яблука', 'груші']):
            return 5
        else:
            return 365  # для сухих продуктів
    
    def get_user_products_from_sheets(self, user_id):
        """Отримання продуктів користувача з Google Sheets з групуванням"""
        if not self.products_sheet:
            logger.error("Google Sheets не підключено")
            return {"regular": [], "freezer_raw": [], "freezer_ready": []}
        
        try:
            all_records = self.products_sheet.get_all_records()
            
            # Групуємо продукти за категоріями
            categorized_products = {
                "regular": [],
                "freezer_raw": [],
                "freezer_ready": []
            }
            
            for record in all_records:
                if str(record.get('user_id', '')) == str(user_id):
                    product_name = record.get('name', '')
                    
                    product_data = [
                        product_name,
                        record.get('quantity', ''),
                        record.get('unit', ''),
                        record.get('expiry_date', '')
                    ]
                    
                    if '[МОРОЗИЛКА-ГОТОВЕ]' in product_name:
                        categorized_products["freezer_ready"].append(product_data)
                    elif '[МОРОЗИЛКА]' in product_name:
                        categorized_products["freezer_raw"].append(product_data)
                    else:
                        categorized_products["regular"].append(product_data)
            
            # Сортуємо кожну категорію за датою закінчення терміну
            for category in categorized_products:
                categorized_products[category].sort(key=lambda x: x[3] if x[3] else '9999-12-31')
            
            return categorized_products
        
        except Exception as e:
            logger.error(f"Помилка отримання продуктів з Sheets: {e}")
            return {"regular": [], "freezer_raw": [], "freezer_ready": []}

# Ініціалізація бота
kitchen_bot = KitchenBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_message = """
🍳 Привіт! Я твій розумний кухонний асистент!

Що я вмію:
📦 Додавати продукти з автоматичним визначенням категорій:
   • "купив 1л молока" → звичайні продукти
   • "заморозив 500г фаршу" → морозилка (сирі)
   • "приготував вареники, заморозив" → морозилка (готові)

📋 Показувати продукти по категоріях: /products
🍽️ Пропонувати рецепти: /recipes
📊 Аналізувати що можна приготувати: /suggest

🤖 Тепер я розумію категорії продуктів і автоматично їх сортую!
    """
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка звичайних повідомлень"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    await update.message.reply_text("🤔 Аналізую твоє повідомлення та визначаю категорії...")
    
    products_data = kitchen_bot.parse_product_message(message_text)
    
    if products_data.get('products'):
        added_products = kitchen_bot.add_products_to_sheets(products_data, user_id)
        
        if added_products:
            response = f"✅ Додав до твоєї кухні:\n" + "\n".join([f"• {product}" for product in added_products])
        else:
            response = "❌ Не вдалося додати продукти. Перевір підключення до Google Sheets."
    else:
        system_prompt = """
        Ти - дружній кухонний асистент. Користувач написав повідомлення, але в ньому немає інформації про продукти.
        Відповідай коротко і дружньо, пропонуй допомогу з кухонними справами.
        Пиши українською мовою.
        """
        
        ai_response = kitchen_bot.call_chatllm_api(message_text, system_prompt)
        response = ai_response if ai_response else "Вибач, не зрозумів. Спробуй написати про продукти, які ти купив або маєш."
    
    await update.message.reply_text(response)

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /products - показати продукти користувача з групуванням по категоріях"""
    user_id = update.effective_user.id
    products = kitchen_bot.get_user_products_from_sheets(user_id)
    
    # Перевіряємо, чи є взагалі продукти
    total_products = len(products["regular"]) + len(products["freezer_raw"]) + len(products["freezer_ready"])
    
    if total_products == 0:
        await update.message.reply_text("📦 Твоя кухня порожня! Додай продукти, написавши про них.")
        return
    
    response = "📦 Твої продукти:\n\n"
    
    # Звичайні продукти
    if products["regular"]:
        response += "🏠 **Звичайні продукти:**\n"
        for name, quantity, unit, expiry_date in products["regular"]:
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
        response += "\n"
    
    # Сирі продукти з морозилки
    if products["freezer_raw"]:
        response += "🧊 **Морозилка (сирі продукти):**\n"
        for name, quantity, unit, expiry_date in products["freezer_raw"]:
            clean_name = name.replace("[МОРОЗИЛКА] ", "")
            response += f"• {quantity} {unit} {clean_name} (до {expiry_date})\n"
        response += "\n"
    
    # Готові страви з морозилки
    if products["freezer_ready"]:
        response += "🍽️❄️ **Морозилка (готові страви):**\n"
        for name, quantity, unit, expiry_date in products["freezer_ready"]:
            clean_name = name.replace("[МОРОЗИЛКА-ГОТОВЕ] ", "")
            response += f"• {quantity} {unit} {clean_name} (до {expiry_date})\n"
    
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
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🤖 Розумний кухонний бот запущено з підтримкою категорій!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
