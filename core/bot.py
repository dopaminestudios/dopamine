import os
import time
import signal
import asyncio
import logging
import discord
from discord.ext import commands
from utils.log import LoggingManager
from core.commands_registry import CommandRegistry
from VERSION import bot_version
from config import TOKEN
import os
import sys

logger = logging.getLogger("discord")

class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix="!!",
            help_command=None,
            member_cache_flags=discord.MemberCacheFlags(voice=True, joined=False),
            chunk_guilds_at_startup=False,
            guild_ready_timeout=0,
            *args, **kwargs
        )
        self.process_start_time = time.time()
        self.registry = CommandRegistry(self)
        self.start_time = None

    async def setup_hook(self):
        self.logger = LoggingManager()

        cogs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cogs")
        if os.path.exists(cogs_dir):
            for filename in os.listdir(cogs_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    extension = f"cogs.{filename[:-3]}"
                    try:
                        await self.load_extension(extension)
                        print(f"> Loaded {extension} Successfully")
                    except Exception as e:
                        print(f"ERROR: Failed to load {extension}: {e}")
        else:
            print("WARNING: 'cogs' directory not found.")

        status = await self.registry.smart_sync()
        print(status)

        for s in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(
                s, lambda: asyncio.create_task(self.signal_handler())
            )

    async def signal_handler(self):
        print("\nBot shutdown requested...")
        extensions = list(self.extensions.keys())
        for extension in extensions:
            try:
                await self.unload_extension(extension)
                print(f"> Unloaded {extension} successfully")
            except Exception as e:
                print(f"Error unloading {extension}: {e}")

        print("👋 Goodbye!")
        await self.close()

    async def restart_bot(self):
        print()
        print("Restarting bot...")
        await self.signal_handler()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def on_ready(self):
        if self.owner_id is None:
            app_info = await self.application_info()
            if app_info.team:
                self.owner_id = app_info.team.owner_id
            else:
                self.owner_id = app_info.owner.id

        owner_user = self.get_user(self.owner_id) or await self.fetch_user(self.owner_id)
        owner_user_name = owner_user.name

        print(f"---------------------------------------------------")
        print(f"Powered by Dopamine Framework {bot_version}")
        print()
        print(f"Bot ready: {self.user} (ID: {self.user.id})")
        print(f"Bot Owner identified: {owner_user_name}")
        print(f"---------------------------------------------------")

        logger.info("")
        logger.info(f"---------------------------------------------------")
        logger.info(f"Powered by Dopamine Framework {bot_version}")
        logger.info(f"Bot ready: {self.user} (ID: {self.user.id})")
        logger.info(f"Bot Owner identified: {owner_user_name}")
        logger.info(f"---------------------------------------------------")
        logger.info("")

        await self.change_presence(
            status=discord.Status.dnd,
            activity=discord.CustomActivity(name="✨ Testing v3.0.0-beta!")
        )
        self.start_time = time.time()