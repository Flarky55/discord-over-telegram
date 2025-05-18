import asyncio
from typing import Callable, Dict, Any, Awaitable, Union, BinaryIO, cast 
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.formatting import Pre
from aiogram.types import Message, PhotoSize, Video, Audio, Animation, Document
from discord import File


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
        if event.media_group_id is None:
            return await handler(event, data)

        try:
            self.medias[event.media_group_id].append(event)
        except KeyError:
            self.medias[event.media_group_id] = [event]
            await asyncio.sleep(self.latecny)
                
            data["media_group"] = self.medias.pop(event.media_group_id)

            await handler(event, data)


class TelegramClient:
    def __init__(self, token: str):
        self.dp = Dispatcher()
        self.bot = Bot(token=token)

        self.dp.message.middleware.register(MediaGroupMiddleware())
        self.dp.message.register(self.command_debug, Command("debug"))

    async def start(self):
        await self.dp.start_polling(self.bot)

    """"""

    @staticmethod
    def get_attachment(message: Message) -> Union[PhotoSize, Video, Audio, Animation, Document] | None:
        return message.photo[-1] if message.photo else message.video or message.audio or message.animation or message.document
    
    @staticmethod
    def has_attachment(message: Message) -> bool:
        return TelegramClient.get_attachment(message) is not None
    
    async def download_as_discord_file(self, message: Message) -> File | None:
        attachment = self.get_attachment(message)
        if not attachment:
            return
        
        file = await self.bot.get_file(attachment.file_id)
        file_path = cast(str, file.file_path)

        buffer = await self.bot.download(file_path)

        return File(buffer, getattr(attachment, "file_name", file_path), spoiler=message.has_media_spoiler)

    """"""

    async def command_debug(self, message: Message):
        await message.answer(**Pre(message.chat.model_dump_json(indent=2), language="json").as_kwargs())