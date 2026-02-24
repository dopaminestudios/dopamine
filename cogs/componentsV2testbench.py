import discord
from discord.ext import commands
from discord import app_commands
from dopamineframework import PrivateLayoutView

class AutoresponseDashboard(PrivateLayoutView):
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## Autoresponse Dashboard"))
        container.add_item(discord.ui.TextDisplay("Reply to messages automatically that contain specific letters or words with a text message, link, or embed."))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### Match Modes:\n* **Exact Match:** Matches the string exactly.\n* **Partial Match:** Triggers if the string is anywhere in the message.\n* **Fuzzy Matching:** Triggers response based on how much a specific string matches the message. It works on a percentage score. Default is 75%, but you can customise it for each Autoresponse!"))
        container.add_item(discord.ui.TextDisplay("### Variables:\n* **User Variables (User who triggered the response):** `{author.mention}`, `{author.name}`, `{author.display_name}`, and `{author.id}`.\n*Channel Variables (Channel where response was triggered): `{channel.mention}`, `{channel.name}`, and `{channel.id}`.\n* Guild Variables (Guild means Server in Discord internally): `{guild.name}`, `{guild.member_count}`, and `{guild.id}`."))
        create_btn = discord.ui.Button(label="Create", style=discord.ButtonStyle.primary) # Sends new message AutoresponseCreateView
        manage_btn = discord.ui.Button(label="Manage & Edit", style=discord.ButtonStyle.secondary) # Edits Message into ManageAutoresponsePage

        row = discord.ui.ActionRow()
        row.add_item(create_btn)
        row.add_item(manage_btn)

        container.add_item(row)

        self.add_item(container)

class ManageAutoresponsePage(PrivateLayoutView):
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## Manage Autoresponse"))
        container.add_item(discord.ui.Separator())

        edit_btn = discord.ui.Button(label=f"Edit", style=discord.ButtonStyle.secondary) # Sends the EditAutoresponsePage.

        container.add_item(discord.ui.Section(discord.ui.TextDisplay("### 1. `[Trigger string]`"), accessory=edit_btn)) # Each embed will have ONE of these entries for them. the number goes up for each of them.

        container.add_item(discord.ui.Separator())
        return_btn = discord.ui.Button(label="Return to Dashboard", style=discord.ButtonStyle.secondary)
        container.add_item(discord.ui.Separator())
        row = discord.ui.ActionRow()
        row.add_item(return_btn)
        container.add_item(row)
        self.add_item(container)


class EditAutoresponsePage(PrivateLayoutView):
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## Edit: `[Trigger string]`"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### ➤ Trigger: `[Trigger string]`\n* Reply: [```message content here, make sure that it doesnt cause visual errors if it contains line breaks``` or Custom Embed]\n* **Channel(s):** [All or Mention of channels separated by commas]\n* **Match Mode:** [Exact Match or Partial Match or Fuzzy Match]\n**Fuzzy Match:** [only show this line if the mode is set to fuzzy match] Default (75%)\n* **Case Sensitive:** No"))

        container.add_item(discord.ui.Separator())

        edit_str_btn = discord.ui.Button(label="Edit Trigger",
                                        style=discord.ButtonStyle.primary) # Opens modal if text, else directs user to use `/embed` and then click on Manage & Edit button. remember, they shalln't be able to change between these two types for an existing autoresponse.
        edit_cn_btn = discord.ui.Button(label="Edit Channel",
                                     style=discord.ButtonStyle.primary)  # Edits message into ChannelSelect.
        mode_btn = discord.ui.Button(label=f"[Exact/Partial/Fuzzy] Mode",
                                        style=discord.ButtonStyle.primary) # cycles between the modes in this order: exact, partial, fuzzy, exact, and so on.
        edit_fuzzy_btn = discord.ui.Button(label="Edit Fuzzy Mode Score",
                                        style=discord.ButtonStyle.secondary) # sends modal. this button is only visible when fuzzy mode is on.
        case_btn = discord.ui.Button(label=f"{'Disable' if 1==1 else 'Enable'} Case Sensitivity", style=discord.ButtonStyle.secondary if 1==1 else discord.ButtonStyle.primary) # 1==1 is check for whether it's enabled. it's disabled by default.
        delete_btn = discord.ui.Button(label="Delete",
                                        style=discord.ButtonStyle.secondary) # Sends DestructiveConfirmationView
        row = discord.ui.ActionRow()
        row.add_item(edit_str_btn)
        row.add_item(edit_cn_btn)
        row.add_item(mode_btn)
        row.add_item(edit_fuzzy_btn)
        row.add_item(case_btn)
        container.add_item(row)

        row = discord.ui.ActionRow()
        row.add_item(delete_btn)
        container.add_item(row)

        container.add_item(discord.ui.Separator())

        return_btn = discord.ui.Button(label="Return to Dashboard", style=discord.ButtonStyle.secondary)
        row = discord.ui.ActionRow()
        row.add_item(return_btn)
        container.add_item(row)
        self.add_item(container)



