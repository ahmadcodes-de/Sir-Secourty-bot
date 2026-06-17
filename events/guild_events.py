import discord
from discord.ext import commands

from database import db
from utils.helpers import get_recent_audit_log_entry, send_log


def _user_ref(user: discord.abc.User | None) -> str:
    if user is None:
        return "Unknown"
    return f"{user.mention} (`{user.id}`)"


def _channel_ref(channel) -> str:
    if channel is None:
        return "None"
    return f"{channel.mention} (`{channel.id}`)"


def _reason_text(reason: str | None) -> str:
    return reason or "No reason provided."


def _feature_flag(features, flag: str) -> bool:
    return flag in set(features or [])


def _format_widget_state(enabled, channel) -> str:
    if enabled is None:
        enabled_text = "Unknown"
    else:
        enabled_text = "Enabled" if enabled else "Disabled"
    channel_text = _channel_ref(channel)
    return f"Status: {enabled_text}\nChannel: {channel_text}"


class GuildEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            await db.init_db()
            await db.get_guild_settings(guild.id)
            print(f"✅ Joined new server: {guild.name} (ID: {guild.id})")
        except Exception as e:
            print(f"Error in on_guild_join for {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        entry = await get_recent_audit_log_entry(
            after,
            discord.AuditLogAction.guild_update,
            after.id,
            within_seconds=10.0,
        )
        actor = entry.user if entry else after.me
        reason = _reason_text(entry.reason if entry else None)

        async def emit(event_name: str, before_value, after_value, details: str | None = None):
            fields = [
                ("Actor", _user_ref(actor), False),
                ("Server", f"{after.name} (`{after.id}`)", False),
                ("Reason", reason, False),
            ]
            if details:
                fields.append(("Details", details[:1024], False))
            await send_log(
                after,
                event_name,
                f"{_user_ref(actor)} updated **{after.name}**.",
                actor=actor,
                target=after,
                before=before_value,
                after=after_value,
                fields=fields,
            )

        if before.afk_channel != after.afk_channel:
            await emit("afk_channel_update", _channel_ref(before.afk_channel), _channel_ref(after.afk_channel))

        if before.afk_timeout != after.afk_timeout:
            await emit("afk_timeout_update", str(before.afk_timeout), str(after.afk_timeout))

        if before.banner != after.banner:
            await emit("server_banner_update", "Updated", "Updated")

        if before.default_notifications != after.default_notifications:
            await emit("message_notifications_update", str(before.default_notifications), str(after.default_notifications))

        if before.discovery_splash != after.discovery_splash:
            await emit("server_discovery_splash_update", "Updated", "Updated")

        if before.explicit_content_filter != after.explicit_content_filter:
            await emit("server_content_filter_level_update", str(before.explicit_content_filter), str(after.explicit_content_filter))

        if set(before.features) != set(after.features):
            await emit("server_features_update", ", ".join(before.features) or "None", ", ".join(after.features) or "None")

            if _feature_flag(before.features, "PARTNERED") != _feature_flag(after.features, "PARTNERED"):
                await emit("partnered_update", str(_feature_flag(before.features, "PARTNERED")), str(_feature_flag(after.features, "PARTNERED")))

            if _feature_flag(before.features, "VERIFIED") != _feature_flag(after.features, "VERIFIED"):
                await emit("verified_update", str(_feature_flag(before.features, "VERIFIED")), str(_feature_flag(after.features, "VERIFIED")))

        if before.icon != after.icon:
            await emit("server_icon_update", "Updated", "Updated")

        if before.mfa_level != after.mfa_level:
            await emit("mfa_level_update", str(before.mfa_level), str(after.mfa_level))

        if before.name != after.name:
            await emit("server_name_update", before.name, after.name)

        if before.description != after.description:
            await emit("server_description_update", before.description or "None", after.description or "None")

        if before.owner_id != after.owner_id:
            await emit("server_owner_update", f"`{before.owner_id}`", f"`{after.owner_id}`")

        if before.premium_tier != after.premium_tier:
            await emit("server_boost_level_update", str(before.premium_tier), str(after.premium_tier))

        if getattr(before, "premium_progress_bar_enabled", None) != getattr(after, "premium_progress_bar_enabled", None):
            await emit(
                "boost_progress_bar_toggle",
                str(getattr(before, "premium_progress_bar_enabled", None)),
                str(getattr(after, "premium_progress_bar_enabled", None)),
            )

        if before.public_updates_channel != after.public_updates_channel:
            await emit("public_updates_channel_update", _channel_ref(before.public_updates_channel), _channel_ref(after.public_updates_channel))

        if before.rules_channel != after.rules_channel:
            await emit("server_rules_channel_update", _channel_ref(before.rules_channel), _channel_ref(after.rules_channel))

        if before.splash != after.splash:
            await emit("server_splash_update", "Updated", "Updated")

        if before.system_channel != after.system_channel:
            await emit("system_channel_update", _channel_ref(before.system_channel), _channel_ref(after.system_channel))

        if before.vanity_url_code != after.vanity_url_code:
            await emit("server_vanity_update", before.vanity_url_code or "None", after.vanity_url_code or "None")

        if before.verification_level != after.verification_level:
            await emit("verification_level_update", str(before.verification_level), str(after.verification_level))

        widget_before = (getattr(before, "widget_enabled", None), getattr(before, "widget_channel", None))
        widget_after = (getattr(after, "widget_enabled", None), getattr(after, "widget_channel", None))
        if widget_before != widget_after:
            await emit(
                "server_widget_update",
                _format_widget_state(widget_before[0], widget_before[1]),
                _format_widget_state(widget_after[0], widget_after[1]),
            )

        if before.preferred_locale != after.preferred_locale:
            await emit("server_preferred_locale_update", str(before.preferred_locale), str(after.preferred_locale))

        onboarding_before = getattr(before, "onboarding", None)
        onboarding_after = getattr(after, "onboarding", None)
        if onboarding_before is not None and onboarding_after is not None:
            enabled_before = getattr(onboarding_before, "enabled", None)
            enabled_after = getattr(onboarding_after, "enabled", None)
            if enabled_before != enabled_after:
                await emit("onboarding_toggle", str(enabled_before), str(enabled_after))

            before_channels = list(getattr(onboarding_before, "default_channel_ids", []) or [])
            after_channels = list(getattr(onboarding_after, "default_channel_ids", []) or [])
            if before_channels != after_channels:
                await emit(
                    "onboarding_channels_update",
                    ", ".join(str(channel_id) for channel_id in before_channels) or "None",
                    ", ".join(str(channel_id) for channel_id in after_channels) or "None",
                )

            before_prompts = {getattr(prompt, "id", None): prompt for prompt in getattr(onboarding_before, "prompts", []) or []}
            after_prompts = {getattr(prompt, "id", None): prompt for prompt in getattr(onboarding_after, "prompts", []) or []}

            for prompt_id, prompt in after_prompts.items():
                if prompt_id not in before_prompts:
                    await emit("onboarding_question_add", "None", getattr(prompt, "title", f"Prompt {prompt_id}"))
                elif getattr(before_prompts[prompt_id], "title", None) != getattr(prompt, "title", None):
                    await emit(
                        "onboarding_question_update",
                        getattr(before_prompts[prompt_id], "title", f"Prompt {prompt_id}"),
                        getattr(prompt, "title", f"Prompt {prompt_id}"),
                    )

            for prompt_id, prompt in before_prompts.items():
                if prompt_id not in after_prompts:
                    await emit("onboarding_question_remove", getattr(prompt, "title", f"Prompt {prompt_id}"), "Removed")


async def setup(bot):
    await bot.add_cog(GuildEvents(bot))
