import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import aiohttp
import io
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from PIL import Image, ImageDraw, ImageFont, ImageOps
from dopamineframework import PrivateLayoutView
from config import LEDB_PATH, LEAVECARD_PATH, BOLDFONT_PATH, MEDIUMFONT_PATH
from dopamineframework import mod_check

async def fetch_image(session: aiohttp.ClientSession, url: str) -> Optional[bytes]:
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    except:
        return None

class LeaveTextModal(discord.ui.Modal, title="Customise Leave Text"):
    message = discord.ui.TextInput(
        label="Message Content",
        style=discord.TextStyle.paragraph,
        placeholder="Goodbye, {member.name}. You will be missed.",
        required=True,
        max_length=2000
    )

    def __init__(self, current_msg: str, callback_func):
        super().__init__()
        self.callback_func = callback_func
        self.message.default = current_msg or "Goodbye, {member.name}. We will miss you."


    async def on_submit(self, interaction: discord.Interaction):
        await self.callback_func(interaction, self.message.value)


class LeaveImageModal(discord.ui.Modal, title="Customise Goodbye Card"):
    img_url = discord.ui.TextInput(
        label="Background Image URL",
        placeholder="https://example.com/image.png (Leave empty for default)",
        required=False
    )
    line1 = discord.ui.TextInput(
        label="Line 1 Text (Big)",
        placeholder="Type here...",
        required=False,
        max_length=40
    )
    line2 = discord.ui.TextInput(
        label="Line 2 Text (Small)",
        placeholder="Type here...",
        required=False,
        max_length=50
    )

    def __init__(self, data: dict, callback_func):
        super().__init__()
        self.callback_func = callback_func
        self.img_url.default = data.get("image_url") or ""
        self.line1.default = data.get("image_line1") or "Goodbye {member.name}"
        self.line2.default = data.get("image_line2") or "We hope to see you again!"

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback_func(interaction, self.img_url.value, self.line1.value, self.line2.value)


class ChannelSelectView(PrivateLayoutView):
    def __init__(self, callback_func, user):
        super().__init__(user, timeout=30)
        self.callback_func = callback_func
        self.build_layout()

    def build_layout(self):
        container = discord.ui.Container()
        self.select = discord.ui.ChannelSelect(placeholder="Select a channel...", min_values=1, max_values=1)
        self.select.callback = self.select_channel
        container.add_item(discord.ui.TextDisplay("## Select the channel where you want leave messages to appear:"))
        container.add_item(discord.ui.ActionRow(self.select))

        self.add_item(container)

    async def select_channel(self, interaction: discord.Interaction):
        channel = self.select.values[0]
        await self.callback_func(interaction, channel)
        self.stop()


