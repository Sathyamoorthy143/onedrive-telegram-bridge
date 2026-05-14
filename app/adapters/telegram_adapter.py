from __future__ import annotations

import logging
from typing import Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.models.events import NormalizedEvent

logger = logging.getLogger(__name__)


class TelegramAdapter:
    def __init__(self, event_callback: Callable[[NormalizedEvent], str]):
        self.event_callback = event_callback
        self.application: Application | None = None

    async def _ingest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.effective_message
        if not msg or not update.effective_chat:
            return
            
        chat_id = str(update.effective_chat.id)
        sender_id = str(update.effective_user.id) if update.effective_user else ''

        if settings.telegram_allowed_chat_id and chat_id != settings.telegram_allowed_chat_id:
            await msg.reply_text(f'Unauthorized chat. Your Chat ID is {chat_id}')
            return

        text = msg.text or msg.caption or ''
        event = NormalizedEvent(
            channel='telegram',
            sender_id=sender_id,
            chat_id=chat_id,
            text=text,
            message_id=str(msg.message_id),
            metadata={'username': getattr(update.effective_user, 'username', '')},
        )
        reply = self.event_callback(event)
        if reply:
            await msg.reply_text(reply)

    async def _mirror_out(self, text: str):
        if not self.application or not settings.telegram_allowed_chat_id:
            return
        await self.application.bot.send_message(chat_id=settings.telegram_allowed_chat_id, text=f'[mirror] {text}')

    def send_mirror_text(self, text: str):
        if self.application:
            self.application.create_task(self._mirror_out(text))

    def healthcheck(self) -> str:
        return 'configured' if settings.telegram_bot_token else 'missing-token'

    def build(self):
        self.application = Application.builder().token(settings.telegram_bot_token).build()
        for cmd in ['start', 'list', 'search', 'get', 'help', 'sync', 'status']:
            self.application.add_handler(CommandHandler(cmd, self._ingest))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._ingest))
        return self.application

    def run(self):
        if not settings.telegram_bot_token:
            logger.warning('Telegram token missing; adapter not started.')
            return
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = self.build()
        app.run_polling(drop_pending_updates=True)