# utils/helpers.py
import asyncio
import datetime
import re
import time
from typing import Iterable

import discord
from discord import Embed

from config import DEFAULT_LOG_SETTINGS, EVENT_COLORS, LOG_EVENT_LABELS
from database import db

_URL_PATTERN = re.compile(r"https?://[^\s<>()]+")


def _has_log_permissions(channel: discord.abc.GuildChannel, me: discord.Member | None) -> bool:
    """Check if the bot can post logs in the target channel."""
    if me is None:
        return False

    perms = channel.permissions_for(me)
    if not perms.view_channel:
        return False

    if isinstance(channel, discord.Thread):
        return bool(perms.send_messages_in_threads or perms.send_messages)
    return bool(perms.send_messages)


def get_available_log_channels(guild: discord.Guild) -> list[discord.TextChannel]:
    """Return text channels where the bot can safely send log messages."""
    me = guild.me
    available: list[discord.TextChannel] = []
    for channel in guild.text_channels:
        if isinstance(channel, discord.TextChannel) and _has_log_permissions(channel, me):
            available.append(channel)
    return available


def sanitize_log_channels(guild: discord.Guild, channel_ids: Iterable[int]) -> tuple[list[int], list[int]]:
    """
    Clean stored log channel IDs by removing:
    - invalid/non-numeric IDs
    - deleted channels
    - unsupported channel types
    - channels where the bot cannot send logs
    """
    cleaned: list[int] = []
    removed: list[int] = []
    seen: set[int] = set()
    me = guild.me

    for raw_id in channel_ids or []:
        try:
            channel_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if channel_id in seen:
            continue
        seen.add(channel_id)

        channel = guild.get_channel(channel_id)
        if channel is None:
            removed.append(channel_id)
            continue

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            removed.append(channel_id)
            continue

        if not _has_log_permissions(channel, me):
            removed.append(channel_id)
            continue

        cleaned.append(channel_id)

    return cleaned, removed


def extract_log_routing(settings: dict) -> tuple[int | None, dict[str, int]]:
    """Extract normalized primary + override routing from guild settings."""
    raw_log_channels = settings.get("log_channels", [])
    primary_channel_id = None
    if isinstance(raw_log_channels, list) and raw_log_channels:
        try:
            primary_channel_id = int(raw_log_channels[0])
        except (TypeError, ValueError):
            primary_channel_id = None

    advanced_logs = settings.get("advanced_logs", {})
    if isinstance(advanced_logs, dict):
        if primary_channel_id is None:
            try:
                advanced_primary = int(advanced_logs.get("primary_channel_id"))
            except (TypeError, ValueError):
                advanced_primary = None
            if advanced_primary and advanced_primary > 0:
                primary_channel_id = advanced_primary

        overrides = advanced_logs.get("event_overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}
    else:
        overrides = {}

    cleaned_overrides: dict[str, int] = {}
    for event_name, channel_id in overrides.items():
        if event_name not in DEFAULT_LOG_SETTINGS:
            continue
        try:
            int_channel_id = int(channel_id)
        except (TypeError, ValueError):
            continue
        if int_channel_id <= 0 or int_channel_id == primary_channel_id:
            continue
        cleaned_overrides[event_name] = int_channel_id

    return primary_channel_id, cleaned_overrides


def get_log_event_label(event_type: str) -> str:
    """Return a human-friendly event label."""
    return LOG_EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())


def mask_urls_for_embed(text) -> str:
    """Hide raw URLs behind a short label for cleaner embeds."""
    if text is None:
        return ""

    value = str(text)

    def replace(match: re.Match) -> str:
        url = match.group(0)
        return f"[Link]({url})"

    return _URL_PATTERN.sub(replace, value)


def _iter_extra_fields(fields) -> list[tuple[str, str, bool]]:
    normalized: list[tuple[str, str, bool]] = []
    for field in fields or []:
        if not isinstance(field, (list, tuple)) or len(field) < 2:
            continue
        name = str(field[0])[:256]
        value = str(field[1])[:1024]
        inline = bool(field[2]) if len(field) > 2 else False
        if not name or not value:
            continue
        normalized.append((name, value, inline))
    return normalized


