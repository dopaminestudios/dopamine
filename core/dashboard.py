import os
import sys
import discord
import signal
import asyncio
from typing import TYPE_CHECKING
from core.bot import Bot
from core.commands_registry import CommandRegistry
signal_handler = Bot.signal_handler
restart_bot = Bot.restart_bot

if TYPE_CHECKING:
    from discord.ext import commands

class PrivateLayoutView(discord.ui.LayoutView):
    def __init__(self, user: discord.User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This isn't for you!",
                ephemeral=True
            )
            return False
        return True

class OwnerDashboard(PrivateLayoutView):
    def __init__(self, bot: 'commands.Bot', user: discord.User, page: int = 1):
        super().__init__(user, timeout=None)
        self.bot = bot
        self.page = page
        self.items_per_page = 5
        self.registry = CommandRegistry(self)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## Owner Dashboard")))
        container.add_item(discord.ui.Separator())

        cogs_dir = os.path.join(os.getcwd(), "cogs")
        cog_files = []
        if os.path.exists(cogs_dir):
            cog_files = [f for f in os.listdir(cogs_dir) if f.endswith(".py") and not f.startswith("__")]

        cog_files.sort()
        total_items = len(cog_files)
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page if total_items > 0 else 1

        start_idx = (self.page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        current_page_cogs = cog_files[start_idx:end_idx]

        if not current_page_cogs:
            container.add_item(discord.ui.TextDisplay("*No extensions found in /cogs.*"))
        else:
            for idx, filename in enumerate(current_page_cogs, start_idx + 1):
                ext_name = f"cogs.{filename[:-3]}"
                is_loaded = ext_name in self.bot.extensions

                cog_btn = discord.ui.Button(
                    label="Unload" if is_loaded else "Load",
                    style=discord.ButtonStyle.secondary if is_loaded else discord.ButtonStyle.primary
                )

                cog_btn.callback = self.create_toggle_callback(ext_name, is_loaded)
                container.add_item(
                    discord.ui.Section(discord.ui.TextDisplay(f"{idx}. `{filename}`"), accessory=cog_btn))

            container.add_item(discord.ui.TextDisplay(f"-# Page {self.page} of {total_pages}"))

        if total_pages > 1:
            nav_row = discord.ui.ActionRow()

            left_btn = discord.ui.Button(label="◀️", style=discord.ButtonStyle.primary, disabled=(self.page <= 1))
            left_btn.callback = self.prev_page
            nav_row.add_item(left_btn)

            go_btn = discord.ui.Button(label="Go To Page", style=discord.ButtonStyle.secondary)
            go_btn.callback = self.go_to_page_callback
            nav_row.add_item(go_btn)

            right_btn = discord.ui.Button(label="▶️", style=discord.ButtonStyle.primary,
                                          disabled=(self.page >= total_pages))
            right_btn.callback = self.next_page
            nav_row.add_item(right_btn)

            container.add_item(nav_row)

        container.add_item(discord.ui.Separator())

        sync_btn = discord.ui.Button(label="Sync Slash Global", style=discord.ButtonStyle.primary)
        sync_local_btn = discord.ui.Button(label="Sync Slash Guild", style=discord.ButtonStyle.primary)
        reload_btn = discord.ui.Button(label="Reload All Cogs", style=discord.ButtonStyle.primary)
        shutdown_btn = discord.ui.Button(label="Shutdown", style=discord.ButtonStyle.danger)
        restart_btn = discord.ui.Button(label="Restart", style=discord.ButtonStyle.danger)
        log_btn = discord.ui.Button(label="Show Log", style=discord.ButtonStyle.secondary)

        sync_btn.callback = self.sync_callback
        sync_local_btn.callback = self.sync_local_callback
        reload_btn.callback = self.reload_all_callback
        shutdown_btn.callback = self.shutdown_callback
        restart_btn.callback = self.restart_callback
        log_btn.callback = self.show_log_callback

        action_row = discord.ui.ActionRow()
        action_row.add_item(sync_btn)
        action_row.add_item(sync_local_btn)
        action_row.add_item(log_btn)
        container.add_item(action_row)

        action_row = discord.ui.ActionRow()
        action_row.add_item(reload_btn)
        action_row.add_item(shutdown_btn)
        action_row.add_item(restart_btn)

        container.add_item(action_row)
        self.add_item(container)

    def create_toggle_callback(self, ext_name, is_loaded):
        async def callback(interaction: discord.Interaction):
            try:
                if is_loaded:
                    await self.bot.unload_extension(ext_name)
                else:
                    await self.bot.load_extension(ext_name)
                self.build_layout()
                await interaction.response.edit_message(view=self)
            except Exception as e:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        return callback

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.build_layout()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.build_layout()
        await interaction.response.edit_message(view=self)

    async def go_to_page_callback(self, interaction: discord.Interaction):
        cogs_dir = os.path.join(os.getcwd(), "cogs")
        cog_files = [f for f in os.listdir(cogs_dir) if f.endswith(".py") and not f.startswith("__")] if os.path.exists(cogs_dir) else []
        total_pages = (len(cog_files) + self.items_per_page - 1) // self.items_per_page
        await interaction.response.send_modal(OwnerGoToPageModal(self, total_pages))

    async def reload_all_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        extensions = list(self.bot.extensions.keys())
        reloaded, failed = [], []
        for ext in extensions:
            try:
                await self.bot.reload_extension(ext)
                reloaded.append(ext)
            except Exception as e:
                failed.append(f"{ext} ({e})")
        status = f"Reloaded {len(reloaded)} cogs."
        if failed: status += f"\n**Failed:** {', '.join(failed)}"
        await interaction.followup.send(status, ephemeral=True)

    async def sync_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.registry.force_sync(guild=None)
        await interaction.followup_send("Synced slash commands globally successfully.", ephemeral=True)

    async def sync_local_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.registry.force_sync(guild=interaction.guild)
        await interaction.followup_send("Synced slash commands in this guild successfully.", ephemeral=True)


    async def shutdown_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Shutting down...", ephemeral=True)
        await signal_handler()

    async def restart_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Restarting process...", ephemeral=True)
        await restart_bot()

    async def show_log_callback(self, interaction: discord.Interaction):
        log_path = os.path.join(os.getcwd(), "discord.log")
        if not os.path.exists(log_path):
            return await interaction.response.send_message("Log file not found.", ephemeral=True)
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_content = f.read()
            if len(log_content) > 1900:
                await interaction.response.send_message("Log exceeds 1900 chars, sending file:", file=discord.File(log_path), ephemeral=True)
            elif not log_content.strip():
                await interaction.response.send_message("Log file is empty.", ephemeral=True)
            else:
                await interaction.response.send_message(f"```\n{log_content}\n```", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to read log: {e}", ephemeral=True)

class OwnerGoToPageModal(discord.ui.Modal):
    def __init__(self, parent_view: OwnerDashboard, total_pages: int):
        super().__init__(title="Jump to Page")
        self.parent_view = parent_view
        self.total_pages = max(total_pages, 1)
        self.page_input = discord.ui.TextInput(
            label=f"Page Number (1-{self.total_pages})",
            placeholder="Enter a page number...",
            min_length=1, max_length=5, required=True
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_num = int(self.page_input.value)
            if 1 <= page_num <= self.total_pages:
                self.parent_view.page = page_num
                self.parent_view.build_layout()
                await interaction.response.edit_message(view=self.parent_view)
            else:
                await interaction.response.send_message(f"Enter a number between 1-{self.total_pages}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid input.", ephemeral=True)