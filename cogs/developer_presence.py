import json
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import DEVELOPER_PRESENCE_GUILD_ID, OWNER_IDS


def _presence_guild_scope():
    try:
        guild_id = int(DEVELOPER_PRESENCE_GUILD_ID)
    except (TypeError, ValueError):
        guild_id = 0

    if guild_id <= 0:
        def passthrough(func):
            return func
        return passthrough

    return app_commands.guilds(discord.Object(id=guild_id))


class DeveloperPresenceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.state_file = os.path.join("database", "guild_presence_settings.json")

    @staticmethod
    def _is_owner(user_id: int) -> bool:
        return user_id in OWNER_IDS

    def _save_guild_presence(self, guild_id: int, payload: dict) -> None:
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        data = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as file:
                    parsed = json.load(file)
                    if isinstance(parsed, dict):
                        data = parsed
            except (OSError, json.JSONDecodeError):
                data = {}

        data[str(guild_id)] = payload

        with open(self.state_file, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    @app_commands.command(
        name="presence",
        description="Change bot presence (Developer only) | تغيير حالة البوت (للمطور فقط)",
    )
    @_presence_guild_scope()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        activity_type="Activity type | نوع النشاط",
        text="Activity text | نص النشاط",
        status="Online status | حالة الاتصال",
        stream_url="Streaming URL (required for streaming) | رابط البث (مطلوب للبث)",
    )
    @app_commands.choices(
        activity_type=[
            app_commands.Choice(name="Playing | يلعب", value="playing"),
            app_commands.Choice(name="Listening | يستمع", value="listening"),
            app_commands.Choice(name="Watching | يشاهد", value="watching"),
            app_commands.Choice(name="Competing | يتنافس", value="competing"),
            app_commands.Choice(name="Streaming | بث مباشر", value="streaming"),
        ],
        status=[
            app_commands.Choice(name="Online | متصل", value="online"),
            app_commands.Choice(name="Idle | خامل", value="idle"),
            app_commands.Choice(name="Do Not Disturb | مشغول", value="dnd"),
            app_commands.Choice(name="Invisible | مخفي", value="invisible"),
        ],
    )
    async def presence(
        self,
        interaction: discord.Interaction,
        activity_type: app_commands.Choice[str],
        text: str,
        status: Optional[app_commands.Choice[str]] = None,
        stream_url: Optional[str] = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command works in servers only.\nهذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )

        if not self._is_owner(interaction.user.id):
            return await interaction.response.send_message(
                "This command is for the developer only.\nهذا الأمر خاص بالمطور فقط.",
                ephemeral=True,
            )

        selected_status = (status.value if status else "online").lower()
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        target_status = status_map.get(selected_status, discord.Status.online)

        selected_activity = activity_type.value
        activity: discord.BaseActivity

        if selected_activity == "playing":
            activity = discord.Game(name=text)
        elif selected_activity == "listening":
            activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif selected_activity == "watching":
            activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        elif selected_activity == "competing":
            activity = discord.Activity(type=discord.ActivityType.competing, name=text)
        elif selected_activity == "streaming":
            if not stream_url or not stream_url.startswith(("http://", "https://")):
                return await interaction.response.send_message(
                    "Streaming needs a valid URL.\nالبث المباشر يحتاج رابط صحيح يبدأ بـ http/https.",
                    ephemeral=True,
                )
            activity = discord.Streaming(name=text, url=stream_url)
        else:
            activity = discord.Game(name=text)

        await self.bot.change_presence(status=target_status, activity=activity)
        self.bot.custom_presence = True

        self._save_guild_presence(
            interaction.guild.id,
            {
                "activity_type": selected_activity,
                "text": text,
                "status": selected_status,
                "stream_url": stream_url or "",
                "updated_by": interaction.user.id,
            },
        )

        embed = discord.Embed(
            title="✅ Presence Updated | تم تحديث الحالة",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Activity | النشاط",
            value=f"`{selected_activity}` - **{text}**",
            inline=False,
        )
        embed.add_field(
            name="Status | الحالة",
            value=f"`{selected_status}`",
            inline=True,
        )
        embed.add_field(
            name="Scope | النطاق",
            value="Manual developer mode enabled (auto updates paused)\nتم تفعيل الوضع اليدوي للمطور (إيقاف التحديث التلقائي)",
            inline=False,
        )
        if stream_url:
            embed.add_field(name="Stream URL", value=stream_url, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DeveloperPresenceCog(bot))
