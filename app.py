import asyncio
import logging
import os.path
from os import getenv
from platform import system
from collections import defaultdict
from typing import TypedDict
from collections.abc import Callable
from io import BytesIO
from discord import Client, Message as DsMessage, DMChannel, File
from telegram import Update, Message as TgMessage, InputMedia, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputFile, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, MessageHandler, MessageReactionHandler, ContextTypes, PicklePersistence, filters
from telegram.constants import ReactionEmoji, ParseMode
from telegram.error import BadRequest


# https://github.com/aio-libs/aiodns?tab=readme-ov-file#note-for-windows-users
if system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# logging.getLogger("httpx").setLevel(logging.WARNING)


TRANSLATE_CONTENT_TYPE = {
    "application": "document",
    "text": "document",
    "image": "photo",
}

CONTENT_IN_CAPTION_MEDIA_TYPE = {"photo", "video", "document"}


class StoredDiscordMessage(TypedDict):
    id: int
    channel_id: int


# TODO: Acknowledge
app_tg = (
    ApplicationBuilder()
    .token(getenv("TELEGRAM_TOKEN"))
    .persistence(PicklePersistence(filepath="data.pickle"))
    .build()
)


# TODO: change func name?
async def relay_message(
        message: DsMessage,
        chat_id: int,
        message_thread_id: int,
        reply_to_message_id: int = None,
        format_message: Callable[[str, DsMessage], str] = None
) -> list[TgMessage]:
    # TODO: parse Markdown
    content = message.clean_content
    
    if format_message:
        content = format_message(content, message)

    media = defaultdict(list)

    for attachment in message.attachments:
        content_type = attachment.content_type
        content_type = TRANSLATE_CONTENT_TYPE.get(content_type, content_type).split("/")[0]
        content_type = TRANSLATE_CONTENT_TYPE.get(content_type, content_type)

        match content_type:
            case "photo":
                media[content_type].append(InputMediaPhoto(
                    media=attachment.url, has_spoiler=attachment.is_spoiler(),
                    caption=attachment.description or content, show_caption_above_media=not attachment.description)
                )
            case "video":
                media[content_type].append(InputMediaVideo(
                    media=attachment.url, has_spoiler=attachment.is_spoiler(),
                    caption=content, show_caption_above_media=True)
                )
            case "document":
                # Telegram can't fetch these by URL
                buf = await attachment.read()

                media[content_type].append(InputMediaDocument(
                    media=buf, caption=content, filename=attachment.filename
                ))
            case _:
                buf = await attachment.read()

                media[content_type].append(InputMedia(
                    content_type, media=InputFile(buf, attachment.filename, True), caption=content)
                )
    

    messages_relayed: list[TgMessage] = []

    if content and not (sum(len(l) for l in media.values()) == 1 and set(media.keys()) <= CONTENT_IN_CAPTION_MEDIA_TYPE):
        messages_relayed.append(
            await app_tg.bot.send_message(chat_id, content, message_thread_id=message_thread_id, reply_to_message_id=reply_to_message_id)
        )

    for m in media.values():
        messages_relayed.extend(
            await app_tg.bot.send_media_group(chat_id, m, message_thread_id=message_thread_id, reply_to_message_id=reply_to_message_id)
        )

    return messages_relayed

# TODO: change func name?
async def persist(message: DsMessage, relayed: list[TgMessage]):
    app_tg.bot_data.update({
        message.id: [m.id for m in relayed],
        **{m.id: {"id": message.id, "channel_id": message.channel.id} for m in relayed}
    })

    await app_tg.update_persistence()


