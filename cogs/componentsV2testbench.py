import discord
from discord.ext import commands
from discord import app_commands
from dopamineframework import PrivateLayoutView

class TemplateHomepage(PrivateLayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## Giveaway Templates")))
        container.add_item(discord.ui.TextDisplay("Giveaway Templates allow you to quicky start a giveaway without needing to manually make one from scratch. To create a new template, go to My Stuff. To browse through the list of user-created templates, click on Browse Templates."))
        container.add_item(discord.ui.Separator())

        repo_btn = discord.ui.Button(label="Browse Templates", style=discord.ButtonStyle.primary)
        my_btn = discord.ui.Button(label="My Stuff", style=discord.ButtonStyle.secondary)
        row = discord.ui.ActionRow()

        row.add_item(repo_btn)
        row.add_item(my_btn)

        container.add_item(row)

        self.add_item(container)

class MystuffPage(PrivateLayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## My Stuff")))
        container.add_item(discord.ui.TextDisplay("Manage all your templates here. Publish a template, edit it, or create a new one."))
        container.add_item(discord.ui.Separator())

        edit_btn = discord.ui.Button(label="Edit", style=discord.ButtonStyle.secondary)

        container.add_item(discord.ui.Section(discord.ui.TextDisplay(
            "### 1. Prize Name\n**Winners:** placeholder\n**Duration:** placeholder (duration, not end time)\n**Channel:** placeholder\n**Giveaway Host:** placeholder\n**Extra Entries Role:** placeholder\n**Required Roles:** placeholder\n**Required Roles Behaviour:** placeholder\n**Winner Role:** placeholder\n**Blacklisted Roles** placeholder\n**Embed Image:** placeholder for yes (only shown if there is one)\n**Embed Thumbnail:** placeholder for yes (only shown if there is one)\n**Colour:** placeholder (default if default)"),
                                              accessory=edit_btn))
        container.add_item(discord.ui.TextDisplay("-# Page 1 of 1"))
        container.add_item(discord.ui.Separator())
        left_btn = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.primary,
                                     disabled=1 == 1)
        go_btn = discord.ui.Button(label="Go to Page", style=discord.ButtonStyle.secondary,
                                   disabled=2 == 2)
        right_btn = discord.ui.Button(emoji="◀▶️", style=discord.ButtonStyle.primary,
                                      disabled=3 == 3)
        row = discord.ui.ActionRow()

        row.add_item(left_btn)
        row.add_item(go_btn)
        row.add_item(right_btn)

        container.add_item(row)
        container.add_item(discord.ui.Separator())
        create_btn = discord.ui.Button(label="Create New Template", style=discord.ButtonStyle.primary)
        row = discord.ui.ActionRow()

        row.add_item(create_btn)

        container.add_item(row)

        self.add_item(container)


class EditPage(PrivateLayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## Edit: prizename")))
        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay(
            "**Winners:** placeholder\n**Duration:** placeholder (duration, not end time)\n**Channel:** placeholder\n**Giveaway Host:** placeholder\n**Extra Entries Role:** placeholder\n**Required Roles:** placeholder\n**Required Roles Behaviour:** placeholder\n**Winner Role:** placeholder\n**Blacklisted Roles** placeholder\n**Embed Image:** placeholder for yes (only shown if there is one)\n**Embed Thumbnail:** placeholder for yes (only shown if there is one)\n**Colour:** placeholder (default if default)"))

        container.add_item(discord.ui.Separator())
        edit_btn = discord.ui.Button(label="Edit",
                                       style=discord.ButtonStyle.secondary)
        publish_btn = discord.ui.Button(label="{'Publish' if 1==1 else 'Unpublish'}",
                                       style=discord.ButtonStyle.primary if 1==1 else discord.ButtonStyle.secondary)
        delete_btn = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger)
        row = discord.ui.ActionRow()

        row.add_item(publish_btn)
        row.add_item(edit_btn)
        row.add_item(delete_btn)

        container.add_item(row)

        self.add_item(container)

