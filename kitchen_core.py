from database import KitchenDatabase
from datetime import datetime

db = KitchenDatabase()

def add_product(user_id, product_name, quantity, unit, expiry_date=None, category=None):
    """Додає продукт або збільшує кількість вже існуючого"""
    products = db.get_products_sheet()
    data = products.get_all_records()

    # спробуємо знайти продукт
    for idx, row in enumerate(data, start=2):  # start=2 бо перший рядок — заголовки
        if str(row["user_id"]) == str(user_id) and row["product_name"].lower() == product_name.lower():
            new_qty = float(row["quantity"]) + quantity
            products.update_cell(idx, 3, new_qty)  # колонка 3 = quantity
            db.log_action(user_id, product_name, quantity, unit, "add")
            return f"✅ Додав {quantity}{unit} {product_name}. Тепер всього: {new_qty}{unit}"

    # Якщо продукту немає -> створимо новий рядок
    if not expiry_date:
        expiry_date = ""
    if not category:
        category = ""

    added_date = datetime.now().strftime("%Y-%m-%d")
    products.append_row([user_id, product_name, quantity, unit, expiry_date, added_date])
    db.log_action(user_id, product_name, quantity, unit, "add")
    return f"✅ Додав новий продукт: {quantity}{unit} {product_name}"

def remove_product(user_id, product_name, quantity, unit):
    """Зменшує кількість продукту або видаляє повністю"""
    products = db.get_products_sheet()
    data = products.get_all_records()

    for idx, row in enumerate(data, start=2):
        if str(row["user_id"]) == str(user_id) and row["product_name"].lower() == product_name.lower():
            current_qty = float(row["quantity"])
            new_qty = current_qty - quantity

            if new_qty > 0:
                products.update_cell(idx, 3, new_qty)
                db.log_action(user_id, product_name, -quantity, unit, "remove")
                return f"➖ Відняв {quantity}{unit} {product_name}. Залишок: {new_qty}{row['unit']}"
            else:
                products.delete_rows(idx)
                db.log_action(user_id, product_name, -current_qty, unit, "remove")
                return f"❌ {product_name} закінчився, видалив із списку"

    return f"❌ Не знайшов {product_name} у списку"

def list_products(user_id, category=None):
    """Повертає список всіх продуктів користувача"""
    products = db.get_products_sheet()
    data = products.get_all_records()

    result = []
    for row in data:
        if str(row["user_id"]) == str(user_id):
            if category and category.lower() not in row["product_name"].lower():
                continue
            result.append(row)
    return result
