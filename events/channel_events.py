import io

import discord
from discord.ext import commands

from utils.helpers import get_recent_audit_log_entry, mask_urls_for_embed, send_log


THREAD_CREATE_ACTION = getattr(discord.AuditLogAction, "thread_create", discord.AuditLogAction.channel_create)
THREAD_DELETE_ACTION = getattr(discord.AuditLogAction, "thread_delete", discord.AuditLogAction.channel_delete)
THREAD_UPDATE_ACTION = getattr(discord.AuditLogAction, "thread_update", discord.AuditLogAction.channel_update)
MEMBER_MOVE_ACTION = getattr(discord.AuditLogAction, "member_move", None)
MEMBER_DISCONNECT_ACTION = getattr(discord.AuditLogAction, "member_disconnect", None)


def _user_ref(user: discord.abc.User | None) -> str:
    if user is None:
        return "Unknown"
    return f"{user.mention} (`{user.id}`)"


def _channel_ref(channel) -> str:
    if channel is None:
        return "Unknown"
    mention = getattr(channel, "mention", f"`{getattr(channel, 'name', 'unknown')}`")
    channel_id = getattr(channel, "id", "unknown")
    return f"{mention} (`{channel_id}`)"


def _channel_kind(channel) -> str:
    if isinstance(channel, discord.TextChannel):
        return "Text Channel"
    if isinstance(channel, discord.VoiceChannel):
        return "Voice Channel"
    if isinstance(channel, discord.StageChannel):
        return "Stage Channel"
    if isinstance(channel, discord.CategoryChannel):
        return "Category"
    if isinstance(channel, discord.ForumChannel):
        return "Forum Channel"
    if isinstance(channel, discord.Thread):
        return "Thread"
    return channel.__class__.__name__


def _reason_text(reason: str | None) -> str:
    return reason or "No reason provided."


def _format_reaction_emoji(value) -> str:
    if value is None:
        return "None"
    emoji = getattr(value, "emoji", None)
    return str(emoji) if emoji else str(value)


def _format_forum_tags(tags) -> str:
    if not tags:
        return "None"
    return ", ".join(getattr(tag, "name", str(tag)) for tag in tags)


def _message_author_ref(user: discord.abc.User | None) -> str:
    if user is None:
        return "Unknown"
    return f"{discord.utils.escape_markdown(str(user))} ({user.mention})"


def _message_created_ref(message: discord.Message) -> str:
    created_at = getattr(message, "created_at", None)
    if created_at is None:
        return "Unknown"
    return f"<t:{int(created_at.timestamp())}:R>"


def _format_message_body(message: discord.Message) -> str:
    parts: list[str] = []

    if message.content:
        parts.append(message.content)

    if message.attachments:
        attachment_lines = [
            f"Attachment: {attachment.filename} - {attachment.url}"
            for attachment in message.attachments[:10]
        ]
        parts.extend(attachment_lines)

    if message.embeds and not parts:
        embed_lines = []
        for embed in message.embeds[:3]:
            title = getattr(embed, "title", None)
            description = getattr(embed, "description", None)
            if title:
                embed_lines.append(f"Embed title: {title}")
            if description:
                embed_lines.append(f"Embed description: {description}")
        parts.extend(embed_lines)

    if not parts:
        parts.append("[No text content]")

    return mask_urls_for_embed("\n".join(parts))[:1024]


def _sanitize_filename_part(value: str) -> str:
    cleaned = "".join(character for character in value if character.isalnum() or character in ("-", "_"))
    return cleaned or "channel"