class BrowsePage(PrivateLayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## Browse — 23 (if exclude global is enabled, it shows the count of templates in current guild) Total Templates")))
        container.add_item(discord.ui.TextDisplay("Browse Giveaway templates here. Use the buttons and dropdowns below to search, or sort."))
        container.add_item(discord.ui.Separator())

        use_btn = discord.ui.Button(label="Use", style=discord.ButtonStyle.primary)
        usee_btn = discord.ui.Button(label="Use", style=discord.ButtonStyle.primary)
        container.add_item(discord.ui.Section(discord.ui.TextDisplay(
            "### 1. Prize Name (Created by: creatorname in guildname) - placeholder for number of usages (only shown if sorting my usage)\n**Template ID:** [adjective-noun-number]\n**Winners:** placeholder\n**Duration:** placeholder (duration, not end time)\n**Embed Image:** placeholder for yes (only shown if there is one)\n**Embed Thumbnail:** placeholder for yes (only shown if there is one)\n**Colour:** placeholder (default if default)"),
                                              accessory=use_btn))
        container.add_item(discord.ui.Section(discord.ui.TextDisplay(
            "### 2. Prize Name (Created by: creatorname)\n**Template ID:** [adjective-noun-number]\n**Winners:** placeholder\n**Duration:** placeholder (duration, not end time)\n**Channel:** placeholder\n**Giveaway Host:** placeholder\n**Extra Entries Role:** placeholder\n**Required Roles:** placeholder\n**Required Roles Behaviour:** placeholder\n**Winner Role:** placeholder\n**Blacklisted Roles** placeholder\n**Embed Image:** placeholder for yes (only shown if there is one)\n**Embed Thumbnail:** placeholder for yes (only shown if there is one)\n**Colour:** placeholder (default if default)"),
                                              accessory=usee_btn))
        container.add_item(discord.ui.TextDisplay("-# Page 1 of 1"))
        container.add_item(discord.ui.Separator())
        left_btn = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.primary, disabled=1==1)
        go_btn = discord.ui.Button(label="Go to Page", style=discord.ButtonStyle.secondary, disabled=2==2)
        right_btn = discord.ui.Button(emoji="◀▶️", style=discord.ButtonStyle.primary, disabled=3==3)
        row = discord.ui.ActionRow()

        row.add_item(left_btn)
        row.add_item(go_btn)
        row.add_item(right_btn)

        container.add_item(row)

        container.add_item(discord.ui.Separator())

        searchprize_btn = discord.ui.Button(label="Search by Prize",
                                       style=discord.ButtonStyle.primary)
        searchID_btn = discord.ui.Button(label="Search by ID",
                                            style=discord.ButtonStyle.primary)
        exclude_btn = discord.ui.Button(label=f"{'Exclude Global Templates' if 4==4 else 'Include Global Templates'}", style=discord.ButtonStyle.secondary if 4==4 else discord.ButtonStyle.secondary)

        row = discord.ui.ActionRow()

        row.add_item(searchprize_btn)
        row.add_item(searchID_btn)
        row.add_item(exclude_btn)

        container.add_item(row)

        sort_dropdown = discord.ui.Select(placeholder=f"placeholder for current mode", options=['Sort by Most Popular', 'Sort by Least Popular', 'Sort by Alphabetical Order', 'Sort by Reversed Alphabetical Order'])

        row = discord.ui.ActionRow()
        row.add_item(sort_dropdown)
        container.add_item(row)


        self.add_item(container)

