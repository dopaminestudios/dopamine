import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import io
import contextlib
from collections import deque

from config import DP_PATH


class ConnectionPool:
    def __init__(self, path: str, size: int = 5):
        self.path = path
        self.size = size
        self.pool = asyncio.Queue()

    async def init(self):
        for _ in range(self.size):
            conn = await aiosqlite.connect(self.path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await self.pool.put(conn)

    @contextlib.asynccontextmanager
    async def acquire(self):
        conn = await self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put_nowait(conn)


class CallSession:
    def __init__(self, chan_a, chan_b, user_a, user_b):
        self.chan_a = chan_a
        self.chan_b = chan_b
        self.user_a = user_a
        self.user_b = user_b
        self.history = deque(maxlen=21)
        self.timeout_task = None


def get_ordinal(n: int) -> str:
    """Helper to convert an integer to its ordinal string representation."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')


class ReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def extract_ids(self, embed: discord.Embed) -> dict:
        """Dynamically fetches target IDs directly from the report embed to avoid memory leaks."""
        data = {}
        for field in embed.fields:
            if field.name == "Reported User ID":
                data['author_id'] = int(field.value)
            elif field.name == "Reported Guild ID":
                data['author_guild_id'] = int(field.value)
            elif field.name == "Reporter User ID":
                data['reporter_id'] = int(field.value)
            elif field.name == "Reporter Guild ID":
                data['reporter_guild_id'] = int(field.value)
        return data

    @discord.ui.button(label="Warn Author", style=discord.ButtonStyle.secondary, custom_id="dp_warn_author")
    async def warn_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        ids = self.extract_ids(interaction.message.embeds[0])
        cog = interaction.client.get_cog("DiscordPhone")
        if cog:
            await cog.increment_stat("users", ids['author_id'], "warned")
            user = interaction.client.get_user(ids['author_id'])
            if user:
                try:
                    await user.send("You have been warned regarding your conduct on Discordphone.")
                except discord.Forbidden:
                    pass
        await interaction.response.send_message("Author warned. (Stats updated and DM attempted)", ephemeral=True)

    @discord.ui.button(label="Ban Author", style=discord.ButtonStyle.danger, custom_id="dp_ban_author")
    async def ban_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        ids = self.extract_ids(interaction.message.embeds[0])
        banning_cog = interaction.client.get_cog("BanningCog")
        if banning_cog:
            await banning_cog.ban_user_api(ids['author_id'])
            await interaction.response.send_message("Author banned from using the bot.", ephemeral=True)
        else:
            await interaction.response.send_message("BanningCog not found!", ephemeral=True)

    @discord.ui.button(label="Ban Author Guild", style=discord.ButtonStyle.danger, custom_id="dp_ban_author_guild")
    async def ban_author_guild(self, interaction: discord.Interaction, button: discord.ui.Button):
        ids = self.extract_ids(interaction.message.embeds[0])
        banning_cog = interaction.client.get_cog("BanningCog")
        if banning_cog:
            await banning_cog.ban_guild_api(ids['author_guild_id'])
            await interaction.response.send_message("Author's Guild has been banned.", ephemeral=True)

    @discord.ui.button(label="Warn Reporter", style=discord.ButtonStyle.secondary, custom_id="dp_warn_reporter")
    async def warn_reporter(self, interaction: discord.Interaction, button: discord.ui.Button):
        ids = self.extract_ids(interaction.message.embeds[0])
        cog = interaction.client.get_cog("DiscordPhone")
        if cog:
            await cog.increment_stat("users", ids['reporter_id'], "warned")
            user = interaction.client.get_user(ids['reporter_id'])
            if user:
                try:
                    await user.send("You have been warned regarding your conduct/false reporting on Discordphone.")
                except discord.Forbidden:
                    pass
        await interaction.response.send_message("Reporter warned.", ephemeral=True)

    @discord.ui.button(label="Ban Reporter", style=discord.ButtonStyle.danger, custom_id="dp_ban_reporter")
    async def ban_reporter(self, interaction: discord.Interaction, button: discord.ui.Button):
        ids = self.extract_ids(interaction.message.embeds[0])
        banning_cog = interaction.client.get_cog("BanningCog")
        if banning_cog:
            await banning_cog.ban_user_api(ids['reporter_id'])
            await interaction.response.send_message("Reporter banned from using the bot.", ephemeral=True)

    @discord.ui.button(label="Ban Reporter Guild", style=discord.ButtonStyle.danger, custom_id="dp_ban_reporter_guild")
    async def ban_reporter_guild(self, interaction: discord.Interaction, button: discord.ui.Button):
        ids = self.extract_ids(interaction.message.embeds[0])
        banning_cog = interaction.client.get_cog("BanningCog")
        if banning_cog:
            await banning_cog.ban_guild_api(ids['reporter_guild_id'])
            await interaction.response.send_message("Reporter's Guild has been banned.", ephemeral=True)


class ReportModal(discord.ui.Modal, title='Report Message'):
    reason = discord.ui.TextInput(
        label='Reason for report',
        style=discord.TextStyle.paragraph,
        placeholder="Why are you reporting this message/conversation?"
    )

    def __init__(self, cog, target_msg_data: dict, call_session: CallSession):
        super().__init__()
        self.cog = cog
        self.target_msg_data = target_msg_data
        self.call_session = call_session

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Thank you for your report and for keeping the community safe! Your report will be processed by a moderator at Dopamine Studios shorty and appropriate action will be taken.",
                                                ephemeral=True)
        await self.cog.process_report(interaction, self.reason.value, self.target_msg_data, self.call_session)


class DiscordPhone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = ConnectionPool(DP_PATH, size=5)

        self.users_cache = {}
        self.guilds_cache = {}
        self.settings_cache = {}

        self.waiting_channel = None
        self.waiting_user = None
        self.active_calls = {}
        self.message_map = {}

        self.report_ctx_menu = app_commands.ContextMenu(
            name="Report Message",
            callback=self.report_context
        )
        self.bot.tree.add_command(self.report_ctx_menu)

    async def cog_load(self):
        self.bot.loop.create_task(self.init_db())
        self.bot.add_view(ReportView())

    async def cog_unload(self):
        self.bot.tree.remove_command(self.report_ctx_menu.name, type=self.report_ctx_menu.type)

    async def init_db(self):
        await self.pool.init()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, reported INTEGER DEFAULT 0, created INTEGER DEFAULT 0, warned INTEGER DEFAULT 0
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guilds (
                    id INTEGER PRIMARY KEY, reported INTEGER DEFAULT 0, created INTEGER DEFAULT 0, warned INTEGER DEFAULT 0
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT
                )
            """)
            await conn.commit()

            async with conn.execute("SELECT id, reported, created, warned FROM users") as cursor:
                async for row in cursor:
                    self.users_cache[row[0]] = {"reported": row[1], "created": row[2], "warned": row[3]}

            async with conn.execute("SELECT id, reported, created, warned FROM guilds") as cursor:
                async for row in cursor:
                    self.guilds_cache[row[0]] = {"reported": row[1], "created": row[2], "warned": row[3]}

            async with conn.execute("SELECT key, value FROM settings") as cursor:
                async for row in cursor:
                    if row[0] == "log_channel":
                        self.settings_cache["log_channel"] = int(row[1])

    async def increment_stat(self, table: str, id_: int, field: str):
        """Write-through cache: Updates memory first, then queues a DB update task."""
        cache = self.users_cache if table == "users" else self.guilds_cache
        if id_ not in cache:
            cache[id_] = {"reported": 0, "created": 0, "warned": 0}

        cache[id_][field] += 1

        self.bot.loop.create_task(self._db_write(table, id_, field, cache[id_][field]))

    async def _db_write(self, table: str, id_: int, field: str, new_val: int):
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {table} (id, reported, created, warned)
                VALUES (?, 0, 0, 0)
                ON CONFLICT(id) DO UPDATE SET {field} = ?
            """, (id_, new_val))
            await conn.commit()

    async def get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        webhooks = await channel.webhooks()
        for wh in webhooks:
            if wh.name == "Dopamine":
                return wh
        return await channel.create_webhook(name="Dopamine")

    async def timeout_handler(self, call: CallSession):
        """Hard 30-minute inactivity hangup."""
        await asyncio.sleep(1800)
        await self.end_call(call, "☎️ Call disconnected due to 30 minutes of inactivity.")

    async def end_call(self, call: CallSession, reason: str):
        if call.timeout_task:
            call.timeout_task.cancel()

        self.active_calls.pop(call.chan_a, None)
        self.active_calls.pop(call.chan_b, None)

        chan_a = self.bot.get_channel(call.chan_a)
        chan_b = self.bot.get_channel(call.chan_b)

        if chan_a: await chan_a.send(reason)
        if chan_b: await chan_b.send(reason)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id not in self.active_calls:
            return

        call = self.active_calls[message.channel.id]
        peer_channel_id = call.chan_b if call.chan_a == message.channel.id else call.chan_a
        peer_channel = self.bot.get_channel(peer_channel_id)
        if not peer_channel:
            return

        if call.timeout_task:
            call.timeout_task.cancel()
        call.timeout_task = self.bot.loop.create_task(self.timeout_handler(call))

        content = discord.utils.escape_mentions(message.content)

        for sticker in message.stickers:
            content += f"\n{sticker.url}"

        embeds = []
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            emb = discord.Embed(description=ref.content)
            emb.set_author(
                name=f"Replying to {ref.author.display_name}",
                icon_url=ref.author.display_avatar.url if ref.author.display_avatar else None
            )
            embeds.append(emb)

        files = []
        for att in message.attachments:
            files.append(discord.File(io.BytesIO(await att.read()), filename=att.filename))

        wh = await self.get_webhook(peer_channel)
        if not wh:
            return

        sent_msg = await wh.send(
            content=content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url if message.author.display_avatar else None,
            embeds=embeds,
            files=files,
            allowed_mentions=discord.AllowedMentions.none(),
            wait=True
        )

        msg_data = {
            "content": content,
            "author_name": message.author.display_name,
            "author_id": message.author.id,
            "guild_id": message.guild.id,
            "timestamp": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        call.history.append(msg_data)
        self.message_map[sent_msg.id] = msg_data

    dp_group = app_commands.Group(name="discordphone", description="Discordphone core commands")

    @dp_group.command(name="start", description="Start a Discordphone call")
    async def start(self, interaction: discord.Interaction):
        if interaction.channel.id in self.active_calls:
            return await interaction.response.send_message("This channel is already in a call!", ephemeral=True)

        if self.waiting_channel and self.waiting_channel.id == interaction.channel.id:
            return await interaction.response.send_message("This channel is already in the matchmaking queue!",
                                                           ephemeral=True)

        await interaction.response.send_message("<a:loading:1475121732108025929> Putting you in the queue...", ephemeral=False)

        log_chan_id = self.settings_cache.get("log_channel")
        log_channel = self.bot.get_channel(log_chan_id) if log_chan_id else None
        if log_channel:
            await log_channel.send(f"🎙️ Channel {interaction.channel.id} from {interaction.guild.name} joined queue.")

        if self.waiting_channel is None:
            self.waiting_channel = interaction.channel
            self.waiting_user = interaction.user
        else:
            chan_a = self.waiting_channel
            user_a = self.waiting_user
            chan_b = interaction.channel
            user_b = interaction.user

            self.waiting_channel = None
            self.waiting_user = None

            call = CallSession(chan_a.id, chan_b.id, user_a, user_b)
            self.active_calls[chan_a.id] = call
            self.active_calls[chan_b.id] = call
            call.timeout_task = self.bot.loop.create_task(self.timeout_handler(call))

            rules_str = "[Rules](https://example.com/rules.pdf)"
            safe_msg = f"Connected! Please stay safe, and remember you can report problematic messages via right-clicking the message -> Apps -> 'Report Message' or using `/discordphone report`. By continuing, you agree to the {rules_str}. If you don't agree, stop using the bot."

            await chan_a.send(f"{user_a.mention} {safe_msg}")
            await chan_b.send(f"{user_b.mention} {safe_msg}")

            if log_channel:
                await log_channel.send(f"📞 Connected channel {chan_a.id} with {chan_b.id}.")

    @dp_group.command(name="hangup", description="Hangup the active Discordphone call")
    async def hangup(self, interaction: discord.Interaction):
        if self.waiting_channel and self.waiting_channel.id == interaction.channel.id:
            self.waiting_channel = None
            self.waiting_user = None
            return await interaction.response.send_message("Removed from queue.", ephemeral=False)

        if interaction.channel.id not in self.active_calls:
            return await interaction.response.send_message("You are not currently in a call.", ephemeral=True)

        call = self.active_calls[interaction.channel.id]
        await interaction.response.send_message("Hanging up...")
        await self.end_call(call, f"Call disconnected by {interaction.user.display_name}.")

    @dp_group.command(name="report", description="Report the current conversation")
    async def report_slash(self, interaction: discord.Interaction):
        if interaction.channel.id not in self.active_calls:
            return await interaction.response.send_message("No active call to report.", ephemeral=True)

        call = self.active_calls[interaction.channel.id]
        msg_data = next((m for m in reversed(call.history) if m['author_id'] != interaction.user.id), None)

        if not msg_data:
            return await interaction.response.send_message("No messages from the other side yet.", ephemeral=True)

        await interaction.response.send_modal(ReportModal(self, msg_data, call))

    async def report_context(self, interaction: discord.Interaction, message: discord.Message):
        if interaction.channel.id not in self.active_calls:
            return await interaction.response.send_message("No active call.", ephemeral=True)

        call = self.active_calls[interaction.channel.id]
        msg_data = self.message_map.get(message.id)

        if not msg_data:
            msg_data = next((m for m in reversed(call.history) if m['author_id'] != interaction.user.id), None)

        if not msg_data:
            return await interaction.response.send_message("Could not identify the message source.", ephemeral=True)

        await interaction.response.send_modal(ReportModal(self, msg_data, call))

    async def process_report(self, interaction: discord.Interaction, reason: str, target_msg: dict,
                             session: CallSession):
        reporter_id = interaction.user.id
        reporter_guild_id = interaction.guild.id
        author_id = target_msg['author_id']
        author_guild_id = target_msg['guild_id']

        await self.increment_stat("users", reporter_id, "created")
        await self.increment_stat("guilds", reporter_guild_id, "created")
        await self.increment_stat("users", author_id, "reported")
        await self.increment_stat("guilds", author_guild_id, "reported")

        author_reported = self.users_cache[author_id]["reported"]
        ordinal = get_ordinal(author_reported)

        embed = discord.Embed(
            title=f"{target_msg['author_name']} from {author_guild_id} has been reported for the #{ordinal} time",
            color=discord.Color.red(),
            description=(
                f"**Warns for Author:** {self.users_cache[author_id]['warned']}\n"
                f"**Reports created by Reporter:** {self.users_cache[reporter_id]['created']}\n"
                f"**Warns for Reporter:** {self.users_cache[reporter_id]['warned']}\n\n"
                f"**Reason for Report:** {reason}"
            )
        )
        embed.add_field(name="Reported User ID", value=str(author_id))
        embed.add_field(name="Reported Guild ID", value=str(author_guild_id))
        embed.add_field(name="Reporter User ID", value=str(reporter_id))
        embed.add_field(name="Reporter Guild ID", value=str(reporter_guild_id))

        content = ""
        for m in session.history:
            content += f"[{m['timestamp']}] {m['author_name']} ({m['author_id']}) from {m['guild_id']}: {m['content']}\n"

        file = discord.File(io.BytesIO(content.encode('utf-8')), filename="report_context.txt")

        log_chan_id = self.settings_cache.get("log_channel")
        if log_chan_id:
            log_chan = self.bot.get_channel(log_chan_id)
            if log_chan:
                await log_chan.send(embed=embed, file=file, view=ReportView())

    @app_commands.command(name="zt", description=".")
    @app_commands.default_permissions(administrator=True)
    async def zt_command(self, interaction: discord.Interaction):
        self.settings_cache["log_channel"] = interaction.channel.id

        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                ("log_channel", str(interaction.channel.id), str(interaction.channel.id)))
            await conn.commit()

        await interaction.response.send_message("Log and Reports channel has been set to this channel.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DiscordPhone(bot))