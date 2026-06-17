import discord
from discord.ui import Modal, Select, TextInput, View

from config import LOG_EVENT_CATEGORIES, LOG_EVENT_LABELS
from database import db
from utils.helpers import get_available_log_channels
from utils.strings import strings


def _t(language: str, en: str, ar: str) -> str:
    return ar if language == "ar" else en


def _event_label(language: str, event_key: str) -> str:
    return LOG_EVENT_LABELS.get(event_key, event_key.replace("_", " ").title())


LOG_CATEGORY_LABELS = {
    "moderation": "Moderation",
    "members": "Members",
    "messages": "Messages",
    "voice": "Voice",
    "channels": "Channels",
    "threads": "Threads",
    "server": "Server",
    "onboarding": "Onboarding",
    "roles": "Roles",
    "invites": "Invites",
}


def _category_label(category_key: str) -> str:
    return LOG_CATEGORY_LABELS.get(category_key, category_key.replace("_", " ").title())


def _get_primary_channel_id(settings: dict) -> int | None:
    log_channels = settings.get("log_channels", [])
    if isinstance(log_channels, list) and log_channels:
        try:
            return int(log_channels[0])
        except (TypeError, ValueError):
            return None

    advanced_logs = settings.get("advanced_logs", {})
    try:
        candidate = int(advanced_logs.get("primary_channel_id"))
    except (TypeError, ValueError, AttributeError):
        return None
    return candidate if candidate > 0 else None


def _get_event_overrides(settings: dict) -> dict[str, int]:
    advanced_logs = settings.get("advanced_logs", {})
    overrides = advanced_logs.get("event_overrides", {}) if isinstance(advanced_logs, dict) else {}
    if not isinstance(overrides, dict):
        return {}

    cleaned: dict[str, int] = {}
    for event_name, channel_id in overrides.items():
        try:
            parsed = int(channel_id)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            cleaned[event_name] = parsed
    return cleaned


def _channel_name(guild: discord.Guild, channel_id: int | None) -> str:
    if not channel_id:
        return "Not set"
    channel = guild.get_channel(channel_id)
    if channel is None:
        return f"Deleted (`{channel_id}`)"
    return f"{channel.mention} (`{channel.id}`)"


def build_logs_overview_embed(language: str, settings: dict, guild: discord.Guild) -> discord.Embed:
    primary_channel_id = _get_primary_channel_id(settings)
    overrides = _get_event_overrides(settings)

    embed = discord.Embed(
        title=strings[language]["advanced_logs_title"],
        description=_t(
            language,
            "**Primary + Overrides routing**\nEach event goes to one destination only: its override channel, or the primary channel as fallback.",
            "**توجيه Primary + Overrides**\nكل حدث يذهب إلى وجهة واحدة فقط: قناة الـ Override الخاصة به، أو القناة الرئيسية كبديل.",
        ),
        color=discord.Color.blue(),
    )
    embed.add_field(
        name=_t(language, "Primary Channel", "القناة الرئيسية"),
        value=_channel_name(guild, primary_channel_id),
        inline=False,
    )
    embed.add_field(
        name=_t(language, "Override Count", "عدد الـ Overrides"),
        value=str(len(overrides)),
        inline=True,
    )
    embed.add_field(
        name=_t(language, "Usable Channels", "القنوات المتاحة"),
        value=str(len(get_available_log_channels(guild))),
        inline=True,
    )

    if overrides:
        for category_key, event_names in LOG_EVENT_CATEGORIES.items():
            lines = []
            for event_name in event_names:
                channel_id = overrides.get(event_name)
                if not channel_id:
                    continue
                lines.append(f"• **{_event_label(language, event_name)}** → {_channel_name(guild, channel_id)}")
            if lines:
                embed.add_field(name=_category_label(category_key), value="\n".join(lines)[:1024], inline=False)
    else:
        embed.add_field(
            name=_t(language, "Overrides", "الـ Overrides"),
            value=_t(language, "No event overrides configured.", "لا توجد Overrides مخصصة حالياً."),
            inline=False,
        )

    return embed


