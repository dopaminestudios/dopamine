import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from config import HEARTBEAT_URL

class StatusHeartbeat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.heartbeat_url = HEARTBEAT_URL
        self.session = None
        self.send_heartbeat.start()

    def cog_unload(self):
        self.send_heartbeat.cancel()
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    @tasks.loop(minutes=1.0)
    async def send_heartbeat(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )

        try:
            async with self.session.get(self.heartbeat_url) as response:
                if response.status != 200:
                    self.bot.logger.warning(f"Heartbeat failed: Status {response.status}")
        except Exception as e:
            if self.bot and hasattr(self.bot, 'logger'):
                self.bot.logger.error(f"Heartbeat loop error: {e}")
            if self.session:
                await self.session.close()

    @send_heartbeat.before_loop
    async def before_heartbeat(self):
        await self.bot.wait_until_ready()

    @send_heartbeat.error
    async def on_heartbeat_error(self, error):
        if self.bot and hasattr(self.bot, 'logger'):
            self.bot.logger.critical(f"The heartbeat task has DIED: {error}")

        if self.bot.owner_ids:
            owners = list(self.bot.owner_ids)
        elif self.bot.owner_id:
            owners = [self.bot.owner_id]
        else:
            app = await self.bot.application_info()
            if app.team:
                owners = [m.id for m in app.team.members]
            else:
                owners = [app.owner.id]

        for owner_id in owners:
            try:
                owner = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
                await owner.send(f"**Critical:** The heartbeat task has failed: ```{error}```")
            except Exception as e:
                    if self.bot and hasattr(self.bot, 'logger'):
                        self.bot.logger.error(f"Could not send DM to owner {owner_id}: {e}")
            if not self.send_heartbeat.is_being_cancelled():
                self.send_heartbeat.restart()

async def setup(bot):
    await bot.add_cog(StatusHeartbeat(bot))