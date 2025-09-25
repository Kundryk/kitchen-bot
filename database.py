database_code = '''import gspread
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

PRODUCTS_WS = "kitchen_products"
LOGS_WS = "kitchen_logs"
SHOPPING_WS = "shopping_list"

PRODUCTS_HEADERS = ["user_id", "product_name", "quantity", "unit", "expiry_date", "added_date"]
LOGS_HEADERS = ["user_id", "product_name", "delta_qty", "unit", "action", "timestamp"]
SHOPPING_HEADERS = ["user_id", "item", "quantity", "unit", "note", "added_date"]

class KitchenDatabase:
    def __init__(self):
        creds_env = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_env:
            raise ValueError("❌ Змінна GOOGLE_CREDENTIALS не знайдена в Railway!")

        service_account_info = json.loads(creds_env)
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )

        client = gspread.authorize(creds)
        self.sh = client.open("kitchen_products")

        # Гарантуємо наявність і заголовки
        self._ensure_worksheet(PRODUCTS_WS, PRODUCTS_HEADERS)
        self._ensure_worksheet(LOGS_WS, LOGS_HEADERS)
        self._ensure_worksheet(SHOPPING_WS, SHOPPING_HEADERS)

    def _ensure_worksheet(self, title: str, headers: list[str]):
        try:
            ws = self.sh.worksheet(title)
        except WorksheetNotFound:
            ws = self.sh.add_worksheet(title=title, rows=1000, cols=max(len(headers), 8))
            ws.append_row(headers)
            return
        
        # Перевіряємо заголовки і виправляємо при потребі
        values = ws.get_all_values()
        if not values:
            ws.append_row(headers)
        else:
            current = [h.strip() for h in values[0]] if values else []
            if [h.lower() for h in current] != [h.lower() for h in headers]:
                ws.delete_rows(1)
                ws.insert_row(headers, 1)

    def get_products_sheet(self):
        return self.sh.worksheet(PRODUCTS_WS)
    
    def get_logs_sheet(self):
        return self.sh.worksheet(LOGS_WS)
    
    def get_shopping_sheet(self):
        return self.sh.worksheet(SHOPPING_WS)

    def log_action(self, user_id, product_name, delta_qty, unit, action):
        logs = self.get_logs_sheet()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs.append_row([str(user_id), product_name, delta_qty, unit, action, timestamp])
'''