class ChannelSelect(PrivateLayoutView): # if firsttime, callback will edit message into FinalStep
    def __init__(self, user, firsttime: int = 0):
        super().__init__(user, timeout=None)
        self.firsttime = firsttime # Set to 1 if triggering this class from the create button
        self.build_layout()

    def build_layout(self):
        container = discord.ui.Container()
        select = discord.ui.ChannelSelect(placeholder="Select a channel...", min_values=0, max_values=25)
        select.callback = self.select_channel
        container.add_item(discord.ui.TextDisplay(f"{"### Step 4: Select the channel where you want the string to be detected:" if self.firsttime else "### Select the channel where you want the string to be detected:"}"))
        container.add_item(discord.ui.ActionRow(select))
        if self.firsttime:
            skip_button = discord.ui.Button(label="Skip (Detect in All Channels / Set it up later)",
                                            style=discord.ButtonStyle.primary)
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.ActionRow(skip_button))
        self.add_item(container)

class FinalStep(PrivateLayoutView): # if firsttime, callback will edit message into
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        container = discord.ui.Container()

        container.add_item(discord.ui.TextDisplay(f"### Step 6: Finalise the Autoresponse by configuring the below modes:"))
        case_btn = discord.ui.Button(label=f"{'Disable' if 1 == 1 else 'Enable'} Case Sensitivity",
                                     style=discord.ButtonStyle.secondary if 1 == 1 else discord.ButtonStyle.primary)  # 1==1 is check for whether it's enabled. it's disabled by default.
        mode_btn = discord.ui.Button(label=f"[Exact/Partial/Fuzzy] Mode",
                                     style=discord.ButtonStyle.primary)  # cycles between the modes in this order: exact, partial, fuzzy, exact, and so on.
        edit_fuzzy_btn = discord.ui.Button(label="Edit Fuzzy Mode Score",
                                           style=discord.ButtonStyle.secondary)  # sends modal. this button is only visible when fuzzy mode is on.
        row = discord.ui.ActionRow()
        row.add_item(case_btn)
        row.add_item(mode_btn)
        row.add_item(edit_fuzzy_btn)
        container.add_item(row)

        container.add_item(discord.ui.Separator())

        save_btn = discord.ui.Button(label="Save and Start Autoreponse", style=discord.ButtonStyle.primary) # Saves and starts the autoresponse
        row = discord.ui.ActionRow()
        row.add_item(save_btn)
        container.add_item(row)
        self.add_item(container)

class CreateAutoresponseView(PrivateLayoutView):
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("### Step 1: Enter the string that you want Dopamine to listen for")) #
        container.add_item(discord.ui.Separator())

        trigger_btn = discord.ui.Button(label="Enter Trigger", style=discord.ButtonStyle.primary) # Opens modal with a single line field. when done, edits message into ReponseTypeView.
        row = discord.ui.ActionRow()
        row.add_item(trigger_btn)
        container.add_item(row)
        self.add_item(container)

class ResponseTypeView(PrivateLayoutView):
    def __init__(self, user):
        super().__init__(user, timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("### Step 2: Select a type of message for the response to continue creating Autoresponse")) #
        container.add_item(discord.ui.Separator())

        text_btn = discord.ui.Button(label="Text", style=discord.ButtonStyle.primary) # Opens modal with a single multi line field. Mention at the top in the modal that it's the Step 3.
        embed_btn = discord.ui.Button(label="Embed", style=discord.ButtonStyle.primary) # Edits message into UseEmbedPage from Embeds cog.
        row = discord.ui.ActionRow()
        row.add_item(text_btn)
        row.add_item(embed_btn)
        container.add_item(row)
        self.add_item(container)

class CV2TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="cv2test", description="Tests Discord Components V2 layout")
    async def cv2test(self, interaction: discord.Interaction):
        view = AutoresponseDashboard(interaction.user)
        await interaction.response.send_message(
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CV2TestCog(bot))