from database import KitchenDatabase
from datetime import datetime, timedelta
import re

db = KitchenDatabase()

# Категорії продуктів
CATEGORIES = {
    "морозилка": "[МОРОЗИЛКА]",
    "готова_їжа": "[ГОТОВА_ЇЖА]", 
    "морозилка_готова": "[МОРОЗИЛКА_ГОТОВА]"
}

def normalize_quantity_and_unit(quantity, unit):
    """Приводить кількість і одиниці до стандартного вигляду"""
    unit = unit.lower().strip()
    quantity = float(quantity)
    
    # Нормалізація одиниць
    if unit in ["г", "гр", "грам", "грамів"]:
        return quantity, "г"
    elif unit in ["кг", "кілограм", "кілограмів"]:
        return quantity * 1000, "г"  # переводимо в грами
    elif unit in ["мл", "мілілітр", "мілілітрів"]:
        return quantity, "мл"
    elif unit in ["л", "літр", "літрів"]:
        return quantity * 1000, "мл"  # переводимо в мілілітри
    elif unit in ["шт", "штук", "штука", "штуки"]:
        return quantity, "шт"
    else:
        return quantity, unit

def detect_category(product_name):
    """Визначає категорію продукту"""
    name_lower = product_name.lower()
    
    # Готова їжа
    ready_food = ["сирники", "котлети", "борщ", "суп", "каша", "макарони", "рис", "гречка"]
    if any(food in name_lower for food in ready_food):
        return CATEGORIES["готова_їжа"]
    
    # Заморожені продукти
    frozen = ["заморожен", "морожен", "лід", "м'ясо", "риба", "креветки"]
    if any(frozen_item in name_lower for frozen_item in frozen):
        return CATEGORIES["морозилка"]
    
    return ""  # без категорії

def _normalize_name(name: str) -> str:
    """Нормалізує назву продукту для пошуку"""
    if not name:
        return ""
    s = name.strip().lower()
    # Прибираємо префікси категорій
    for cat in CATEGORIES.values():
        s = s.replace(cat.lower(), "").strip()
    return " ".join(s.split())

def add_product(user_id, product_name, quantity, unit, expiry_date=None, category=None):
    """Додає продукт до кухні"""
    ws = db.get_products_sheet()
    data = ws.get_all_records()
    
    # Нормалізуємо кількість і одиниці
    norm_qty, norm_unit = normalize_quantity_and_unit(quantity, unit)
    
    # Автоматично визначаємо категорію
    if not category:
        category = detect_category(product_name)
    
    # Додаємо категорію до назви
    full_name = f"{category} {product_name}".strip()
    target_name_norm = _normalize_name(full_name)
    
    # Шукаємо існуючий продукт
    for idx, row in enumerate(data, start=2):
        if str(row.get("user_id", "")) != str(user_id):
            continue
            
        row_name = row.get("product_name", "")
        if _normalize_name(row_name) == target_name_norm:
            # Оновлюємо кількість
            current_qty = float(str(row.get("quantity", "0")).replace(",", "."))
            new_qty = current_qty + norm_qty
            ws.update_cell(idx, 3, new_qty)  # колонка quantity
            db.log_action(user_id, full_name, norm_qty, norm_unit, "add")
            return f"✅ Додав {quantity}{unit} {product_name}. Тепер всього: {new_qty}{norm_unit}"
    
    # Створюємо новий продукт
    if not expiry_date:
        expiry_date = ""
    
    added_date = datetime.now().strftime("%Y-%m-%d")
    new_row = [str(user_id), full_name, norm_qty, norm_unit, expiry_date, added_date]
    ws.append_row(new_row)
    db.log_action(user_id, full_name, norm_qty, norm_unit, "add")
    return f"✅ Додав новий продукт: {quantity}{unit} {product_name}"