def _build_deleted_messages_file(messages) -> discord.File:
    lines: list[str] = []
    ordered_messages = sorted(
        messages,
        key=lambda message: (
            getattr(message, "created_at", discord.utils.utcnow()),
            getattr(message, "id", 0),
        ),
    )

    for message in ordered_messages:
        author = getattr(message, "author", None)
        author_name = discord.utils.escape_markdown(str(author)) if author else "Unknown"
        author_id = getattr(author, "id", "Unknown")
        created_at = getattr(message, "created_at", None)
        created_label = created_at.strftime("%d/%m/%Y - %H:%M") if created_at else "Unknown time"
        channel_name = getattr(getattr(message, "channel", None), "name", "unknown-channel")
        channel_id = getattr(getattr(message, "channel", None), "id", "Unknown")

        lines.append(f"[{created_label}] {author_name} ({author_id})")
        lines.append(f"ID: {getattr(message, 'id', 'Unknown')}")
        lines.append(f"Channel: #{channel_name} ({channel_id})")

        if message.content:
            lines.append(message.content)

        if message.attachments:
            lines.extend(f"Attachment: {attachment.filename} - {attachment.url}" for attachment in message.attachments[:10])

        if not message.content and not message.attachments:
            lines.append("[No text content]")

        lines.append("")

    transcript = "\n".join(lines).encode("utf-8")
    sample_channel = getattr(getattr(messages[0], "channel", None), "name", "channel")
    timestamp = discord.utils.utcnow().isoformat().replace(":", "-")
    filename = f"{_sanitize_filename_part(sample_channel)}_DeletedMessages_{timestamp}.txt"
    return discord.File(io.BytesIO(transcript), filename=filename)


class ChannelEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _get_recent_voice_move_entry(
        self,
        guild: discord.Guild,
        member: discord.Member,
        before_channel,
        after_channel,
        *,
        within_seconds: float = 5.0,
    ):
        if MEMBER_MOVE_ACTION is None:
            return None

        entry = await get_recent_audit_log_entry(
            guild,
            MEMBER_MOVE_ACTION,
            member.id,
            within_seconds=within_seconds,
        )
        if entry is not None:
            return entry

        try:
            now = discord.utils.utcnow()
            fallback_entry = None
            relevant_channel_ids = {
                channel.id for channel in (before_channel, after_channel) if getattr(channel, "id", None) is not None
            }

            async for candidate in guild.audit_logs(limit=6, action=MEMBER_MOVE_ACTION):
                created_at = getattr(candidate, "created_at", None)
                if created_at is None:
                    continue

                if abs((now - created_at).total_seconds()) > within_seconds:
                    continue

                if getattr(getattr(candidate, "target", None), "id", None) == member.id:
                    return candidate

                extra = getattr(candidate, "extra", None)
                extra_channel = getattr(extra, "channel", None)
                extra_channel_id = getattr(extra_channel, "id", None)
                if extra_channel_id in relevant_channel_ids:
                    return candidate

                if fallback_entry is None and getattr(extra, "count", None) == 1:
                    fallback_entry = candidate

            return fallback_entry
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def _send_channel_update(
        self,
        guild: discord.Guild,
        event_name: str,
        *,
        actor,
        channel,
        before=None,
        after=None,
        details: str | None = None,
    ):
        fields = [
            ("Actor", _user_ref(actor), False),
            ("Channel", _channel_ref(channel), False),
            ("Channel Type", _channel_kind(channel), True),
        ]
        if details:
            fields.append(("Details", details[:1024], False))
        await send_log(
            guild,
            event_name,
            f"{_user_ref(actor)} updated {_channel_ref(channel)}.",
            actor=actor or guild.me,
            target=channel,
            before=before,
            after=after,
            fields=fields,
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author is None:
            return

        entry = await get_recent_audit_log_entry(
            message.guild,
            discord.AuditLogAction.message_delete,
            getattr(message.author, "id", None),
            within_seconds=5.0,
        )
        if entry and getattr(getattr(entry, "extra", None), "count", 1) > 1:
            return

        actor = entry.user if entry else None
        await send_log(
            message.guild,
            "message_delete",
            "",
            title="Message deleted",
            user=message.author,
            fields=[
                ("Channel", f"`{getattr(message.channel, 'name', 'unknown')}` ({message.channel.mention})", False),
                ("Message ID", f"`{message.id}`", False),
                ("Message author", _message_author_ref(message.author), False),
                ("Message created", _message_created_ref(message), False),
                ("Deleted by", _user_ref(actor) if actor and actor.id != message.author.id else "Self / Unknown", False),
                ("Reason", _reason_text(entry.reason if entry else None), False),
                ("Message", _format_message_body(message), False),
            ],
        )

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages or not messages[0].guild:
            return

        guild = messages[0].guild
        channel = messages[0].channel
        entry = await get_recent_audit_log_entry(
            guild,
            discord.AuditLogAction.message_bulk_delete,
            within_seconds=5.0,
        )
        actor = entry.user if entry else None
        await send_log(
            guild,
            "message_bulk_delete",
            "",
            title=f"{len(messages)} messages deleted",
            user=actor or guild.me,
            file=_build_deleted_messages_file(messages),
            fields=[
                ("Channel", f"`{getattr(channel, 'name', 'unknown')}` ({channel.mention})", False),
                ("Messages Deleted", str(len(messages)), False),
                ("Deleted by", _user_ref(actor) if actor else "Unknown", False),
                ("Reason", _reason_text(entry.reason if entry else None), False),
            ],
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild:
            return
        if before.content == after.content:
            return

        await send_log(
            before.guild,
            "message_edit",
            "",
            title="Message edited",
            user=before.author,
            before=before.content[:1000] if before.content else "[No content]",
            after=after.content[:1000] if after.content else "[No content]",
            fields=[
                ("Channel", f"`{getattr(before.channel, 'name', 'unknown')}` ({before.channel.mention})", False),
                ("Message ID", f"`{before.id}`", False),
                ("Message author", _message_author_ref(before.author), False),
                ("Message created", _message_created_ref(before), False),
            ],
        )

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, channel: discord.abc.GuildChannel, last_pin):
        if not channel.guild:
            return

        await send_log(
            channel.guild,
            "channel_pins_update",
            f"Pins updated in {channel.mention}.",
            actor=channel.guild.me,
            target=channel,
            fields=[
                ("Room", _channel_ref(channel), False),
                ("Room ID", f"`{channel.id}`", False),
                ("Last Pin", f"<t:{int(last_pin.timestamp())}:F>" if last_pin else "No pinned messages", False),
            ],
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.guild is None:
            return

        if before.channel is None and after.channel is not None:
            await send_log(
                member.guild,
                "voice_join",
                f"{member.mention} joined {after.channel.mention}.",
                user=member,
                fields=[
                    ("User", _user_ref(member), False),
                    ("Room", _channel_ref(after.channel), False),
                    ("Room ID", f"`{after.channel.id}`", False),
                ],
            )
            if after.channel.user_limit and len(after.channel.members) == after.channel.user_limit:
                await send_log(
                    member.guild,
                    "voice_channel_full",
                    f"{after.channel.mention} is now full.",
                    actor=member,
                    target=after.channel,
                    fields=[
                        ("Trigger Member", _user_ref(member), False),
                        ("Room", _channel_ref(after.channel), False),
                        ("Room ID", f"`{after.channel.id}`", False),
                        ("Limit", str(after.channel.user_limit), False),
                    ],
                )
            return

        if before.channel is not None and after.channel is None:
            disconnect_entry = await get_recent_audit_log_entry(
                member.guild,
                MEMBER_DISCONNECT_ACTION,
                member.id,
                within_seconds=5.0,
            )
            if disconnect_entry is not None:
                await send_log(
                    member.guild,
                    "voice_user_kick",
                    f"{disconnect_entry.user.mention} disconnected {member.mention} from voice.",
                    actor=disconnect_entry.user,
                    target=member,
                    fields=[
                        ("Actor", _user_ref(disconnect_entry.user), False),
                        ("Target", _user_ref(member), False),
                        ("Previous Room", _channel_ref(before.channel), False),
                        ("Room ID", f"`{before.channel.id}`", False),
                        ("Reason", _reason_text(disconnect_entry.reason), False),
                    ],
                )
                return

            await send_log(
                member.guild,
                "voice_leave",
                f"{member.mention} left {before.channel.mention}.",
                user=member,
                fields=[
                    ("User", _user_ref(member), False),
                    ("Previous Room", _channel_ref(before.channel), False),
                    ("Room ID", f"`{before.channel.id}`", False),
                ],
            )
            return

        if before.channel is not None and after.channel is not None and before.channel != after.channel:
            move_entry = await self._get_recent_voice_move_entry(
                member.guild,
                member,
                before.channel,
                after.channel,
                within_seconds=5.0,
            )
            if move_entry is not None:
                event_name = "voice_user_move"
                description = f"{move_entry.user.mention} moved {member.mention} to {after.channel.mention}."
                actor = move_entry.user
                reason = _reason_text(move_entry.reason)
            else:
                event_name = "voice_move"
                description = f"{member.mention} switched voice channels."
                actor = member
                reason = "Self move"

            await send_log(
                member.guild,
                event_name,
                description,
                actor=actor,
                target=member,
                fields=[
                    ("Actor", _user_ref(actor), False),
                    ("Target", _user_ref(member), False),
                    ("From", _channel_ref(before.channel), False),
                    ("From ID", f"`{before.channel.id}`", False),
                    ("To", _channel_ref(after.channel), False),
                    ("To ID", f"`{after.channel.id}`", False),
                    ("Reason", reason, False),
                ],
            )
            if after.channel.user_limit and len(after.channel.members) == after.channel.user_limit:
                await send_log(
                    member.guild,
                    "voice_channel_full",
                    f"{after.channel.mention} is now full.",
                    actor=actor,
                    target=after.channel,
                    fields=[
                        ("Trigger Member", _user_ref(member), False),
                        ("Room", _channel_ref(after.channel), False),
                        ("Room ID", f"`{after.channel.id}`", False),
                        ("Limit", str(after.channel.user_limit), False),
                    ],
                )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not channel.guild:
            return

        entry = await get_recent_audit_log_entry(
            channel.guild,
            discord.AuditLogAction.channel_create,
            channel.id,
            within_seconds=10.0,
        )
        actor = entry.user if entry else None
        await send_log(
            channel.guild,
            "channel_create",
            f"{actor.mention if actor else 'Unknown moderator'} created {channel.mention if hasattr(channel, 'mention') else channel.name}.",
            actor=actor or channel.guild.me,
            target=channel,
            fields=[
                ("Actor", _user_ref(actor), False),
                ("Channel", _channel_ref(channel), False),
                ("Channel Type", _channel_kind(channel), False),
                ("Parent", _channel_ref(channel.category) if getattr(channel, "category", None) else "None", False),
            ],
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not channel.guild:
            return

        entry = await get_recent_audit_log_entry(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            channel.id,
            within_seconds=10.0,
        )
        actor = entry.user if entry else None
        await send_log(
            channel.guild,
            "channel_delete",
            f"{actor.mention if actor else 'Unknown moderator'} deleted `{channel.name}`.",
            actor=actor or channel.guild.me,
            target=channel,
            fields=[
                ("Actor", _user_ref(actor), False),
                ("Channel", f"`{channel.name}` (`{channel.id}`)", False),
                ("Channel Type", _channel_kind(channel), False),
                ("Parent", _channel_ref(channel.category) if getattr(channel, "category", None) else "None", False),
                ("Reason", _reason_text(entry.reason if entry else None), False),
            ],
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not before.guild:
            return

        entry = await get_recent_audit_log_entry(
            before.guild,
            discord.AuditLogAction.channel_update,
            after.id,
            within_seconds=10.0,
        )
        actor = entry.user if entry else before.guild.me

        if before.name != after.name:
            await self._send_channel_update(before.guild, "channel_name_update", actor=actor, channel=after, before=before.name, after=after.name)

        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel) and before.topic != after.topic:
            await self._send_channel_update(before.guild, "channel_topic_update", actor=actor, channel=after, before=before.topic or "None", after=after.topic or "None")

        if hasattr(before, "nsfw") and hasattr(after, "nsfw") and before.nsfw != after.nsfw:
            await self._send_channel_update(before.guild, "channel_nsfw_update", actor=actor, channel=after, before=str(before.nsfw), after=str(after.nsfw))

        if getattr(before, "category_id", None) != getattr(after, "category_id", None):
            await self._send_channel_update(
                before.guild,
                "channel_parent_update",
                actor=actor,
                channel=after,
                before=_channel_ref(before.category) if getattr(before, "category", None) else "None",
                after=_channel_ref(after.category) if getattr(after, "category", None) else "None",
            )

        if before.overwrites != after.overwrites:
            await self._send_channel_update(
                before.guild,
                "channel_permissions_update",
                actor=actor,
                channel=after,
                details="Permission overwrites changed.",
            )

        if before.type != after.type:
            await self._send_channel_update(before.guild, "channel_type_update", actor=actor, channel=after, before=str(before.type), after=str(after.type))

        if hasattr(before, "bitrate") and hasattr(after, "bitrate") and before.bitrate != after.bitrate:
            await self._send_channel_update(before.guild, "channel_bitrate_update", actor=actor, channel=after, before=str(before.bitrate), after=str(after.bitrate))

        if hasattr(before, "user_limit") and hasattr(after, "user_limit") and before.user_limit != after.user_limit:
            await self._send_channel_update(before.guild, "channel_user_limit_update", actor=actor, channel=after, before=str(before.user_limit), after=str(after.user_limit))

        if hasattr(before, "slowmode_delay") and hasattr(after, "slowmode_delay") and before.slowmode_delay != after.slowmode_delay:
            await self._send_channel_update(before.guild, "channel_slow_mode_update", actor=actor, channel=after, before=str(before.slowmode_delay), after=str(after.slowmode_delay))

        if hasattr(before, "rtc_region") and hasattr(after, "rtc_region") and before.rtc_region != after.rtc_region:
            await self._send_channel_update(before.guild, "channel_rtc_region_update", actor=actor, channel=after, before=str(before.rtc_region), after=str(after.rtc_region))

        if hasattr(before, "video_quality_mode") and hasattr(after, "video_quality_mode") and before.video_quality_mode != after.video_quality_mode:
            await self._send_channel_update(before.guild, "channel_video_quality_update", actor=actor, channel=after, before=str(before.video_quality_mode), after=str(after.video_quality_mode))

        if hasattr(before, "default_auto_archive_duration") and hasattr(after, "default_auto_archive_duration") and before.default_auto_archive_duration != after.default_auto_archive_duration:
            await self._send_channel_update(before.guild, "channel_default_archive_duration_update", actor=actor, channel=after, before=str(before.default_auto_archive_duration), after=str(after.default_auto_archive_duration))

        if hasattr(before, "default_thread_slowmode_delay") and hasattr(after, "default_thread_slowmode_delay") and before.default_thread_slowmode_delay != after.default_thread_slowmode_delay:
            await self._send_channel_update(before.guild, "channel_default_thread_slow_mode_update", actor=actor, channel=after, before=str(before.default_thread_slowmode_delay), after=str(after.default_thread_slowmode_delay))

        if hasattr(before, "default_reaction_emoji") and hasattr(after, "default_reaction_emoji") and before.default_reaction_emoji != after.default_reaction_emoji:
            await self._send_channel_update(before.guild, "channel_default_reaction_emoji_update", actor=actor, channel=after, before=_format_reaction_emoji(before.default_reaction_emoji), after=_format_reaction_emoji(after.default_reaction_emoji))

        if hasattr(before, "default_sort_order") and hasattr(after, "default_sort_order") and before.default_sort_order != after.default_sort_order:
            await self._send_channel_update(before.guild, "channel_default_sort_order_update", actor=actor, channel=after, before=str(before.default_sort_order), after=str(after.default_sort_order))

        if hasattr(before, "available_tags") and hasattr(after, "available_tags") and before.available_tags != after.available_tags:
            await self._send_channel_update(before.guild, "channel_forum_tags_update", actor=actor, channel=after, before=_format_forum_tags(before.available_tags), after=_format_forum_tags(after.available_tags))

        if hasattr(before, "default_forum_layout") and hasattr(after, "default_forum_layout") and before.default_forum_layout != after.default_forum_layout:
            await self._send_channel_update(before.guild, "channel_forum_layout_update", actor=actor, channel=after, before=str(before.default_forum_layout), after=str(after.default_forum_layout))

        if hasattr(before, "status") and hasattr(after, "status") and before.status != after.status:
            await self._send_channel_update(before.guild, "channel_voice_status_update", actor=actor, channel=after, before=str(before.status), after=str(after.status))

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        entry = await get_recent_audit_log_entry(thread.guild, THREAD_CREATE_ACTION, thread.id, within_seconds=10.0)
        actor = entry.user if entry else None
        await send_log(
            thread.guild,
            "thread_create",
            f"{actor.mention if actor else 'Unknown moderator'} created thread {thread.mention}.",
            actor=actor or thread.guild.me,
            target=thread,
            fields=[
                ("Actor", _user_ref(actor), False),
                ("Thread", _channel_ref(thread), False),
                ("Parent", _channel_ref(thread.parent) if thread.parent else "None", False),
            ],
        )

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        entry = await get_recent_audit_log_entry(thread.guild, THREAD_DELETE_ACTION, thread.id, within_seconds=10.0)
        actor = entry.user if entry else None
        await send_log(
            thread.guild,
            "thread_delete",
            f"{actor.mention if actor else 'Unknown moderator'} deleted thread `{thread.name}`.",
            actor=actor or thread.guild.me,
            target=thread,
            fields=[
                ("Actor", _user_ref(actor), False),
                ("Thread", f"`{thread.name}` (`{thread.id}`)", False),
                ("Parent", _channel_ref(thread.parent) if thread.parent else "None", False),
            ],
        )

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        entry = await get_recent_audit_log_entry(after.guild, THREAD_UPDATE_ACTION, after.id, within_seconds=10.0)
        actor = entry.user if entry else after.guild.me

        if before.name != after.name:
            await send_log(
                after.guild,
                "thread_name_update",
                f"{_user_ref(actor)} updated thread name for {after.mention}.",
                actor=actor,
                target=after,
                before=before.name,
                after=after.name,
                fields=[("Thread", _channel_ref(after), False)],
            )

        if before.slowmode_delay != after.slowmode_delay:
            await send_log(
                after.guild,
                "thread_slow_mode_update",
                f"{_user_ref(actor)} updated slowmode for {after.mention}.",
                actor=actor,
                target=after,
                before=str(before.slowmode_delay),
                after=str(after.slowmode_delay),
                fields=[("Thread", _channel_ref(after), False)],
            )

        if before.auto_archive_duration != after.auto_archive_duration:
            await send_log(
                after.guild,
                "thread_archive_duration_update",
                f"{_user_ref(actor)} updated archive duration for {after.mention}.",
                actor=actor,
                target=after,
                before=str(before.auto_archive_duration),
                after=str(after.auto_archive_duration),
                fields=[("Thread", _channel_ref(after), False)],
            )

        if before.archived != after.archived:
            await send_log(
                after.guild,
                "thread_archive" if after.archived else "thread_unarchive",
                f"{_user_ref(actor)} {'archived' if after.archived else 'unarchived'} {after.mention}.",
                actor=actor,
                target=after,
                fields=[("Thread", _channel_ref(after), False)],
            )

        if before.locked != after.locked:
            await send_log(
                after.guild,
                "thread_lock" if after.locked else "thread_unlock",
                f"{_user_ref(actor)} {'locked' if after.locked else 'unlocked'} {after.mention}.",
                actor=actor,
                target=after,
                fields=[("Thread", _channel_ref(after), False)],
            )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        actor = invite.inviter
        guild = invite.guild
        channel = invite.channel
        if guild is None:
            return

        await send_log(
            guild,
            "invite_create",
            f"{actor.mention if actor else 'Unknown moderator'} created invite `{invite.code}`.",
            actor=actor or guild.me,
            target=channel,
            fields=[
                ("Actor", _user_ref(actor), False),
                ("Invite Code", f"`{invite.code}`", False),
                ("Room", _channel_ref(channel), False),
                ("Room ID", f"`{channel.id}`" if channel else "Unknown", False),
            ],
        )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        guild = invite.guild
        if guild is None:
            return

        entry = await get_recent_audit_log_entry(guild, discord.AuditLogAction.invite_delete, within_seconds=10.0)
        actor = entry.user if entry else None
        await send_log(
            guild,
            "invite_delete",
            f"{actor.mention if actor else 'Unknown moderator'} deleted invite `{invite.code}`.",
            actor=actor or guild.me,
            target=invite.channel,
            fields=[
                ("Actor", _user_ref(actor), False),
                ("Invite Code", f"`{invite.code}`", False),
                ("Room", _channel_ref(invite.channel), False),
                ("Room ID", f"`{invite.channel.id}`" if invite.channel else "Unknown", False),
                ("Reason", _reason_text(entry.reason if entry else None), False),
            ],
        )


async def setup(bot):
    await bot.add_cog(ChannelEvents(bot))
