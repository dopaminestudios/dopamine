import os
import logging
import asyncio
import discord
from config import TOKEN, LOGGING_DEBUG_MODE
from logging.handlers import RotatingFileHandler
from dopamineframework import Bot
import traceback

if not TOKEN:
    raise SystemExit("ERROR: Set DISCORD_TOKEN in a .env in root folder.")

logger = logging.getLogger("discord")
if LOGGING_DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    print("Running logger in DEBUG mode")
else:
    logger.setLevel(logging.INFO)
    print("Running logger in PRODUCTION mode")
log_path = os.path.join(os.path.dirname(__file__), "discord.log")
handler = RotatingFileHandler(
    filename=log_path,
    encoding="utf-8",
    mode="a",
    maxBytes=1 * 1024 * 1024,
    backupCount=5
)
logger.addHandler(handler)

log_format = '%(asctime)s||%(levelname)s: %(message)s'
date_format = '%H:%M:%S %d-%m'

formatter = logging.Formatter(log_format, datefmt=date_format)

handler.setFormatter(formatter)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

activity = discord.Streaming(name="✨ Testing v3.0.0 beta!", url="https://www.twitch.tv/dopaminediscordbot")

bot = Bot(
    command_prefix="!!",
    cogs_path="cogs",
    default_diagnostics=False,
    activity=activity,
    status=discord.Status.dnd,
    intents=intents
)

if __name__ == "__main__":
    async def main_async():
        try:
            async with bot:
                await bot.start(TOKEN)
        except Exception as e:
            print(f"ERROR: Failed to start the bot: {e}")
            traceback.print_exc()


    asyncio.run(main_async())