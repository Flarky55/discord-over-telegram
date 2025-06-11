import asyncio
from typing import Callable, Coroutine, Any
from discord import Client, Message, DMChannel, Attachment
from discord.abc import Messageable


TRANSLATION = {
    "image": "photo",
    "application": "document",
    "text": "document",
}


class DiscordClient(Client):
    def __init__(self, token: str):
        super().__init__()

        self.token = token

    async def start(self):
        await super().start(self.token)

    """"""

    @staticmethod
    def get_telegram_attachment_type(attachment: Attachment):
        mime_type = attachment.content_type
        _type = mime_type.split("/")[0]

        return TRANSLATION.get(_type, _type)

    @staticmethod
    def is_forwardable_channel(channel: Messageable):
        return isinstance(channel, DMChannel)
    
    def is_forwardable_message(self, message: Message):
        if message.author == self.user:
            return False

        return self.is_forwardable_channel(message.channel)
    
    """"""

    def register_event(self, event_name: str, coro: Callable[..., Coroutine[Any, Any, Any]]):
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('event registered must be a coroutine function')

        setattr(self, event_name, coro)
