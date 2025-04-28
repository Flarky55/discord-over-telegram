import sys
from typing import TYPE_CHECKING, Union
from datetime import datetime
from discord import Message as DsMessage, Reaction, Member, User
from discord.abc import Messageable
from aiogram import F
from aiogram.types import Message as TgMessage, ErrorEvent, MessageReactionUpdated, Poll, PollAnswer

if TYPE_CHECKING:
    from ..clients import DiscordClient, TelegramClient


class Bridge:
    def __init__(self, telegram: "TelegramClient", discord: "DiscordClient", chat_id: int):
        self.telegram = telegram
        self.discord = discord

        self.chat_id = chat_id

        telegram.dp.error.register(self.handle_telegram_error, F)
        telegram.dp.message.register(self.handle_telegram_message, F.chat.id == chat_id)
        telegram.dp.edited_message.register(self.handle_telegram_message_edit, F.chat.id == chat_id)
        telegram.dp.message_reaction.register(self.handle_telegram_reaction_update, F.chat.id == chat_id)
        telegram.dp.poll.register(self.handle_telegram_poll, F.chat.id == chat_id)
        telegram.dp.poll_answer.register(self.handle_telegram_poll_answer, F.chat.id == chat_id)

        discord.register_event("on_ready", self.on_discord_ready)
        discord.register_event("on_connect", self.on_discord_connect)
        discord.register_event("on_disconnect", self.on_discord_disconnect)
        discord.register_event("on_error", self.handle_discord_error)
        discord.register_event("on_message", self.handle_discord_message)
        discord.register_event("on_message_edit", self.handle_discord_message_edit)
        discord.register_event("on_message_delete", self.handle_discord_message_delete)
        discord.register_event("on_reaction_add", self.handle_discord_reaction_add)
        discord.register_event("on_reaction_remove", self.handle_discord_reaction_remove)
        discord.register_event("on_typing", self.handle_discord_typing)

    """"""

    """"""

    async def handle_telegram_error(self, exception: ErrorEvent):
        raise exception.exception

    async def handle_telegram_message(self, message: TgMessage):
        print("TG: ", message)

    async def handle_telegram_message_edit(self, message: TgMessage):
        pass

    async def handle_telegram_reaction_update(self, reaction: MessageReactionUpdated):
        pass

    async def handle_telegram_poll(self, poll: Poll):
        pass

    async def handle_telegram_poll_answer(self, answer: PollAnswer):
        pass

    """"""

    async def on_discord_ready(self):
        pass

    async def on_discord_connect(self):
        pass

    async def on_discord_disconnect(self):
        pass

    async def handle_discord_error(self, event_name: str):
        exception = sys.exc_info()
        
        raise exception

    async def handle_discord_message(self, message: DsMessage):
        if not self.discord.is_forwardable_message(message):
            return

        pass

    async def handle_discord_message_edit(self, before: DsMessage, after: DsMessage):
        pass

    async def handle_discord_message_delete(self, message: DsMessage):
        pass

    async def handle_discord_reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        pass

    async def handle_discord_reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        pass

    async def handle_discord_typing(self, channel: Messageable, user: Union[User, Member], when: datetime):
        pass

    """"""
