import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import asyncio
from collections import deque
from typing import Optional, Dict, Set, Tuple, Any
import time
from contextlib import asynccontextmanager
from config import SKDB_PATH
from dopamineframework import PrivateLayoutView


class ThresholdModal(discord.ui.Modal, title="Edit Skull Threshold"):
    def __init__(self, view: 'SkullboardDashboard'):
        super().__init__()
        self.view = view
        self.threshold_input = discord.ui.TextInput(
            label="Skull Threshold",
            placeholder="Enter a number (min 1)",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.threshold_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.threshold_input.value)
            if val < 1:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("Please enter a valid number greater than 0.",
                                                           ephemeral=True)

        await self.view.cog.update_guild_setting(interaction.guild.id, skull_threshold=val)

        self.view.build_layout()
        await interaction.response.edit_message(view=self.view)


class SkullboardDashboard(PrivateLayoutView):
    def __init__(self, user, cog, guild_id):
        super().__init__(user, timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.build_layout()

    def build_layout(self):
        self.clear_items()

        settings = self.cog.settings_cache.get(self.guild_id, {})
        is_enabled = bool(settings.get("enabled", 0))
        current_channel_id = settings.get("skullboard_channel_id")
        current_threshold = settings.get("skull_threshold", 3)

        channel_mention = f"<#{current_channel_id}>" if current_channel_id else "Not Set"

        container = discord.ui.Container()

        toggle_style = discord.ButtonStyle.secondary if is_enabled else discord.ButtonStyle.primary
        toggle_label = "Disable" if is_enabled else "Enable"
        toggle_btn = discord.ui.Button(label=toggle_label, style=toggle_style)
        toggle_btn.callback = self.toggle_callback

        container.add_item(discord.ui.Section(discord.ui.TextDisplay("## Skullboard Dashboard"), accessory=toggle_btn))

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(
            "A skullboard is like a Hall Of Shame for Discord messages. Users can react to a message with a 💀 and once it reaches the set threshold, Dopamine will post a copy of it in the channel you choose."))

        if is_enabled:
            container.add_item(discord.ui.TextDisplay(
                f"* **Current Channel:** {channel_mention}\n* **Current Threshold:** {current_threshold}"))
            container.add_item(discord.ui.Separator())

            threshold_btn = discord.ui.Button(label="Edit Threshold", style=discord.ButtonStyle.primary)
            threshold_btn.callback = self.threshold_callback

            channel_btn = discord.ui.Button(label="Edit Channel", style=discord.ButtonStyle.secondary)
            channel_btn.callback = self.channel_edit_callback

            row = discord.ui.ActionRow()
            row.add_item(threshold_btn)
            row.add_item(channel_btn)
            container.add_item(row)

        self.add_item(container)

    async def toggle_callback(self, interaction: discord.Interaction):
        settings = self.cog.settings_cache.get(self.guild_id, {})
        current_state = bool(settings.get("enabled", 0))
        current_channel = settings.get("skullboard_channel_id")

        if not current_state and not current_channel:
            await self.cog.update_guild_setting(self.guild_id, enabled=1)

            view = ChannelSelectView(self, self.user, self.cog, self.guild_id, interaction)
            return await interaction.response.edit_message(view=view)

        new_state = 0 if current_state else 1
        await self.cog.update_guild_setting(self.guild_id, enabled=new_state)

        self.build_layout()
        await interaction.response.edit_message(view=self)

    async def threshold_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ThresholdModal(self))

    async def channel_edit_callback(self, interaction: discord.Interaction):
        view = ChannelSelectView(self, self.user, self.cog, self.guild_id, interaction)
        await interaction.response.edit_message(view=view)


class ChannelSelectView(PrivateLayoutView):
    def __init__(self, view: 'SkullboardDashboard', user, cog, guild_id, parent_interaction: discord.Interaction):
        super().__init__(user, timeout=None)
        self.cog = cog
        self.view = view
        self.guild_id = guild_id
        self.parent_interaction = parent_interaction
        self.build_layout()

    def build_layout(self):
        container = discord.ui.Container()

        select = discord.ui.ChannelSelect(
            placeholder="Select a channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1
        )
        select.callback = self.select_callback

        row = discord.ui.ActionRow()
        row.add_item(select)

        container.add_item(discord.ui.TextDisplay("### Select a Channel"))
        container.add_item(discord.ui.TextDisplay("Choose the channel where you want the skullboard to appear:"))
        container.add_item(row)
        self.add_item(container)

    async def select_callback(self, interaction: discord.Interaction):
        selected_channel = interaction.data['values'][0]

        await self.cog.update_guild_setting(self.guild_id, skullboard_channel_id=int(selected_channel))

        self.view.build_layout()
        await self.parent_interaction.edit_original_response(view=self.view)


class SkullboardCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.SDB_PATH = SKDB_PATH
        self.SKULL_EMOJI = "💀"

        self.settings_cache: Dict[int, dict] = {}
        self.skull_posts_cache: Dict[int, Dict[int, int]] = {}

        self.skulled_messages: deque[int] = deque(maxlen=10000)
        self.guild_cooldowns: dict[int, float] = {}

        self.db_pool: Optional[asyncio.Queue[aiosqlite.Connection]] = None
        self._skullboard_tasks: Dict[int, asyncio.Task] = {}

    async def cog_load(self):
        await self.init_pools()
        await self.init_db()
        await self.populate_caches()
        if not self._cache_cleanup.is_running():
            self._cache_cleanup.start()

    async def cog_unload(self):
        self._cache_cleanup.cancel()

        for task in self._skullboard_tasks.values():
            if not task.done():
                task.cancel()

        if self._skullboard_tasks:
            await asyncio.gather(*self._skullboard_tasks.values(), return_exceptions=True)

        if self.db_pool is not None:
            while not self.db_pool.empty():
                try:
                    conn = self.db_pool.get_nowait()
                    await asyncio.wait_for(conn.close(), timeout=1.0)
                except (asyncio.QueueEmpty, asyncio.TimeoutError):
                    break

    async def init_pools(self, pool_size: int = 5):
        if self.db_pool is None:
            self.db_pool = asyncio.Queue(maxsize=pool_size)
            for _ in range(pool_size):
                conn = await aiosqlite.connect(
                    self.SDB_PATH,
                    timeout=5
                )
                await conn.execute("PRAGMA busy_timeout=5000")
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA synchronous=NORMAL")
                await conn.execute("PRAGMA foreign_keys=ON")
                await conn.commit()
                await self.db_pool.put(conn)

    @asynccontextmanager
    async def acquire_db(self):
        if self.db_pool is None:
            await self.init_pools()
        conn = await self.db_pool.get()
        try:
            yield conn
        finally:
            await self.db_pool.put(conn)

    async def init_db(self):
        async with self.acquire_db() as db:
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS guild_settings
                             (
                                 guild_id INTEGER PRIMARY KEY,
                                 skull_threshold INTEGER DEFAULT 3,
                                 skullboard_channel_id INTEGER,
                                 enabled INTEGER DEFAULT 0
                             )
                             """)
            try:
                await db.execute("ALTER TABLE guild_settings ADD COLUMN enabled INTEGER DEFAULT 0")
            except Exception:
                pass

            await db.execute("""
                             CREATE TABLE IF NOT EXISTS skull_posts
                             (
                                 guild_id INTEGER NOT NULL,
                                 source_message_id INTEGER NOT NULL,
                                 skullboard_message_id INTEGER NOT NULL,
                                 PRIMARY KEY (guild_id, source_message_id)
                             )
                             """)
            await db.commit()

    async def populate_caches(self):
        """Load all data from DB into memory."""
        self.settings_cache.clear()
        self.skull_posts_cache.clear()

        async with self.acquire_db() as db:
            async with db.execute("SELECT * FROM guild_settings") as cursor:
                rows = await cursor.fetchall()
                cols = [c[0] for c in cursor.description]
                for row in rows:
                    data = dict(zip(cols, row))
                    self.settings_cache[data["guild_id"]] = data

            async with db.execute("SELECT guild_id, source_message_id, skullboard_message_id FROM skull_posts") as cursor:
                rows = await cursor.fetchall()
                for gid, src_id, sb_id in rows:
                    if gid not in self.skull_posts_cache:
                        self.skull_posts_cache[gid] = {}
                    self.skull_posts_cache[gid][src_id] = sb_id

    async def get_guild_settings(self, guild_id: int) -> dict:
        """Fetch settings from cache, or create in DB and cache if missing."""
        if guild_id in self.settings_cache:
            return self.settings_cache[guild_id]

        async with self.acquire_db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id, enabled) VALUES (?, 0)",
                (guild_id,)
            )
            await db.commit()

            async with db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                cols = [c[0] for c in cursor.description]
                data = dict(zip(cols, row))

        self.settings_cache[guild_id] = data
        return data

    async def update_guild_setting(self, guild_id: int, **kwargs):
        """Update both DB and cache manually (Write-Through)."""
        if not kwargs:
            return

        settings = await self.get_guild_settings(guild_id)
        settings.update(kwargs)

        set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values()) + [guild_id]

        async with self.acquire_db() as db:
            await db.execute(f"UPDATE guild_settings SET {set_clause} WHERE guild_id = ?", values)
            await db.commit()

    async def upsert_skull_post(self, guild_id: int, source_id: int, skullboard_id: int):
        """Update both DB and cache manually for skull posts."""
        if guild_id not in self.skull_posts_cache:
            self.skull_posts_cache[guild_id] = {}
        self.skull_posts_cache[guild_id][source_id] = skullboard_id

        async with self.acquire_db() as db:
            await db.execute("""
                             INSERT INTO skull_posts (guild_id, source_message_id, skullboard_message_id)
                             VALUES (?, ?, ?) ON CONFLICT(guild_id, source_message_id) DO
                             UPDATE SET
                                 skullboard_message_id = excluded.skullboard_message_id
                             """, (guild_id, source_id, skullboard_id))
            await db.commit()

    async def delete_skull_post(self, guild_id: int, source_id: int):
        """Remove from both DB and cache manually."""
        if guild_id in self.skull_posts_cache:
            self.skull_posts_cache[guild_id].pop(source_id, None)

        async with self.acquire_db() as db:
            await db.execute(
                "DELETE FROM skull_posts WHERE guild_id = ? AND source_message_id = ?",
                (guild_id, source_id)
            )
            await db.commit()

    def get_skull_post(self, guild_id: int, source_id: int) -> Optional[int]:
        """Pure cache read for performance."""
        return self.skull_posts_cache.get(guild_id, {}).get(source_id)

    def get_source_from_skullboard(self, guild_id: int, skullboard_message_id: int) -> Optional[int]:
        """Reverse lookup in cache to find source ID from skullboard ID."""
        if guild_id not in self.skull_posts_cache:
            return None
        for src_id, sb_id in self.skull_posts_cache[guild_id].items():
            if sb_id == skullboard_message_id:
                return src_id
        return None

    @tasks.loop(minutes=5)
    async def _cache_cleanup(self):
        """Standard Cooldown cleanup."""
        current_time = time.time()
        to_remove_cd = [k for k, v in self.guild_cooldowns.items() if current_time - v > 600]
        for k in to_remove_cd:
            self.guild_cooldowns.pop(k, None)

    def build_skullboard_embed(self, message: discord.Message) -> discord.Embed:
        text = message.content.strip() if message.content else ""
        embed = discord.Embed(description=text, color=discord.Color(0xc7c7c7))
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.add_field(name="Jump to Message", value=f"[Click Here]({message.jump_url})", inline=False)
        embed.timestamp = message.created_at

        image_url = None
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                image_url = att.url
                break
        if not image_url:
            for e in message.embeds:
                if e.image and e.image.url: image_url = e.image.url; break
                if e.thumbnail and e.thumbnail.url: image_url = e.thumbnail.url; break
                if e.type == "image" and e.url: image_url = e.url; break
        if image_url:
            embed.set_image(url=image_url)
        return embed

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id != self.bot.user.id and str(payload.emoji) == self.SKULL_EMOJI:
            self._schedule_skullboard_update(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) == self.SKULL_EMOJI:
            self._schedule_skullboard_update(payload)

    def _schedule_skullboard_update(self, payload: discord.RawReactionActionEvent):
        mid = payload.message_id
        if mid in self._skullboard_tasks and not self._skullboard_tasks[mid].done():
            self._skullboard_tasks[mid].cancel()
        self._skullboard_tasks[mid] = self.bot.loop.create_task(self._process_skullboard_payload(payload))

    async def _process_skullboard_payload(self, payload: discord.RawReactionActionEvent):
        await asyncio.sleep(0.5)
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                guild = await self.bot.fetch_guild(payload.guild_id)
            if not guild: return

            settings = await self.get_guild_settings(guild.id)

            if not settings.get("enabled", 0):
                return

            sb_id = settings.get("skullboard_channel_id")
            if not sb_id: return

            source_id_from_sb = self.get_source_from_skullboard(guild.id, payload.message_id)

            if source_id_from_sb:
                source_msg_id = source_id_from_sb
                sb_chan = guild.get_channel(payload.channel_id) or await guild.fetch_channel(payload.channel_id)
                sb_msg = await sb_chan.fetch_message(payload.message_id)

                try:
                    url = sb_msg.embeds[0].fields[0].value.split("(")[1].split(")")[0]
                    parts = url.split("/")
                    source_channel_id = int(parts[-2])
                except (IndexError, ValueError):
                    return
            else:
                if payload.channel_id == sb_id:
                    return
                source_msg_id = payload.message_id
                source_channel_id = payload.channel_id

            try:
                src_chan = guild.get_channel(source_channel_id) or await guild.fetch_channel(source_channel_id)
                msg = await src_chan.fetch_message(source_msg_id)
            except discord.NotFound:
                return

            if msg.author.bot:
                existing = self.get_skull_post(guild.id, msg.id)
                if existing:
                    try:
                        sbc = guild.get_channel(sb_id)
                        sbm = await sbc.fetch_message(existing)
                        await sbm.delete()
                    except:
                        pass
                    await self.delete_skull_post(guild.id, msg.id)
                return

            skull_react_source = next((r for r in msg.reactions if str(r.emoji) == self.SKULL_EMOJI), None)
            count_source = skull_react_source.count if skull_react_source else 0

            existing_id = self.get_skull_post(guild.id, msg.id)
            count_sb = 0
            sbc = guild.get_channel(sb_id)
            if not sbc:
                try:
                    sbc = await guild.fetch_channel(sb_id)
                except discord.NotFound:
                    return

            if existing_id:
                try:
                    sbm = await sbc.fetch_message(existing_id)
                    skull_react_sb = next((r for r in sbm.reactions if str(r.emoji) == self.SKULL_EMOJI), None)
                    if skull_react_sb:
                        count_sb = skull_react_sb.count
                except discord.NotFound:
                    await self.delete_skull_post(guild.id, msg.id)
                    existing_id = None
                except:
                    pass

            total_count = count_source + count_sb

            if total_count < settings["skull_threshold"]:
                if existing_id:
                    try:
                        sbm = await sbc.fetch_message(existing_id)
                        await sbm.delete()
                    except:
                        pass
                    await self.delete_skull_post(guild.id, msg.id)
                return

            embed = self.build_skullboard_embed(msg)
            content_str = f"💀 **{total_count}** | {msg.channel.mention}"

            if existing_id:
                try:
                    sbm = await sbc.fetch_message(existing_id)
                    await sbm.edit(content=content_str, embed=embed)
                except discord.NotFound:
                    new_sbm = await sbc.send(content=content_str, embed=embed)
                    await self.upsert_skull_post(guild.id, msg.id, new_sbm.id)
            else:
                new_sbm = await sbc.send(content=content_str, embed=embed)
                await self.upsert_skull_post(guild.id, msg.id, new_sbm.id)

        finally:
            self._skullboard_tasks.pop(payload.message_id, None)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        existing = self.get_skull_post(payload.guild_id, payload.message_id)
        if not existing: return

        try:
            settings = await self.get_guild_settings(payload.guild_id)
            sbc = self.bot.get_channel(settings["skullboard_channel_id"])
            sbm = await sbc.fetch_message(existing)
            await sbm.delete()
        except:
            pass
        await self.delete_skull_post(payload.guild_id, payload.message_id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not after.guild: return
        existing = self.get_skull_post(after.guild.id, after.id)
        if not existing: return

        settings = await self.get_guild_settings(after.guild.id)
        skull_react = next((r for r in after.reactions if str(r.emoji) == self.SKULL_EMOJI), None)
        count_source = skull_react.count if skull_react else 0

        try:
            sbc = after.guild.get_channel(settings["skullboard_channel_id"])
            sbm = await sbc.fetch_message(existing)

            skull_react_sb = next((r for r in sbm.reactions if str(r.emoji) == self.SKULL_EMOJI), None)
            count_sb = skull_react_sb.count if skull_react_sb else 0

            total = count_source + count_sb

            embed = self.build_skullboard_embed(after)
            content_str = f"💀 {total} in {after.channel.mention}"
            await sbm.edit(content=content_str, embed=embed)
        except:
            pass

    @app_commands.command(name="skullboard", description="Configure the Skullboard via Dashboard")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def skullboard_dashboard(self, interaction: discord.Interaction):
        await self.get_guild_settings(interaction.guild.id)
        view = SkullboardDashboard(interaction.user, self, interaction.guild.id)
        await interaction.response.send_message(view=view)

    @commands.command(name="testskullboard")
    async def testskullboard(self, ctx: commands.Context):
        if ctx.author.id != 758576879715483719 or not ctx.message.reference: return

        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        settings = await self.get_guild_settings(ctx.guild.id)
        sb_id = settings.get("skullboard_channel_id")
        if not sb_id: return

        skull_react = next((r for r in ref.reactions if str(r.emoji) == self.SKULL_EMOJI), None)
        count = skull_react.count if skull_react else 0

        embed = self.build_skullboard_embed(ref)
        content_str = f"💀 {count} in {ref.channel.mention}"

        await self.bot.get_channel(sb_id).send(content=content_str, embed=embed)


async def setup(bot):
    await bot.add_cog(SkullboardCog(bot))