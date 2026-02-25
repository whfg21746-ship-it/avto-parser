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
MAX_SELLER_ITEMS: int = int(os.getenv("MAX_SELLER_ITEMS", "15"))
MAX_SELLER_CATEGORY_ITEMS: int = int(os.getenv("MAX_SELLER_CATEGORY_ITEMS", "3"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/flipper.db")
SEARCH_PAGES: int = int(os.getenv("SEARCH_PAGES", "3"))

AVITO_BASE_URL: str = "https://www.avito.ru"

# Whitelist of Telegram user IDs allowed to use the bot.
# Empty list = no restriction (anyone can use).
_allowed_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: list[int] = [
    int(uid.strip()) for uid in _allowed_raw.split(",")
    if uid.strip().isdigit()
]
