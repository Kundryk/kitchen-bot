import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import Database
from nlp_processor import NLPProcessor
from recipe_manager import RecipeManager

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class KitchenBot:
    def __init__(self):
        self.db = Database()
        self.nlp = NLPProcessor()
        self.recipe_manager = RecipeManager(self.db)
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        welcome_message = """
🍳 **Привіт! Я твій кухонний помічник!**

Я розумію звичайну мову, тому можеш писати мені як другу:

🔍 **Рецепти:**
• "дай рецепт борщу"
• "борщ на 6 порцій"
• "що приготувати з курки?"
• "випадковий рецепт"

🛒 **Продукти:**
• "мої запаси"
• "додай молоко 2 літри"
• "що є в холодильнику?"

🔄 **Заміни:**
• "чим замінити молоко?"
• "немає цукру, що робити?"

📊 **Харчування:**
• "калорії борщу"
• "поживність м'яса"

💡 **Поради:**
• "поради для борщу"
• "як краще готувати?"

Просто пиши мені природною мовою! 😊
        """
        
        # Кнопки швидкого доступу
        keyboard = [
            [InlineKeyboardButton("🍲 Випадковий рецепт", callback_data="random_recipe")],
            [InlineKeyboardButton("🛒 Мої запаси", callback_data="my_inventory")],
            [InlineKeyboardButton("📚 Всі рецепти", callback_data="all_recipes")],
            [InlineKeyboardButton("💡 Що приготувати?", callback_data="cooking_suggestions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка звичайних повідомлень"""
        user_message = update.message.text
        
        # Обробляємо повідомлення через NLP
        processed = self.nlp.process_message(user_message)
        intent = processed['intent']
        params = processed['parameters']
        
        # Показуємо що зрозуміли
        response_template = self.nlp.generate_response_template(intent, params)
        await update.message.reply_text(response_template)
        
        # Обробляємо за типом запиту
        if intent == 'recipe':
            await self.handle_recipe_request(update, params)
        elif intent == 'substitution':
            await self.handle_substitution_request(update, params)
        elif intent == 'nutrition':
            await self.handle_nutrition_request(update, params)
        elif intent == 'inventory':
            await self.handle_inventory_request(update)
        elif intent == 'meal_plan':
            await self.handle_meal_plan_request(update)
        else:
            await self.handle_unknown_request(update, user_message)
    
    async def handle_recipe_request(self, update: Update, params: dict):
        """Обробка запитів рецептів"""
        dish = params.get('dish')
        servings = params.get('servings')
        category = params.get('category')
        difficulty = params.get('difficulty')
        
        if dish:
            # Шукаємо конкретну страву
            recipe = self.recipe_manager.get_recipe_by_name(dish, servings)
            if recipe:
                message = self.recipe_manager.format_recipe_message(recipe)
                
                # Додаємо кнопки для додаткових дій
                keyboard = [
                    [InlineKeyboardButton("🔍 Перевірити інгредієнти", callback_data=f"check_ingredients_{recipe['id']}")],
                    [InlineKeyboardButton("💡 Поради", callback_data=f"cooking_tips_{recipe['id']}")],
                    [InlineKeyboardButton("🛒 Список покупок", callback_data=f"shopping_list_{recipe['id']}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                # Пропонуємо схожі рецепти
                similar_recipes = self.recipe_manager.find_recipes(dish)
                if similar_recipes:
                    message = self.recipe_manager.format_recipe_list(similar_recipes, f"Схожі рецепти на '{dish}'")
                    await update.message.reply_text(message, parse_mode='Markdown')
                else:
                    await update.message.reply_text(f"❌ Рецепт '{dish}' не знайдено. Спробуй інші варіанти:")
                    await self.send_recipe_suggestions(update)
        else:
            # Випадковий рецепт з фільтрами
            recipe = self.recipe_manager.get_random_recipe(category, difficulty)
            if recipe:
                message = "🎲 **Випадковий рецепт для тебе:**\n\n"
                message += self.recipe_manager.format_recipe_message(recipe)
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Не знайшов підходящих рецептів")
    
    async def handle_substitution_request(self, update: Update, params: dict):
        """Обробка запитів замін"""
        ingredient = params.get('ingredient')
        
        if ingredient:
            substitutions = self.db.get_substitutions(ingredient)
            if substitutions:
                message = f"🔄 **Чим можна замінити {ingredient}:**\n\n"
                for i, (substitute, ratio, notes) in enumerate(substitutions, 1):
                    message += f"{i}. **{substitute}**"
                    if ratio != 1.0:
                        message += f" (коефіцієнт {ratio})"
                    message += "\n"
                    if notes:
                        message += f"   💡 {notes}\n"
                    message += "\n"
            else:
                message = f"❌ Не знайшов замін для '{ingredient}'\n\n"
                message += "💡 Спробуй написати інакше або запитай про інший інгредієнт"
        else:
            message = "❓ Не зрозумів який інгредієнт потрібно замінити. Спробуй написати: 'чим замінити молоко?'"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_nutrition_request(self, update: Update, params: dict):
        """Обробка запитів харчової цінності"""
        item = params.get('item')
        
        if item:
            # Тут можна додати логіку для отримання харчової цінності
            message = f"📊 **Харчова цінність {item} (на 100г):**\n\n"
            message += "⚠️ Функція в розробці. Скоро буде доступна!"
        else:
            message = "❓ Не зрозумів для якого продукту показати харчову цінність"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_inventory_request(self, update: Update):
        """Обробка запитів запасів"""
        products = self.db.get_products()
        
        if products:
            message = "🛒 **Твої запаси:**\n\n"
            
            # Групуємо за категоріями
            categories = {}
            for product in products:
                category = product[5] or 'інше'
                if category not in categories:
                    categories[category] = []
                categories[category].append(product)
            
            # Емодзі для категорій
            category_emoji = {
                'м\'ясо': '🥩',
                'овочі': '🥕',
                'фрукти': '🍎',
                'молочні': '🥛',
                'крупи': '🌾',
                'інше': '📦'
            }
            
            for category, items in categories.items():
                emoji = category_emoji.get(category, '📦')
                message += f"{emoji} **{category.title()}:**\n"
                
                for product in items:
                    name, quantity, unit = product[1], product[2], product[3]
                    if quantity > 0:
                        message += f"• {name} - {quantity} {unit}\n"
                    else:
                        message += f"• {name} - ❌ закінчилось\n"
                message += "\n"
            
            # Кнопки для управління
            keyboard = [
                [InlineKeyboardButton("➕ Додати продукт", callback_data="add_product")],
                [InlineKeyboardButton("📝 Редагувати", callback_data="edit_inventory")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        else:
            message = "📦 **Твої запаси порожні**\n\nДодай продукти командою: 'додай молоко 2 літри'"
            keyboard = [
                [InlineKeyboardButton("➕ Додати перший продукт", callback_data="add_product")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_meal_plan_request(self, update: Update):
        """Обробка запитів планування харчування"""
        message = "📅 **Планування харчування**\n\n"
        message += "⚠️ Функція в розробці. Скоро буде доступна!\n\n"
        message += "Поки що можеш:\n"
        message += "• Отримати випадковий рецепт\n"
        message += "• Переглянути всі рецепти\n"
        message += "• Перевірити свої запаси"
        
        keyboard = [
            [InlineKeyboardButton("🎲 Випадковий рецепт", callback_data="random_recipe")],
            [InlineKeyboardButton("📚 Всі рецепти", callback_data="all_recipes")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_unknown_request(self, update: Update, user_message: str):
        """Обробка незрозумілих запитів"""
        suggestions = self.nlp.get_suggestions(user_message)
        
        message = "🤔 **Не зовсім зрозумів що ти хочеш**\n\n"
        message += "Можливо, ти мав на увазі:\n"
        
        keyboard = []
        for suggestion in suggestions:
            keyboard.append([InlineKeyboardButton(f"💡 {suggestion}", callback_data=f"suggest_{suggestion}")])
        
        keyboard.append([InlineKeyboardButton("❓ Показати приклади", callback_data="show_examples")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка натискань кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "random_recipe":
            recipe = self.recipe_manager.get_random_recipe()
            if recipe:
                message = "🎲 **Випадковий рецепт:**\n\n"
                message += self.recipe_manager.format_recipe_message(recipe)
                await query.edit_message_text(message, parse_mode='Markdown')
        
        elif data == "my_inventory":
            await self.handle_inventory_request_callback(query)
        
        elif data == "all_recipes":
            recipes = self.recipe_manager.find_recipes("")
            message = self.recipe_manager.format_recipe_list(recipes, "Всі доступні рецепти")
            await query.edit_message_text(message, parse_mode='Markdown')
        
        elif data == "cooking_suggestions":
            await self.send_cooking_suggestions(query)
        
        elif data.startswith("check_ingredients_"):
            recipe_id = int(data.split("_")[2])
            recipe = self.db.get_recipe_by_id(recipe_id)
            if recipe:
                recipe_dict = {
                    'id': recipe[0], 'name': recipe[1], 'description': recipe[2],
                    'instructions': recipe[3], 'prep_time': recipe[4], 'cook_time': recipe[5],
                    'servings': recipe[6], 'difficulty': recipe[7], 'category': recipe[8]
                }
                ingredients = self.db.get_recipe_ingredients(recipe_id)
                recipe_dict['ingredients'] = [
                    {'name': ing[0], 'quantity': ing[1], 'unit': ing[2]} 
                    for ing in ingredients
                ]
                message = self.recipe_manager.format_ingredient_check(recipe_dict)
                await query.edit_message_text(message, parse_mode='Markdown')
        
        elif data.startswith("cooking_tips_"):
            recipe_id = int(data.split("_")[2])
            recipe = self.db.get_recipe_by_id(recipe_id)
            if recipe:
                recipe_dict = {
                    'name': recipe[1], 'difficulty': recipe[7], 'category': recipe[8],
                    'prep_time': recipe[4], 'cook_time': recipe[5]
                }
                message = self.recipe_manager.get_cooking_tips(recipe_dict)
                await query.edit_message_text(message, parse_mode='Markdown')
        
        elif data == "show_examples":
            await self.send_examples(query)
        
        elif data.startswith("suggest_"):
            suggestion = data[8:]  # Прибираємо "suggest_"
            # Обробляємо пропозицію як звичайне повідомлення
            processed = self.nlp.process_message(suggestion)
            # Тут можна додати логіку обробки пропозиції
            await query.edit_message_text(f"Обробляю: {suggestion}")
    
    async def handle_inventory_request_callback(self, query):
        """Обробка запиту запасів через callback"""
        products = self.db.get_products()
        
        if products:
            message = "🛒 **Твої запаси:**\n\n"
            for product in products[:10]:  # Показуємо перші 10
                name, quantity, unit = product[1], product[2], product[3]
                if quantity > 0:
                    message += f"• {name} - {quantity} {unit}\n"
                else:
                    message += f"• {name} - ❌ закінчилось\n"
            
            if len(products) > 10:
                message += f"\n... та ще {len(products) - 10} продуктів"
        else:
            message = "📦 Твої запаси порожні"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def send_recipe_suggestions(self, update: Update):
        """Відправляє пропозиції рецептів"""
        keyboard = [
            [InlineKeyboardButton("🍲 Борщ", callback_data="suggest_рецепт борщу")],
            [InlineKeyboardButton("🥟 Вареники", callback_data="suggest_рецепт вареників")],
            [InlineKeyboardButton("🥗 Салат", callback_data="suggest_рецепт салату")],
            [InlineKeyboardButton("🎲 Випадковий", callback_data="random_recipe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💡 **Популярні рецепти:**", 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    
    async def send_cooking_suggestions(self, query):
        """Відправляє пропозиції що приготувати"""
        message = "🍳 **Що можна приготувати:**\n\n"
        message += "🎲 Випадковий рецепт - сюрприз для тебе\n"
        message += "🍲 Перші страви - супи, борщі\n"
        message += "🍖 Основні страви - м'ясо, гарніри\n"
        message += "🥗 Салати - легкі та свіжі\n"
        message += "🍰 Десерти - солодощі\n\n"
        message += "Просто напиши що хочеш!"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def send_examples(self, query):
        """Відправляє приклади команд"""
        message = """
💡 **Приклади команд:**

🔍 **Рецепти:**
• "рецепт борщу"
• "борщ на 8 порцій"
• "що приготувати з курки"
• "випадковий рецепт"

🛒 **Продукти:**
• "мої запаси"
• "що є вдома"
• "додай молоко 2 літри"

🔄 **Заміни:**
• "чим замінити молоко"
• "немає цукру"

📊 **Харчування:**
• "калорії борщу"
• "поживність м'яса"

Пиши природною мовою! 😊
        """
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка помилок"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.message:
            await update.message.reply_text(
                "😅 Щось пішло не так. Спробуй ще раз або напиши /start"
            )

def main():
    """Запуск бота"""
    # Отримуємо токен з змінних середовища
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        print("❌ Помилка: Не знайдено BOT_TOKEN в змінних середовища")
        return
    
    # Створюємо бота
    bot = KitchenBot()
    
    # Створюємо додаток
    application = Application.builder().token(TOKEN).build()
    
    # Додаємо обробники
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    # Додаємо обробник помилок
    application.add_error_handler(bot.error_handler)
    
    # Запускаємо бота
    print("🤖 Кухонний бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
