import discord
from discord.ext import commands

from database import db
from utils.helpers import get_recent_audit_log_entry, send_log
from utils.protection import check_action_limit


def _user_ref(user: discord.abc.User | None) -> str:
    if user is None:
        return "Unknown"
    return f"{user.mention} (`{user.id}`)"


def _role_ref(role: discord.Role) -> str:
    return f"{role.mention} (`{role.id}`)"


def _reason_text(reason: str | None) -> str:
    return reason or "No reason provided."


def _format_permission_name(name: str) -> str:
    return name.replace("_", " ").title().replace("Tts", "TTS")


def _format_permission_changes(before: discord.Permissions, after: discord.Permissions) -> tuple[str, str]:
    changed_permissions: list[tuple[str, bool, bool]] = []

    for permission_name, before_value in before:
        after_value = getattr(after, permission_name, before_value)
        if before_value == after_value:
            continue
        changed_permissions.append((permission_name, before_value, after_value))

    if not changed_permissions:
        return str(before), str(after)

    before_lines = [
        f"{_format_permission_name(permission_name)}: {'Enabled' if before_value else 'Disabled'}"
        for permission_name, before_value, _after_value in changed_permissions
    ]
    after_lines = [
        f"{_format_permission_name(permission_name)}: {'Enabled' if after_value else 'Disabled'}"
        for permission_name, _before_value, after_value in changed_permissions
    ]
    return "\n".join(before_lines), "\n".join(after_lines)


class RoleEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        settings = await db.get_guild_settings(role.guild.id)
        entry = await get_recent_audit_log_entry(
            role.guild,
            discord.AuditLogAction.role_create,
            role.id,
            within_seconds=10.0,
        )
        creator = entry.user if entry else None

        await send_log(
            role.guild,
            "role_create",
            f"{creator.mention if creator else 'Unknown moderator'} created {role.mention}.",
            actor=creator or role.guild.me,
            target=role,
            fields=[
                ("Actor", _user_ref(creator), False),
                ("Role", _role_ref(role), False),
                ("Reason", _reason_text(entry.reason if entry else None), False),
            ],
        )

        if creator and not creator.guild_permissions.administrator:
            protection_settings = settings["protection_settings"]
            exceeded = await check_action_limit(
                role.guild,
                creator,
                "role_create",
                protection_settings.get("limitsroleC", 3),
            )
            if exceeded:
                print(f"ðŸ›¡ï¸ Protection: User {creator} exceeded role creation limit")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        settings = await db.get_guild_settings(role.guild.id)
        entry = await get_recent_audit_log_entry(
            role.guild,
            discord.AuditLogAction.role_delete,
            role.id,
            within_seconds=10.0,
        )
        deleter = entry.user if entry else None

        await send_log(
            role.guild,
            "role_delete",
            f"{deleter.mention if deleter else 'Unknown moderator'} deleted `{role.name}`.",
            actor=deleter or role.guild.me,
            target=role,
            fields=[
                ("Actor", _user_ref(deleter), False),
                ("Role", f"`{role.name}` (`{role.id}`)", False),
                ("Reason", _reason_text(entry.reason if entry else None), False),
            ],
        )

        if deleter and not deleter.guild_permissions.administrator:
            protection_settings = settings["protection_settings"]
            exceeded = await check_action_limit(
                role.guild,
                deleter,
                "role_delete",
                protection_settings.get("limitsroleD", 3),
            )
            if exceeded:
                print(f"ðŸ›¡ï¸ Protection: User {deleter} exceeded role deletion limit")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        entry = await get_recent_audit_log_entry(
            after.guild,
            discord.AuditLogAction.role_update,
            after.id,
            within_seconds=10.0,
        )
        actor = entry.user if entry else None
        base_fields = [
            ("Actor", _user_ref(actor), False),
            ("Role", _role_ref(after), False),
        ]

        if before.name != after.name:
            await send_log(
                after.guild,
                "role_name_update",
                f"{_user_ref(actor)} updated role name for {after.mention}.",
                actor=actor or after.guild.me,
                target=after,
                before=before.name,
                after=after.name,
                fields=base_fields,
            )

        if before.color != after.color:
            await send_log(
                after.guild,
                "role_color_update",
                f"{_user_ref(actor)} updated role color for {after.mention}.",
                actor=actor or after.guild.me,
                target=after,
                before=str(before.color),
                after=str(after.color),
                fields=base_fields,
            )

        if before.hoist != after.hoist:
            await send_log(
                after.guild,
                "role_hoist_update",
                f"{_user_ref(actor)} updated role hoist for {after.mention}.",
                actor=actor or after.guild.me,
                target=after,
                before=str(before.hoist),
                after=str(after.hoist),
                fields=base_fields,
            )

        if before.mentionable != after.mentionable:
            await send_log(
                after.guild,
                "role_mentionable_update",
                f"{_user_ref(actor)} updated role mentionability for {after.mention}.",
                actor=actor or after.guild.me,
                target=after,
                before=str(before.mentionable),
                after=str(after.mentionable),
                fields=base_fields,
            )

        if before.permissions != after.permissions:
            before_permissions, after_permissions = _format_permission_changes(before.permissions, after.permissions)
            await send_log(
                after.guild,
                "role_permissions_update",
                f"{_user_ref(actor)} updated permissions for {after.mention}.",
                actor=actor or after.guild.me,
                target=after,
                before=before_permissions,
                after=after_permissions,
                fields=base_fields,
            )

        before_icon = (getattr(before, "display_icon", None), getattr(before, "unicode_emoji", None))
        after_icon = (getattr(after, "display_icon", None), getattr(after, "unicode_emoji", None))
        if before_icon != after_icon:
            await send_log(
                after.guild,
                "role_icon_update",
                f"{_user_ref(actor)} updated icon for {after.mention}.",
                actor=actor or after.guild.me,
                target=after,
                fields=base_fields,
            )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild is None:
            return

        nick_changed = before.nick != after.nick
        roles_changed = before.roles != after.roles
        before_timeout = before.timed_out_until
        after_timeout = after.timed_out_until
        timeout_changed = before_timeout != after_timeout

        if not (nick_changed or roles_changed or timeout_changed):
            return

        entry = None
        if nick_changed or timeout_changed:
            entry = await get_recent_audit_log_entry(
                before.guild,
                discord.AuditLogAction.member_update,
                before.id,
                within_seconds=10.0,
            )

        role_entry = None
        if roles_changed:
            role_entry = await get_recent_audit_log_entry(
                before.guild,
                discord.AuditLogAction.member_role_update,
                before.id,
                within_seconds=10.0,
            )

        actor = role_entry.user if role_entry else (entry.user if entry else None)

        if nick_changed:
            await send_log(
                before.guild,
                "nickname_change",
                f"{after.mention} nickname changed.",
                actor=actor or after,
                target=after,
                before=before.nick or before.name,
                after=after.nick or after.name,
                fields=[
                    ("Actor", _user_ref(actor) if actor and actor.id != after.id else "Self update", False),
                    ("Target", _user_ref(after), False),
                ],
            )

        if roles_changed:
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]
            visible_added_roles = [role for role in added_roles if role.name.casefold() != "muted"]
            visible_removed_roles = [role for role in removed_roles if role.name.casefold() != "muted"]
            actor_value = _user_ref(actor) if actor and actor.id != after.id else "Self / System"
            if visible_added_roles and visible_removed_roles:
                await send_log(
                    before.guild,
                    "user_roles_update",
                    f"Roles updated for {after.mention}.",
                    actor=actor or after,
                    target=after,
                    fields=[
                        ("Actor", actor_value, False),
                        ("Target", _user_ref(after), False),
                        ("Added", ", ".join(role.mention for role in visible_added_roles)[:1024], False),
                        ("Removed", ", ".join(role.mention for role in visible_removed_roles)[:1024], False),
                    ],
                )
            elif visible_added_roles:
                await send_log(
                    before.guild,
                    "user_roles_add",
                    f"Roles added for {after.mention}.",
                    actor=actor or after,
                    target=after,
                    fields=[
                        ("Actor", actor_value, False),
                        ("Target", _user_ref(after), False),
                        ("Added", ", ".join(role.mention for role in visible_added_roles)[:1024], False),
                    ],
                )
            elif visible_removed_roles:
                await send_log(
                    before.guild,
                    "user_roles_remove",
                    f"Roles removed for {after.mention}.",
                    actor=actor or after,
                    target=after,
                    fields=[
                        ("Actor", actor_value, False),
                        ("Target", _user_ref(after), False),
                        ("Removed", ", ".join(role.mention for role in visible_removed_roles)[:1024], False),
                    ],
                )

        if timeout_changed:
            actor_value = _user_ref(entry.user) if entry else "Unknown"
            if after_timeout and (before_timeout is None or after_timeout > before_timeout):
                await send_log(
                    before.guild,
                    "user_timed_out",
                    f"{after.mention} was timed out.",
                    actor=entry.user if entry else after.guild.me,
                    target=after,
                    fields=[
                        ("Actor", actor_value, False),
                        ("Target", _user_ref(after), False),
                        ("Until", f"<t:{int(after_timeout.timestamp())}:F>", False),
                        ("Reason", _reason_text(entry.reason if entry else None), False),
                    ],
                )
            elif before_timeout and (after_timeout is None or after_timeout < before_timeout):
                await send_log(
                    before.guild,
                    "user_timeout_removed",
                    f"Timeout removed from {after.mention}.",
                    actor=entry.user if entry else after.guild.me,
                    target=after,
                    fields=[
                        ("Actor", actor_value, False),
                        ("Target", _user_ref(after), False),
                        ("Reason", _reason_text(entry.reason if entry else None), False),
                    ],
                )


async def setup(bot):
    await bot.add_cog(RoleEvents(bot))

