import json
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

_proxy_raw = os.getenv("PROXY_LIST", "[]")
try:
    PROXY_LIST: list[str] = json.loads(_proxy_raw)
except (json.JSONDecodeError, TypeError):
    PROXY_LIST = []

SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "60"))
MAX_SELLER_ITEMS: int = int(os.getenv("MAX_SELLER_ITEMS", "10"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/flipper.db")

AVITO_BASE_URL: str = "https://www.avito.ru"