def _build_log_embed(event_type: str, message: str, **kwargs) -> discord.Embed:
    description = mask_urls_for_embed(message)[:4096] if message else None
    embed = discord.Embed(
        title=str(kwargs.get("title") or get_log_event_label(event_type))[:256],
        description=description,
        color=EVENT_COLORS.get(event_type, discord.Color.blue()),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    user = kwargs.get("actor") or kwargs.get("user")
    if user is not None:
        author_name = str(user)
        avatar = None
        try:
            avatar = user.display_avatar.url if hasattr(user, "display_avatar") else None
        except Exception:
            avatar = None

        if avatar:
            embed.set_author(name=author_name, icon_url=avatar)
            embed.set_thumbnail(url=avatar)
        else:
            embed.set_author(name=author_name)

    if kwargs.get("content"):
        embed.add_field(name="Content", value=mask_urls_for_embed(kwargs["content"])[:1024], inline=False)
    if kwargs.get("before"):
        embed.add_field(name="Before", value=mask_urls_for_embed(kwargs["before"])[:1024], inline=True)
    if kwargs.get("after"):
        embed.add_field(name="After", value=mask_urls_for_embed(kwargs["after"])[:1024], inline=True)
    for name, value, inline in _iter_extra_fields(kwargs.get("fields", [])):
        embed.add_field(name=name, value=value, inline=inline)
    return embed


def _build_plain_log_message(message: str, **kwargs) -> str:
    parts = [mask_urls_for_embed(message)] if message else []
    if kwargs.get("content"):
        parts.append(f"Content: {mask_urls_for_embed(kwargs['content'])[:1000]}")
    if kwargs.get("before"):
        parts.append(f"Before: {mask_urls_for_embed(kwargs['before'])[:500]}")
    if kwargs.get("after"):
        parts.append(f"After: {mask_urls_for_embed(kwargs['after'])[:500]}")
    for name, value, _inline in _iter_extra_fields(kwargs.get("fields", [])):
        parts.append(f"{name}: {value}")

    text = "\n".join(parts)
    if len(text) > 2000:
        text = f"{text[:1997]}..."
    return text


async def send_log(guild: discord.Guild, event_type: str, message: str, **kwargs):
    """Send a log event to configured log channels safely."""
    try:
        settings = await db.get_guild_settings(guild.id)
        primary_channel_id, overrides = extract_log_routing(settings)
        override_channel_id = overrides.get(event_type)

        candidate_channel_ids = []
        if override_channel_id:
            candidate_channel_ids.append(override_channel_id)
        if primary_channel_id and primary_channel_id != override_channel_id:
            candidate_channel_ids.append(primary_channel_id)
        if not candidate_channel_ids:
            return

        embed = _build_log_embed(event_type, message, **kwargs)
        plain_message = _build_plain_log_message(message, **kwargs)
        if not plain_message:
            plain_message = str(kwargs.get("title") or get_log_event_label(event_type))
        files = []
        if kwargs.get("file") is not None:
            files.append(kwargs["file"])
        files.extend(kwargs.get("files", []) or [])

        for channel_id in candidate_channel_ids:
            try:
                channel = guild.get_channel(channel_id)
                if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                    if channel_id == override_channel_id:
                        await db.remove_event_log_override(guild.id, event_type)
                        continue
                    if channel_id == primary_channel_id:
                        await db.update_primary_log_channel(guild.id, None)
                    continue

                me = guild.me
                if not _has_log_permissions(channel, me):
                    if channel_id == override_channel_id:
                        await db.remove_event_log_override(guild.id, event_type)
                        continue
                    if channel_id == primary_channel_id:
                        await db.update_primary_log_channel(guild.id, None)
                    continue

                perms = channel.permissions_for(me)
                send_kwargs = {}
                for file in files:
                    try:
                        file.fp.seek(0)
                    except Exception:
                        pass

                if perms.embed_links:
                    send_kwargs["embed"] = embed
                else:
                    send_kwargs["content"] = plain_message or None
                if files:
                    send_kwargs["files"] = files

                await channel.send(**send_kwargs)
                return
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                try:
                    channel = guild.get_channel(channel_id)
                    if isinstance(channel, (discord.TextChannel, discord.Thread)):
                        fallback_kwargs = {"content": plain_message or None}
                        if files:
                            for file in files:
                                try:
                                    file.fp.seek(0)
                                except Exception:
                                    pass
                            fallback_kwargs["files"] = files
                        await channel.send(**fallback_kwargs)
                        return
                except (discord.Forbidden, discord.HTTPException):
                    continue
            except Exception as e:
                print(f"[ERROR] Error sending log to channel {channel_id}: {e}")
    except Exception as e:
        print(f"[ERROR] Error in send_log: {e}")


def format_time_delta(seconds: int) -> str:
    """Format seconds into a readable short duration."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


def create_embed(title: str, description: str = "", color: int = 0x0000FF, **kwargs) -> Embed:
    """Create an embed with common defaults."""
    return Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


async def get_audit_log_user(
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: int = None,
) -> discord.Member:
    """Get the user responsible for an audit log action."""
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if target_id:
                if hasattr(entry.target, "id") and entry.target.id == target_id:
                    return entry.user
            else:
                return entry.user
    except discord.Forbidden:
        print(f"No permission to view audit logs in {guild.name}")
    except Exception as e:
        print(f"Error getting audit log: {e}")
    return None


async def get_recent_audit_log_entry(
    guild: discord.Guild,
    action,
    target_id: int = None,
    *,
    within_seconds: float = 10.0,
):
    """Return a recent audit log entry for the matching action/target."""
    if guild is None or action is None:
        return None

    cache_store = globals().setdefault("_AUDIT_LOG_CACHE", {})
    lock_store = globals().setdefault("_AUDIT_LOG_LOCKS", {})
    cooldown_store = globals().setdefault("_AUDIT_LOG_COOLDOWNS", {})
    warning_store = globals().setdefault("_AUDIT_LOG_WARNING_WINDOWS", {})
    action_key = getattr(action, "value", str(action))
    cache_key = (guild.id, action_key)

    def _get_cached_entries():
        cached = cache_store.get(cache_key)
        if cached is None:
            return None

        expires_at, entries = cached
        if expires_at <= time.monotonic():
            cache_store.pop(cache_key, None)
            return None
        return entries

    def _find_match(entries):
        if entries is None:
            return None

        now = discord.utils.utcnow()
        for entry in entries:
            if target_id is not None and getattr(entry.target, "id", None) != target_id:
                continue

            if within_seconds is not None:
                created_at = getattr(entry, "created_at", None)
                if created_at is None:
                    continue
                delta = abs((now - created_at).total_seconds())
                if delta > within_seconds:
                    continue

            return entry
        return None

    cached_entries = _get_cached_entries()
    if cached_entries is not None:
        return _find_match(cached_entries)

    cooldown_until = cooldown_store.get(cache_key, 0.0)
    if cooldown_until > time.monotonic():
        return None

    lock = lock_store.get(cache_key)
    if lock is None:
        lock = asyncio.Lock()
        lock_store[cache_key] = lock

    async with lock:
        cached_entries = _get_cached_entries()
        if cached_entries is not None:
            return _find_match(cached_entries)

        cooldown_until = cooldown_store.get(cache_key, 0.0)
        if cooldown_until > time.monotonic():
            return None

        try:
            entries = []
            async for entry in guild.audit_logs(limit=4, action=action):
                entries.append(entry)

            cache_store[cache_key] = (time.monotonic() + 2.0, entries)
            cooldown_store.pop(cache_key, None)
            warning_store.pop(cache_key, None)
            return _find_match(entries)
        except discord.Forbidden:
            cooldown_store[cache_key] = time.monotonic() + 60.0
            if warning_store.get(cache_key, 0.0) <= time.monotonic():
                warning_store[cache_key] = time.monotonic() + 60.0
                print(f"No permission to view audit logs in {guild.name}")
            return None
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                retry_after = getattr(e, "retry_after", None)
                cooldown_seconds = max(15.0, min(float(retry_after or 15.0) * 2.0, 90.0))
                cooldown_store[cache_key] = time.monotonic() + cooldown_seconds
                if warning_store.get(cache_key, 0.0) <= time.monotonic():
                    warning_store[cache_key] = time.monotonic() + cooldown_seconds
                    print(
                        f"Audit log lookup rate limited in guild {guild.id} "
                        f"for action {action_key}; suppressing retries for {cooldown_seconds:.0f}s."
                    )
                return _find_match(_get_cached_entries())

            cooldown_store[cache_key] = time.monotonic() + 5.0
            if warning_store.get(cache_key, 0.0) <= time.monotonic():
                warning_store[cache_key] = time.monotonic() + 5.0
                print(f"Audit log lookup failed in guild {guild.id} for action {action_key}: {e}")
            return _find_match(_get_cached_entries())
        except Exception as e:
            cooldown_store[cache_key] = time.monotonic() + 5.0
            if warning_store.get(cache_key, 0.0) <= time.monotonic():
                warning_store[cache_key] = time.monotonic() + 5.0
                print(f"Audit log lookup failed in guild {guild.id} for action {action_key}: {e}")
            return _find_match(_get_cached_entries())


async def get_audit_log_entry(
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: int = None,
):
    """Get a full audit log entry."""
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if target_id:
                if hasattr(entry.target, "id") and entry.target.id == target_id:
                    return entry
            else:
                return entry
    except discord.Forbidden:
        print(f"No permission to view audit logs in {guild.name}")
    except Exception as e:
        print(f"Error getting audit log entry: {e}")
    return None


def format_admin_info(admin_user: discord.Member) -> str:
    """Format admin reference text."""
    if admin_user:
        return f"by {admin_user.mention} (`{admin_user.name}`)"
    return "by Unknown"


def get_relative_time(dt: datetime.datetime) -> str:
    """Return Arabic relative time text from datetime."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    diff = now - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} Ø³Ù†Ø©" if years == 1 else f"{years} Ø³Ù†ÙˆØ§Øª"
    if diff.days > 30:
        months = diff.days // 30
        return f"{months} Ø´Ù‡Ø±" if months == 1 else f"{months} Ø£Ø´Ù‡Ø±"
    if diff.days > 0:
        return f"{diff.days} ÙŠÙˆÙ…" if diff.days == 1 else f"{diff.days} Ø£ÙŠØ§Ù…"
    if diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours} Ø³Ø§Ø¹Ø©" if hours == 1 else f"{hours} Ø³Ø§Ø¹Ø§Øª"
    if diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"{minutes} Ø¯Ù‚ÙŠÙ‚Ø©" if minutes == 1 else f"{minutes} Ø¯Ù‚Ø§Ø¦Ù‚"
    return "Ø§Ù„Ø¢Ù†"


