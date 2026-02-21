import discord
import importlib
import config
import dopamineframework
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import sys


class Reload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rs", description=".")
    async def reload(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("🤫", ephemeral=True)
            return

        load_dotenv(override=True)
        importlib.reload(config)
        importlib.reload(dopamineframework)

        await interaction.response.send_message("👍️", ephemeral=True)

    @commands.command(name="rs")
    async def reload(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            return

        modules_to_purge = [
            'dopamineframework',
            'dopamineframework.core',
            'dopamineframework.core.commands_registry',
            'dopamineframework.core.dashboard',
            'dopamineframework.ext',
            'dopamineframework.ext.diagnostics',
            'dopamineframework.ext.path',
            'dopamineframework.ext.pic',
            'dopamineframework.utils',
            'dopamineframework.utils.checks',
            'dopamineframework.utils.log',
            'dopamineframework.utils.paginator',
            'dopamineframework.utils.timeparser',
            'dopamineframework.utils.views',
            'dopamineframework.bot'
        ]

        try:
            for module in modules_to_purge:
                if module in sys.modules:
                    del sys.modules[module]

            importlib.import_module('dopamineframework')
            load_dotenv(override=True)
            importlib.reload(config)
            await ctx.send("👍️")
        except Exception as e:
            await ctx.send(f"Error: {e}")


async def setup(bot):
    await bot.add_cog(Reload(bot))