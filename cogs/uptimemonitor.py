import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from config import HEARTBEAT_URL


class StatusHeartbeat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.heartbeat_url = HEARTBEAT_URL
        self.send_heartbeat.start()

    def cog_unload(self):
        self.send_heartbeat.cancel()

    @tasks.loop(minutes=1.0)
    async def send_heartbeat(self):
        try:
            timeout = aiohttp.ClientTimeout(total=15, connect=5)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.heartbeat_url) as response:
                    if response.status != 200:
                        self.bot.logger.warning(f"Heartbeat failed: Status {response.status}")
                    else:
                        pass

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.bot.logger.error(f"Network error during heartbeat: {e}")
        except Exception as e:
            self.bot.logger.error(f"Unexpected error in heartbeat loop: {e}")

    @send_heartbeat.before_loop
    async def before_heartbeat(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(StatusHeartbeat(bot))