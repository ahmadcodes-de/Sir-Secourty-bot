import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from ui.views import AdvancedProtectionView
from utils.strings import strings

I18N = {
    "en": {
        "cmd_antibots_desc": "Manage anti-bots protection options",
        "desc_action": "Enable, disable, or show anti-bots status",
        "desc_enforcement": "Action against blocked bots",
        "desc_allow_verified": "Allow verified Discord bots to join",
        "desc_whitelist_action": "Manage anti-bots whitelist",
        "desc_whitelist_bot_id": "Bot ID for add/remove whitelist operations",
        "title_antibots": "🛡️ Anti-Bots Protection",
        "status_enabled": "Enabled",
        "status_disabled": "Disabled",
        "usage_error_bot_id": "❌ Please provide a valid bot ID (numbers only).",
        "usage_error_whitelist_id_required": "❌ `whitelist_bot_id` is required for add/remove.",
        "updated": "✅ Anti-bots settings updated successfully.",
        "no_change": "ℹ️ No changes applied. Showing current status.",
        "enforcement": "Enforcement",
        "allow_verified": "Allow Verified Bots",
        "whitelist": "Whitelist",
        "mode": "Mode",
        "details": "Details",
        "added_whitelist": "Added bot `{bot_id}` to whitelist.",
        "removed_whitelist": "Removed bot `{bot_id}` from whitelist.",
        "already_whitelisted": "Bot `{bot_id}` is already in whitelist.",
        "not_in_whitelist": "Bot `{bot_id}` is not in whitelist.",
        "whitelist_cleared": "Whitelist cleared.",
        "cmd_scanbots_desc": "Scan and show all bots in the server",
        "scan_title": "🤖 Bot Scan Results",
        "stats": "📊 Statistics",
        "detected_bots": "🔍 Detected Bots",
        "and_more": "... and {count} more bots",
        "scan_footer": "Scan completed • {guild}",
        "cmd_settings_desc": "Advanced protection settings panel",
        "settings_panel_desc": "**🎛️ Interactive Settings Panel**\n\n• Select and update protection options instantly.",
        "cmd_check_desc": "Check current protection settings and status",
        "check_title": "🛡️ Protection Status",
        "check_settings": "🔧 Protection Settings",
        "active_tracking": "📊 Active Tracking",
        "no_tracking": "No active action tracking",
        "check_footer": "Protection tracking window: 10 seconds",
    },
    "ar": {
        "cmd_antibots_desc": "إدارة خيارات حماية مانع البوتات",
        "desc_action": "تفعيل أو تعطيل أو عرض حالة مانع البوتات",
        "desc_enforcement": "نوع الإجراء ضد البوتات الممنوعة",
        "desc_allow_verified": "السماح للبوتات الموثقة من ديسكورد",
        "desc_whitelist_action": "إدارة القائمة البيضاء لمانع البوتات",
        "desc_whitelist_bot_id": "معرف البوت لعمليات الإضافة/الإزالة من القائمة البيضاء",
        "title_antibots": "🛡️ حماية مانع البوتات",
        "status_enabled": "مفعّل",
        "status_disabled": "معطّل",
        "usage_error_bot_id": "❌ يرجى إدخال معرف بوت صحيح (أرقام فقط).",
        "usage_error_whitelist_id_required": "❌ يجب تمرير `whitelist_bot_id` مع add/remove.",
        "updated": "✅ تم تحديث إعدادات مانع البوتات بنجاح.",
        "no_change": "ℹ️ لم يتم تطبيق تغييرات. هذه هي الحالة الحالية.",
        "enforcement": "الإجراء",
        "allow_verified": "السماح بالبوتات الموثقة",
        "whitelist": "القائمة البيضاء",
        "mode": "الحالة",
        "details": "التفاصيل",
        "added_whitelist": "تمت إضافة البوت `{bot_id}` إلى القائمة البيضاء.",
        "removed_whitelist": "تمت إزالة البوت `{bot_id}` من القائمة البيضاء.",
        "already_whitelisted": "البوت `{bot_id}` موجود بالفعل في القائمة البيضاء.",
        "not_in_whitelist": "البوت `{bot_id}` غير موجود في القائمة البيضاء.",
        "whitelist_cleared": "تم مسح القائمة البيضاء.",
        "cmd_scanbots_desc": "فحص وعرض كل البوتات في السيرفر",
        "scan_title": "🤖 نتائج فحص البوتات",
        "stats": "📊 الإحصائيات",
        "detected_bots": "🔍 البوتات المكتشفة",
        "and_more": "... و {count} بوت إضافي",
        "scan_footer": "اكتمل الفحص • {guild}",
        "cmd_settings_desc": "لوحة إعدادات الحماية المتقدمة",
        "settings_panel_desc": "**🎛️ لوحة إعدادات تفاعلية**\n\n• اختر الإعدادات وحدثها مباشرة.",
        "cmd_check_desc": "فحص حالة وإعدادات الحماية الحالية",
        "check_title": "🛡️ حالة الحماية",
        "check_settings": "🔧 إعدادات الحماية",
        "active_tracking": "📊 التتبع النشط",
        "no_tracking": "لا يوجد تتبع نشط حاليًا",
        "check_footer": "نافذة تتبع الحماية: 10 ثوانٍ",
    },
}


