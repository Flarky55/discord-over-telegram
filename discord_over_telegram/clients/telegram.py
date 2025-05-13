import asyncio
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.formatting import Pre
from aiogram.types import Message


class MediaGroupMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.01):
        self.medias = {}
        self.latecny = latency

    async def __call__(
            self, 
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]], 
            event: Message, 
            data: Dict[str, Any]
    ) -> Any:
        if event.media_group_id:
            try:
                self.medias[event.media_group_id].append(event)
            except KeyError:
                self.medias[event.media_group_id] = [event]
                await asyncio.sleep(self.latecny)
                    
                data["media_events"] = self.medias.pop(event.media_group_id)

        return await handler(event, data)
        


class TelegramClient:
    def __init__(self, token: str):
        self.dp = Dispatcher()
        self.bot = Bot(token=token)

        self.dp.message.middleware.register(MediaGroupMiddleware())
        self.dp.message.register(self.command_debug, Command("debug"))

    async def start(self):
        await self.dp.start_polling(self.bot)

    """"""

    async def command_debug(self, message: Message):
        await message.answer(**Pre(message.chat.model_dump_json(indent=2), language="json").as_kwargs())