class SelfClient(Client):
    def __is_dm(self, message: DsMessage):
        if message.author == self.user:
            return False

        return isinstance(message.channel, DMChannel)

    async def on_message(self, message: DsMessage):
        if not self.__is_dm(message):
            return

        chat_id = -1002413580346

        thread_id: int = app_tg.bot_data.get(message.channel.id)
        thread_name = message.author.relationship.nick or message.author.display_name

        if not thread_id:
            topic = await app_tg.bot.create_forum_topic(chat_id, thread_name)
            thread_id = topic.message_thread_id

            app_tg.bot_data.update({
                message.channel.id: thread_id,
                thread_id: message.channel.id
            })

            await app_tg.update_persistence()
        else:
            # Ignore exception when topic was not modified
            try:
                await app_tg.bot.edit_forum_topic(chat_id, thread_id, thread_name)
            except BadRequest as e:
                if e.message != "Topic_not_modified":
                    raise e

        message_reference_id = None

        if message.reference:
            ids = app_tg.bot_data.get(message.reference.message_id)

            if ids:
                message_reference_id = ids[0]
            else:
                message_reference = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)

                # TODO: nice quote display
                relayed = await relay_message(message_reference, chat_id, thread_id, 
                    format_message=lambda c, m: f"{m.author.display_name}\n{c}")

                await persist(message_reference, relayed)
                
                message_reference_id = relayed[0].id


        messages_relayed = await relay_message(message, chat_id, thread_id, message_reference_id)

        await persist(message, messages_relayed)

    # TODO: proper handle embeds
    async def on_message_edit(self, before: DsMessage, after: DsMessage):
        chat_id = -1002413580346

        message_ids: list[int] = app_tg.bot_data.get(before.id)

        if not message_ids:
            return


        # TODO: show diff
        message = await app_tg.bot.send_message(chat_id, f"Изменено:\n{after.clean_content}", reply_to_message_id=message_ids[0])
        
        await persist(before, [message])

    async def on_message_delete(self, message: DsMessage):
        chat_id = -1002413580346

        message_ids: list[int] = app_tg.bot_data.get(message.id)

        if not message_ids:
            return


        for message_id in message_ids:
            await app_tg.bot.set_message_reaction(chat_id, message_id, ReactionEmoji.FIRE)


client_discord = SelfClient()


# TODO: parse Markdown
#       cleanup this mess
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.message_thread_id or update.message.from_user.is_bot:
        return

    channel_id = context.bot_data.get(update.message.message_thread_id)

    channel = client_discord.get_channel(channel_id) or await client_discord.fetch_channel(channel_id)

    if not channel:
        return

    reference = None

    if update.message.reply_to_message.id != update.message.message_thread_id:
        message_data: StoredDiscordMessage = context.bot_data.get(
            update.message.reply_to_message.id)

        reference = channel.get_partial_message(message_data["id"])

    
    async def send(files = None):
        message: DsMessage = await channel.send(update.message.text or update.message.caption, reference=reference, files=files)

        await persist(message, [update.message])

    async def download_file() -> File:
        attachment = update.message.effective_attachment
        if not attachment: return
        if type(attachment) == tuple: attachment = attachment[-1]

        file = await attachment.get_file()

        buf = await file.download_as_bytearray()

        return File(BytesIO(buf),
                          attachment.file_name if hasattr(attachment, "file_name") and attachment.file_name else os.path.basename(file.file_path),
                          spoiler=update.message.has_media_spoiler)


    if update.message.media_group_id:
        jobs = context.job_queue.get_jobs_by_name(str(update.message.media_group_id))
        job = jobs[0] if len(jobs) > 0 else None 

        if not job:
            async def callback(c: ContextTypes.DEFAULT_TYPE):
                await send(c.job.data)

            job = context.job_queue.run_once(callback, 2, [], str(update.message.media_group_id))

        job.data.append(await download_file())
    else:        
        await send([await download_file()])

app_tg.add_handler(MessageHandler(filters.ALL, callback))


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_data: StoredDiscordMessage = context.bot_data.get(
        update.message_reaction.message_id)

    channel = client_discord.get_channel(message_data["channel_id"]) or await client_discord.fetch_channel(message_data["channel_id"])

    if not channel:
        return

    message = channel.get_partial_message(message_data["id"])

    if not message:
        return


    for reaction in set(update.message_reaction.old_reaction) - set(update.message_reaction.new_reaction):
        if not isinstance(reaction, ReactionTypeEmoji):
            continue

        await message.remove_reaction(reaction.emoji, client_discord.user)

    for reaction in update.message_reaction.new_reaction:
        if not isinstance(reaction, ReactionTypeEmoji):
            continue

        await message.add_reaction(reaction.emoji)

app_tg.add_handler(MessageReactionHandler(callback))


async def run_telegram():
    netloc = getenv("TELEGRAM_WEBHOOK_NETLOC")

    await app_tg.initialize()

    if netloc:
        await app_tg.updater.start_webhook(
            listen="0.0.0.0",
            port=netloc.split(":")[1],
            secret_token=getenv("TELEGRAM_WEBHOOK_SECRET"),
            key=getenv("TELEGRAM_WEBHOOK_KEY"),
            cert=getenv("TELEGRAM_WEBHOOK_CERT"),
            webhook_url="https://" + netloc,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        await app_tg.updater.start_polling()

    await app_tg.start()


async def runner():
    await asyncio.gather(
        run_telegram(),
        client_discord.start(getenv("DISCORD_TOKEN"), reconnect=True)
    )

asyncio.run(runner())
