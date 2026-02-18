import discord
from discord.ext import commands, tasks
import aiohttp
import logging
from config import HEARTBEAT_URL
logger = logging.getLogger('discord')


class StatusHeartbeat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.heartbeat_url = HEARTBEAT_URL

        self.send_heartbeat.start()

    def cog_unload(self):
        self.send_heartbeat.cancel()

    @tasks.loop(minutes=1.0)
    async def send_heartbeat(self):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.heartbeat_url, timeout=10) as response:
                    if response.status != 200:
                        logger.warning(f"Heartbeat failed with status: {response.status}")
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")

    @send_heartbeat.before_loop
    async def before_heartbeat(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(StatusHeartbeat(bot))