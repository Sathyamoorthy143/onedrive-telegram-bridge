from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from app.adapters.telegram_adapter import TelegramAdapter
from app.commands.handlers import CommandHandler
from app.commands.parser import parse_command
from app.config import ROOT_DIR, settings
from app.services.onedrive_service import OneDriveService
from app.services.state_store import StateStore

LOG_DIR = ROOT_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'app.log'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

store = StateStore()
onedrive = OneDriveService()
telegram_adapter: TelegramAdapter | None = None
handler: CommandHandler | None = None


def process_event(event):
    if handler is None:
        return "Not initialized"
    
    store.save_event(event)
    request = parse_command(event)
    response = handler.handle(request)
    store.save_command_result(event.correlation_id, event.channel, request.name, response.data)

    return response.message


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global telegram_adapter
    tb_app = None
    if settings.telegram_bot_token and telegram_adapter is not None:
        logger.info("Starting Telegram bot natively...")
        tb_app = telegram_adapter.build()
        await tb_app.initialize()
        await tb_app.start()
        await tb_app.updater.start_polling(drop_pending_updates=True)
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down bridge...")
    if tb_app is not None:
        await tb_app.updater.stop()
        await tb_app.stop()
        await tb_app.shutdown()


def create_app() -> FastAPI:
    global telegram_adapter, handler

    telegram_adapter = TelegramAdapter(process_event)
    
    try:
        handler = CommandHandler(onedrive, store)
    except Exception as e:
        logger.error("Failed to initialize CommandHandler (check OneDrive auth): %s", e)
        handler = None

    app = FastAPI(title='OneDrive Telegram Bridge', lifespan=lifespan)

    @app.get('/')
    def index():
        return {
            'message': 'Welcome to OneDrive Telegram Bridge', 
            'docs': '/docs', 
            'health': '/health'
        }

    @app.get('/health')
    def health():
        return {
            'status': 'ok', 
            'app': settings.app_name,
            'telegram_active': bool(settings.telegram_bot_token)
        }

    return app


app = create_app()


if __name__ == '__main__':
    mode = settings.environment.lower()
    port = 8080
    logger.info('Starting app in %s mode on port %d', mode, port)
    uvicorn.run(app, host='0.0.0.0', port=port)