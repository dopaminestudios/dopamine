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


bot = Bot(
    command_prefix="!!",
    cogs_path="cogs",
    default_diagnostics=False,
    intents=intents
)

@bot.tree.context_menu(name="Get User ID")
async def get_user_id(interaction: discord.Interaction, message: discord.Message):
    author = message.author
    await interaction.response.send_message(
        f"{author.id}",
        ephemeral=True
    )

@bot.tree.context_menu(name="Get Message ID")
async def get_message_id(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_message(
        f"{message.id}",
        ephemeral=True
    )

@bot.tree.command(name="ls", description=".")
async def ls(interaction: discord.Interaction):
    if not await bot.is_owner(interaction.user):
        await interaction.response.send_message(":shushing_face:", ephemeral=True)
        return
    guilds = bot.guilds
    if not guilds:
        await interaction.response.send_message("I am not in any servers!", ephemeral=True)
        return

    server_list = ""
    for i, guild in enumerate(guilds, start=1):
        server_list += f"{i}. **{guild.name}** (ID: `{guild.id}`) - {guild.member_count} members\n"

    if len(server_list) > 2000:
        await interaction.response.send_message("The list is too long to send in one message!", ephemeral=True)
    else:
        await interaction.response.send_message(server_list, ephemeral=True)

if __name__ == "__main__":
    async def main_async():
        try:
            async with bot:
                await bot.start(TOKEN)
        except Exception as e:
            print(f"ERROR: Failed to start the bot: {e}")
            traceback.print_exc()


    asyncio.run(main_async())