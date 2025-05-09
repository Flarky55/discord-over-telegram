import sys
from .clients import DiscordClient, TelegramClient
from .storage import BaseStorage
from typing import Union, Optional
from datetime import datetime
from discord import Message as DsMessage, Reaction, Member, User, Relationship
from discord.abc import Messageable
from aiogram import F
from aiogram.types import Message as TgMessage, MessageReactionUpdated, Poll, PollAnswer, ForumTopic
from aiogram.filters import Filter
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import TopicIconColor


class Bridge:
    def __init__(self, telegram: TelegramClient, discord: DiscordClient, db: BaseStorage, chat_id: int):
        self.telegram = telegram
        self.discord = discord
        self.db = db

        self.chat_id = chat_id

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
        discord.register_event("on_relationship_add", self.handle_discord_relationship_add)
        discord.register_event("on_relationship_remove", self.handle_discord_relationship_remove)

    """"""
    
    async def start(self):
        # self.db.shelf.clear()

        await self.init_topics()
        await self.discord.start()

    """"""

    def _db_unique(self, key: str) -> str:
        return f"{self.chat_id}:{key}"
    
    def _db_unique_unpack(self, key: str) -> str:
        return key.replace(self._db_unique(""), "")

    def _db_topic_key(self, key: str) -> str: 
        return self._db_unique(f"topic.{key}")
    
    def _db_topic_key_unpack(self, key: str) -> str:
        return key.replace(self._db_topic_key(""), "")

    async def _create_topic(self, key: str, bidirectional: bool, *args, **kwargs,) -> int:
        topic = await self.telegram.bot.create_forum_topic(self.chat_id, *args, **kwargs)

        if bidirectional:
            self.db.set_bidirectional(key, self._db_unique(topic.message_thread_id))
        else:
            self.db.set(key, topic.message_thread_id)

        return topic.message_thread_id

    async def create_unique_topic(self, key: str, name: str, icon_color: Optional[int] = None, bidirectional: Optional[bool] = False) -> int:
        message_thread_id = self.db.get(str(key))

        if bidirectional:
            message_thread_id = self._db_unique_unpack(message_thread_id)

        if not message_thread_id:
            message_thread_id = await self._create_topic(key, bidirectional, name, icon_color)
        else:
            try:
                await self.telegram.bot.edit_forum_topic(self.chat_id, message_thread_id, name)
            except TelegramBadRequest as e:
                if e.message.find("TOPIC_ID_INVALID") != -1:
                    message_thread_id = await self._create_topic(key, bidirectional, name, icon_color)

        return message_thread_id
    
    async def init_topics(self):
        await self.create_unique_topic(self._db_topic_key("errors"), "Errors", TopicIconColor.RED)
        await self.create_unique_topic(self._db_topic_key("relationships"), "Relationships", TopicIconColor.ROSE)
        await self.create_unique_topic(self._db_topic_key("calls"), "Calls", TopicIconColor.GREEN)

    """"""

    async def to_telegram(self, message: DsMessage, message_thread_id: int = None, reply_to_message_id: int = None) -> TgMessage:
        message_tg = await self.telegram.bot.send_message(self.chat_id, message.content, 
                                                          message_thread_id=message_thread_id, reply_to_message_id=reply_to_message_id)
        
        return message_tg
    
    async def to_discord(self, message: TgMessage) -> DsMessage:
        pass

    """"""

    async def handle_telegram_message(self, message: TgMessage):
        if self.db.get(self._db_unique(message.message_thread_id)) is None:
            return

        channel_id = self.db.get(self._db_unique(message.message_thread_id))
        channel_id = self._db_topic_key_unpack(channel_id)

        print(channel_id)

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

    async def handle_discord_error(self, event_name: str, *args, **kwargs):
        exception = sys.exc_info()

        raise exception

    async def handle_discord_message(self, message: DsMessage):
        if not self.discord.is_forwardable_message(message):
            return
        
        name = message.author.relationship.nick or message.author.display_name
        message_thread_id = await self.create_unique_topic(self._db_topic_key(message.channel.id), name, bidirectional=True)

        message_refernce_id = None

        if message.reference:
            pass

        await self.telegram.bot.send_message(self.chat_id, message.content, message_thread_id=message_thread_id)


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

    async def handle_discord_relationship_add(self, relationship: Relationship):
        pass

    async def handle_discord_relationship_remove(self, relationship: Relationship):
        pass

    """"""
