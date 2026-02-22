import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import contextlib
from config import BAN_PATH

class BanningCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.banned_users_cache: set[int] = set()
        self.banned_guilds_cache: set[int] = set()

        self.db_path = BAN_PATH
        self.db_pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=2)

        self.bot.tree.add_check(self.global_ban_check)

    async def cog_load(self):
        for _ in range(2):
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA cache_size=-64000;")
            await conn.execute("PRAGMA temp_store=MEMORY;")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS banned_guilds (
                    guild_id INTEGER PRIMARY KEY
                )
            """)
            await conn.commit()
            await self.db_pool.put(conn)

        async with self.acquire_db() as conn:
            async with conn.execute("SELECT user_id FROM banned_users") as cursor:
                async for row in cursor:
                    self.banned_users_cache.add(row[0])

            async with conn.execute("SELECT guild_id FROM banned_guilds") as cursor:
                async for row in cursor:
                    self.banned_guilds_cache.add(row[0])

    async def cog_unload(self):
        self.bot.tree.remove_check(self.global_ban_check)
        while not self.db_pool.empty():
            conn = self.db_pool.get_nowait()
            await conn.close()

    @contextlib.asynccontextmanager
    async def acquire_db(self):
        conn = await self.db_pool.get()
        try:
            yield conn
        finally:
            self.db_pool.put_nowait(conn)

    async def ban_user_api(self, user_id: int) -> bool:
        if user_id in self.banned_users_cache:
            return False

        self.banned_users_cache.add(user_id)

        async with self.acquire_db() as conn:
            await conn.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (user_id,))
            await conn.commit()
        return True

    async def ban_guild_api(self, guild_id: int) -> bool:
        if guild_id in self.banned_guilds_cache:
            return False

        self.banned_guilds_cache.add(guild_id)

        async with self.acquire_db() as conn:
            await conn.execute("INSERT OR IGNORE INTO banned_guilds (guild_id) VALUES (?)", (guild_id,))
            await conn.commit()

        guild = self.bot.get_guild(guild_id)
        if guild:
            await guild.leave()

        return True

    async def global_ban_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id and interaction.guild_id in self.banned_guilds_cache:
            await interaction.response.send_message(
                "This server is banned from using Dopamine. I will now leave the server. If you have any questions, email dopaminediscordbot@gmail.com.",
                ephemeral=True
            )
            if interaction.guild:
                await interaction.guild.leave()
            return False

        if interaction.user.id in self.banned_users_cache:
            await interaction.response.send_message(
                "You are banned from using Dopamine. If you have any questions, email dopaminediscordbot@gmail.com.",
                ephemeral=True
            )
            return False

        return True

    async def is_dev(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)

    @app_commands.command(name="devuserban", description=".")
    @app_commands.check(is_dev)
    @app_commands.describe(user_id="The ID of the user to ban")
    async def devuserban(self, interaction: discord.Interaction, user_id: str):
        try:
            target_id = int(user_id)
        except ValueError:
            return await interaction.response.send_message("Invalid ID format.", ephemeral=True)

        success = await self.ban_user_api(target_id)
        if success:
            await interaction.response.send_message(f"✅ User `{target_id}` has been banned.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ User `{target_id}` is already banned.", ephemeral=True)

    @app_commands.command(name="devguildban", description=".")
    @app_commands.check(is_dev)
    @app_commands.describe(guild_id="Select a guild to ban")
    async def devguildban(self, interaction: discord.Interaction, guild_id: str):
        try:
            target_id = int(guild_id)
        except ValueError:
            return await interaction.response.send_message("Invalid ID format.", ephemeral=True)

        success = await self.ban_guild_api(target_id)
        if success:
            await interaction.response.send_message(
                f"✅ Guild `{target_id}` has been banned. The bot will leave if present.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ Guild `{target_id}` is already banned.", ephemeral=True)

    @devguildban.autocomplete('guild_id')
    async def devguildban_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        choices = []
        for guild in self.bot.guilds:
            if guild.id in self.banned_guilds_cache:
                continue
            if current.lower() in guild.name.lower():
                choices.append(app_commands.Choice(name=f"{guild.name} ({guild.id})", value=str(guild.id)))

        return choices[:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(BanningCog(bot))