def lang_for(guild_lang: Optional[str]) -> str:
    return "ar" if guild_lang == "ar" else "en"


def t(lang: str, key: str) -> str:
    return I18N[lang][key]


def status_label(lang: str, enabled: bool) -> str:
    return t(lang, "status_enabled") if enabled else t(lang, "status_disabled")


class ProtectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="antibots", description="Manage anti-bots protection options | إدارة خيارات مانع البوتات")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        action="Enable, disable, or show anti-bots status | تفعيل/تعطيل/حالة",
        enforcement="Action against blocked bots | الإجراء ضد البوت المخالف",
        allow_verified="Allow verified Discord bots | السماح للبوتات الموثقة",
        whitelist_action="Manage anti-bots whitelist | إدارة القائمة البيضاء",
        whitelist_bot_id="Bot ID for whitelist add/remove | معرف البوت للإضافة/الإزالة",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Enable | تفعيل", value="enable"),
            app_commands.Choice(name="Disable | تعطيل", value="disable"),
            app_commands.Choice(name="Status | الحالة", value="status"),
        ],
        enforcement=[
            app_commands.Choice(name="Kick | طرد", value="kick"),
            app_commands.Choice(name="Ban | حظر", value="ban"),
        ],
        whitelist_action=[
            app_commands.Choice(name="Add | إضافة", value="add"),
            app_commands.Choice(name="Remove | إزالة", value="remove"),
            app_commands.Choice(name="Show | عرض", value="show"),
            app_commands.Choice(name="Clear | مسح", value="clear"),
        ],
    )
    async def antibots(
        self,
        interaction: discord.Interaction,
        action: Optional[app_commands.Choice[str]] = None,
        enforcement: Optional[app_commands.Choice[str]] = None,
        allow_verified: Optional[bool] = None,
        whitelist_action: Optional[app_commands.Choice[str]] = None,
        whitelist_bot_id: Optional[str] = None,
    ):
        """Configure anti-bots system with full options."""
        if not interaction.guild:
            return await interaction.response.send_message("This command works in servers only.", ephemeral=True)

        settings = await db.get_guild_settings(interaction.guild.id)
        lang = lang_for(settings.get("language"))
        protection_settings = dict(settings.get("protection_settings", {}))

        changed_messages = []
        changed = False

        requested_action = action.value if action else "status"
        if requested_action == "enable" and not protection_settings.get("antibots", False):
            protection_settings["antibots"] = True
            changed_messages.append(f"{t(lang, 'mode')}: {status_label(lang, True)}")
            changed = True
        elif requested_action == "disable" and protection_settings.get("antibots", False):
            protection_settings["antibots"] = False
            changed_messages.append(f"{t(lang, 'mode')}: {status_label(lang, False)}")
            changed = True

        if enforcement:
            selected = enforcement.value
            if protection_settings.get("antibots_action") != selected:
                protection_settings["antibots_action"] = selected
                changed_messages.append(f"{t(lang, 'enforcement')}: `{selected}`")
                changed = True

        if allow_verified is not None:
            if bool(protection_settings.get("antibots_allow_verified", True)) != allow_verified:
                protection_settings["antibots_allow_verified"] = allow_verified
                changed_messages.append(
                    f"{t(lang, 'allow_verified')}: `{status_label(lang, allow_verified)}`"
                )
                changed = True

        whitelist = protection_settings.get("antibots_whitelist", [])
        if not isinstance(whitelist, list):
            whitelist = []

        if whitelist_action:
            mode = whitelist_action.value
            if mode in {"add", "remove"}:
                if not whitelist_bot_id:
                    return await interaction.response.send_message(
                        t(lang, "usage_error_whitelist_id_required"),
                        ephemeral=True,
                    )
                try:
                    bot_id = int(whitelist_bot_id.strip())
                except (TypeError, ValueError):
                    return await interaction.response.send_message(
                        t(lang, "usage_error_bot_id"),
                        ephemeral=True,
                    )

                if mode == "add":
                    if bot_id in whitelist:
                        changed_messages.append(t(lang, "already_whitelisted").format(bot_id=bot_id))
                    else:
                        whitelist.append(bot_id)
                        changed_messages.append(t(lang, "added_whitelist").format(bot_id=bot_id))
                        changed = True
                else:
                    if bot_id in whitelist:
                        whitelist.remove(bot_id)
                        changed_messages.append(t(lang, "removed_whitelist").format(bot_id=bot_id))
                        changed = True
                    else:
                        changed_messages.append(t(lang, "not_in_whitelist").format(bot_id=bot_id))

            elif mode == "clear":
                if whitelist:
                    whitelist = []
                    changed = True
                changed_messages.append(t(lang, "whitelist_cleared"))

            elif mode == "show":
                pass

        protection_settings["antibots_whitelist"] = whitelist

        if changed:
            await db.update_protection_settings(interaction.guild.id, protection_settings)

        final_settings = (await db.get_guild_settings(interaction.guild.id)).get("protection_settings", {})
        current_mode = final_settings.get("antibots", False)
        current_action = final_settings.get("antibots_action", "kick")
        current_allow_verified = final_settings.get("antibots_allow_verified", True)
        current_whitelist = final_settings.get("antibots_whitelist", [])

        embed = discord.Embed(
            title=t(lang, "title_antibots"),
            color=discord.Color.green() if changed else discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.description = t(lang, "updated") if changed else t(lang, "no_change")

        embed.add_field(
            name=t(lang, "mode"),
            value=f"`{status_label(lang, current_mode)}`",
            inline=True,
        )
        embed.add_field(
            name=t(lang, "enforcement"),
            value=f"`{current_action}`",
            inline=True,
        )
        embed.add_field(
            name=t(lang, "allow_verified"),
            value=f"`{status_label(lang, current_allow_verified)}`",
            inline=True,
        )

        if current_whitelist:
            preview = ", ".join(str(bot_id) for bot_id in current_whitelist[:15])
            if len(current_whitelist) > 15:
                preview += f", ... ({len(current_whitelist)} total)"
            embed.add_field(name=t(lang, "whitelist"), value=preview, inline=False)
        else:
            embed.add_field(name=t(lang, "whitelist"), value="`[]`", inline=False)

        if changed_messages:
            embed.add_field(
                name=t(lang, "details"),
                value="\n".join(f"• {line}" for line in changed_messages[:10]),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="scanbots", description="Scan and show all bots in the server | فحص جميع البوتات")
    @app_commands.default_permissions(administrator=True)
    async def scanbots(self, interaction: discord.Interaction):
        """Scan all bots in the server."""
        if not interaction.guild:
            return await interaction.response.send_message("This command works in servers only.", ephemeral=True)

        settings = await db.get_guild_settings(interaction.guild.id)
        lang = lang_for(settings.get("language"))
        protection = settings.get("protection_settings", {})

        bot_members = [m for m in interaction.guild.members if m.bot]
        human_members = [m for m in interaction.guild.members if not m.bot]
        protection_status = status_label(lang, bool(protection.get("antibots", False)))

        embed = discord.Embed(
            title=t(lang, "scan_title"),
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name=t(lang, "stats"),
            value=(
                f"**Total Members:** {interaction.guild.member_count}\n"
                f"**Bots:** {len(bot_members)}\n"
                f"**Humans:** {len(human_members)}\n"
                f"**Anti-Bots:** `{protection_status}`"
            ),
            inline=True,
        )

        if bot_members:
            bot_list = "\n".join([f"• {bot.mention} (`{bot.id}`)" for bot in bot_members[:10]])
            if len(bot_members) > 10:
                bot_list += f"\n• {t(lang, 'and_more').format(count=len(bot_members) - 10)}"
            embed.add_field(name=t(lang, "detected_bots"), value=bot_list, inline=False)

        embed.set_footer(text=t(lang, "scan_footer").format(guild=interaction.guild.name))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="settings", description="Advanced protection settings panel | لوحة إعدادات الحماية المتقدمة")
    @app_commands.default_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """Advanced protection settings with UI panel."""
        if not interaction.guild:
            return await interaction.response.send_message("This command works in servers only.", ephemeral=True)

        settings_data = await db.get_guild_settings(interaction.guild.id)
        lang = lang_for(settings_data.get("language"))
        protection_settings = settings_data.get("protection_settings", {})

        embed = discord.Embed(
            title=strings[settings_data.get("language", "en")].get("advanced_protection_title", "Advanced Protection"),
            description=t(lang, "settings_panel_desc"),
            color=discord.Color.blue(),
        )

        view = AdvancedProtectionView(settings_data.get("language", "en"), protection_settings)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="checkprotection", description="Check current protection settings and status | فحص إعدادات الحماية")
    @app_commands.default_permissions(administrator=True)
    async def checkprotection(self, interaction: discord.Interaction):
        """Show current protection status."""
        if not interaction.guild:
            return await interaction.response.send_message("This command works in servers only.", ephemeral=True)

        settings = await db.get_guild_settings(interaction.guild.id)
        lang = lang_for(settings.get("language"))
        protection = settings.get("protection_settings", {})

        embed = discord.Embed(
            title=t(lang, "check_title"),
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name=t(lang, "check_settings"),
            value=(
                f"**Anti-Bots:** `{status_label(lang, protection.get('antibots', False))}`\n"
                f"**Anti-Bots Action:** `{protection.get('antibots_action', 'kick')}`\n"
                f"**Allow Verified Bots:** `{status_label(lang, protection.get('antibots_allow_verified', True))}`\n"
                f"**Whitelist Size:** `{len(protection.get('antibots_whitelist', []))}`\n"
                f"**Max Bans:** `{protection.get('limitsban', 5)}`\n"
                f"**Max Kicks:** `{protection.get('limitskick', 5)}`\n"
                f"**Max Role Creations:** `{protection.get('limitsroleC', 3)}`\n"
                f"**Max Role Deletions:** `{protection.get('limitsroleD', 3)}`\n"
                f"**Max Channel Deletions:** `{protection.get('limitschannelD', 3)}`"
            ),
            inline=False,
        )

        from utils.protection import user_action_tracker

        active_tracking = []
        for user_key, actions in user_action_tracker.items():
            if user_key.startswith(f"{interaction.guild.id}_"):
                for action_type, timestamps in actions.items():
                    if timestamps:
                        user_id = user_key.split("_")[1]
                        user = interaction.guild.get_member(int(user_id))
                        username = user.mention if user else f"User {user_id}"
                        active_tracking.append(f"{username}: {len(timestamps)} {action_type} / 10s")

        embed.add_field(
            name=t(lang, "active_tracking"),
            value="\n".join(active_tracking[:5]) if active_tracking else t(lang, "no_tracking"),
            inline=False,
        )
        embed.set_footer(text=t(lang, "check_footer"))
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ProtectionCog(bot))
