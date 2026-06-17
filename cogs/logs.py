import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui.log_views import AdvancedLogsView, build_logs_overview_embed
from ui.views import LanguageView
from utils.helpers import get_available_log_channels, sanitize_log_channels
from utils.strings import strings


def _t(language: str, en: str, ar: str) -> str:
    return ar if language == "ar" else en


class LogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setlogs",
        description="Manage advanced logs channels | إدارة قنوات السجلات المتقدمة",
    )
    @app_commands.default_permissions(administrator=True)
    async def setlogs(self, interaction: discord.Interaction):
        """Manage log routing using one primary channel plus per-event overrides."""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command works in servers only.",
                ephemeral=True,
            )

        settings = await db.get_guild_settings(interaction.guild.id)
        lang = settings.get("language", "en")
        raw_log_channels = settings.get("log_channels", [])
        log_channels, removed_channels = sanitize_log_channels(interaction.guild, raw_log_channels)
        primary_channel_id = log_channels[0] if log_channels else None

        overrides = await db.get_event_log_overrides(interaction.guild.id)
        cleaned_overrides = {}
        removed_overrides = []
        for event_name, channel_id in overrides.items():
            channel = interaction.guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel) and channel in get_available_log_channels(interaction.guild):
                cleaned_overrides[event_name] = channel_id
            else:
                removed_overrides.append(f"{event_name}:{channel_id}")

        advanced_logs = dict(settings.get("advanced_logs", {}))
        advanced_logs["primary_channel_id"] = primary_channel_id
        advanced_logs["event_overrides"] = cleaned_overrides

        if log_channels != raw_log_channels or cleaned_overrides != overrides:
            await db.set_guild_settings(
                interaction.guild.id,
                lang,
                [primary_channel_id] if primary_channel_id else [],
                settings["protection_settings"],
                advanced_logs,
                settings["automod_settings"],
            )
            settings = await db.get_guild_settings(interaction.guild.id)

        embed = build_logs_overview_embed(lang, settings, interaction.guild)
        if removed_channels or removed_overrides:
            removed_parts = []
            if removed_channels:
                removed_parts.append(f"channels: {', '.join(str(channel_id) for channel_id in removed_channels[:8])}")
            if removed_overrides:
                removed_parts.append(f"overrides: {', '.join(removed_overrides[:8])}")
            embed.add_field(
                name=_t(lang, "Auto Cleanup", "تنظيف تلقائي"),
                value=" | ".join(removed_parts),
                inline=False,
            )

        view = AdvancedLogsView(interaction.user.id, lang, settings, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="setlang",
        description="Change bot language (EN/AR) | تغيير لغة البوت",
    )
    @app_commands.default_permissions(administrator=True)
    async def setlang(self, interaction: discord.Interaction):
        """Change bot language."""
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command works in servers only.",
                ephemeral=True,
            )

        settings = await db.get_guild_settings(interaction.guild.id)
        lang = settings.get("language", "en")

        view = LanguageView(admin_id=interaction.user.id)
        embed = discord.Embed(
            title=strings[lang]["choose_language"],
            description=_t(
                lang,
                "**Only the command user can select language!**",
                "**فقط صاحب الأمر يمكنه اختيار اللغة!**",
            ),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(LogsCog(bot))