def remove_product(user_id, product_name, quantity, unit):
    """Віднімає продукт з кухні"""
    ws = db.get_products_sheet()
    data = ws.get_all_records()
    
    # Нормалізуємо кількість і одиниці
    norm_qty, norm_unit = normalize_quantity_and_unit(quantity, unit)
    target_name_norm = _normalize_name(product_name)
    
    # Шукаємо продукт
    for idx, row in enumerate(data, start=2):
        if str(row.get("user_id", "")) != str(user_id):
            continue
            
        row_name = row.get("product_name", "")
        if _normalize_name(row_name) == target_name_norm:
            current_qty = float(str(row.get("quantity", "0")).replace(",", "."))
            new_qty = current_qty - norm_qty
            
            if new_qty > 0:
                ws.update_cell(idx, 3, new_qty)
                db.log_action(user_id, row_name, -norm_qty, norm_unit, "remove")
                return f"➖ Відняв {quantity}{unit} {product_name}. Залишок: {new_qty}{norm_unit}"
            else:
                ws.delete_rows(idx)
                db.log_action(user_id, row_name, -current_qty, norm_unit, "remove")
                return f"❌ {product_name} закінчився, видалив із списку"
    
    return f"❌ Не знайшов {product_name} у списку"

def list_products(user_id, category=None):
    """Показує список продуктів"""
    ws = db.get_products_sheet()
    data = ws.get_all_records()
    
    result = []
    for row in data:
        if str(row.get("user_id", "")) != str(user_id):
            continue
            
        # Фільтр по категорії
        if category:
            product_name = row.get("product_name", "")
            if category.lower() not in product_name.lower():
                continue
        
        result.append({
            "user_id": row.get("user_id", ""),
            "product_name": row.get("product_name", ""),
            "quantity": row.get("quantity", ""),
            "unit": row.get("unit", ""),
            "expiry_date": row.get("expiry_date", ""),
            "added_date": row.get("added_date", "")
        })
    
    return result

def find_product(user_id, search_name):
    """Шукає продукт за назвою"""
    products = list_products(user_id)
    search_norm = _normalize_name(search_name)
    
    found = []
    for product in products:
        product_norm = _normalize_name(product["product_name"])
        if search_norm in product_norm or product_norm in search_norm:
            found.append(product)
    
    return found

def get_expiring_products(user_id, days=3):
    """Повертає продукти, що скоро псуються"""
    products = list_products(user_id)
    expiring = []
    
    today = datetime.now().date()
    threshold = today + timedelta(days=days)
    
    for product in products:
        expiry_str = product.get("expiry_date", "")
        if not expiry_str:
            continue
            
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            if expiry_date <= threshold:
                days_left = (expiry_date - today).days
                product["days_left"] = days_left
                expiring.append(product)
        except ValueError:
            continue
    
    return sorted(expiring, key=lambda x: x["days_left"])

def add_to_shopping_list(user_id, item, quantity, unit, note=""):
    """Додає товар до списку покупок"""
    ws = db.get_shopping_sheet()
    added_date = datetime.now().strftime("%Y-%m-%d")
    norm_qty, norm_unit = normalize_quantity_and_unit(quantity, unit)
    
    new_row = [str(user_id), item, norm_qty, norm_unit, note, added_date]
    ws.append_row(new_row)
    return f"✅ Додав до списку покупок: {quantity}{unit} {item}"

def get_shopping_list(user_id):
    """Повертає список покупок"""
    ws = db.get_shopping_sheet()
    data = ws.get_all_records()
    
    result = []
    for row in data:
        if str(row.get("user_id", "")) == str(user_id):
            result.append(row)
    
    return result

def remove_from_shopping_list(user_id, item):
    """Видаляє товар зі списку покупок"""
    ws = db.get_shopping_sheet()
    data = ws.get_all_records()
    
    for idx, row in enumerate(data, start=2):
        if str(row.get("user_id", "")) == str(user_id) and item.lower() in row.get("item", "").lower():
            ws.delete_rows(idx)
            return f"✅ Видалив {item} зі списку покупок"
    
    return f"❌ Не знайшов {item} у списку покупок"

def get_consumption_stats(user_id, days=7):
    """Статистика споживання за останні дні"""
    logs_ws = db.get_logs_sheet()
    data = logs_ws.get_all_records()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    stats = {"consumed": [], "added": []}
    
    for row in data:
        if str(row.get("user_id", "")) != str(user_id):
            continue
            
        try:
            log_date = datetime.strptime(row.get("timestamp", ""), "%Y-%m-%d %H:%M:%S")
            if log_date >= cutoff_date:
                action = row.get("action", "")
                product = row.get("product_name", "")
                qty = row.get("delta_qty", 0)
                
                if action == "remove":
                    stats["consumed"].append({"product": product, "quantity": abs(float(qty))})
                elif action == "add":
                    stats["added"].append({"product": product, "quantity": float(qty)})
        except ValueError:
            continue
    
    return stats
