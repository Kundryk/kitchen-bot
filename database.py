import sqlite3
import os
from datetime import datetime

class Database:
    def __init__(self, db_name="kitchen_bot.db"):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблиця продуктів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                quantity REAL DEFAULT 0,
                unit TEXT DEFAULT 'шт',
                expiry_date TEXT,
                category TEXT DEFAULT 'інше',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблиця рецептів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                instructions TEXT NOT NULL,
                prep_time INTEGER DEFAULT 0,
                cook_time INTEGER DEFAULT 0,
                servings INTEGER DEFAULT 1,
                difficulty TEXT DEFAULT 'легко',
                category TEXT DEFAULT 'основні страви',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблиця інгредієнтів для рецептів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                ingredient_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id)
            )
        ''')
        
        # Таблиця замін інгредієнтів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS substitutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_ingredient TEXT NOT NULL,
                substitute TEXT NOT NULL,
                ratio REAL DEFAULT 1.0,
                notes TEXT
            )
        ''')
        
        # Таблиця планів харчування
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                recipe_id INTEGER,
                servings INTEGER DEFAULT 1,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id)
            )
        ''')
        
        # Таблиця нагадувань
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                reminder_date TEXT NOT NULL,
                is_completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблиця харчової цінності
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nutrition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_name TEXT NOT NULL UNIQUE,
                calories_per_100g REAL DEFAULT 0,
                protein_per_100g REAL DEFAULT 0,
                carbs_per_100g REAL DEFAULT 0,
                fat_per_100g REAL DEFAULT 0,
                fiber_per_100g REAL DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Додаємо базові дані
        self.add_sample_data()
    
    def add_sample_data(self):
        """Додає базові рецепти та дані"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Перевіряємо чи є вже рецепти
        cursor.execute("SELECT COUNT(*) FROM recipes")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return
        
        # Додаємо базові рецепти
        recipes = [
            ("Борщ", "Традиційний український борщ", 
             "1. Відварити м'ясо\n2. Додати буряк та капусту\n3. Приправити часником та кропом", 
             30, 120, 6, "середньо", "перші страви"),
            ("Вареники з картоплею", "Класичні українські вареники", 
             "1. Зробити тісто\n2. Приготувати начинку\n3. Ліпити та варити", 
             60, 20, 4, "складно", "основні страви"),
            ("Салат Олів'є", "Новорічний салат", 
             "1. Відварити овочі\n2. Нарізати все кубиками\n3. Заправити майонезом", 
             45, 0, 8, "легко", "салати")
        ]
        
        for recipe in recipes:
            cursor.execute('''
                INSERT INTO recipes (name, description, instructions, prep_time, cook_time, servings, difficulty, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', recipe)
        
        # Додаємо інгредієнти для борщу
        cursor.execute("SELECT id FROM recipes WHERE name = 'Борщ'")
        borsch_id = cursor.fetchone()[0]
        
        borsch_ingredients = [
            (borsch_id, "м'ясо", 500, "г"),
            (borsch_id, "буряк", 2, "шт"),
            (borsch_id, "капуста", 300, "г"),
            (borsch_id, "морква", 1, "шт"),
            (borsch_id, "цибуля", 1, "шт"),
            (borsch_id, "часник", 3, "зубчики"),
            (borsch_id, "томатна паста", 2, "ст.л.")
        ]
        
        for ingredient in borsch_ingredients:
            cursor.execute('''
                INSERT INTO recipe_ingredients (recipe_id, ingredient_name, quantity, unit)
                VALUES (?, ?, ?, ?)
            ''', ingredient)
        
        # Додаємо базові заміни
        substitutions = [
            ("молоко", "рослинне молоко", 1.0, "Для веганських страв"),
            ("масло", "олія", 0.8, "Менше калорій"),
            ("цукор", "мед", 0.7, "Натуральний підсолоджувач"),
            ("борошно", "вівсяне борошно", 1.0, "Без глютену")
        ]
        
        for sub in substitutions:
            cursor.execute('''
                INSERT INTO substitutions (original_ingredient, substitute, ratio, notes)
                VALUES (?, ?, ?, ?)
            ''', sub)
        
        # Додаємо базову харчову цінність
        nutrition_data = [
            ("м'ясо", 250, 26, 0, 15, 0),
            ("буряк", 43, 1.6, 10, 0.2, 2.8),
            ("капуста", 25, 1.3, 6, 0.1, 2.5),
            ("морква", 41, 0.9, 10, 0.2, 2.8),
            ("цибуля", 40, 1.1, 9, 0.1, 1.7)
        ]
        
        for nutrition in nutrition_data:
            cursor.execute('''
                INSERT INTO nutrition (ingredient_name, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g, fiber_per_100g)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', nutrition)
        
        conn.commit()
        conn.close()
    
    # Методи для роботи з продуктами
    def add_product(self, name, quantity=0, unit='шт', expiry_date=None, category='інше'):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO products (name, quantity, unit, expiry_date, category)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, quantity, unit, expiry_date, category))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_products(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products ORDER BY name')
        products = cursor.fetchall()
        conn.close()
        return products
    
    def update_product_quantity(self, name, quantity):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE products SET quantity = ? WHERE name = ?', (quantity, name))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    
    # Методи для роботи з рецептами
    def get_recipes(self, search_term=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if search_term:
            cursor.execute('''
                SELECT * FROM recipes 
                WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
                ORDER BY name
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        else:
            cursor.execute('SELECT * FROM recipes ORDER BY name')
        
        recipes = cursor.fetchall()
        conn.close()
        return recipes
    
    def get_recipe_by_id(self, recipe_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,))
        recipe = cursor.fetchone()
        conn.close()
        return recipe
    
    def get_recipe_ingredients(self, recipe_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ingredient_name, quantity, unit 
            FROM recipe_ingredients 
            WHERE recipe_id = ?
        ''', (recipe_id,))
        ingredients = cursor.fetchall()
        conn.close()
        return ingredients
    
    def get_substitutions(self, ingredient):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT substitute, ratio, notes 
            FROM substitutions 
            WHERE original_ingredient LIKE ?
        ''', (f'%{ingredient}%',))
        substitutions = cursor.fetchall()
        conn.close()
        return substitutions
