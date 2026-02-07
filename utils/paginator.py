import discord
from discord.ui import View, LayoutView, Container, ActionRow, Button, TextDisplay, Section, Separator, Modal, TextInput
from typing import List, Any, Callable


class GoToPageModal(Modal):
    def __init__(self, parent_paginator: Any, max_pages: int):
        super().__init__(title="Go to Page")
        self.parent = parent_paginator
        self.max_pages = max_pages
        self.page_input = TextInput(
            label=f"Enter Page Number (between 1 and {max_pages})",
            default=str(self.parent.page),
            min_length=1,
            max_length=len(str(max_pages))
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_num = int(self.page_input.value)
            if 1 <= page_num <= self.max_pages:
                self.parent.page = page_num
                await self.parent.update_view(interaction)
            else:
                await interaction.response.send_message(f"Please enter a number between 1 and {self.max_pages}.",
                                                        ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid number entered.", ephemeral=True)


class ViewPaginator(View):
    def __init__(self, data: List[Any], per_page: int = 10, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.data = data
        self.page = 1
        self.per_page = per_page
        self.total_pages = (len(data) - 1) // per_page + 1 if data else 1

    def get_current_page_data(self):
        start = (self.page - 1) * self.per_page
        return self.data[start: start + self.per_page]

    async def update_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if self.page > 1:
            self.page -= 1
            await self.update_view(interaction)

    @discord.ui.button(label="Go To Page", style=discord.ButtonStyle.gray)
    async def go_to_page(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(GoToPageModal(self, self.total_pages))

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages:
            self.page += 1
            await self.update_view(interaction)


class LayoutViewPaginator(LayoutView):
    def __init__(self, user: discord.User, data: List[Any], per_page: int = 5):
        super().__init__(timeout=None)
        self.user = user
        self.data = data
        self.page = 1
        self.per_page = per_page
        self.total_pages = (len(data) - 1) // per_page + 1 if data else 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return False
        return True

    def get_current_page_data(self):
        start = (self.page - 1) * self.per_page
        return self.data[start: start + self.per_page]

    async def update_view(self, interaction: discord.Interaction):
        self.build_layout()
        await interaction.response.edit_message(view=self)

    def add_pagination_controls(self, container: Container):
        container.add_item(TextDisplay(f"-# Page {self.page} of {self.total_pages}"))
        container.add_item(Separator())

        row = ActionRow()

        left_btn = Button(emoji="◀️", style=discord.ButtonStyle.primary, disabled=self.page == 1)
        left_btn.callback = self.prev_callback

        go_btn = Button(label="Go to Page", style=discord.ButtonStyle.secondary, disabled=self.total_pages <= 1)
        go_btn.callback = self.goto_callback

        right_btn = Button(emoji="▶️", style=discord.ButtonStyle.primary, disabled=self.page == self.total_pages)
        right_btn.callback = self.next_callback

        row.add_item(left_btn)
        row.add_item(go_btn)
        row.add_item(right_btn)
        container.add_item(row)

    async def prev_callback(self, interaction: discord.Interaction):
        self.page -= 1
        await self.update_view(interaction)

    async def next_callback(self, interaction: discord.Interaction):
        self.page += 1
        await self.update_view(interaction)

    async def goto_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GoToPageModal(self, self.total_pages))