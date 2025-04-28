from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart


class TelegramClient:
    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()

        self.dp.message.register(self.handle_command_start, CommandStart())

    async def start(self):
        await self.dp.start_polling(self.bot)

    """"""

    async def handle_command_start(self, message: Message):
        await message.answer(f"Hello, {message.from_user.full_name}")