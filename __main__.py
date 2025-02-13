import asyncio
import logging
from dotenv import load_dotenv
from os import getenv
from discord import Client, Message as DsMessage, DMChannel, GroupChannel
from telegram import Update, Message as TgMessage
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PicklePersistence
from telegram.constants import ReactionEmoji
from platform import system


load_dotenv()

# https://github.com/aio-libs/aiodns?tab=readme-ov-file#note-for-windows-users
if system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# logging.getLogger("httpx").setLevel(logging.WARNING)


app_tg = ApplicationBuilder().token(getenv("TELEGRAM_TOKEN")).persistence(PicklePersistence(filepath="data.pickle")).build()


async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(context._chat_id)

app_tg.add_handler(CommandHandler("debug", debug))


class SelfClient(Client):
    def __is_valid_message(self, message: DsMessage):
        if message.author == self.user:
            return False

        return \
            isinstance(message.channel, DMChannel) or isinstance(message.channel, GroupChannel)\
            or self.user in message.mentions or message.mention_everyone


    async def on_message(self, message: DsMessage):
        if not self.__is_valid_message(message):
            return
        
        chat_id = -1002413580346
        
        thread_id_key = f"{message.author.id}:thread_id"
        thread_id = app_tg.bot_data.get(thread_id_key)

        if thread_id is None:
            topic = await app_tg.bot.create_forum_topic(chat_id, message.author.name)
            thread_id = topic.message_thread_id

            app_tg.bot_data[thread_id_key] = thread_id

            await app_tg.update_persistence()

        message_relay = await app_tg.bot.send_message(chat_id, message.clean_content, message_thread_id=thread_id)

        app_tg.bot_data[message.id] = message_relay.id

            
    async def on_message_edit(self, before: DsMessage, after: DsMessage):
        chat_id = -1002413580346

        message_id_key = before.id
        message_id = app_tg.bot_data.get(message_id_key)
        
        if message_id is None:
            return

        await app_tg.bot.send_message(chat_id, f"Изменено:\n{after.clean_content}", reply_to_message_id=message_id)

    async def on_message_delete(self, message: DsMessage):
        chat_id = -1002413580346

        message_id_key = message.id
        message_id = app_tg.bot_data.get(message_id_key)
        
        if message_id is None:
            return
        
        await app_tg.bot.set_message_reaction(chat_id, message_id, ReactionEmoji.FIRE)


client_discord = SelfClient()


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