class CreatewithtemplatePage(PrivateLayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## Choose an option below to continue creating with template.")))
        container.add_item(discord.ui.Separator())

        id_btn = discord.ui.Button(label="Enter Template ID",
                                       style=discord.ButtonStyle.primary)
        browse_btn = discord.ui.Button(label="Browse Templates",
                                       style=discord.ButtonStyle.primary)
        my_btn = discord.ui.Button(label="My Templates", style=discord.ButtonStyle.secondary)
        row = discord.ui.ActionRow()

        row.add_item(id_btn)
        row.add_item(browse_btn)
        row.add_item(my_btn)

        container.add_item(row)

        self.add_item(container)

class MystuffUse(PrivateLayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container()
        container.add_item((discord.ui.TextDisplay("## My Templates")))
        container.add_item(discord.ui.Separator())

        use_btn = discord.ui.Button(label="Use", style=discord.ButtonStyle.secondary)

        container.add_item(discord.ui.Section(discord.ui.TextDisplay(
            "### 1. Prize Name\n**Winners:** placeholder\n**Duration:** placeholder (duration, not end time)\n**Channel:** placeholder\n**Giveaway Host:** placeholder\n**Extra Entries Role:** placeholder\n**Required Roles:** placeholder\n**Required Roles Behaviour:** placeholder\n**Winner Role:** placeholder\n**Blacklisted Roles** placeholder\n**Embed Image:** placeholder for yes (only shown if there is one)\n**Embed Thumbnail:** placeholder for yes (only shown if there is one)\n**Colour:** placeholder (default if default)"),
                                              accessory=use_btn))
        container.add_item(discord.ui.TextDisplay("-# Page 1 of 1"))
        container.add_item(discord.ui.Separator())
        left_btn = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.primary,
                                     disabled=1 == 1)
        go_btn = discord.ui.Button(label="Go to Page", style=discord.ButtonStyle.secondary,
                                   disabled=2 == 2)
        right_btn = discord.ui.Button(emoji="◀▶️", style=discord.ButtonStyle.primary,
                                      disabled=3 == 3)
        row = discord.ui.ActionRow()

        row.add_item(left_btn)
        row.add_item(go_btn)
        row.add_item(right_btn)

        container.add_item(row)

        self.add_item(container)

class GoToPageModal(discord.ui.Modal):
    def __init__(self, parent_view: "ManagePage", total_pages: int):
        super().__init__(title="Jump to Page")
        self.parent_view = parent_view
        self.total_pages = total_pages

        self.page_input = discord.ui.TextInput(
            label=f"Page Number (1-{total_pages})",
            placeholder="Enter a page number...",
            min_length=1,
            max_length=5,
            required=True,
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
                await interaction.response.send_message(
                    f"Please enter a number between 1 and {self.total_pages}.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                "Invalid input. Please enter a valid whole number.",
                ephemeral=True
            )



class DestructiveConfirmationView(PrivateLayoutView):
    def __init__(self, user, title_name, cog, guild_id):
        super().__init__(user, timeout=30)
        self.title_name = title_name
        self.cog = cog
        self.color = None
        self.guild_id = guild_id
        self.value = None
        self.title_text = "Delete Giveaway Template"
        self.body_text = f"Are you sure you want to delete template for [placeholder for prize]? This cannot be undone."
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container(accent_color=self.color)
        container.add_item(discord.ui.TextDisplay(f"### {self.title_text}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(self.body_text))

        is_disabled = self.value is not None
        action_row = discord.ui.ActionRow()
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.gray, disabled=is_disabled)
        confirm = discord.ui.Button(label="Delete Permanently", style=discord.ButtonStyle.red, disabled=is_disabled)

        cancel.callback = self.cancel_callback
        confirm.callback = self.confirm_callback

        action_row.add_item(cancel)
        action_row.add_item(confirm)
        container.add_item(discord.ui.Separator())
        container.add_item(action_row)

        self.add_item(container)

    async def update_view(self, interaction: discord.Interaction, title: str, color: discord.Color):
        self.title_text = title
        self.body_text = f"~~{self.body_text}~~"
        self.build_layout()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        self.value = False
        await self.update_view(interaction, "Action Canceled", discord.Color(0xdf5046))

    async def confirm_callback(self, interaction: discord.Interaction):
        self.value = True
        await self.update_view(interaction, "Action Confirmed", discord.Color.green())
        await self.cog.delete_panel(self.guild_id, self.title_name)

    async def on_timeout(self, interaction: discord.Interaction):
        if self.value is None:
            self.value = False
            await self.update_view(interaction, "Timed Out", discord.Color(0xdf5046))

class ConfirmationView(PrivateLayoutView):
    def __init__(self, user, title_name, cog, guild_id):
        super().__init__(user, timeout=30)
        self.title_name = title_name
        self.cog = cog
        self.color = None
        self.guild_id = guild_id
        self.value = None
        self.title_text = "Publish Giveaway Template"
        self.body_text = f"Are you sure you want to **globally** publish template for **[placeholder for prize]**? Anyone will be able to search and use your template."
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        container = discord.ui.Container(accent_color=self.color)
        container.add_item(discord.ui.TextDisplay(f"### {self.title_text}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(self.body_text))

        is_disabled = self.value is not None
        action_row = discord.ui.ActionRow()
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, disabled=is_disabled)
        confirm = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green, disabled=is_disabled)

        cancel.callback = self.cancel_callback
        confirm.callback = self.confirm_callback

        action_row.add_item(cancel)
        action_row.add_item(confirm)
        container.add_item(discord.ui.Separator())
        container.add_item(action_row)

        self.add_item(container)

    async def update_view(self, interaction: discord.Interaction, title: str, color: discord.Color):
        self.title_text = title
        self.body_text = f"~~{self.body_text}~~"
        self.build_layout()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        self.value = False
        await self.update_view(interaction, "Action Canceled", discord.Color(0xdf5046))

    async def confirm_callback(self, interaction: discord.Interaction):
        self.value = True
        await self.update_view(interaction, "Action Confirmed", discord.Color.green())
        await self.cog.delete_panel(self.guild_id, self.title_name)

    async def on_timeout(self, interaction: discord.Interaction):
        if self.value is None:
            self.value = False
            await self.update_view(interaction, "Timed Out", discord.Color(0xdf5046))


class CV2TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="cv2test", description="Tests Discord Components V2 layout")
    async def cv2test(self, interaction: discord.Interaction):
        view = BrowsePage()
        await interaction.response.send_message(
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CV2TestCog(bot))