import discord
from discord.ext import commands

from database import db
from utils.helpers import get_recent_audit_log_entry, send_log


def _user_ref(user: discord.abc.User) -> str:
    return f"{user.mention} (`{user.id}`)"


def _reason_text(reason: str | None) -> str:
    return reason or "No reason provided."


class MemberEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            settings = await db.get_guild_settings(member.guild.id)
            protection_settings = settings["protection_settings"]

            if protection_settings.get("antibots", False) and member.bot:
                try:
                    whitelist = protection_settings.get("antibots_whitelist", [])
                    if member.id in whitelist:
                        await send_log(
                            member.guild,
                            "member_join",
                            f"Whitelisted bot joined {member.mention}.",
                            actor=member,
                            fields=[
                                ("Member", _user_ref(member), False),
                                ("Bot", "Whitelisted by Anti-Bots", False),
                            ],
                        )
                        return

                    allow_verified = bool(protection_settings.get("antibots_allow_verified", True))
                    is_verified_bot = bool(getattr(getattr(member, "public_flags", None), "verified_bot", False))
                    if allow_verified and is_verified_bot:
                        await send_log(
                            member.guild,
                            "member_join",
                            f"Verified bot joined {member.mention}.",
                            actor=member,
                            fields=[
                                ("Member", _user_ref(member), False),
                                ("Bot", "Verified bot allowed by Anti-Bots", False),
                            ],
                        )
                        return

                    action = str(protection_settings.get("antibots_action", "kick")).lower()
                    reason = "Anti-bots protection: Unauthorized bot"
                    me = member.guild.me
                    if me is None:
                        return

                    can_moderate = me.top_role > member.top_role
                    if action == "ban":
                        can_moderate = can_moderate and me.guild_permissions.ban_members
                    else:
                        can_moderate = can_moderate and me.guild_permissions.kick_members

                    if not can_moderate:
                        await send_log(
                            member.guild,
                            "member_kick",
                            f"Anti-Bots failed for {member.mention}.",
                            actor=member,
                            fields=[
                                ("Member", _user_ref(member), False),
                                ("Reason", "Missing permissions or role hierarchy.", False),
                            ],
                        )
                        return

                    if action == "ban":
                        await member.ban(reason=reason)
                    else:
                        await member.kick(reason=reason)
                    return
                except discord.Forbidden:
                    await send_log(
                        member.guild,
                        "member_kick",
                        f"Anti-Bots failed for {member.mention}.",
                        actor=member,
                        fields=[
                            ("Member", _user_ref(member), False),
                            ("Reason", "Missing permissions.", False),
                        ],
                    )
                    return

            await send_log(
                member.guild,
                "member_join",
                f"{member.mention} joined the server.",
                actor=member,
                fields=[
                    ("Member", _user_ref(member), False),
                    ("Created", f"<t:{int(member.created_at.timestamp())}:F>", False),
                ],
            )
        except Exception as e:
            print(f"Error in on_member_join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            entry = await get_recent_audit_log_entry(
                member.guild,
                discord.AuditLogAction.kick,
                member.id,
                within_seconds=8.0,
            )
            if entry is not None:
                await send_log(
                    member.guild,
                    "member_kick",
                    f"{entry.user.mention} kicked {member.mention}.",
                    actor=entry.user,
                    target=member,
                    fields=[
                        ("Moderator", _user_ref(entry.user), False),
                        ("Target", _user_ref(member), False),
                        ("Reason", _reason_text(entry.reason), False),
                    ],
                )
                return

            await send_log(
                member.guild,
                "member_remove",
                f"{member.mention} left the server.",
                actor=member,
                fields=[
                    ("Member", _user_ref(member), False),
                    ("Joined Server", f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", False),
                ],
            )
        except Exception as e:
            print(f"Error in on_member_remove: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        try:
            entry = await get_recent_audit_log_entry(
                guild,
                discord.AuditLogAction.ban,
                user.id,
                within_seconds=10.0,
            )
            actor = entry.user if entry else None
            message = f"{actor.mention if actor else 'Unknown moderator'} banned {user.mention}."
            await send_log(
                guild,
                "member_ban",
                message,
                actor=actor or user,
                target=user,
                fields=[
                    ("Moderator", _user_ref(actor) if actor else "Unknown", False),
                    ("Target", _user_ref(user), False),
                    ("Reason", _reason_text(entry.reason if entry else None), False),
                ],
            )
        except Exception as e:
            print(f"Error in on_member_ban: {e}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        try:
            entry = await get_recent_audit_log_entry(
                guild,
                discord.AuditLogAction.unban,
                user.id,
                within_seconds=10.0,
            )
            actor = entry.user if entry else None
            await send_log(
                guild,
                "ban_remove",
                f"{actor.mention if actor else 'Unknown moderator'} unbanned {user.mention}.",
                actor=actor or user,
                target=user,
                fields=[
                    ("Moderator", _user_ref(actor) if actor else "Unknown", False),
                    ("Target", _user_ref(user), False),
                    ("Reason", _reason_text(entry.reason if entry else None), False),
                ],
            )
        except Exception as e:
            print(f"Error in on_member_unban: {e}")

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        try:
            if before.name == after.name and before.display_avatar == after.display_avatar:
                return

            for guild in self.bot.guilds:
                member = guild.get_member(after.id)
                if member is None:
                    continue

                if before.name != after.name:
                    await send_log(
                        guild,
                        "user_name_update",
                        f"{member.mention} updated their username.",
                        actor=member,
                        target=member,
                        before=before.name,
                        after=after.name,
                        fields=[
                            ("Member", _user_ref(member), False),
                        ],
                    )

                if before.display_avatar != after.display_avatar:
                    before_avatar_url = str(before.display_avatar.url)
                    after_avatar_url = str(after.display_avatar.url)
                    display_name = discord.utils.escape_markdown(member.display_name)
                    await send_log(
                        guild,
                        "user_avatar_update",
                        f"{member.mention} updated their avatar.",
                        user=member,
                        fields=[
                            ("User", f"{member.mention} ({display_name})", False),
                            ("URL", f"[Open]({after_avatar_url})", False),
                            ("Previous URL", f"[Open]({before_avatar_url})", False),
                        ],
                    )
        except Exception as e:
            print(f"Error in on_user_update: {e}")


async def setup(bot):
    await bot.add_cog(MemberEvents(bot))
