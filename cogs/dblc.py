import importlib
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dopamineframework import mod_check
from utils.log import LoggingManager
import VERSION
import time
import psutil
import asyncio
import os
import io
from PIL import Image, ImageDraw, ImageFont
from collections import deque
from config import BOLDFONT_PATH
from dopamineframework.ext.path import framework_version

class Dblc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        importlib.reload(VERSION)
        self.bot_version = VERSION.bot_version
        self.latency_cache = deque(maxlen=1440)
        self.temp_samples = []
        self.process = psutil.Process(os.getpid())
        self.process.cpu_percent(interval=None)
        self.current_cpu = 0.0
        self.cache_task.start()

    def cog_unload(self):
        self.cache_task.cancel()

    @tasks.loop(seconds=5.0)
    async def cache_task(self):
        if not self.bot.is_ready():
            return

        try:
            self.current_cpu = self.process.cpu_percent(interval=None)
            total_latency = None

            try:
                start = time.perf_counter()
                await asyncio.wait_for(
                    self.bot.http.request(discord.http.Route("GET", "/gateway")),
                    timeout=3.0
                )
                end = time.perf_counter()
                total_latency = round((end - start) * 1000)
            except asyncio.TimeoutError:
                total_latency = None
            except Exception as e:
                print(f"Latency Request Error: {e}")
                total_latency = None

            if isinstance(total_latency, (int, float)):
                self.temp_samples.append(total_latency)

            if len(self.temp_samples) >= 12:
                avg_latency = sum(self.temp_samples) / len(self.temp_samples)
                self.latency_cache.append(avg_latency)
                self.temp_samples.clear()

        except Exception as e:
            print(f"Critical error in cache_task: {e}")

    @cache_task.before_loop
    async def before_cache_task(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

    def generate_latency_graph(self):
        scale_factor = 2
        width, height = 600 * scale_factor, 300 * scale_factor
        pad_top, pad_bot, pad_left, pad_right = 200, 80, 100, 40

        img = Image.new("RGBA", (width, height), color=(30, 31, 34, 255))
        draw = ImageDraw.Draw(img)

        try:
            title_font = ImageFont.truetype(BOLDFONT_PATH, 24 * scale_factor)
            draw.text(
                (50, 50),
                "Dopamine - Average API Latency",
                fill=(255, 255, 255, 255),
                font=title_font
            )
        except Exception as e:
            print(f"Font loading error: {e}")
            draw.text((50, 50), "Dopamine - Average API Latency", fill=(255, 255, 255, 255))

        data = list(self.latency_cache)
        num_samples = len(data)

        if num_samples < 2:
            return None

        max_val = max(data) if data else 100
        steps = [10, 25, 50, 100, 250, 500, 1000]
        target_step = next((s for s in steps if s > max_val / 4), max_val / 4)
        y_limit = target_step * 4

        grid_color = (60, 62, 68, 255)
        num_y_labels = 4
        graph_height = height - pad_top - pad_bot
        for i in range(num_y_labels + 1):
            val = target_step * i
            y = (height - pad_bot) - (val / y_limit) * graph_height
            draw.line([(pad_left, y), (width - pad_right, y)], fill=grid_color, width=1 * scale_factor)
            draw.text((pad_left - 15, y), f"{int(val)}ms", fill=(180, 180, 180), anchor="rm",
                      font_size=12 * scale_factor)

        graph_width = width - pad_left - pad_right

        num_x_labels = 5
        for i in range(num_x_labels):
            sample_idx = int((i / (num_x_labels - 1)) * (num_samples - 1))

            x = pad_left + (i / (num_x_labels - 1)) * graph_width

            mins_ago = num_samples - 1 - sample_idx

            if mins_ago == 0:
                label = "Now"
            elif mins_ago >= 60:
                label = f"{round(mins_ago / 60, 1)}h"
            else:
                label = f"{mins_ago}m"

            draw.line([(x, height - pad_bot), (x, height - pad_bot + 10)], fill=(150, 150, 150), width=2)
            draw.text((x, height - pad_bot + 25), label, fill=(150, 150, 150), anchor="mt", font_size=12 * scale_factor)

        points = []
        for i, val in enumerate(data):
            x = pad_left + (i / (num_samples - 1)) * graph_width
            y = (height - pad_bot) - (val / y_limit) * graph_height
            points.append((x, y))

        fill_points = [(pad_left, height - pad_bot)] + points + [(width - pad_right, height - pad_bot)]
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.polygon(fill_points, fill=(134, 50, 230, 40))
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)
        draw.line(points, fill=(160, 80, 255), width=3 * scale_factor, joint="round")

        img = img.resize((600, 300), resample=Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @app_commands.command(name="avatar", description="Get a user's avatar.")
    @app_commands.describe(user="The user whose avatar you want to see.")
    async def avatar(self, interaction: discord.Interaction, user: discord.User):
        embed = discord.Embed(
            title=f"{user.name}",
            description="### User Avatar",
            color=discord.Color(0x944ae8)
        )
        embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="purge", description="Delete recent messages.")
    @app_commands.check(mod_check)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(number="Number of messages to delete (max 100)")
    async def purge(self, interaction: discord.Interaction, number: int):
        number = max(1, min(number, 100))

        await interaction.response.defer(ephemeral=True)

        try:

            messages = [msg async for msg in interaction.channel.history(limit=number)]

            if not messages:
                return await interaction.edit_original_response("No messages found to delete.", ephemeral=True)

            await interaction.channel.delete_messages(messages)
            deleted_count = len(messages)

        except discord.Forbidden:
            return await interaction.edit_original_response("I don't have permission to delete messages here.", ephemeral=True)
        except discord.HTTPException as e:
            if e.code == 50034:
                return await interaction.edit_original_response(
                    "Cannot delete messages older than 14 days using bulk delete.",
                    ephemeral=True
                )
            return await interaction.edit_original_response(f"An error occurred: {e}", ephemeral=True)
        channel_id = await self.bot.manager.logging_get(interaction.guild.id)
        log_ch = self.bot.get_channel(channel_id)
        if not log_ch:
            log_ch = self.bot.fetch_channel(channel_id)
        if log_ch:
            log_embed = discord.Embed(
                description=f"**{deleted_count}** message(s) purged in {interaction.channel.mention}.",
                color=discord.Color.red()
            )
            log_embed.set_footer(text=f"By {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await log_ch.send(embed=log_embed)

        await interaction.edit_original_response(f"Successfully purged **{deleted_count}** messages.", ephemeral=True)

    @app_commands.command(name="ban", description="Fake-ban someone (cosmetic).")
    @app_commands.describe(member="Who to fake-ban", duration="How long (text)", reason="Optional reason")
    async def ban(self, interaction: discord.Interaction, member: discord.Member | None = None,
                        duration: str | None = None, reason: str | None = None):
        try:

            embed = discord.Embed(
                description=f"**{member.mention}** has been **banned**"
                            + (f" for {duration}" if duration else "")
                            + (f"\n\n**Reason:** {reason}\n\n" if reason else "."),
                color=discord.Color.red()
            )
            embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url)
            embed.set_footer(text=f"by {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(
                        "An unexpected error occurred while running this command.", ephemeral=True
                    )
                except Exception:
                    pass
            else:
                try:
                    await interaction.response.send_message(
                        "An unexpected error occurred while running this command.", ephemeral=True
                    )
                except Exception:
                    pass

    @app_commands.command(name="echo", description="Make the bot say a message in a channel.")
    @app_commands.check(mod_check)
    @app_commands.describe(channel="Where to send the message", message="What to say")
    async def echo(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        try:
            await channel.send(message)
            await interaction.response.send_message("Message echoed successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: Could not send message: {e}", ephemeral=True)

    @app_commands.command(name="say", description="Ask the bot to say something")
    @app_commands.describe(channel="Where to send it", message="What to say")
    async def say(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        try:
            text = f"{interaction.user.mention} has desperately begged on their knees and asked me to say: {message}"
            await channel.send(text)
            await interaction.response.send_message("Sent.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: Could not send message: {e}", ephemeral=True)

    @app_commands.command(name="servercount", description="Get the number of servers the bot is in.")
    async def servercount(self, interaction: discord.Interaction):
        server_count = len(self.bot.guilds)
        await interaction.response.send_message(f"I am currently in **{server_count}** servers.")

    latency = app_commands.Group(name="latency", description="Latency-related commands.")

    @app_commands.command(name="ping", description="Get detailed latency and bot information")

    async def info(self, interaction: discord.Interaction):
        def format_uptime(seconds):
            weeks = seconds // (7 * 24 * 60 * 60)
            seconds %= (7 * 24 * 60 * 60)
            days = seconds // (24 * 60 * 60)
            seconds %= (24 * 60 * 60)
            hours = seconds // (60 * 60)
            seconds %= (60 * 60)
            minutes = seconds // 60
            seconds %= 60

            parts = []
            if weeks > 0:
                parts.append(f"{int(weeks)}w")
            if days > 0:
                parts.append(f"{int(days)}d")
            if hours > 0:
                parts.append(f"{int(hours)}h")
            if minutes > 0:
                parts.append(f"{int(minutes)}m")
            if seconds > 0 or not parts:
                parts.append(f"{int(seconds)}s")

            return " ".join(parts)

        initial_message = (
            "Pinging...\n"
            "Digging around for your IP address...\n"
            "Getting your location...\n"
            "Calculating distance to your home...\n"
            "Sending you some icecream...\n"
            "Done! Icecream sent."
        )

        if self.latency_cache:
            avg_latency = round(sum(self.latency_cache) / len(self.latency_cache), 2)
            sample_count = len(self.latency_cache)
        else:
            avg_latency = "Calculating..."
            sample_count = 0
        start_time = time.time()
        await interaction.response.send_message(initial_message)
        gateway_raw = str(self.bot.ws.gateway)
        gateway_node = gateway_raw.split('gateway-')[-1].split('.')[
            0] if 'gateway-' in gateway_raw else "Global/Unknown"
        end_time = time.time()
        round_latency = round((end_time - start_time) * 1000)
        discord_latency = round(self.bot.latency * 1000)
        try:
            start = time.perf_counter()
            await self.bot.http.request(discord.http.Route("GET", "/gateway"))
            end = time.perf_counter()
            connection_latency = round((end - start) * 1000)
        except Exception:
            connection_latency = "Error"

        if hasattr(self.bot, 'start_time'):
            uptime_seconds = int(time.time() - self.bot.start_time)
        else:
            uptime_seconds = 0
        uptime_formatted = format_uptime(uptime_seconds)

        proc_seconds = int(time.time() - getattr(self.bot, 'process_start_time', time.time()))
        proc_uptime = format_uptime(proc_seconds)

        try:
            process = psutil.Process(os.getpid())
            memory_bytes = process.memory_info().rss
            memory_mb = memory_bytes / (1024 * 1024)

            if memory_mb >= 1024:
                memory_gb = int(memory_mb // 1024)
                memory_remaining_mb = round(memory_mb % 1024, 2)
                memory_usage = f"{memory_gb}GB {memory_remaining_mb}MB"
            else:
                memory_usage = f"{round(memory_mb, 2)}MB"
        except Exception:
            memory_usage = "Unable to calculate"

        try:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                charging = battery.power_plugged
                battery_status = f"Host Device Battery Status: `{percent}% ({'Charging' if charging else 'Discharging'})`"
            else:
                battery_status = "Host Device Battery Status: `Device has no battery`"
        except Exception:
            battery_status = "Host Device Battery Status: `Unable to determine`"

        cpu_usage = self.current_cpu
        if cpu_usage == 0:
            formatted_cpu_usage = "0"
        else:
            formatted_cpu_usage = f"{cpu_usage:.1f}"
        embed = discord.Embed(
            title="Latency Info",
            description=(
                f"> Bot Version: `{self.bot_version}`\n"
                f"> Powered by Dopamine Framework `v{framework_version}`\n\n"
                f"> Connected to Discord Gateway: `{gateway_node}`\n"
                "> Bot Host Location: `South Asia`\n\n"
                f"> API Latency: `{connection_latency}ms`\n"
                f"> Round-trip Latency: `{round_latency}ms`\n"
                f"> Heartbeat/WebSocket Latency: `{discord_latency}ms`\n\n"
                f"> Average API Latency: `{avg_latency}ms` (over `{sample_count}` samples where each sample is average of 12 samples)\n\n"
                f"> Connection Uptime: `{uptime_formatted}`\n"
                f"> Process Uptime: `{proc_uptime}`\n\n"
                f"> CPU Usage: `{formatted_cpu_usage}%`\n"
                f"> Memory Usage: `{memory_usage}`\n"
                f"> {battery_status}"
            ),
            color=discord.Color(0x944ae8)
        )
        message = await interaction.original_response()
        await message.edit(content=None, embed=embed)

    @latency.command(name="graph", description="Shows a graph of the average latency in the last 24 hours")
    async def graph(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            graph_buffer = self.generate_latency_graph()
        except Exception as e:
            return await interaction.edit_original_response(content=f"ERROR: {e}")
        if graph_buffer:
            file = discord.File(graph_buffer, filename="graph.png")
            await interaction.edit_original_response(content=None, attachments=[file])
        else:
            await interaction.edit_original_response(content="Not enough data yet! The bot or cog was restarted very recently. Please wait a few minutes.")

async def setup(bot):
    await bot.add_cog(Dblc(bot))