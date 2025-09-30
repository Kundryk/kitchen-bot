import re
from typing import Dict, List, Tuple, Optional

class NLPProcessor:
    def __init__(self):
        # Ключові слова для різних дій
        self.recipe_keywords = [
            'рецепт', 'приготувати', 'зварити', 'спекти', 'готувати', 
            'як зробити', 'як приготувати', 'покажи рецепт', 'дай рецепт',
            'хочу приготувати', 'буду готувати', 'готую'
        ]
        
        self.ingredient_keywords = [
            'інгредієнти', 'склад', 'що потрібно', 'з чого готувати',
            'які продукти', 'що входить', 'компоненти'
        ]
        
        self.substitution_keywords = [
            'замінити', 'заміна', 'чим замінити', 'альтернатива',
            'немає', 'закінчилось', 'не маю', 'замість'
        ]
        
        self.nutrition_keywords = [
            'калорії', 'калорійність', 'поживність', 'білки', 'жири', 
            'вуглеводи', 'харчова цінність', 'скільки калорій'
        ]
        
        self.inventory_keywords = [
            'що є', 'мої продукти', 'запаси', 'холодильник',
            'що в мене є', 'мої інгредієнти', 'склад'
        ]
        
        self.meal_plan_keywords = [
            'план', 'меню', 'що готувати', 'планування',
            'розклад їжі', 'план харчування'
        ]
        
        # Числа українською
        self.numbers_ua = {
            'один': 1, 'одна': 1, 'одну': 1,
            'два': 2, 'дві': 2,
            'три': 3, 'чотири': 4, "п'ять": 5, 'пять': 5,
            'шість': 6, 'сім': 7, 'вісім': 8, "дев'ять": 9, 'девять': 9,
            'десять': 10, 'одинадцять': 11, 'дванадцять': 12
        }
        
        # Одиниці вимірювання
        self.units = {
            'порцій': 'порцій', 'порції': 'порцій', 'порція': 'порцій',
            'людей': 'порцій', 'персон': 'порцій', 'осіб': 'порцій',
            'грам': 'г', 'г': 'г', 'кг': 'кг', 'кілограм': 'кг',
            'літр': 'л', 'л': 'л', 'мл': 'мл', 'мілілітр': 'мл',
            'штук': 'шт', 'шт': 'шт', 'штуки': 'шт', 'штука': 'шт',
            'ложка': 'ст.л.', 'ложки': 'ст.л.', 'ложок': 'ст.л.',
            'чайна ложка': 'ч.л.', 'чайні ложки': 'ч.л.',
            'склянка': 'склянка', 'склянки': 'склянка', 'стакан': 'склянка'
        }
        
        # Популярні страви
        self.dishes = [
            'борщ', 'вареники', 'голубці', 'котлети', 'суп', 'каша',
            'салат', 'олів\'є', 'вінегрет', 'деруни', 'сирники',
            'млинці', 'пельмені', 'піца', 'паста', 'рис', 'гречка',
            'картопля', 'м\'ясо', 'курка', 'риба', 'овочі'
        ]
    
    def process_message(self, message: str) -> Dict:
        """Основна функція обробки повідомлення"""
        message = message.lower().strip()
        
        # Визначаємо тип запиту
        intent = self._detect_intent(message)
        
        # Витягуємо параметри
        params = self._extract_parameters(message, intent)
        
        return {
            'intent': intent,
            'parameters': params,
            'original_message': message
        }
    
    def _detect_intent(self, message: str) -> str:
        """Визначає намір користувача"""
        
        # Перевіряємо рецепти
        if any(keyword in message for keyword in self.recipe_keywords):
            return 'recipe'
        
        # Перевіряємо інгредієнти
        if any(keyword in message for keyword in self.ingredient_keywords):
            return 'ingredients'
        
        # Перевіряємо заміни
        if any(keyword in message for keyword in self.substitution_keywords):
            return 'substitution'
        
        # Перевіряємо харчову цінність
        if any(keyword in message for keyword in self.nutrition_keywords):
            return 'nutrition'
        
        # Перевіряємо запаси
        if any(keyword in message for keyword in self.inventory_keywords):
            return 'inventory'
        
        # Перевіряємо план харчування
        if any(keyword in message for keyword in self.meal_plan_keywords):
            return 'meal_plan'
        
        # Якщо згадується страва без ключових слів - припускаємо рецепт
        if any(dish in message for dish in self.dishes):
            return 'recipe'
        
        return 'unknown'
    
    def _extract_parameters(self, message: str, intent: str) -> Dict:
        """Витягує параметри з повідомлення"""
        params = {}
        
        if intent == 'recipe':
            params.update(self._extract_recipe_params(message))
        elif intent == 'substitution':
            params.update(self._extract_substitution_params(message))
        elif intent == 'nutrition':
            params.update(self._extract_nutrition_params(message))
        
        return params
    
    def _extract_recipe_params(self, message: str) -> Dict:
        """Витягує параметри для рецептів"""
        params = {}
        
        # Шукаємо назву страви
        dish_name = self._find_dish_name(message)
        if dish_name:
            params['dish'] = dish_name
        
        # Шукаємо кількість порцій
        servings = self._extract_servings(message)
        if servings:
            params['servings'] = servings
        
        # Шукаємо складність
        if 'легко' in message or 'простий' in message:
            params['difficulty'] = 'легко'
        elif 'складно' in message or 'важкий' in message:
            params['difficulty'] = 'складно'
        elif 'середньо' in message:
            params['difficulty'] = 'середньо'
        
        # Шукаємо категорію
        if 'суп' in message or 'борщ' in message:
            params['category'] = 'перші страви'
        elif 'салат' in message:
            params['category'] = 'салати'
        elif 'десерт' in message or 'солодке' in message:
            params['category'] = 'десерти'
        
        return params
    
    def _extract_substitution_params(self, message: str) -> Dict:
        """Витягує параметри для замін"""
        params = {}
        
        # Шукаємо що замінити
        substitution_patterns = [
            r'замінити\s+([а-яё]+)',
            r'чим замінити\s+([а-яё]+)',
            r'немає\s+([а-яё]+)',
            r'не маю\s+([а-яё]+)',
            r'замість\s+([а-яё]+)'
        ]
        
        for pattern in substitution_patterns:
            match = re.search(pattern, message)
            if match:
                params['ingredient'] = match.group(1)
                break
        
        return params
    
    def _extract_nutrition_params(self, message: str) -> Dict:
        """Витягує параметри для харчової цінності"""
        params = {}
        
        # Шукаємо назву продукту
        dish_name = self._find_dish_name(message)
        if dish_name:
            params['item'] = dish_name
        
        return params
    
    def _find_dish_name(self, message: str) -> Optional[str]:
        """Знаходить назву страви в повідомленні"""
        # Спочатку шукаємо точні збіги
        for dish in self.dishes:
            if dish in message:
                return dish
        
        # Потім шукаємо часткові збіги
        words = message.split()
        for word in words:
            for dish in self.dishes:
                if word in dish or dish in word:
                    return dish
        
        return None
    
    def _extract_servings(self, message: str) -> Optional[int]:
        """Витягує кількість порцій"""
        # Шукаємо числа
        numbers = re.findall(r'\d+', message)
        if numbers:
            # Беремо перше число
            num = int(numbers[0])
            if 1 <= num <= 20:  # Розумні межі
                return num
        
        # Шукаємо числа українською
        for ua_num, value in self.numbers_ua.items():
            if ua_num in message:
                return value
        
        return None
    
    def generate_response_template(self, intent: str, params: Dict) -> str:
        """Генерує шаблон відповіді"""
        if intent == 'recipe':
            dish = params.get('dish', 'страву')
            servings = params.get('servings', '')
            if servings:
                return f"Шукаю рецепт {dish} на {servings} порцій..."
            else:
                return f"Шукаю рецепт {dish}..."
        
        elif intent == 'substitution':
            ingredient = params.get('ingredient', 'інгредієнт')
            return f"Шукаю чим можна замінити {ingredient}..."
        
        elif intent == 'nutrition':
            item = params.get('item', 'продукт')
            return f"Шукаю харчову цінність для {item}..."
        
        elif intent == 'inventory':
            return "Показую твої запаси..."
        
        elif intent == 'meal_plan':
            return "Готую план харчування..."
        
        else:
            return "Не зовсім зрозумів, що ти хочеш. Спробуй сказати інакше."
    
    def get_suggestions(self, message: str) -> List[str]:
        """Дає пропозиції якщо не зрозумів запит"""
        suggestions = []
        
        if any(dish in message for dish in self.dishes):
            dish = next(dish for dish in self.dishes if dish in message)
            suggestions.extend([
                f"Рецепт {dish}",
                f"Інгредієнти для {dish}",
                f"Калорійність {dish}"
            ])
        
        if not suggestions:
            suggestions = [
                "Покажи рецепт борщу",
                "Що можна приготувати з курки?",
                "Чим замінити молоко?",
                "Мої запаси продуктів",
                "План харчування на тиждень"
            ]
        
        return suggestions[:3]  # Максимум 3 пропозиції