class DestructiveConfirmationView(PrivateLayoutView):
    def __init__(self, user, title_text, body_text):
        super().__init__(user=user, timeout=30)
        self.title_text = title_text
        self.body_text = body_text
        self.value = None
        self.color = None
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container(accent_color=self.color)
        container.add_item(discord.ui.TextDisplay(f"### {self.title_text}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(self.body_text))

        is_disabled = self.value is not None
        action_row = discord.ui.ActionRow()
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.gray, disabled=is_disabled)
        confirm = discord.ui.Button(label="Reset to Default", style=discord.ButtonStyle.red, disabled=is_disabled)

        cancel.callback = self.cancel_callback
        confirm.callback = self.confirm_callback

        action_row.add_item(cancel)
        action_row.add_item(confirm)
        container.add_item(discord.ui.Separator())
        container.add_item(action_row)

        self.add_item(container)

    async def update_view(self, interaction: discord.Interaction, title: str, color: discord.Color):
        self.title_text = title
        if not self.body_text.startswith("~~"):
            self.body_text = f"~~{self.body_text}~~"
        self.color = color
        self.build_layout()

        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        self.value = False
        await self.update_view(interaction, "Action Canceled", discord.Color(0xdf5046))

    async def confirm_callback(self, interaction: discord.Interaction):
        self.value = True
        await self.update_view(interaction, "Action Confirmed", discord.Color.green())

    async def on_timeout(self, interaction: discord.Interaction):
        if self.value is None:
            self.value = False
            await self.update_view(interaction, "Timed Out", discord.Color(0xdf5046))


class LeaveDashboardView(PrivateLayoutView):
    def __init__(self, cog, guild_id: int, user: discord.Member):
        super().__init__(user=user, timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.data = self.cog.leave_cache.get(guild_id, {})
        self.build_layout()

    async def refresh_state(self):
        self.data = self.cog.leave_cache.get(self.guild_id, {})
        self.build_layout()

    async def update_db(self, **kwargs):
        async with self.cog.acquire_db() as db:
            columns = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values())
            cursor = await db.execute("SELECT 1 FROM leave_settings WHERE guild_id = ?", (self.guild_id,))
            if not await cursor.fetchone():
                await db.execute("INSERT INTO leave_settings (guild_id) VALUES (?)", (self.guild_id,))

            await db.execute(f"UPDATE leave_settings SET {columns} WHERE guild_id = ?", (*values, self.guild_id))
            await db.commit()

        if self.guild_id not in self.cog.leave_cache:
            self.cog.leave_cache[self.guild_id] = {"guild_id": self.guild_id}
        self.cog.leave_cache[self.guild_id].update(kwargs)

        if "image_url" in kwargs:
            self.cog.image_bytes_cache.pop(self.guild_id, None)

    async def toggle_feature(self, interaction: discord.Interaction):
        is_enabled = self.data.get("is_enabled", 0)
        new_state = 0 if is_enabled else 1

        if new_state == 1 and not self.data.get("channel_id"):
            view = ChannelSelectView(self.channel_selected_callback, interaction.user)
            await interaction.response.edit_message(view=view)
            return

        await self.update_db(is_enabled=new_state)
        await self.refresh_state()
        await interaction.response.edit_message(view=self)

    async def channel_selected_callback(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.update_db(channel_id=channel.id, is_enabled=1)
        await self.refresh_state()
        await interaction.response.edit_message(view=self)

    async def channel_button_callback(self, interaction: discord.Interaction):
        view = ChannelSelectView(self.channel_selected_callback, interaction.user)
        await interaction.response.edit_message(view=view)

    async def test_button_callback(self, interaction: discord.Interaction):
        channel_id = self.data.get("channel_id")
        guild = interaction.guild
        channel = guild.get_channel(channel_id) if channel_id else None

        if not channel:
            await interaction.response.send_message("The configured leave channel no longer exists or isn't set.",
                                                    ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        bot_member = guild.me
        content, file = None, None

        if self.data.get("show_text", 1):
            raw_msg = self.data.get("custom_message") or "Goodbye, {member.name}. We will miss you."
            content = f"**TEST:** {raw_msg.format(member=bot_member, server=guild)}"

        if self.data.get("show_image", 1):
            file = await self.cog.generate_leave_card(bot_member, self.data)

        try:
            await channel.send(content=content, file=file)
            await interaction.followup.send(f"Test message sent to {channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"I don't have permission to send messages in {channel.mention}.",
                                            ephemeral=True)

    async def toggle_text(self, interaction: discord.Interaction):
        current = self.data.get("show_text", 1)
        await self.update_db(show_text=0 if current else 1)
        await self.refresh_state()
        await interaction.response.edit_message(view=self)

    async def open_text_modal(self, interaction: discord.Interaction):
        current_msg = self.data.get("custom_message")
        await interaction.response.send_modal(LeaveTextModal(current_msg, self.text_modal_callback))

    async def text_modal_callback(self, interaction: discord.Interaction, value: str):
        await self.update_db(custom_message=value)
        await self.refresh_state()
        await interaction.response.edit_message(view=self)

    async def toggle_image(self, interaction: discord.Interaction):
        current = self.data.get("show_image", 1)
        await self.update_db(show_image=0 if current else 1)
        await self.refresh_state()
        await interaction.response.edit_message(view=self)

    async def open_image_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LeaveImageModal(self.data, self.image_modal_callback))

    async def image_modal_callback(self, interaction: discord.Interaction, url: str, line1: str, line2: str):
        final_url = url if url and ("http" in url) else None
        await self.update_db(image_url=final_url, image_line1=line1, image_line2=line2)
        await self.refresh_state()
        await interaction.response.edit_message(view=self)

    async def reset_button_callback(self, interaction: discord.Interaction):
        view = DestructiveConfirmationView(
            user=interaction.user,
            title_text="Reset Leave Settings?",
            body_text="This will delete all custom text, images, and configurations. The feature will remain enabled if it is currently enabled."
        )
        await interaction.response.send_message(view=view, ephemeral=True)
        await view.wait()

        if view.value:
            async with self.cog.acquire_db() as db:
                await db.execute("""
                    UPDATE leave_settings 
                    SET custom_message=NULL, custom_line1=NULL, custom_line2=NULL, 
                        image_url=NULL, embed_color=NULL, show_text=1, show_image=1 
                    WHERE guild_id=?
                """, (self.guild_id,))
                await db.commit()

            if self.guild_id in self.cog.leave_cache:
                saved_channel = self.cog.leave_cache[self.guild_id].get("channel_id")
                saved_enabled = self.cog.leave_cache[self.guild_id].get("is_enabled")
                self.cog.leave_cache[self.guild_id] = {
                    "guild_id": self.guild_id,
                    "channel_id": saved_channel,
                    "is_enabled": saved_enabled,
                    "show_text": 1,
                    "show_image": 1
                }
            self.cog.image_bytes_cache.pop(self.guild_id, None)
            await self.refresh_state()

    def build_layout(self):
        self.clear_items()

        is_enabled = bool(self.data.get("is_enabled", 0))
        show_text = bool(self.data.get("show_text", 1))
        show_image = bool(self.data.get("show_image", 1))

        channel_id = self.data.get("channel_id")
        channel_mention = f"<#{channel_id}>" if channel_id else "`Not Set`"

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## Goodbye Feature Dashboard"))

        btn_main = discord.ui.Button(
            label=f"{'Disable Goodbye Feature' if is_enabled else 'Enable'}",
            style=discord.ButtonStyle.secondary if is_enabled else discord.ButtonStyle.primary
        )
        btn_main.callback = self.toggle_feature

        btn_channel = discord.ui.Button(
            label="Edit Channel",
            style=discord.ButtonStyle.primary
        )
        btn_channel.callback = self.channel_button_callback

        section = discord.ui.Section(
            discord.ui.TextDisplay(
                "Configure all settings related to Dopamine's leave/goodbye feature. Click the adjacent button to enable or disable the feature."),
            accessory=btn_main
        )
        container.add_item(section)

        if is_enabled:
            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                f"Use the Edit Channel button to edit the channel. The current channel is: {channel_mention}"),
                                                  accessory=btn_channel))
            container.add_item(discord.ui.Separator())

            btn_text_toggle = discord.ui.Button(
                label=f"{'Disable' if show_text else 'Enable'}",
                style=discord.ButtonStyle.secondary if show_text else discord.ButtonStyle.primary
            )
            btn_text_toggle.callback = self.toggle_text

            section = discord.ui.Section(
                discord.ui.TextDisplay("### Text"),
                accessory=btn_text_toggle
            )
            container.add_item(section)

            if show_text:
                btn_text_config = discord.ui.Button(label=f"Customise", style=discord.ButtonStyle.primary)
                btn_text_config.callback = self.open_text_modal

                curr_text = self.data.get("custom_message") or "Goodbye, {member.name}. We will miss you."

                section = discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"The text part of the leave message. Click the customise button to customise the format.\n\n* **Current Format:**\n  * ```{curr_text}```\n* **Available Variables:**\n  * `{{member.name}}` - The member's username.\n  * `{{server.name}}` - The name of the server."),
                    accessory=btn_text_config
                )
                container.add_item(section)

            container.add_item(discord.ui.Separator())

            btn_img_toggle = discord.ui.Button(
                label=f"{'Disable' if show_image else 'Enable'}",
                style=discord.ButtonStyle.secondary if show_image else discord.ButtonStyle.primary
            )
            btn_img_toggle.callback = self.toggle_image

            section = discord.ui.Section(
                discord.ui.TextDisplay("### Leave Card"),
                accessory=btn_img_toggle
            )
            container.add_item(section)

            if show_image:
                btn_img_config = discord.ui.Button(label="Customise", style=discord.ButtonStyle.primary)
                btn_img_config.callback = self.open_image_modal

                curr_l1 = self.data.get("image_line1") or "Goodbye {member.name}"
                curr_l2 = self.data.get("image_line2") or "We hope to see you again!"
                using_custom_img = "Yes" if self.data.get("image_url") else "No"

                section = discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"The Leave Card (image). Use the customise button to provide a custom image URL, or to edit text.\n\n* **Custom Background:** {using_custom_img}\n* **Current Image Text:**\n  * Line 1: `{curr_l1}`\n  * Line 2: `{curr_l2}`\n* **Available Variables:**\n  * `{{member.name}}`, `{{server.name}}`"),
                    accessory=btn_img_config
                )
                container.add_item(section)

            container.add_item(discord.ui.Separator())

            btn_test = discord.ui.Button(label="Send Test Message", style=discord.ButtonStyle.primary)
            btn_test.callback = self.test_button_callback

            container.add_item(discord.ui.TextDisplay("### Test Message"))

            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                f"Click the Send Test Message button to send a test message/preview in the set channel: {channel_mention}"),
                                                  accessory=btn_test))

            container.add_item(discord.ui.Separator())

            container.add_item(discord.ui.TextDisplay("### Reset to Default"))

            btn_reset = discord.ui.Button(label="Reset", style=discord.ButtonStyle.secondary)
            btn_reset.callback = self.reset_button_callback

            container.add_item(discord.ui.Section(
                discord.ui.TextDisplay("Click the Reset button to reset everything to default."),
                accessory=btn_reset
            ))

        self.add_item(container)


