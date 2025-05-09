from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.utils.formatting import Pre
from aiogram.types import Message


class TelegramClient:
    def __init__(self, token: str):
        self.dp = Dispatcher()
        self.bot = Bot(token=token)

        self.dp.message.register(self.command_debug, Command("debug"))

    async def start(self):
        await self.dp.start_polling(self.bot)

    """"""

    async def command_debug(self, message: Message):
        await message.answer(**Pre(message.chat.model_dump_json(indent=2), language="json").as_kwargs())