class OwnedView(View):
    def __init__(self, owner_id: int, language: str, *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.language = language

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                strings[self.language].get("only_command_user", "Only the command user can use this panel."),
                ephemeral=True,
            )
            return False
        return True


class PrimaryChannelModal(Modal):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild):
        super().__init__(title="Set Primary Log Channel")
        self.owner_id = owner_id
        self.language = language
        self.guild = guild
        self.channel_id = TextInput(
            label="Channel ID",
            placeholder="Enter a text channel ID...",
            required=True,
            max_length=25,
        )
        self.add_item(self.channel_id)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("Only the command user can use this panel.", ephemeral=True)

        try:
            channel_id = int(self.channel_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)

        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("❌ Channel not found or not a text channel.", ephemeral=True)

        if channel not in get_available_log_channels(self.guild):
            return await interaction.response.send_message("❌ Bot cannot send logs to that channel.", ephemeral=True)

        await db.update_primary_log_channel(self.guild.id, channel_id)
        await interaction.response.send_message(
            f"✅ Primary log channel set to {channel.mention} (`{channel.id}`)",
            ephemeral=True,
        )


class OverrideChannelModal(Modal):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild, event_name: str):
        super().__init__(title=f"Override: {LOG_EVENT_LABELS.get(event_name, event_name)}")
        self.owner_id = owner_id
        self.language = language
        self.guild = guild
        self.event_name = event_name
        self.channel_id = TextInput(
            label="Channel ID",
            placeholder="Enter a text channel ID...",
            required=True,
            max_length=25,
        )
        self.add_item(self.channel_id)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("Only the command user can use this panel.", ephemeral=True)

        try:
            channel_id = int(self.channel_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)

        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("❌ Channel not found or not a text channel.", ephemeral=True)

        if channel not in get_available_log_channels(self.guild):
            return await interaction.response.send_message("❌ Bot cannot send logs to that channel.", ephemeral=True)

        await db.update_event_log_override(self.guild.id, self.event_name, channel_id)
        await interaction.response.send_message(
            f"✅ Override set for **{_event_label(self.language, self.event_name)}** → {channel.mention} (`{channel.id}`)",
            ephemeral=True,
        )


