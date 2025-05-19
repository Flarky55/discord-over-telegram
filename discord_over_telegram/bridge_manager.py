import asyncio
from .clients import TelegramClient, DiscordClient
from .storage import BaseStorage, ShelveStorage
from .bridge import Bridge


class BridgeManager:
    def __init__(self, telegram: TelegramClient, db: BaseStorage):
        self.telegram = telegram
        self.db = db

        self.bridges: list[Bridge] = []

    async def start(self):
        await asyncio.gather(
            self.telegram.start(),
            *(bridge.start() for bridge in self.bridges),
        )

    """"""

    @staticmethod
    def new(telegram_token: str, db_filepath: str = "data.db"):
        telegram = TelegramClient(telegram_token)
        db = ShelveStorage(db_filepath)

        return BridgeManager(telegram, db)

    """"""

    def add_discord_client(self, token: str, chat_id: int) -> Bridge:
        discord = DiscordClient(token)

        bridge = Bridge(self.telegram, discord, self.db, chat_id)

        self.bridges.append(bridge)

        return bridge