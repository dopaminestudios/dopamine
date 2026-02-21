import discord
from discord.ext import commands
from discord import app_commands
from dopamineframework import PrivateLayoutView

class MessageReportDashboard(PrivateLayoutView):
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## Message Report Dashboard")))
        toggle_btn = discord.ui.Button(label=f"{'Disable' if 1 ==1 else 'Enable'}", style=discord.ButtonStyle.secondary if 1==1 else discord.ButtonStyle.primary)
        container.add_item(discord.ui.Section(discord.ui.TextDisplay("Message reports allow users to report any message directly to the moderators. Use this dashboard to configure it."), accessory=toggle_btn))

        if 1==1:
            container.add_item(discord.ui.Separator())

            channel_btn = discord.ui.Button(label="Edit Channel", style=discord.ButtonStyle.primary)

            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                "* Channel where reported messages will be sent: {channel}"), accessory=channel_btn))
            role_btn = discord.ui.Button(label="Edit Roles", style=discord.ButtonStyle.primary)

            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                "* Roles that will be pinged upon a report: {roles separated by commas}"), accessory=role_btn))

            container.add_item(discord.ui.Separator())
            test_btn = discord.ui.Button(label="Send Test Message", style=discord.ButtonStyle.primary)

            container.add_item(discord.ui.Section(discord.ui.TextDisplay(
                "* Click the button to send a test message to the chosen channel."), accessory=test_btn))

        container.add_item(discord.ui.Separator())
        return_btn = discord.ui.Button(label="Return to Dashboard", style=discord.ButtonStyle.secondary)

        container.add_item(discord.ui.ActionRow(return_btn))

        self.add_item(container)

class ChannelSelect(PrivateLayoutView):
    def __init__(self, user, firsttime: int = 0):
        super().__init__(user, timeout=None)
        self.firsttime = firsttime
        self.build_layout()

    def build_layout(self):
        container = discord.ui.Container()
        select = discord.ui.ChannelSelect(placeholder="Select a channel...", min_values=1, max_values=1)
        select.callback = self.select_channel
        container.add_item(discord.ui.TextDisplay(f"{"## Step 1: Select the channel where you want welcome messages to appear:" if self.firsttime else "## Select the channel where you want welcome messages to appear:"}"))
        container.add_item(discord.ui.ActionRow(select))

        self.add_item(container)

class RoleSelect(PrivateLayoutView):
    def __init__(self, user, firsttime: int = 0):
        super().__init__(user, timeout=None)
        self.firsttime = firsttime
        self.build_layout()

    def build_layout(self):
        container = discord.ui.Container()
        select = discord.ui.RoleSelect(placeholder="Select role(s)...", min_values=1, max_values=25)
        select.callback = self.select_role
        container.add_item(discord.ui.TextDisplay(f"{"## Step 2: Select the roles that Dopamine should ping when a message is reported:" if self.firsttime else "## Select the roles that Dopamine should ping when a message is reported:"}"))
        skip_button = discord.ui.Button(label="Skip (Don't ping anyone / Set it up later)", style=discord.ButtonStyle.secondary)
        container.add_item(discord.ui.ActionRow(skip_button))
        container.add_item(discord.ui.ActionRow(select))

        self.add_item(container)

class CV2TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="cv2test", description="Tests Discord Components V2 layout")
    async def cv2test(self, interaction: discord.Interaction):
        view = MessageReportDashboard(interaction.user)
        await interaction.response.send_message(
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CV2TestCog(bot))