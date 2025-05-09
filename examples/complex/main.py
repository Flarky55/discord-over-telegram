import asyncio
from discord_over_telegram import BridgeManager
from discord_over_telegram.clients import TelegramClient
from discord_over_telegram.storage import ShelveStorage
from os import getenv


async def main():
    telegram = TelegramClient(getenv("TELEGRAM_TOKEN"))
    db = ShelveStorage("data.db")

    manager = BridgeManager(telegram, db)
    manager.add_discord_client(getenv("DISCORD_TOKEN"), -1002413580346)

    manager2 = BridgeManager(telegram)

    print(manager)


if __name__ == "__main__":
    asyncio.run(main())