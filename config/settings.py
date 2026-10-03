import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    MASTER_PASSWORD: str = os.getenv("MASTER_PASSWORD", "admin123").strip()
    OWNER_ID: int = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID", "0").isdigit() else 0
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "bot_database.db"))
    
    # Feature Flags
    AUTO_DELETE_PASSWORD: bool = os.getenv("AUTO_DELETE_PASSWORD", "True").lower() in ("true", "1", "yes")
    DEFAULT_PREVIEW_MODE: bool = os.getenv("DEFAULT_PREVIEW_MODE", "True").lower() in ("true", "1", "yes")
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOGIN_COOLDOWN_SECONDS: int = int(os.getenv("LOGIN_COOLDOWN_SECONDS", "60"))
    
    # Queue & Worker Settings
    WORKER_COUNT: int = int(os.getenv("WORKER_COUNT", "1"))  # 1 worker guarantees strict FIFO order
    MAX_BOT_DOWNLOAD_MB: int = int(os.getenv("MAX_BOT_DOWNLOAD_MB", "10"))
    
    # Promotion & Central Channel Links
    MAIN_CHANNEL_USERNAME: str = os.getenv("MAIN_CHANNEL_USERNAME", "").strip().lstrip("@")
    PROMO_BOT_USERNAME: str = os.getenv("PROMO_BOT_USERNAME", "").strip().lstrip("@")
    
    # Cloud Deployment / Health Check Server (Render, Koyeb, Railway)
    PORT: int = int(os.getenv("PORT", "8080")) if os.getenv("PORT", "8080").isdigit() else 8080
    ENABLE_WEB_SERVER: bool = os.getenv("ENABLE_WEB_SERVER", "True").lower() in ("true", "1", "yes")

settings = Settings()

