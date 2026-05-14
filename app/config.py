from pathlib import Path
import os
from dataclasses import dataclass
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env')


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', 'personal-command-bridge')
    environment: str = os.getenv('ENVIRONMENT', 'development')
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_allowed_chat_id: str = os.getenv('TELEGRAM_ALLOWED_CHAT_ID', '')

    microsoft_tenant_id: str = os.getenv('MICROSOFT_TENANT_ID', '')
    microsoft_client_id: str = os.getenv('MICROSOFT_CLIENT_ID', '')
    microsoft_client_secret: str = os.getenv('MICROSOFT_CLIENT_SECRET', '')
    onedrive_user_id: str = os.getenv('ONEDRIVE_USER_ID', '')
    onedrive_drive_id: str = os.getenv('ONEDRIVE_DRIVE_ID', '')
    onedrive_root_path: str = os.getenv('ONEDRIVE_ROOT_PATH', '')

    database_url: str = os.getenv('DATABASE_URL', f"sqlite:///{ROOT_DIR / 'data' / 'app.db'}")
    max_results: int = int(os.getenv('MAX_RESULTS', '10'))


settings = Settings()