def format_dt(dt: datetime.datetime, style: str = "R") -> str:
    """Format datetime for Discord timestamp markdown."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    valid_styles = ["t", "T", "d", "D", "f", "F", "R"]
    if style not in valid_styles:
        style = "R"

    timestamp = int(dt.timestamp())
    return f"<t:{timestamp}:{style}>"


def format_date_arabic(dt: datetime.datetime) -> str:
    """Format datetime in Arabic style."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    arabic_months = [
        "ÙŠÙ†Ø§ÙŠØ±",
        "ÙØ¨Ø±Ø§ÙŠØ±",
        "Ù…Ø§Ø±Ø³",
        "Ø£Ø¨Ø±ÙŠÙ„",
        "Ù…Ø§ÙŠÙˆ",
        "ÙŠÙˆÙ†ÙŠÙˆ",
        "ÙŠÙˆÙ„ÙŠÙˆ",
        "Ø£ØºØ³Ø·Ø³",
        "Ø³Ø¨ØªÙ…Ø¨Ø±",
        "Ø£ÙƒØªÙˆØ¨Ø±",
        "Ù†ÙˆÙÙ…Ø¨Ø±",
        "Ø¯ÙŠØ³Ù…Ø¨Ø±",
    ]

    day = dt.day
    month = arabic_months[dt.month - 1]
    year = dt.year
    hour = dt.hour
    minute = dt.minute

    return f"{day} {month} {year} Ø§Ù„Ø³Ø§Ø¹Ø© {hour:02d}:{minute:02d}"


def seconds_to_human_readable(seconds: int) -> str:
    """Convert seconds to Arabic human-readable duration."""
    if seconds < 60:
        return f"{seconds} Ø«Ø§Ù†ÙŠØ©"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} Ø¯Ù‚ÙŠÙ‚Ø©" if minutes == 1 else f"{minutes} Ø¯Ù‚Ø§Ø¦Ù‚"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} Ø³Ø§Ø¹Ø©" if hours == 1 else f"{hours} Ø³Ø§Ø¹Ø§Øª"
    days = seconds // 86400
    return f"{days} ÙŠÙˆÙ…" if days == 1 else f"{days} Ø£ÙŠØ§Ù…"


def datetime_to_timestamp(dt: datetime.datetime) -> int:
    """Convert datetime to unix timestamp."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


def timestamp_to_datetime(timestamp: int) -> datetime.datetime:
    """Convert unix timestamp to datetime."""
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


