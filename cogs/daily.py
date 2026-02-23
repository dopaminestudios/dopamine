import asyncio
import logging
import random
import aiosqlite
from datetime import datetime, timedelta, time
import json

import discord
from discord import app_commands, Interaction, TextChannel
from discord.ext import commands, tasks

from config import DB_PATH, WORDS_PATH

logger = logging.getLogger('discord')
class DatabasePool:

    def __init__(self, db_path, size=5):
        self.db_path = db_path
        self.size = size
        self.connections = []
        self._pointer = 0

    async def init(self):
        for _ in range(self.size):
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            self.connections.append(conn)

    def get_connection(self) -> aiosqlite.Connection:
        conn = self.connections[self._pointer]
        self._pointer = (self._pointer + 1) % self.size
        return conn

    async def close(self):
        for conn in self.connections:
            await conn.close()


class DailyWords(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_pool = DatabasePool(DB_PATH)

        self.active_channels = set()
        self.word_list = []
        self.next_send_time = None

        self.init_data.start()

    def cog_unload(self):
        self.init_data.cancel()
        self.daily_task.cancel()

        asyncio.create_task(self.db_pool.close())

        self.word_list.clear()
        self.active_channels.clear()

        self.word_list = None
        self.active_channels = None
        self.next_send_time = None

    @tasks.loop(count=1)
    async def init_data(self):
        try:
            with open(WORDS_PATH, 'r') as f:
                data = json.load(f)
                self.word_list = list(data.keys())

            if not self.word_list:
                logger.warning(f"Warning: {WORDS_PATH} was loaded but appears to be empty.")
        except json.JSONDecodeError:
            logger.error(f"Error: {WORDS_PATH} is not a valid JSON file.")
        except FileNotFoundError:
            logger.critical(f"Error: {WORDS_PATH} not found.")
            return

        await self.db_pool.init()
        conn = self.db_pool.get_connection()

        await conn.execute("CREATE TABLE IF NOT EXISTS channels (channel_id INTEGER PRIMARY KEY)")
        await conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await conn.commit()

        async with conn.execute("SELECT channel_id FROM channels") as cursor:
            async for row in cursor:
                self.active_channels.add(row[0])

        async with conn.execute("SELECT value FROM settings WHERE key = 'next_send_time'") as cursor:
            row = await cursor.fetchone()
            if row:
                self.next_send_time = datetime.fromisoformat(row[0])
            else:
                now = datetime.now()
                self.next_send_time = datetime.combine(now.date() + timedelta(days=1), time(0, 1))
                await self.save_next_time()

        self.daily_task.start()

    async def save_next_time(self):
        conn = self.db_pool.get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ('next_send_time', self.next_send_time.isoformat())
        )
        await conn.commit()

    @tasks.loop(seconds=30)
    async def daily_task(self):
        if not self.next_send_time or not self.word_list:
            return

        now = datetime.now()
        if now >= self.next_send_time:
            word = random.choice(self.word_list)
            message = f"Today's Word: **{word}**"

            for channel_id in list(self.active_channels):
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(message)
                    except Exception as e:
                        print(f"Failed to send to {channel_id}: {e}")

            self.next_send_time = self.next_send_time + timedelta(hours=24) - timedelta(minutes=1)
            await self.save_next_time()

    daily = app_commands.Group(name="daily", description="Daily commands")
    words = app_commands.Group(name="words", description="Words commands", parent=daily)
    @words.command(name="start", description="Start daily messages in a channel.")
    @app_commands.describe(channel="The channel where you want the daily word to be posted (defaults to current channel).")
    async def daily_words_start(self, interaction: Interaction, channel: discord.TextChannel = None):
        channel_id = channel.id if channel else interaction.channel_id
        conn = self.db_pool.get_connection()

        if channel_id in self.active_channels:
            return await interaction.response.send_message("Feature is already active here!", ephemeral=True)

        await conn.execute("INSERT INTO channels (channel_id) VALUES (?)", (channel_id,))
        await conn.commit()
        self.active_channels.add(channel_id)

        await interaction.response.send_message(
            f"Daily words started! Next word at: {self.next_send_time.strftime('%Y-%m-%d %H:%M')}")

    @words.command(name="stop", description="Stop daily messages in a channel.")
    @app_commands.describe(
        channel="The channel where you want the daily word to be stopped (defaults to current channel).")
    async def daily_words_stop(self, interaction: Interaction, channel: discord.TextChannel = None):
        channel_id = channel.id if channel else interaction.channel_id
        conn = self.db_pool.get_connection()
        if channel_id not in self.active_channels:
            return await interaction.response.send_message("Feature isn't active in this channel.", ephemeral=True)

        await conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await conn.commit()
        self.active_channels.remove(channel_id)

        await interaction.response.send_message(content="Daily words stopped.")


async def setup(bot):
    await bot.add_cog(DailyWords(bot))