import asyncio
import io
import logging
import random
import aiosqlite
from datetime import datetime, timedelta, time
import json

import discord
from discord import app_commands, Interaction, TextChannel
from discord.ext import commands, tasks
from dopamineframework import mod_check, dopamine_commands

from config import DDB_PATH, WORDS_PATH


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
        self.db_pool = DatabasePool(DDB_PATH)

        self.active_word_channels = set()
        self.active_cat_channels = set()
        self.word_list = []
        self.next_send_time = None

        self.init_data.start()

    def cog_unload(self):
        self.init_data.cancel()
        self.daily_task.cancel()

        asyncio.create_task(self.db_pool.close())

        self.word_list.clear()
        self.active_word_channels.clear()
        self.active_cat_channels.clear()

        self.word_list = None
        self.active_word_channels = None
        self.active_cat_channels = None
        self.next_send_time = None

    @tasks.loop(count=1)
    async def init_data(self):
        try:
            with open(WORDS_PATH, 'r', encoding='utf-8') as f:
                self.word_list = [line.strip() for line in f if line.strip()]

            if not self.word_list:
                print(f"Warning: {WORDS_PATH} was loaded but appears to be empty.")

        except FileNotFoundError:
            print(f"Error: {WORDS_PATH} not found.")

        except Exception as e:
            print(f"Error reading {WORDS_PATH}: {e}")

        await self.db_pool.init()
        conn = self.db_pool.get_connection()

        await conn.execute(
            "CREATE TABLE IF NOT EXISTS word_channels (channel_id INTEGER PRIMARY KEY)")

        await conn.execute(
            "CREATE TABLE IF NOT EXISTS cat_channels (channel_id INTEGER PRIMARY KEY)")
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS cat_images (id INTEGER PRIMARY KEY AUTOINCREMENT, image_data BLOB)")

        await conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await conn.commit()

        async with conn.execute("SELECT channel_id FROM word_channels") as cursor:
            async for row in cursor:
                self.active_word_channels.add(row[0])

        async with conn.execute("SELECT channel_id FROM cat_channels") as cursor:
            async for row in cursor:
                self.active_cat_channels.add(row[0])

        async with conn.execute("SELECT value FROM settings WHERE key = 'next_send_time'") as cursor:
            row = await cursor.fetchone()
            if row:
                self.next_send_time = datetime.fromisoformat(row[0])
            else:
                now = datetime.now()
                self.next_send_time = datetime.combine(now.date() + timedelta(days=1), time(0, 0))
                await self.save_next_time()

        self.daily_task.start()

    async def save_next_time(self):
        conn = self.db_pool.get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ('next_send_time', self.next_send_time.isoformat())
        )
        await conn.commit()

    @commands.command(name="catadd", hidden=True)
    @commands.is_owner()
    async def catadd(self, ctx: commands.Context):
        if not ctx.message.attachments:
            return await ctx.send("Please attach at least one image.")

        valid_types = ['image/png', 'image/jpeg', 'image/gif']
        images_added = 0
        conn = self.db_pool.get_connection()

        for attachment in ctx.message.attachments:
            if attachment.content_type not in valid_types:
                await ctx.send(f"Skipping {attachment.filename}: Not a valid image type (PNG/JPEG/GIF).",
                               delete_after=10)
                continue

            try:
                image_bytes = await attachment.read()

                await conn.execute("INSERT INTO cat_images (image_data) VALUES (?)", (image_bytes,))
                images_added += 1
            except Exception as e:
                await ctx.send(f"Failed to add {attachment.filename}: {e}", delete_after=10)

        await conn.commit()
        await ctx.send(f"Successfully added {images_added} cat pics to the database!", delete_after=10)
        asyncio.sleep(10)
        await ctx.message.delete()

    @tasks.loop(seconds=30)
    async def daily_task(self):
        if not self.next_send_time or (not self.word_list and not self.active_cat_channels):
            return

        now = datetime.now()
        if now >= self.next_send_time:
            word = None
            if self.word_list and self.active_word_channels:
                word = random.choice(self.word_list)

            image_blob = None
            if self.active_cat_channels:
                conn = self.db_pool.get_connection()
                async with conn.execute("SELECT id FROM cat_images") as cursor:
                    ids = [row[0] for row in await cursor.fetchall()]

                if ids:
                    random_id = random.choice(ids)
                    async with conn.execute("SELECT image_data FROM cat_images WHERE id = ?", (random_id,)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            image_blob = row[0]

            message_word = f"Today's Word: **{word}**" if word else None

            async def send_to_channel(channel_id):
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                if not channel: return

                if channel_id in self.active_word_channels and message_word:
                    try:
                        await channel.send(message_word)
                    except Exception as e:
                        print(f"Failed to send WORD to {channel_id}: {e}")

                if channel_id in self.active_cat_channels and image_blob:
                    try:
                        file = discord.File(io.BytesIO(image_blob), filename="daily_cat.png")
                        await channel.send(content="Today's Cat Pic:", file=file)
                    except Exception as e:
                        print(f"Failed to send CAT to {channel_id}: {e}")

            all_target_channels = self.active_word_channels.union(self.active_cat_channels)

            await asyncio.gather(*(send_to_channel(cid) for cid in list(all_target_channels)))

            self.next_send_time = self.next_send_time + timedelta(hours=23)
            await self.save_next_time()

    daily = dopamine_commands.Group(name="daily", description="Daily automated messages.", permissions_preset="automation")

    words_group = app_commands.Group(name="words", description="Daily word commands", parent=daily)

    cat_group = app_commands.Group(name="cat", description="Daily cat image commands", parent=daily)

    @words_group.command(name="start", description="Start daily word messages in a channel.")
    @app_commands.describe(
        channel="The channel where you want the daily word to be posted (defaults to current channel).")
    async def daily_words_start(self, interaction: Interaction, channel: discord.TextChannel = None):
        channel_id = (channel.id if channel else interaction.channel_id)
        conn = self.db_pool.get_connection()

        if channel_id in self.active_word_channels:
            return await interaction.response.send_message("Feature is already active here!", ephemeral=True)

        await conn.execute("INSERT INTO word_channels (channel_id) VALUES (?)", (channel_id,))
        await conn.commit()
        self.active_word_channels.add(channel_id)

        unix_timestamp = int(self.next_send_time.timestamp())

        await interaction.response.send_message(
            f"Daily words started! Next word at: <t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)"
        )

    @words_group.command(name="stop", description="Stop daily word messages in a channel.")
    @app_commands.check(mod_check)
    @app_commands.describe(
        channel="The channel where you want the daily word to be stopped (defaults to current channel).")
    async def daily_words_stop(self, interaction: Interaction, channel: discord.TextChannel = None):
        channel_id = channel.id if channel else interaction.channel_id
        conn = self.db_pool.get_connection()
        if channel_id not in self.active_word_channels:
            return await interaction.response.send_message("Feature isn't active in this channel.", ephemeral=True)

        await conn.execute("DELETE FROM word_channels WHERE channel_id = ?", (channel_id,))
        await conn.commit()
        self.active_word_channels.remove(channel_id)

        await interaction.response.send_message(content="Daily words stopped.")

    @cat_group.command(name="start", description="Start daily cat pics in a channel.")
    @app_commands.check(mod_check)
    @app_commands.describe(
        channel="The channel where you want the daily cat image to be posted (defaults to current channel).")
    async def daily_cat_start(self, interaction: Interaction, channel: discord.TextChannel = None):
        channel_id = (channel.id if channel else interaction.channel_id)
        conn = self.db_pool.get_connection()

        if channel_id in self.active_cat_channels:
            return await interaction.response.send_message("Daily cat pics are already active here!", ephemeral=True)

        await conn.execute("INSERT INTO cat_channels (channel_id) VALUES (?)", (channel_id,))
        await conn.commit()
        self.active_cat_channels.add(channel_id)

        unix_timestamp = int(self.next_send_time.timestamp())

        await interaction.response.send_message(
            f"Daily cat pictures started! Next cat pic at: <t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)"
        )

    @cat_group.command(name="stop", description="Stop daily cat pics in a channel.")
    @app_commands.check(mod_check)
    @app_commands.describe(
        channel="The channel where you want the daily cat image to be stopped (defaults to current channel).")
    async def daily_cat_stop(self, interaction: Interaction, channel: discord.TextChannel = None):
        channel_id = channel.id if channel else interaction.channel_id
        conn = self.db_pool.get_connection()
        if channel_id not in self.active_cat_channels:
            return await interaction.response.send_message("Feature isn't active in this channel.", ephemeral=True)

        await conn.execute("DELETE FROM cat_channels WHERE channel_id = ?", (channel_id,))
        await conn.commit()
        self.active_cat_channels.remove(channel_id)

        await interaction.response.send_message(content="Daily cat pictures stopped.")

    @commands.command(name="del", hidden=True)
    @commands.is_owner()
    async def catwipe(self, ctx: commands.Context):
        conn = self.db_pool.get_connection()

        try:
            async with conn.execute("SELECT COUNT(*) FROM cat_images") as cursor:
                count = (await cursor.fetchone())[0]

            if count == 0:
                return await ctx.send("The cat database is already empty.")

            await conn.execute("DELETE FROM cat_images")
            await conn.execute("DELETE FROM sqlite_sequence WHERE name='cat_images'")
            await conn.commit()

            await ctx.send(f"Successfully wiped **{count}** images from the database.")

        except Exception as e:
            await ctx.send(f"An error occurred while wiping the database: {e}")

async def setup(bot):
    await bot.add_cog(DailyWords(bot))