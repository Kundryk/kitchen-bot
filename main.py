main_code = '''import os
import json
import logging
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import gspread
from google.oauth2.service_account import Credentials

# Імпортуємо нові модулі
from database import KitchenDatabase
from kitchen_core import (
    add_product, remove_product, list_products, find_product,
    get_expiring_products, add_to_shopping_list, get_shopping_list,
    remove_from_shopping_list, get_consumption_stats
)

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
        self.db = KitchenDatabase()
    
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
    
    def parse_user_intent(self, message_text, user_id):
        """Розпізнавання наміру користувача через ChatLLM"""
        # Отримуємо список продуктів для контексту
        products = list_products(user_id)
        products_context = ", ".join([p["product_name"] for p in products[:10]])  # перші 10
        
        system_prompt = f"""
        Ти - асистент для розпізнавання намірів користувача щодо кухонних продуктів.
        
        Контекст: у користувача є такі продукти: {products_context}
        
        Визнач намір і поверни JSON:
        
        1. ДОДАТИ продукт:
        {{"action": "add", "product_name": "назва", "quantity": число, "unit": "одиниця", "confidence": 0.9}}
        
        2. ВІДНЯТИ/З'ЇСТИ продукт:
        {{"action": "remove", "product_name": "назва", "quantity": число, "unit": "одиниця", "confidence": 0.9}}
        
        3. ЗАПИТАТИ про наявність:
        {{"action": "query", "product_name": "назва", "confidence": 0.9}}
        
        4. ДОДАТИ до списку покупок:
        {{"action": "shopping_add", "product_name": "назва", "quantity": число, "unit": "одиниця", "confidence": 0.9}}
        
        5. ЗАГАЛЬНА РОЗМОВА:
        {{"action": "chat", "confidence": 0.5}}

        Ключові слова:
        - Додати: "купив", "додав", "поклав", "привіз", "отримав"
        - Відняти: "з'їв", "зїв", "витратив", "використав", "приготував", "відняти"
        - Запитати: "скільки", "чи є", "що у мене", "маю", "залишилось"
        - Покупки: "треба купити", "додай до списку", "нагадай купити"
        
        Приклади:
        "купив 1л молока" → {{"action": "add", "product_name": "молоко", "quantity": 1, "unit": "л", "confidence": 0.9}}
        "з'їв 250г сирників" → {{"action": "remove", "product_name": "сирники", "quantity": 250, "unit": "г", "confidence": 0.9}}
        "скільки у мене картоплі?" → {{"action": "query", "product_name": "картопля", "confidence": 0.9}}
        "треба купити хліб" → {{"action": "shopping_add", "product_name": "хліб", "quantity": 1, "unit": "шт", "confidence": 0.8}}
        """
        
        response = self.call_chatllm_api(message_text, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error(f"Не вдалося розпарсити JSON: {response}")
        return {"action": "chat", "confidence": 0.0}

# Ініціалізація бота
kitchen_bot = KitchenBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_message = """
🍳 Привіт! Я твій розумний кухонний асистент!

🤖 Що я розумію:
• "купив 1л молока" → додам до кухні
• "з'їв 250г сирників" → відніму з кухні  
• "скільки у мене картоплі?" → покажу наявність
• "треба купити хліб" → додам до списку покупок

📋 Команди:
• /products - всі продукти
• /expiring - що скоро псується
• /shopping - список покупок
• /stats - статистика споживання
• /remove 250 г сирників - точне віднімання

🎯 Просто пиши природною мовою!
    """
    await update.message.reply_text(welcome_message)

# Регулярні вирази для швидкого парсингу
REMOVE_RX = re.compile(r"^/remove\\s+(?P<qty>[\\d.,]+)\\s*(?P<unit>г|гр|кг|мл|л|шт)\\s+(?P<name>.+)$", re.IGNORECASE)
QUICK_REMOVE_RX = re.compile(r"(?P<qty>[\\d.,]+)\\s*(?P<unit>г|гр|кг|мл|л|шт)\\s+(?P<name>.+?)(?:\\s|$)", re.IGNORECASE)

async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /remove для точного віднімання"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    m = REMOVE_RX.match(text)
    if not m:
        await update.message.reply_text("Формат: /remove 250 г сирників")
        return
    
    qty = float(m.group("qty").replace(",", "."))
    unit = m.group("unit")
    name = m.group("name").strip()
    
    result = remove_product(user_id, name, qty, unit)
    await update.message.reply_text(result)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Головна обробка повідомлень"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Швидкий парсинг для віднімання
    low = message_text.lower()
    if any(kw in low for kw in ["з'їв", "зїв", "відніми", "відняти", "мінус", "використав", "витратив"]):
        m = QUICK_REMOVE_RX.search(low)
        if m:
            qty = float(m.group("qty").replace(",", "."))
            unit = m.group("unit")
            name = m.group("name").strip()
            result = remove_product(user_id, name, qty, unit)
            await update.message.reply_text(result)
            return
    
    # AI розпізнавання наміру
    await update.message.reply_text("🤔 Аналізую твоє повідомлення...")
    intent = kitchen_bot.parse_user_intent(message_text, user_id)
    
    if intent["action"] == "add":
        result = add_product(
            user_id, 
            intent["product_name"], 
            intent["quantity"], 
            intent["unit"]
        )
        await update.message.reply_text(result)
        
    elif intent["action"] == "remove":
        result = remove_product(
            user_id, 
            intent["product_name"], 
            intent["quantity"], 
            intent["unit"]
        )
        await update.message.reply_text(result)
        
    elif intent["action"] == "query":
        found_products = find_product(user_id, intent["product_name"])
        if found_products:
            response = f"🔍 Знайшов {intent['product_name']}:\\n\\n"
            for product in found_products:
                response += f"• {product['quantity']}{product['unit']} {product['product_name']}\\n"
        else:
            response = f"❌ У тебе немає {intent['product_name']}"
        await update.message.reply_text(response)
        
    elif intent["action"] == "shopping_add":
        result = add_to_shopping_list(
            user_id,
            intent["product_name"],
            intent.get("quantity", 1),
            intent.get("unit", "шт")
        )
        await update.message.reply_text(result)
        
    else:
        # Загальна розмова
        system_prompt = """
        Ти - дружній кухонний асистент. Відповідай коротко і корисно.
        Пропонуй допомогу з кухонними справами. Пиши українською.
        """
        ai_response = kitchen_bot.call_chatllm_api(message_text, system_prompt)
        response = ai_response if ai_response else "Вибач, не зрозумів. Спробуй написати про продукти!"
        await update.message.reply_text(response)

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /products"""
    user_id = update.effective_user.id
    products = list_products(user_id)
    
    if not products:
        await update.message.reply_text("📦 Твоя кухня порожня! Додай продукти.")
        return
    
    # Групуємо по категоріях
    categories = {"Звичайні": [], "Морозилка": [], "Готова їжа": []}
    
    for product in products:
        name = product["product_name"]
        if "[МОРОЗИЛКА]" in name:
            categories["Морозилка"].append(product)
        elif "[ГОТОВА_ЇЖА]" in name or "[МОРОЗИЛКА_ГОТОВА]" in name:
            categories["Готова їжа"].append(product)
        else:
            categories["Звичайні"].append(product)
    
    response = "📦 Твої продукти:\\n\\n"
    for cat_name, items in categories.items():
        if items:
            response += f"**{cat_name}:**\\n"
            for product in items:
                clean_name = product["product_name"].replace("[МОРОЗИЛКА]", "").replace("[ГОТОВА_ЇЖА]", "").replace("[МОРОЗИЛКА_ГОТОВА]", "").strip()
                expiry_info = f" (до {product['expiry_date']})" if product.get('expiry_date') else ""
                response += f"• {product['quantity']}{product['unit']} {clean_name}{expiry_info}\\n"
            response += "\\n"
    
    await update.message.reply_text(response)

async def show_expiring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /expiring"""
    user_id = update.effective_user.id
    expiring = get_expiring_products(user_id, days=3)
    
    if not expiring:
        await update.message.reply_text("✅ Немає продуктів, що скоро псуються!")
        return
    
    response = "⚠️ Продукти, що скоро псуються:\\n\\n"
    for product in expiring:
        days_left = product["days_left"]
        if days_left < 0:
            status = "❌ ПРОСТРОЧЕНО"
        elif days_left == 0:
            status = "🔥 СЬОГОДНІ"
        elif days_left == 1:
            status = "⚡ ЗАВТРА"
        else:
            status = f"📅 {days_left} днів"
        
        clean_name = product["product_name"].replace("[МОРОЗИЛКА]", "").replace("[ГОТОВА_ЇЖА]", "").strip()
        response += f"• {product['quantity']}{product['unit']} {clean_name} - {status}\\n"
    
    await update.message.reply_text(response)

async def show_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /shopping"""
    user_id = update.effective_user.id
    shopping = get_shopping_list(user_id)
    
    if not shopping:
        await update.message.reply_text("📝 Список покупок порожній!")
        return
    
    response = "🛒 Список покупок:\\n\\n"
    for item in shopping:
        response += f"• {item['quantity']}{item['unit']} {item['item']}\\n"
    
    await update.message.reply_text(response)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats"""
    user_id = update.effective_user.id
    stats = get_consumption_stats(user_id, days=7)
    
    response = "📊 Статистика за тиждень:\\n\\n"
    
    if stats["consumed"]:
        response += "🍽️ **Спожито:**\\n"
        for item in stats["consumed"][:5]:  # топ 5
            response += f"• {item['quantity']}г/мл {item['product']}\\n"
        response += "\\n"
    
    if stats["added"]:
        response += "📦 **Додано:**\\n"
        for item in stats["added"][:5]:  # топ 5
            response += f"• {item['quantity']}г/мл {item['product']}\\n"
    
    if not stats["consumed"] and not stats["added"]:
        response += "Поки що немає активності 🤷‍♂️"
    
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
    
    # Реєструємо команди
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(CommandHandler("expiring", show_expiring))
    application.add_handler(CommandHandler("shopping", show_shopping))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("remove", cmd_remove))
    
    # Обробка повідомлень (має бути останньою)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🤖 Розумний кухонний бот запущено з повним функціоналом!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
'''

# Записуємо файли
with open('database.py', 'w', encoding='utf-8') as f:
    f.write(database_code)

with open('kitchen_core.py', 'w', encoding='utf-8') as f:
    f.write(kitchen_core_code)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(main_code)

print("✅ Створено 3 файли:")
print("📁 database.py - робота з Google Sheets")
print("📁 kitchen_core.py - основна логіка кухні") 
print("📁 main.py - Telegram бот")
print("\n🚀 Готово до деплою!")
