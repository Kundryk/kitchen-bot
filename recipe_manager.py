from database import Database
from typing import List, Dict, Optional, Tuple
import random

class RecipeManager:
    def __init__(self, db: Database):
        self.db = db
    
    def find_recipes(self, query: str, servings: Optional[int] = None) -> List[Dict]:
        """Знаходить рецепти за запитом"""
        recipes = self.db.get_recipes(query)
        
        result = []
        for recipe in recipes:
            recipe_dict = {
                'id': recipe[0],
                'name': recipe[1],
                'description': recipe[2],
                'instructions': recipe[3],
                'prep_time': recipe[4],
                'cook_time': recipe[5],
                'servings': recipe[6],
                'difficulty': recipe[7],
                'category': recipe[8],
                'created_at': recipe[9]
            }
            
            # Додаємо інгредієнти
            ingredients = self.db.get_recipe_ingredients(recipe[0])
            recipe_dict['ingredients'] = []
            
            for ingredient in ingredients:
                ing_dict = {
                    'name': ingredient[0],
                    'quantity': ingredient[1],
                    'unit': ingredient[2]
                }
                
                # Якщо потрібно перерахувати на іншу кількість порцій
                if servings and servings != recipe[6]:
                    multiplier = servings / recipe[6]
                    ing_dict['quantity'] = round(ingredient[1] * multiplier, 2)
                
                recipe_dict['ingredients'].append(ing_dict)
            
            # Оновлюємо кількість порцій якщо потрібно
            if servings:
                recipe_dict['servings'] = servings
                # Перерахуємо час приготування (може трохи збільшитись)
                if servings > recipe[6]:
                    multiplier = servings / recipe[6]
                    recipe_dict['cook_time'] = int(recipe[5] * (1 + (multiplier - 1) * 0.3))
            
            result.append(recipe_dict)
        
        return result
    
    def get_recipe_by_name(self, name: str, servings: Optional[int] = None) -> Optional[Dict]:
        """Отримує рецепт за назвою"""
        recipes = self.find_recipes(name, servings)
        
        # Шукаємо точний збіг
        for recipe in recipes:
            if recipe['name'].lower() == name.lower():
                return recipe
        
        # Якщо точного збігу немає, повертаємо перший результат
        return recipes[0] if recipes else None
    
    def get_random_recipe(self, category: Optional[str] = None, difficulty: Optional[str] = None) -> Optional[Dict]:
        """Повертає випадковий рецепт"""
        all_recipes = self.db.get_recipes()
        
        # Фільтруємо за категорією та складністю
        filtered_recipes = []
        for recipe in all_recipes:
            if category and recipe[8] != category:
                continue
            if difficulty and recipe[7] != difficulty:
                continue
            filtered_recipes.append(recipe)
        
        if not filtered_recipes:
            return None
        
        # Вибираємо випадковий
        random_recipe = random.choice(filtered_recipes)
        
        # Конвертуємо в словник
        recipe_dict = {
            'id': random_recipe[0],
            'name': random_recipe[1],
            'description': random_recipe[2],
            'instructions': random_recipe[3],
            'prep_time': random_recipe[4],
            'cook_time': random_recipe[5],
            'servings': random_recipe[6],
            'difficulty': random_recipe[7],
            'category': random_recipe[8],
            'created_at': random_recipe[9]
        }
        
        # Додаємо інгредієнти
        ingredients = self.db.get_recipe_ingredients(random_recipe[0])
        recipe_dict['ingredients'] = []
        
        for ingredient in ingredients:
            recipe_dict['ingredients'].append({
                'name': ingredient[0],
                'quantity': ingredient[1],
                'unit': ingredient[2]
            })
        
        return recipe_dict
    
    def format_recipe_message(self, recipe: Dict) -> str:
        """Форматує рецепт для відправки користувачу"""
        if not recipe:
            return "❌ Рецепт не знайдено"
        
        # Заголовок
        message = f"🍽️ **{recipe['name']}**\n\n"
        
        # Опис
        if recipe.get('description'):
            message += f"📝 {recipe['description']}\n\n"
        
        # Інформація про рецепт
        info_parts = []
        if recipe.get('servings'):
            info_parts.append(f"👥 {recipe['servings']} порцій")
        if recipe.get('prep_time'):
            info_parts.append(f"⏱️ Підготовка: {recipe['prep_time']} хв")
        if recipe.get('cook_time'):
            info_parts.append(f"🔥 Готування: {recipe['cook_time']} хв")
        if recipe.get('difficulty'):
            difficulty_emoji = {'легко': '🟢', 'середньо': '🟡', 'складно': '🔴'}
            emoji = difficulty_emoji.get(recipe['difficulty'], '⚪')
            info_parts.append(f"{emoji} {recipe['difficulty'].title()}")
        
        if info_parts:
            message += " | ".join(info_parts) + "\n\n"
        
        # Інгредієнти
        if recipe.get('ingredients'):
            message += "🛒 **Інгредієнти:**\n"
            for ingredient in recipe['ingredients']:
                quantity = ingredient['quantity']
                # Форматуємо кількість
                if quantity == int(quantity):
                    quantity = int(quantity)
                message += f"• {ingredient['name']} - {quantity} {ingredient['unit']}\n"
            message += "\n"
        
        # Інструкції
        if recipe.get('instructions'):
            message += "👨‍🍳 **Приготування:**\n"
            instructions = recipe['instructions'].strip()
            
            # Якщо інструкції вже пронумеровані
            if any(line.strip().startswith(('1.', '1)', '1 ')) for line in instructions.split('\n')):
                message += instructions
            else:
                # Розбиваємо на кроки
                steps = [step.strip() for step in instructions.split('\n') if step.strip()]
                for i, step in enumerate(steps, 1):
                    message += f"{i}. {step}\n"
        
        return message
    
    def format_recipe_list(self, recipes: List[Dict], title: str = "Знайдені рецепти") -> str:
        """Форматує список рецептів"""
        if not recipes:
            return "❌ Рецепти не знайдено"
        
        message = f"📚 **{title}**\n\n"
        
        for i, recipe in enumerate(recipes[:5], 1):  # Максимум 5 рецептів
            # Емодзі для категорій
            category_emoji = {
                'перші страви': '🍲',
                'основні страви': '🍖',
                'салати': '🥗',
                'десерти': '🍰',
                'напої': '🥤'
            }
            emoji = category_emoji.get(recipe.get('category', ''), '🍽️')
            
            message += f"{i}. {emoji} **{recipe['name']}**\n"
            
            if recipe.get('description'):
                message += f"   {recipe['description'][:50]}{'...' if len(recipe['description']) > 50 else ''}\n"
            
            # Коротка інформація
            info = []
            if recipe.get('servings'):
                info.append(f"{recipe['servings']} порцій")
            if recipe.get('cook_time'):
                total_time = recipe.get('prep_time', 0) + recipe['cook_time']
                info.append(f"{total_time} хв")
            if recipe.get('difficulty'):
                info.append(recipe['difficulty'])
            
            if info:
                message += f"   📋 {' • '.join(info)}\n"
            
            message += "\n"
        
        if len(recipes) > 5:
            message += f"... та ще {len(recipes) - 5} рецептів\n"
        
        message += "\n💡 Напиши назву рецепту щоб отримати повну інформацію"
        
        return message
    
    def check_available_ingredients(self, recipe: Dict) -> Dict:
        """Перевіряє які інгредієнти є в наявності"""
        if not recipe.get('ingredients'):
            return {'available': [], 'missing': [], 'substitutions': []}
        
        available_products = self.db.get_products()
        product_names = [product[1].lower() for product in available_products]
        
        available = []
        missing = []
        substitutions = []
        
        for ingredient in recipe['ingredients']:
            ingredient_name = ingredient['name'].lower()
            
            if ingredient_name in product_names:
                available.append(ingredient)
            else:
                missing.append(ingredient)
                # Шукаємо заміни
                subs = self.db.get_substitutions(ingredient_name)
                if subs:
                    for sub in subs:
                        substitutions.append({
                            'original': ingredient['name'],
                            'substitute': sub[0],
                            'ratio': sub[1],
                            'notes': sub[2]
                        })
        
        return {
            'available': available,
            'missing': missing,
            'substitutions': substitutions
        }
    
    def format_ingredient_check(self, recipe: Dict) -> str:
        """Форматує перевірку інгредієнтів"""
        check_result = self.check_available_ingredients(recipe)
        
        message = f"🔍 **Перевірка інгредієнтів для "{recipe['name']}"**\n\n"
        
        # Доступні інгредієнти
        if check_result['available']:
            message += "✅ **Є в наявності:**\n"
            for ingredient in check_result['available']:
                message += f"• {ingredient['name']} - {ingredient['quantity']} {ingredient['unit']}\n"
            message += "\n"
        
        # Відсутні інгредієнти
        if check_result['missing']:
            message += "❌ **Потрібно купити:**\n"
            for ingredient in check_result['missing']:
                message += f"• {ingredient['name']} - {ingredient['quantity']} {ingredient['unit']}\n"
            message += "\n"
        
        # Можливі заміни
        if check_result['substitutions']:
            message += "🔄 **Можливі заміни:**\n"
            for sub in check_result['substitutions']:
                message += f"• {sub['original']} → {sub['substitute']}"
                if sub['ratio'] != 1.0:
                    message += f" (коефіцієнт {sub['ratio']})"
                if sub['notes']:
                    message += f"\n  💡 {sub['notes']}"
                message += "\n"
            message += "\n"
        
        # Підсумок
        total_ingredients = len(recipe.get('ingredients', []))
        available_count = len(check_result['available'])
        
        if available_count == total_ingredients:
            message += "🎉 **Усі інгредієнти є! Можна готувати!**"
        elif available_count > total_ingredients // 2:
            message += f"👍 **Більшість інгредієнтів є ({available_count}/{total_ingredients})**"
        else:
            message += f"🛒 **Потрібно докупити багато інгредієнтів ({total_ingredients - available_count}/{total_ingredients})**"
        
        return message
    
    def get_cooking_tips(self, recipe: Dict) -> str:
        """Повертає поради для приготування"""
        tips = []
        
        # Поради за складністю
        if recipe.get('difficulty') == 'складно':
            tips.append("⚠️ Складний рецепт - читай інструкції уважно")
            tips.append("📖 Підготуй всі інгредієнти заздалегідь")
        
        # Поради за часом
        total_time = recipe.get('prep_time', 0) + recipe.get('cook_time', 0)
        if total_time > 120:
            tips.append("⏰ Довгий процес приготування - заплануй час")
        
        # Поради за категорією
        category = recipe.get('category', '')
        if 'суп' in category or 'перші страви' in category:
            tips.append("🍲 Суп краще настоюється - дай постояти 10-15 хвилин")
        elif 'салат' in category:
            tips.append("🥗 Заправляй салат безпосередньо перед подачею")
        elif 'м\'ясо' in recipe.get('name', '').lower():
            tips.append("🥩 Дай м'ясу відпочити 5 хвилин після готування")
        
        # Загальні поради
        tips.extend([
            "🧂 Пробуй на сіль під час готування",
            "🔥 Не залишай плиту без нагляду",
            "🧽 Мий посуд по ходу приготування"
        ])
        
        # Повертаємо випадкові 3-4 поради
        selected_tips = random.sample(tips, min(4, len(tips)))
        
        message = "💡 **Поради для приготування:**\n"
        for tip in selected_tips:
            message += f"{tip}\n"
        
        return message
