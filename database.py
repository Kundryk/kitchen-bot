import gspread
from datetime import datetime

class KitchenDatabase:
    def __init__(self, credentials_file="credentials.json"):
        self.gc = gspread.service_account(filename=credentials_file)
        self.sh = self.gc.open("kitchen_products")  # твоя основна таблиця

    def get_products_sheet(self):
        return self.sh.worksheet("kitchen_products")
    
    def get_logs_sheet(self):
        return self.sh.worksheet("kitchen_logs")
    
    def get_shopping_sheet(self):
        return self.sh.worksheet("shopping_list")

    def log_action(self, user_id, product_name, delta_qty, unit, action):
        """Записати будь‑яку дію користувача у kitchen_logs"""
        logs = self.get_logs_sheet()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs.append_row([user_id, product_name, delta_qty, unit, action, timestamp])