class PrimaryLogChannelSelect(Select):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild, primary_channel_id: int | None):
        self.owner_id = owner_id
        self.language = language
        self.guild = guild

        options = []
        for channel in get_available_log_channels(guild)[:25]:
            options.append(
                discord.SelectOption(
                    label=f"#{channel.name}"[:100],
                    value=str(channel.id),
                    description=f"ID: {channel.id}"[:100],
                    default=channel.id == primary_channel_id,
                )
            )

        has_options = bool(options)
        if not has_options:
            options.append(
                discord.SelectOption(
                    label="No usable text channels",
                    value="0",
                    description="Bot needs View + Send permissions.",
                )
            )

        super().__init__(
            placeholder="Choose primary log channel...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="primary_log_channel_select",
            disabled=not has_options,
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        if channel_id <= 0:
            return await interaction.response.send_message("❌ No usable channel selected.", ephemeral=True)

        await db.update_primary_log_channel(interaction.guild_id, channel_id)
        settings = await db.get_guild_settings(interaction.guild_id)
        view = AdvancedLogsView(self.owner_id, self.language, settings, interaction.guild)
        embed = build_logs_overview_embed(self.language, settings, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class OverrideCategorySelect(Select):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild):
        self.owner_id = owner_id
        self.language = language
        self.guild = guild
        options = [
            discord.SelectOption(
                label=_category_label(category_key),
                value=category_key,
                description=f"{len(event_names)} events",
            )
            for category_key, event_names in LOG_EVENT_CATEGORIES.items()
        ]
        super().__init__(
            placeholder="Select an event category...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="override_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        settings = await db.get_guild_settings(interaction.guild_id)
        category_key = self.values[0]
        view = OverrideEventListView(self.owner_id, self.language, self.guild, settings, category_key)
        embed = discord.Embed(
            title=f"{_category_label(category_key)} Overrides",
            description="Choose an event, then assign a dedicated log channel for it.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class OverrideEventSelect(Select):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild, settings: dict, category_key: str):
        self.owner_id = owner_id
        self.language = language
        self.guild = guild
        self.settings = settings
        self.category_key = category_key
        overrides = _get_event_overrides(settings)

        options = []
        for event_name in LOG_EVENT_CATEGORIES[category_key]:
            channel_id = overrides.get(event_name)
            options.append(
                discord.SelectOption(
                    label=_event_label(language, event_name)[:100],
                    value=event_name,
                    description=_channel_name(guild, channel_id)[:100] if channel_id else "Uses primary channel",
                )
            )

        super().__init__(
            placeholder="Select an event...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="override_event_select",
        )

    async def callback(self, interaction: discord.Interaction):
        settings = await db.get_guild_settings(interaction.guild_id)
        event_name = self.values[0]
        view = OverrideRoutingView(self.owner_id, self.language, self.guild, settings, self.category_key, event_name)
        primary_channel_id = _get_primary_channel_id(settings)
        overrides = _get_event_overrides(settings)
        embed = discord.Embed(
            title=_event_label(self.language, event_name),
            description="Assign a dedicated channel or reset the event to use the primary channel.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Primary", value=_channel_name(self.guild, primary_channel_id), inline=False)
        embed.add_field(
            name="Current Override",
            value=_channel_name(self.guild, overrides.get(event_name)) if overrides.get(event_name) else "Uses primary channel",
            inline=False,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class OverrideChannelSelect(Select):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild, settings: dict, category_key: str, event_name: str):
        self.owner_id = owner_id
        self.language = language
        self.guild = guild
        self.category_key = category_key
        self.event_name = event_name
        current_override = _get_event_overrides(settings).get(event_name)

        options = []
        for channel in get_available_log_channels(guild)[:25]:
            options.append(
                discord.SelectOption(
                    label=f"#{channel.name}"[:100],
                    value=str(channel.id),
                    description=f"ID: {channel.id}"[:100],
                    default=channel.id == current_override,
                )
            )

        has_options = bool(options)
        if not has_options:
            options.append(
                discord.SelectOption(
                    label="No usable text channels",
                    value="0",
                    description="Bot needs View + Send permissions.",
                )
            )

        super().__init__(
            placeholder="Choose override channel...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"override_channel_select_{event_name}",
            disabled=not has_options,
        )

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        if channel_id <= 0:
            return await interaction.response.send_message("❌ No usable channel selected.", ephemeral=True)

        await db.update_event_log_override(interaction.guild_id, self.event_name, channel_id)
        settings = await db.get_guild_settings(interaction.guild_id)
        view = OverrideRoutingView(self.owner_id, self.language, self.guild, settings, self.category_key, self.event_name)
        embed = discord.Embed(
            title=_event_label(self.language, self.event_name),
            description=f"✅ Override updated to {_channel_name(self.guild, channel_id)}",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class AdvancedLogsView(OwnedView):
    def __init__(self, owner_id: int, language: str, settings: dict, guild: discord.Guild):
        super().__init__(owner_id, language, timeout=180)
        self.guild = guild
        self.settings = settings
        self.add_item(PrimaryLogChannelSelect(owner_id, language, guild, _get_primary_channel_id(settings)))
        self.configure_events.label = _t(language, "Configure Overrides", "ضبط الـ Overrides")
        self.view_selected.label = _t(language, "View Routing", "عرض التوجيه")
        self.search_channels.label = _t(language, "Primary by ID", "تعيين الرئيسي عبر ID")
        self.select_all.label = _t(language, "Clear Overrides", "مسح الـ Overrides")
        self.clear_all.label = _t(language, "Clear Primary", "مسح الرئيسي")

    @discord.ui.button(label="Configure Overrides", style=discord.ButtonStyle.primary, emoji="🔧", row=1)
    async def configure_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await db.get_guild_settings(interaction.guild_id)
        view = OverrideCategoryView(self.owner_id, self.language, interaction.guild)
        embed = discord.Embed(
            title="Event Override Categories",
            description="Choose a category, then assign a dedicated channel for any event.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Primary", value=_channel_name(interaction.guild, _get_primary_channel_id(settings)), inline=False)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="View Routing", style=discord.ButtonStyle.primary, emoji="👁️", row=1)
    async def view_selected(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await db.get_guild_settings(interaction.guild_id)
        embed = build_logs_overview_embed(self.language, settings, interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Primary by ID", style=discord.ButtonStyle.secondary, emoji="🔢", row=2)
    async def search_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PrimaryChannelModal(self.owner_id, self.language, interaction.guild))

    @discord.ui.button(label="Clear Overrides", style=discord.ButtonStyle.secondary, emoji="🧹", row=2)
    async def select_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.clear_event_log_overrides(interaction.guild_id)
        settings = await db.get_guild_settings(interaction.guild_id)
        view = AdvancedLogsView(self.owner_id, self.language, settings, interaction.guild)
        embed = build_logs_overview_embed(self.language, settings, interaction.guild)
        embed.description = "✅ All event overrides cleared."
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Clear Primary", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.update_primary_log_channel(interaction.guild_id, None)
        settings = await db.get_guild_settings(interaction.guild_id)
        view = AdvancedLogsView(self.owner_id, self.language, settings, interaction.guild)
        embed = build_logs_overview_embed(self.language, settings, interaction.guild)
        embed.description = "✅ Primary log channel cleared."
        await interaction.response.edit_message(embed=embed, view=view)


class OverrideCategoryView(OwnedView):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild):
        super().__init__(owner_id, language, timeout=180)
        self.guild = guild
        self.add_item(OverrideCategorySelect(owner_id, language, guild))


class OverrideEventListView(OwnedView):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild, settings: dict, category_key: str):
        super().__init__(owner_id, language, timeout=180)
        self.guild = guild
        self.category_key = category_key
        self.add_item(OverrideEventSelect(owner_id, language, guild, settings, category_key))
        self.back_to_categories.label = _t(language, "Back to Categories", "العودة للفئات")

    @discord.ui.button(label="Back to Categories", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back_to_categories(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = OverrideCategoryView(self.owner_id, self.language, self.guild)
        embed = discord.Embed(
            title="Event Override Categories",
            description="Choose a category, then assign a dedicated channel for any event.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class OverrideRoutingView(OwnedView):
    def __init__(self, owner_id: int, language: str, guild: discord.Guild, settings: dict, category_key: str, event_name: str):
        super().__init__(owner_id, language, timeout=180)
        self.guild = guild
        self.category_key = category_key
        self.event_name = event_name
        self.add_item(OverrideChannelSelect(owner_id, language, guild, settings, category_key, event_name))
        self.set_by_id.label = _t(language, "Override by ID", "تعيين عبر ID")
        self.use_primary.label = _t(language, "Use Primary", "استخدم الرئيسي")
        self.back_to_events.label = _t(language, "Back to Events", "العودة للأحداث")

    @discord.ui.button(label="Override by ID", style=discord.ButtonStyle.primary, emoji="🔢", row=1)
    async def set_by_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OverrideChannelModal(self.owner_id, self.language, self.guild, self.event_name))

    @discord.ui.button(label="Use Primary", style=discord.ButtonStyle.secondary, emoji="↩️", row=1)
    async def use_primary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.remove_event_log_override(interaction.guild_id, self.event_name)
        settings = await db.get_guild_settings(interaction.guild_id)
        view = OverrideRoutingView(self.owner_id, self.language, self.guild, settings, self.category_key, self.event_name)
        embed = discord.Embed(
            title=_event_label(self.language, self.event_name),
            description="✅ Override removed. This event now uses the primary channel.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back to Events", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back_to_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await db.get_guild_settings(interaction.guild_id)
        view = OverrideEventListView(self.owner_id, self.language, self.guild, settings, self.category_key)
        embed = discord.Embed(
            title=f"{_category_label(self.category_key)} Overrides",
            description="Choose an event, then assign a dedicated log channel for it.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)
