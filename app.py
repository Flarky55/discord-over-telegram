import asyncio
import logging
from os import getenv
from platform import system
from collections import defaultdict
from discord import Client, Message as DsMessage, DMChannel
from telegram import Update, Message as TgMessage, InputMedia, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackContext, PicklePersistence, filters
from telegram.constants import ReactionEmoji
from telegram.error import BadRequest


# https://github.com/aio-libs/aiodns?tab=readme-ov-file#note-for-windows-users
if system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# logging.getLogger("httpx").setLevel(logging.WARNING)

TRANSLATE_CONTENT_TYPE = {
    "application/pdf": "document",
    "text": "document",
    "image": "photo",
}

CONTENT_IN_CAPTION_MEDIA_TYPE = {"photo", "video"}


app_tg = (
    ApplicationBuilder()
          .token(getenv("TELEGRAM_TOKEN"))
          .persistence(PicklePersistence(filepath="data.pickle"))
          .build()
)


class SelfClient(Client):
    def __is_dm(self, message: DsMessage):
        if message.author == self.user:
            return False

        return isinstance(message.channel, DMChannel)
        # return \
        #     isinstance(message.channel, DMChannel) or isinstance(message.channel, GroupChannel)\
        #     or self.user in message.mentions or message.mention_everyone

    # TODO: support mentions, not only DMs
    async def on_message(self, message: DsMessage):
        if not self.__is_dm(message):
            return
        
        chat_id = -1002413580346

        thread_id = app_tg.bot_data.get(message.author.id)
        thread_name = message.author.relationship.nick or message.author.global_name
        message_reference_id = message.reference and app_tg.bot_data.get(message.reference.message_id)[0]

        if thread_id is None:
            topic = await app_tg.bot.create_forum_topic(chat_id, thread_name)
            thread_id = topic.message_thread_id

            app_tg.bot_data.update({
                message.author.id: thread_id,
                thread_id: message.author.id
            })

            await app_tg.update_persistence()
        else:
            # Ignore exception when topic was not modified
            try:
                await app_tg.bot.edit_forum_topic(chat_id, thread_id, thread_name)
            except BadRequest as e:
                if e.message != "Topic_not_modified":
                    raise e

        media = defaultdict(list)

        # TODO: support plain text files (.txt, .lua, etc.)
        for attachment in message.attachments:
            content_type = attachment.content_type
            content_type = TRANSLATE_CONTENT_TYPE.get(content_type, content_type).split("/")[0]
            content_type = TRANSLATE_CONTENT_TYPE.get(content_type, content_type)

            match content_type:
                case "photo":
                    media[content_type].append(InputMediaPhoto(
                        media=attachment.url, has_spoiler=attachment.is_spoiler(),
                        caption=attachment.description or message.clean_content, show_caption_above_media=attachment.description is None)
                    )
                case "video":
                    media[content_type].append(InputMediaVideo(
                        media=attachment.url, has_spoiler=attachment.is_spoiler(),
                        caption=message.clean_content, show_caption_above_media=True)
                    )
                case _:
                    media[content_type].append(InputMedia(
                        content_type, media=attachment.url)
                    )


        messages_relayed: list[TgMessage] = []


        if message.clean_content and not (sum(len(l) for l in media.values()) == 1 and set(media.keys()) <= CONTENT_IN_CAPTION_MEDIA_TYPE):
            # TODO: parse Markdown
            messages_relayed.append(
                await app_tg.bot.send_message(chat_id, message.clean_content, message_thread_id=thread_id, reply_to_message_id=message_reference_id)
            )

        for m in media.values():
            messages_relayed.extend(
                await app_tg.bot.send_media_group(chat_id, m, message_thread_id=thread_id, reply_to_message_id=message_reference_id)
            )

        app_tg.bot_data.update({
            message.id: [m.id for m in messages_relayed],
            **{m.id: message.id for m in messages_relayed}
        })

        await app_tg.update_persistence()

            
    async def on_message_edit(self, before: DsMessage, after: DsMessage):
        chat_id = -1002413580346

        message_ids = app_tg.bot_data.get(before.id)
        
        if message_ids is None:
            return

        # TODO: show diff
        await app_tg.bot.send_message(chat_id, f"Изменено:\n{after.clean_content}", reply_to_message_id=message_ids[0])

    async def on_message_delete(self, message: DsMessage):
        chat_id = -1002413580346

        message_ids = app_tg.bot_data.get(message.id)

        if message_ids is None:
            return
        
        for message_id in message_ids:
            await app_tg.bot.set_message_reaction(chat_id, message_id, ReactionEmoji.FIRE)


client_discord = SelfClient()


# TODO: parse Markdown
async def callback(update: Update, context: CallbackContext):
    user = client_discord.get_user(
        context.bot_data.get(update.message.message_thread_id))

    reference = update.message.reply_to_message.text and user.dm_channel.get_partial_message(
        context.bot_data.get(update.message.reply_to_message.id))

    message: DsMessage = await user.dm_channel.send(update.message.text, reference=reference)

    app_tg.bot_data.update({
        message.id: update.message.id,
        update.message.id: message.id,
    })

    await app_tg.update_persistence()

app_tg.add_handler(MessageHandler(filters.TEXT, callback))


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
            webhook_url="https://" + netloc
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