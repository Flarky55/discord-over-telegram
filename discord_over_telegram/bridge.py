import sys
import traceback
from .clients import DiscordClient, TelegramClient
from .storage import BaseStorage
from .utils import discord_decoration
from typing import Union, cast
from enum import Enum
from datetime import datetime
from discord import Message as DsMessage, Reaction, Member, User, Relationship, RelationshipType, DMChannel, PartialMessage, PrivateCall, GroupCall, File
from discord.abc import Messageable
from aiogram import F
from aiogram.types import Message as TgMessage, MessageReactionUpdated, Poll, PollAnswer, ReactionTypeEmoji, ReplyParameters, BufferedInputFile
from aiogram.filters import Command, CommandObject
from aiogram.utils.formatting import Text, Bold, Italic, BlockQuote, Pre
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import TopicIconColor
from emoji import is_emoji


class CommonTopic(Enum):
    LOGS = 1
    RELATIONSHIPS = 2
    CALLS = 3


class Bridge:
    def __init__(self, telegram: TelegramClient, discord: DiscordClient, db: BaseStorage, chat_id: int):
        self.telegram = telegram
        self.discord = discord
        self.db = db

        self.chat_id = chat_id

        telegram.dp.message.register(self._handle_telegram_command_react, Command("react"), F.chat.id == chat_id)

        telegram.dp.message.register(self._handle_telegram_message, F.chat.id == chat_id)
        telegram.dp.edited_message.register(self._handle_telegram_message_edit, F.chat.id == chat_id)
        telegram.dp.message_reaction.register(self._handle_telegram_reaction_update, F.chat.id == chat_id)
        telegram.dp.poll.register(self._handle_telegram_poll, F.chat.id == chat_id)
        telegram.dp.poll_answer.register(self._handle_telegram_poll_answer, F.chat.id == chat_id)

    """"""
    
    async def start(self):
        self._topics = {
            CommonTopic.LOGS:             await self.create_unique_topic("logs", "Logs", TopicIconColor.BLUE),
            CommonTopic.RELATIONSHIPS:    await self.create_unique_topic("relationships", "Relationships", TopicIconColor.ROSE),
            CommonTopic.CALLS:            await self.create_unique_topic("calls", "Calls", TopicIconColor.GREEN),
        }

        self.discord.register_event("on_ready", self._on_discord_ready)
        self.discord.register_event("on_connect", self._on_discord_connect)
        self.discord.register_event("on_disconnect", self._on_discord_disconnect)
        self.discord.register_event("on_error", self._handle_discord_error)
        self.discord.register_event("on_message", self._handle_discord_message)
        self.discord.register_event("on_message_edit", self._handle_discord_message_edit)
        self.discord.register_event("on_message_delete", self._handle_discord_message_delete)
        self.discord.register_event("on_reaction_add", self._handle_discord_reaction_add)
        self.discord.register_event("on_reaction_remove", self._handle_discord_reaction_remove)
        self.discord.register_event("on_typing", self._handle_discord_typing)
        self.discord.register_event("on_relationship_add", self._handle_discord_relationship_add)
        self.discord.register_event("on_relationship_remove", self._handle_discord_relationship_remove)
        self.discord.register_event("on_relationship_update", self._handle_discord_relationship_update)
        self.discord.register_event("on_call_create", self._handle_discord_call_create)
        self.discord.register_event("on_call_delete", self._handle_discord_call_delete)
        self.discord.register_event("on_call_update", self._handle_discord_call_update)

        await self.discord.start()

    """"""

    def _db_unique(self, key: str, prefix: str = "") -> str:
        return f"{self.chat_id}{ (":" + prefix) if prefix else "" }.{key}"

    """"""

    async def _create_topic(self, key: str, *args, **kwargs) -> int:
        topic = await self.telegram.bot.create_forum_topic(self.chat_id, *args, **kwargs)

        self.db.set(key, topic.message_thread_id)

        return topic.message_thread_id

    async def create_unique_topic(self, key: str, name: str, icon_color: int = None) -> int:
        key = self._db_unique(key, "topic")
        
        message_thread_id = self.db.get(key)

        if not message_thread_id:
            message_thread_id = await self._create_topic(key, name, icon_color)
        else:
            try:
                await self.telegram.bot.edit_forum_topic(self.chat_id, message_thread_id, name)
            except TelegramBadRequest as e:
                if e.message.find("TOPIC_ID_INVALID") != -1:
                    message_thread_id = await self._create_topic(key, name, icon_color)

        return message_thread_id

    async def send_message_to_common_topic(self, type: CommonTopic, *args, **kwargs):
        await self.telegram.bot.send_message(self.chat_id, *args, message_thread_id=self._topics[type], **kwargs)

    """"""

    async def to_telegram(self, message: DsMessage, message_thread_id: int = None, reply_message_id: int = None) -> TgMessage:
        messages_tg: list[TgMessage] = []


        content = Text(message.content)

        if message.author == self.discord.user:
            content = BlockQuote(Bold(message.author.display_name), "\n", content)

        if len(message.attachments) > 0:
            media_group = MediaGroupBuilder(caption=content)
            
            for attahcment in message.attachments:
                media_type = self.discord.get_telegram_attachment_type(attahcment)

                if media_type in ("photo", "video"):
                    media_group.add(
                        type=media_type, media=attahcment.url, has_spoiler=attahcment.is_spoiler(),
                        **content.as_caption_kwargs()
                    ) 
                else:
                    buf = await attahcment.read()

                    media_group.add(
                        type=media_type, media=BufferedInputFile(buf, attahcment.filename)
                    )

            messages_tg.append(
                await self.telegram.bot.send_media_group(
                    self.chat_id, message_thread_id=message_thread_id,
                    reply_parameters=ReplyParameters(message_id=reply_message_id) if reply_message_id else None,
                    media=media_group.build(),
                )
            )
        else:
            messages_tg.append(
                await self.telegram.bot.send_message(
                    self.chat_id, message_thread_id=message_thread_id, 
                    reply_parameters=ReplyParameters(message_id=reply_message_id) if reply_message_id else None,
                    **content.as_kwargs()
                )
            )

        self.db.set(self._db_unique(message.id, "message"), messages_tg[0].message_id)

        for message_tg in messages_tg:
            self.db.set(self._db_unique(message_tg.message_id, "message"), message.id)

        return messages_tg
        
    async def to_discord(self, message: TgMessage, channel: DMChannel, reference: Union[DsMessage, PartialMessage] = None, files: list[File] = None) -> DsMessage:
        content = message.text or message.caption
        file = None

        entities = message.entities or message.caption_entities

        if content and entities:
            content = discord_decoration.unparse(content, entities)
            
        if self.telegram.has_attachment(message):
            file = await self.telegram.download_as_discord_file(message)

        date_timestamp = message.date.timestamp()
        delay = datetime.now().timestamp() - date_timestamp

        if delay > 2:
            date_timestamp_rounded = round(date_timestamp)

            content += f"\n-# Отправлено <t:{date_timestamp_rounded}:f> (<t:{date_timestamp_rounded}:R>) с задержкой {delay:,.3}s"

        message_ds: DsMessage = await channel.send(
            content,
            reference=reference,
            files=files,
            file=file
        )
        
        self.db.set(self._db_unique(message.message_id, "message"), message_ds.id)
        self.db.set(self._db_unique(message_ds.id, "message"), message.message_id)

        return message_ds
    
    async def get_telegram_message(self, message: DsMessage, message_thread_id: int = None) -> int:
        message_id = self.db.get(self._db_unique(message.id, "message"))

        if not message_id:
            message_tg = await self.to_telegram(message, message_thread_id)
            
            message_id = message_tg.message_id

        return message_id
    
    async def get_discord_message(self, message: TgMessage, channel: DMChannel, partial: bool = False) -> DsMessage | None:
        message_id = self.db.get(self._db_unique(message.message_id, "message"))

        if message_id:
            if partial:
                return channel.get_partial_message(message_id)
            else:
                return await channel.fetch_message(message_id)

        return None
    
    async def create_discord_topic(self, channel_id: int, name: str) -> int:
        message_thread_id = await self.create_unique_topic(channel_id, name)

        self.db.set(self._db_unique(message_thread_id, "channel"), channel_id)

        return message_thread_id

    def has_discord_topic(self, message_thread_id: int) -> bool:
        return self.db.get(self._db_unique(message_thread_id, "channel")) is not None

    async def get_telegram_topic(self, channel: DMChannel, user: Union[User, Member]) -> int:
        name = user.relationship.nick or user.display_name

        message_thread_id = await self.create_discord_topic(channel.id, name)

        return message_thread_id

    async def get_discord_channel(self, message_thread_id: int) -> DMChannel:
        channel_id = self.db.get(self._db_unique(message_thread_id, "channel"))

        return self.discord.get_channel(channel_id) or await self.discord.fetch_channel(channel_id)

    """"""

    async def _handle_telegram_command_react(self, message: TgMessage, command: CommandObject):
        # TODO: proper check if message is reply
        if not message.reply_to_message:
            return
        
        emoji = command.args
        if not emoji:
            return
        
        if not is_emoji(emoji):
            return
        
        channel = await self.get_discord_channel(message.message_thread_id)
        message_ds = await self.get_discord_message(message.reply_to_message, channel)

        await message_ds.add_reaction(emoji)

    async def _handle_telegram_message(self, message: TgMessage, media_group: list[TgMessage] = None):
        if not self.has_discord_topic(message.message_thread_id):
            return
        
        channel = await self.get_discord_channel(message.message_thread_id)
        reference = None
        files = None

        if message.reply_to_message:
            reference = await self.get_discord_message(message.reply_to_message, channel, True)

        if media_group:
            files = [await self.telegram.download_as_discord_file(media) for media in media_group]

        try:
            await self.to_discord(message, channel, reference, files)
        except:
            await self.send_message_to_common_topic(
                CommonTopic.LOGS, reply_parameters=ReplyParameters(message_id=message.message_id),
                **Text(Bold("Error : Telegram"), "\n", Pre(traceback.format_exc())).as_kwargs()
            )

    async def _handle_telegram_message_edit(self, message: TgMessage):
        pass

    async def _handle_telegram_reaction_update(self, reaction: MessageReactionUpdated):
        pass

    async def _handle_telegram_poll(self, poll: Poll):
        pass

    async def _handle_telegram_poll_answer(self, answer: PollAnswer):
        pass

    """"""

    async def _on_discord_ready(self):
        await self.send_message_to_common_topic(
            CommonTopic.LOGS,
            **Text(Bold("Discord Client"), "\n", "Ready").as_kwargs()
        )

    async def _on_discord_connect(self):
        await self.send_message_to_common_topic(
            CommonTopic.LOGS,
            **Text(Bold("Discord Client"), "\n", "Connected").as_kwargs()
        )

    async def _on_discord_disconnect(self):
        await self.send_message_to_common_topic(
            CommonTopic.LOGS,
            **Text(Bold("Discord Client"), "\n", "Disconnected").as_kwargs()
        )

    async def _handle_discord_error(self, event_name: str, *args, **kwargs):
        exception = sys.exc_info()

        raise exception

    async def _handle_discord_message(self, message: DsMessage):
        if not self.discord.is_forwardable_message(message):
            return
        
        message_thread_id = await self.get_telegram_topic(message.channel, message.author)
        reply_message_id = None

        if message.reference:
            reply_message_id = await self.get_telegram_message(
                message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id),
                message_thread_id,
            )

        try:
            await self.to_telegram(message, message_thread_id, reply_message_id)
        except:
            await self.send_message_to_common_topic(
                CommonTopic.LOGS,
                **Text(Bold("Error : Discord"), "\n", message.jump_url, "\n", Pre(message.content), "\n", Pre(traceback.format_exc())).as_kwargs()
            )


    async def _handle_discord_message_edit(self, before: DsMessage, after: DsMessage):
        if not self.discord.is_forwardable_message(after):
            return
        
        message_thread_id = await self.get_telegram_topic(after.channel, after.author)
        message_id = await self.get_telegram_message(after, message_thread_id)

        message_tg = await self.telegram.bot.send_message(
            self.chat_id, message_thread_id=message_thread_id, reply_parameters=ReplyParameters(message_id=message_id),
            **Text(Bold("Изменено"), "\n", BlockQuote(after.content)).as_kwargs()
        )

        self.db.set(self._db_unique(message_tg.message_id, "message"), after.id)

    async def _handle_discord_message_delete(self, message: DsMessage):
        if not self.discord.is_forwardable_message(message):
            return
        
        message_thread_id = await self.get_telegram_topic(message.channel, message.author)
        message_id = await self.get_telegram_message(message, message_thread_id)

        await self.telegram.bot.set_message_reaction(self.chat_id, message_id, [ReactionTypeEmoji(emoji="🔥")], True)
        await self.telegram.bot.send_message(
            self.chat_id, message_thread_id=message_thread_id, reply_parameters=ReplyParameters(message_id=message_id),
            **BlockQuote("Сообщение удалено").as_kwargs()
        )

    async def _handle_discord_reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        pass

    async def _handle_discord_reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        pass

    async def _handle_discord_typing(self, channel: Messageable, user: Union[User, Member], when: datetime):
        if not self.discord.is_forwardable_channel(channel): 
            return
        
        return
        
        message_thread_id = await self.get_telegram_topic(channel, user)

        await self.telegram.bot.send_message(
            self.chat_id, message_thread_id=message_thread_id, 
            **BlockQuote(Italic("печатаю")).as_kwargs()
        )

    async def _handle_discord_relationship_add(self, relationship: Relationship):
        if relationship.type != RelationshipType.incoming_request:
            return
        
        await self.send_message_to_common_topic(
            CommonTopic.RELATIONSHIPS,
            **Text(Bold("Входящий запрос"), "\n", f"{relationship.user.display_name} ({relationship.user.name})").as_kwargs()
        )

    async def _handle_discord_relationship_remove(self, relationship: Relationship):
        if relationship.type != RelationshipType.friend:
            return

        await self.send_message_to_common_topic(
            CommonTopic.RELATIONSHIPS,
            **Text(Bold("Удалён из друзей"), "\n", f"{relationship.user.display_name} ({relationship.user.name})").as_kwargs()
        )
    
    async def _handle_discord_relationship_update(self, before: Relationship, after: Relationship):
        if after.type != RelationshipType.incoming_request:
            return
        
        await self.send_message_to_common_topic(
            CommonTopic.RELATIONSHIPS, 
            **Text(Bold("Входящий запрос"), "\n", f"{after.user.display_name} ({after.user.name})").as_kwargs()
        )

    async def _handle_discord_call_create(self, call: Union[PrivateCall, GroupCall]):
        # await self.telegram.bot.send_message(
        #     self.chat_id, message_thread_id=self._topics[GeneralTopic.CALLS],
        #     **Text(call).as_kwargs()
        # )
        pass

    async def _handle_discord_call_delete(self, call: Union[PrivateCall, GroupCall]):
        pass

    async def _handle_discord_call_update(self, befoe: Union[PrivateCall, GroupCall], after: Union[PrivateCall, GroupCall]):
        pass

    """"""
