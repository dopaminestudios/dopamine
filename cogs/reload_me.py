import discord
import importlib
import config
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
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
        await interaction.response.send_message("👍️", ephemeral=True)

    @commands.command(name="rs")
    async def reload(self, ctx: commands.Context):
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("🤫", delete_after=5)
            return

        load_dotenv(override=True)
        importlib.reload(config)

        await ctx.send("👍️")

async def setup(bot):
    await bot.add_cog(Reload(bot))