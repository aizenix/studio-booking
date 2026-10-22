from aiogram import BaseMiddleware
from asgiref.sync import sync_to_async
from django.db import close_old_connections


class DbConnectionMiddleware(BaseMiddleware):
    # Django drops stale connections at the start and end of each HTTP request.
    # The bot is one long-running process, so do the same around every update.
    async def __call__(self, handler, event, data):
        await sync_to_async(close_old_connections)()
        try:
            return await handler(event, data)
        finally:
            await sync_to_async(close_old_connections)()