class Leaves(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leave_cache: Dict[int, dict] = {}
        self.image_bytes_cache: Dict[int, bytes] = {}
        self.db_pool: Optional[asyncio.Queue] = None

    async def cog_load(self):
        await self.init_pools()
        await self.init_db()
        await self.populate_caches()

    async def cog_unload(self):
        if self.db_pool:
            while not self.db_pool.empty():
                conn = await self.db_pool.get()
                await conn.close()
            self.db_pool = None

    async def init_pools(self, pool_size: int = 5):
        if self.db_pool is None:
            self.db_pool = asyncio.Queue(maxsize=pool_size)
            for _ in range(pool_size):
                conn = await aiosqlite.connect(LEDB_PATH, timeout=5)
                await conn.execute("PRAGMA busy_timeout=5000")
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA synchronous = NORMAL")
                await conn.commit()
                await self.db_pool.put(conn)

    @asynccontextmanager
    async def acquire_db(self):
        conn = await self.db_pool.get()
        try:
            yield conn
        finally:
            await self.db_pool.put(conn)

    async def init_db(self):
        async with self.acquire_db() as db:
            await db.execute('''
                             CREATE TABLE IF NOT EXISTS leave_settings
                             (
                                 guild_id INTEGER PRIMARY KEY,
                                 channel_id INTEGER,
                                 is_enabled INTEGER DEFAULT 0,
                                 show_text INTEGER DEFAULT 1,
                                 custom_message TEXT,
                                 custom_line1 TEXT,
                                 custom_line2 TEXT,
                                 show_image INTEGER DEFAULT 1,
                                 image_url TEXT,
                                 image_line1 TEXT,
                                 image_line2 TEXT,
                                 embed_color TEXT
                             )
                             ''')
    async def populate_caches(self):
        self.leave_cache.clear()
        async with self.acquire_db() as db:
            async with db.execute("SELECT * FROM leave_settings") as cursor:
                rows = await cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                for row in rows:
                    data = dict(zip(columns, row))
                    self.leave_cache[data["guild_id"]] = data

    async def get_background_image(self, guild_id: int, image_url: Optional[str]) -> Image.Image:

        if guild_id in self.image_bytes_cache:
            return Image.open(io.BytesIO(self.image_bytes_cache[guild_id])).convert("RGBA")

        if image_url:
            async with aiohttp.ClientSession() as session:
                img_bytes = await fetch_image(session, image_url)
                if img_bytes:
                    try:
                        with Image.open(io.BytesIO(img_bytes)) as img:
                            img = img.convert("RGBA")
                            target_size = (686, 291)
                            img = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

                            output = io.BytesIO()
                            img.save(output, format="PNG")
                            self.image_bytes_cache[guild_id] = output.getvalue()

                            return img
                    except Exception as e:
                        print(f"Error processing custom image for guild {guild_id}: {e}")


        return Image.open(LEAVECARD_PATH).convert("RGBA")

    async def generate_leave_card(self, member: discord.Member, data: dict) -> discord.File:

        guild_id = member.guild.id
        image_url = data.get("image_url")

        line1_text = (data.get("image_line1") or "Goodbye {member.name}").format(
            member=member, server=member.guild
        )
        line2_text = (data.get("image_line2") or "We hope to see you again!").format(
            member=member, server=member.guild
        )

        background = await self.get_background_image(guild_id, image_url)

        avatar_size = 100
        avatar_bytes = None

        if member.display_avatar:
             async with aiohttp.ClientSession() as session:
                avatar_bytes = await fetch_image(session, member.display_avatar.url)

        if avatar_bytes:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

            mask = Image.new("L", (avatar_size, avatar_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

            avatar_pos = (343 - avatar_size // 2, 102 - avatar_size // 2)

            background.paste(avatar, avatar_pos, mask)

        draw = ImageDraw.Draw(background)

        try:
            font_big = ImageFont.truetype(BOLDFONT_PATH, 25)
            font_small = ImageFont.truetype(MEDIUMFONT_PATH, 20)
        except:
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()


        draw.text((342, 188), line1_text, font=font_big, fill="white", anchor="mm")

        draw.text((342, 228), line2_text, font=font_small, fill="white", anchor="mm")

        buffer = io.BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename="leave.png")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        data = self.leave_cache.get(member.guild.id)
        if not data or not data.get("is_enabled") or not data.get("channel_id"):
            return

        channel = member.guild.get_channel(data["channel_id"])
        if not channel:
            return

        try:
            msg_content = None
            msg_file = None

            if data.get("show_text", 1):
                raw_msg = data.get("custom_message") or "Goodbye, {member.name}. We will miss you."
                msg_content = raw_msg.format(
                    member=member,
                    server=member.guild
                )

            if data.get("show_image", 1):
                msg_file = await self.generate_leave_card(member, data)

            if msg_content or msg_file:
                await channel.send(content=msg_content, file=msg_file)

        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"Error sending leave message in {member.guild.name}: {e}")

    @app_commands.command(name="goodbye", description="Open the leave/goodbye feature dashboard.")
    @app_commands.check(mod_check)
    async def leave_dashboard(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=LeaveDashboardView(self, interaction.guild.id, interaction.user)
        )

async def setup(bot):
    await bot.add_cog(Leaves(bot))