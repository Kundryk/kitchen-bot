import gspread
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

class KitchenDatabase:
    def __init__(self):
        # Тепер беремо креденшіали з ENV (як у твоєму старому коді)
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
