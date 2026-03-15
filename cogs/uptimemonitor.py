import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import logging
from config import HEARTBEAT_URL


class StatusHeartbeat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.heartbeat_url = HEARTBEAT_URL
        self._session = None
        self.send_heartbeat.start()

    def cog_unload(self):
        self.send_heartbeat.cancel()
        if self._session:
            asyncio.create_task(self._session.close())

    async def get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @tasks.loop(minutes=1.0)
    async def send_heartbeat(self):
        try:
            session = await self.get_session()
            timeout = aiohttp.ClientTimeout(total=15)

            async with session.get(self.heartbeat_url, timeout=timeout) as response:
                if response.status != 200:
                    self.bot.logger.warning(f"Heartbeat failed: {response.status}")

        except Exception as e:
            self.bot.logger.error(f"Heartbeat loop encountered an error: {e}")

    @send_heartbeat.before_loop
    async def before_heartbeat(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(StatusHeartbeat(bot))