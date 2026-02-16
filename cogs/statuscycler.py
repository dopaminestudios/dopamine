import discord
from discord.ext import tasks, commands


class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.index = 0
        self.change_status.start()

    def cog_unload(self):
        self.change_status.cancel()

    async def get_stats(self):
        if not self.bot.application:
            await self.bot.application_info()

        guild_count = len(self.bot.guilds)
        user_installs = self.bot.application.approximate_user_install_count or 0
        total_members = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)

        return [
            "✨ v3 is here!",
            f"✨ Watching {guild_count} Servers",
            "✨ Watching downfall of GiveawayBot",
            "✨ Offering premium exp without paywalls",
            f"✨ Watching {user_installs} User-installs",
            "✨ Enforcing no nickel-&-diming policy",
            "✨ Powered by Dopamine Framework!",
            f"✨ Watching {total_members} Members",
            "✨ Watching downfall of GiveawayBoat",
            "✨ It's so hard being the best!",
            "✨ Bullying Sapphire for fun"
        ]

    @tasks.loop(seconds=30)
    async def change_status(self):
        statuses = await self.get_stats()

        current_text = statuses[self.index]

        activity = discord.Streaming(
            name=current_text,
            url="https://www.twitch.tv/dopaminediscordbot"
        )

        await self.bot.change_presence(activity=activity)

        self.index = (self.index + 1) % len(statuses)

    @change_status.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(StatusCog(bot))