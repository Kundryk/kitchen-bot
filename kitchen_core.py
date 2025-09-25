from database import KitchenDatabase
from datetime import datetime

db = KitchenDatabase()

PREFIXES = ["[МОРОЗИЛКА-ГОТОВЕ]", "[МОРОЗИЛКА_ГОТОВА]", "[ГОТОВА_ЇЖА]", "[МОРОЗИЛКА]", "[МОРОЗИЛКА_ГОТОВА]"]

def _norm_name(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    for p in PREFIXES:
        s = s.replace(p.lower(), "").strip()
    # Прибрати подвійні пробіли
    return " ".join(s.split())

def _build_header_map(worksheet):
    headers = worksheet.row_values(1)
    hmap = {h.strip().lower(): i+1 for i, h in enumerate(headers)}  # 1-based index
    return headers, hmap

def _get_row_val(row_dict: dict, keys: list[str], default=None):
    # шукає перший доступний ключ із варіантів
    for k in keys:
        if k in row_dict and row_dict[k] not in (None, ""):
            return row_dict[k]
    return default

def add_product(user_id, product_name, quantity, unit, expiry_date=None, category=None):
    ws = db.get_products_sheet()
    data = ws.get_all_records()
    headers, hmap = _build_header_map(ws)

    # Визначаємо ключі під різні схеми
    user_key = "user_id"
    name_keys = ["product_name", "name"]
    qty_key = "quantity"
    unit_key = "unit"
    exp_key = "expiry_date"
    added_key = "added_date"

    # Знайдемо індекси колонок
    qty_col = hmap.get(qty_key, 3)  # fallback на 3 як у твоїй схемі
    unit_col = hmap.get(unit_key, 4)
    exp_col = hmap.get(exp_key, 5)
    # name/product_name колонки використовуються тільки при створенні рядка

    target_name_norm = _norm_name(product_name)

    # спробуємо знайти існуючий рядок
    for idx, row in enumerate(data, start=2):
        row_user = str(_get_row_val(row, [user_key], ""))
        row_name = _get_row_val(row, name_keys, "")
        if not row_name:
            continue

        if row_user == str(user_id) and _norm_name(row_name) == target_name_norm:
            # оновлюємо кількість
            try:
                current_qty = float(str(row.get(qty_key, "0")).replace(",", "."))
            except:
                current_qty = 0.0
            new_qty = current_qty + float(quantity)
            ws.update_cell(idx, qty_col, new_qty)
            db.log_action(user_id, row_name, quantity, unit, "add")
            return f"✅ Додав {quantity}{unit} {product_name}. Тепер всього: {new_qty}{unit}"

    # Якщо продукту немає -> створимо новий рядок
    if not expiry_date:
        expiry_date = ""
    if not category:
        category = ""

    added_date = datetime.now().strftime("%Y-%m-%d")

    # Підготуємо рядок у правильному порядку колонок
    row_template = {
        "user_id": str(user_id),
        "product_name": product_name,
        "name": product_name,  # продублюємо для сумісності
        "quantity": quantity,
        "unit": unit,
        "expiry_date": expiry_date,
        "added_date": added_date,
    }

    # Зберемо список значень відповідно до існуючих заголовків
    new_row = []
    for h in headers:
        key = h.strip()
        lk = key.lower()
        new_row.append(row_template.get(lk, row_template.get(key, "")))

    ws.append_row(new_row)
    db.log_action(user_id, product_name, quantity, unit, "add")
    return f"✅ Додав новий продукт: {quantity}{unit} {product_name}"

def remove_product(user_id, product_name, quantity, unit):
    ws = db.get_products_sheet()
    data = ws.get_all_records()
    headers, hmap = _build_header_map(ws)

    user_key = "user_id"
    name_keys = ["product_name", "name"]
    qty_key = "quantity"
    unit_key = "unit"

    qty_col = hmap.get(qty_key, 3)

    target_name_norm = _norm_name(product_name)

    # Пошук точного збігу по нормалізованій назві
    for idx, row in enumerate(data, start=2):
        row_user = str(_get_row_val(row, [user_key], ""))
        row_name = _get_row_val(row, name_keys, "")
        if row_user != str(user_id) or not row_name:
            continue

        if _norm_name(row_name) == target_name_norm:
            # одиниці не завжди збігаються, але ми просто віднімаємо кількість
            try:
                current_qty = float(str(row.get(qty_key, "0")).replace(",", "."))
            except:
                current_qty = 0.0

            new_qty = current_qty - float(quantity)
            if new_qty > 0:
                ws.update_cell(idx, qty_col, new_qty)
                db.log_action(user_id, row_name, -abs(quantity), unit, "remove")
                return f"➖ Відняв {quantity}{unit} {product_name}. Залишок: {new_qty}{row.get(unit_key, unit)}"
            else:
                ws.delete_rows(idx)
                db.log_action(user_id, row_name, -abs(current_qty), unit, "remove")
                return f"❌ {product_name} закінчився, видалив із списку"

    return f"❌ Не знайшов {product_name} у списку"

def list_products(user_id, category=None):
    ws = db.get_products_sheet()
    data = ws.get_all_records()

    user_key = "user_id"
    name_keys = ["product_name", "name"]

    result = []
    for row in data:
        if str(_get_row_val(row, [user_key], "")) != str(user_id):
            continue

        # Повертаємо уніфіковане представлення
        unified = {
            "user_id": _get_row_val(row, [user_key], ""),
            "product_name": _get_row_val(row, name_keys, ""),
            "quantity": row.get("quantity", ""),
            "unit": row.get("unit", ""),
            "expiry_date": row.get("expiry_date", ""),
            "added_date": row.get("added_date", row.get("added", "")),
        }

        # Фільтр по категорії (через префікс у назві)
        if category:
            pname = unified["product_name"] or ""
            if category.lower() not in pname.lower():
                continue

        result.append(unified)

    return result
