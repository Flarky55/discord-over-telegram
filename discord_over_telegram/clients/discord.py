import asyncio
from typing import Callable, Coroutine, Any
from discord import Client, Message, DMChannel
from discord.abc import Messageable


class DiscordClient(Client):
    def __init__(self, token: str):
        super().__init__()

        self.token = token

    async def start(self):
        await super().start(self.token)

    """"""

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
