import asyncio
import logging
from os import getenv
from platform import system
from collections import defaultdict
from itertools import chain
from dotenv import load_dotenv
from discord import Client, Message as DsMessage, DMChannel, GroupChannel, Attachment
from telegram import Update, Message as TgMessage, InputMedia, InputMediaPhoto, InputMediaVideo, InputMediaAudio
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackContext, PicklePersistence, filters
from telegram.constants import ReactionEmoji


load_dotenv()

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
        message_reference_id = message.reference and app_tg.bot_data.get(message.reference.message_id)[0]

        if thread_id is None:
            topic = await app_tg.bot.create_forum_topic(chat_id, message.author.name)
            thread_id = topic.message_thread_id

            app_tg.bot_data.update({
                message.author.id: thread_id,
                thread_id: message.author.id
            })

            await app_tg.update_persistence()
            

        media = defaultdict(list)

        # TODO: support plain text files (.txt, .lua, etc.)
        for attachment in message.attachments:
            content_type = attachment.content_type
            content_type = TRANSLATE_CONTENT_TYPE.get(content_type, content_type).split("/")[0]
            content_type = TRANSLATE_CONTENT_TYPE.get(content_type, content_type)

            match content_type:
                case "photo":
                    media[content_type].append(InputMediaPhoto(media=attachment.url, has_spoiler=attachment.is_spoiler(), caption=attachment.description))
                case "video":
                    media[content_type].append(InputMediaVideo(media=attachment.url, has_spoiler=attachment.is_spoiler()))
                case _:
                    media[content_type].append(InputMedia(content_type, media=attachment.url))


        messages_relayed: list[TgMessage] = [] 

        if message.clean_content:
            # TODO: parse Markdown
            messages_relayed.append(await app_tg.bot.send_message(chat_id, message.clean_content, message_thread_id=thread_id, reply_to_message_id=message_reference_id))

        for m in media.values():
            messages_relayed.extend(await app_tg.bot.send_media_group(chat_id, m, message_thread_id=thread_id, reply_to_message_id=message_reference_id))

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
    user_id = context.bot_data.get(update.message.message_thread_id)
    user = client_discord.get_user(user_id)

    message = await user.dm_channel.send(update.message.text + "\n-# Discord-over-Telegram")

    app_tg.bot_data.update({
        message.id: update.message.id,
        update.message.id: message.id,
    })

    await app_tg.update_persistence()

app_tg.add_handler(MessageHandler(filters.TEXT, callback))


async def run_telegram():
    netloc = getenv("TELEGRAM_WEBHOOK_NETLOC")

    await app_tg.initialize()

    await app_tg.updater.start_webhook(
        listen="0.0.0.0",
        port=netloc.split(":")[1],
        secret_token=getenv("TELEGRAM_WEBHOOK_SECRET"),
        key=getenv("TELEGRAM_WEBHOOK_KEY"),
        cert=getenv("TELEGRAM_WEBHOOK_CERT"),
        webhook_url="https://" + netloc
    )

    await app_tg.start()


async def runner():
    await asyncio.gather(
        run_telegram(),
        client_discord.start(getenv("DISCORD_TOKEN"), reconnect=True)
    )

asyncio.run(runner())