import asyncio
import discord
from os import getenv
from core import Bridge
from clients import DiscordClient, TelegramClient
from services import DatabaseService
from aiogram.types import Message
from aiogram.filters import Command, CommandObject


class BridgeManager:
    def __init__(self, token: str):
        self.telegram = TelegramClient(token)
        self.bridges: list[Bridge] = []

        self.telegram.dp.message.register(self.handle_command_register, Command("register"))

    async def start(self):
        pass

    """"""

    def add_discord_client(self, token: str, chat_id: int):
        discord = DiscordClient(token)
        bridge = Bridge(self.telegram, discord, chat_id)

        self.bridges.append(bridge)

    async def handle_command_register(self, message: Message, command: CommandObject):
        # self.add_discord_client(command.args, message.chat.id)

        pass


async def main():
    db = DatabaseService("data.db")

    manager = BridgeManager(getenv("TELEGRAM_TOKEN"))
    manager.add_discord_client(getenv("DISCORD_TOKEN"), -1002413580346)

    manager.start()


if __name__ == "__main__":
    discord.utils.setup_logging()

    asyncio.run(main())