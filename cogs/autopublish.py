import discord
import aiosqlite
import asyncio
import logging
from discord.ext import commands
from discord import app_commands
from typing import List, Set

from config import APDB_PATH

from dopamineframework import dopamine_commands


class ConnectionPool:

    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.queue = asyncio.Queue(maxsize=max_connections)
        self.connections = []

    async def init_pool(self):
        for _ in range(self.max_connections):
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA busy_timeout=5000;")
            await conn.commit()

            self.connections.append(conn)
            await self.queue.put(conn)

    async def acquire(self) -> aiosqlite.Connection:
        return await self.queue.get()

    async def release(self, conn: aiosqlite.Connection):
        await self.queue.put(conn)

    async def close(self):
        for conn in self.connections:
            await conn.close()


class AutoPublish(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool = ConnectionPool(APDB_PATH, max_connections=5)
        self.cache: Set[int] = set()

    async def cog_load(self):
        await self.pool.init_pool()

        conn = await self.pool.acquire()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS autopublish_channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER
                )
            """)
            await conn.commit()

            async with conn.execute("SELECT channel_id FROM autopublish_channels") as cursor:
                rows = await cursor.fetchall()
                self.cache = {row[0] for row in rows}
        finally:
            await self.pool.release(conn)

    async def cog_unload(self):
        await self.pool.close()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return

        if message.channel.id not in self.cache:
            return

        if message.channel.type == discord.ChannelType.news:
            try:
                await message.publish()
            except discord.Forbidden:
                print(f"Missing permissions to publish in {message.channel.id}")
            except discord.HTTPException as e:
                print(f"Failed to publish message: {e}")

    autopublish_group = dopamine_commands.Group(name="autopublish",
                                           description="Manage auto-publishing for announcement channels.")

    @autopublish_group.command(name="enable", description="Enable auto-publishing for a specific channel.")
    @app_commands.describe(channel="The announcement channel to enable auto-publish for.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ap_enable(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not channel.is_news():
            return await interaction.response.send_message(f"{channel.mention} is not an Announcement channel!",
                                                           ephemeral=True)

        if channel.id in self.cache:
            return await interaction.response.send_message(f"Auto-publish is already enabled for {channel.mention}!",
                                                           ephemeral=True)

        conn = await self.pool.acquire()
        try:
            await conn.execute(
                "INSERT OR IGNORE INTO autopublish_channels (channel_id, guild_id) VALUES (?, ?)",
                (channel.id, interaction.guild.id)
            )
            await conn.commit()

            self.cache.add(channel.id)

            await interaction.response.send_message(f"Auto-publish enabled for {channel.mention}.", ephemeral=True)
        except Exception as e:
            print(f"DB Error on enable: {e}")
            await interaction.response.send_message("A database error occurred.", ephemeral=True)
        finally:
            await self.pool.release(conn)

    async def channel_autocomplete(self, interaction: discord.Interaction, current: str) -> List[
        app_commands.Choice[str]]:
        if not interaction.guild:
            return []

        choices = []
        for channel_id in self.cache:
            channel = interaction.guild.get_channel(channel_id) or await interaction.guild.fetch_channel(channel_id)
            if channel and current.lower() in channel.name.lower():
                choices.append(app_commands.Choice(name=channel.name, value=str(channel_id)))

            if len(choices) >= 25:
                break

        return choices

    @autopublish_group.command(name="disable", description="Disable auto-publishing for a channel.")
    @app_commands.autocomplete(channel_id=channel_autocomplete)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ap_disable(self, interaction: discord.Interaction, channel_id: str):
        try:
            cid = int(channel_id)
        except ValueError:
            return await interaction.response.send_message("Invalid channel ID selection.", ephemeral=True)

        if cid not in self.cache:
            return await interaction.response.send_message("Auto-publish is not enabled for this channel!",
                                                           ephemeral=True)

        conn = await self.pool.acquire()
        try:
            await conn.execute("DELETE FROM autopublish_channels WHERE channel_id = ?", (cid,))
            await conn.commit()

            self.cache.discard(cid)

            channel = interaction.guild.get_channel(cid) or await interaction.guild.fetch_channel(cid)
            name = channel.mention if channel else f"ID: {cid}"

            await interaction.response.send_message(f"Auto-publish disabled for {name}.", ephemeral=True)
        except Exception as e:
            print(f"DB Error on disable: {e}")
            await interaction.response.send_message("A database error occurred.", ephemeral=True)
        finally:
            await self.pool.release(conn)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoPublish(bot))