import asyncio
import discord
from discord_over_telegram import BridgeManager
from os import getenv


async def main():
    manager = BridgeManager.new(getenv("TELEGRAM_TOKEN"))
    manager.add_discord_client(getenv("DISCORD_TOKEN"), -1002335065354)

    await manager.telegram.bot.delete_webhook()

    asyncio.create_task(manager.start())

    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    discord.utils.setup_logging()

    asyncio.run(main())