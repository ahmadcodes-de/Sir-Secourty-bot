import discord
import asyncio
import time
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import datetime
from typing import Optional

from utils.helpers import create_embed, format_time_delta, send_log
from utils.strings import strings
from database import db
from config import OWNER_IDS

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_bot_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user and int(interaction.user.id) in OWNER_IDS:
            return True
        await interaction.response.send_message("This command is for bot owners only.", ephemeral=True)
        return False

    async def _log_command_message(
        self,
        interaction: discord.Interaction,
        summary: str,
        *,
        target=None,
        extra_fields: list[tuple[str, str, bool]] | None = None,
    ):
        if interaction.guild is None or interaction.channel is None:
            return

        command_name = getattr(getattr(interaction, "command", None), "qualified_name", "unknown")
        fields = [
            ("Actor", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
            ("Command", f"`/{command_name}`", False),
            ("Room", f"{interaction.channel.mention} (`{interaction.channel.id}`)", False),
        ]
        if target is not None:
            target_value = getattr(target, "mention", f"`{getattr(target, 'name', str(target))}`")
            target_id = getattr(target, "id", None)
            fields.append(("Target", f"{target_value} (`{target_id}`)" if target_id else target_value, False))
        if extra_fields:
            fields.extend(extra_fields)

        await send_log(
            interaction.guild,
            "message_sent_command",
            summary,
            actor=interaction.user,
            target=target or interaction.channel,
            fields=fields,
        )

    @app_commands.command(name="botservers", description="List servers the bot is in | عرض سيرفرات البوت")
    async def botservers(self, interaction: discord.Interaction):
        if not await self._ensure_bot_owner(interaction):
            return

        guilds = sorted(self.bot.guilds, key=lambda guild: guild.member_count or 0, reverse=True)
        if not guilds:
            return await interaction.response.send_message("Bot is not in any servers.", ephemeral=True)

        lines = []
        for index, guild in enumerate(guilds, start=1):
            owner = guild.owner or self.bot.get_user(guild.owner_id)
            owner_text = f"{owner} ({guild.owner_id})" if owner else str(guild.owner_id)
            lines.append(
                f"`{index:02}` **{guild.name}**\n"
                f"ID: `{guild.id}` | Members: `{guild.member_count or 0}` | Owner: `{owner_text}`"
            )

        pages = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 2 > 3900:
                pages.append(current)
                current = ""
            current += line + "\n\n"
        if current:
            pages.append(current)

        embed = discord.Embed(
            title=f"Bot Servers ({len(guilds)})",
            description=pages[0],
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if len(pages) > 1:
            embed.set_footer(text=f"Page 1/{len(pages)}. Use /botservers again if you need the full list split differently.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        for page_number, page in enumerate(pages[1:], start=2):
            embed = discord.Embed(
                title=f"Bot Servers ({len(guilds)})",
                description=page,
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_footer(text=f"Page {page_number}/{len(pages)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="leaveguild", description="Make the bot leave a server by ID | إخراج البوت من سيرفر")
    @app_commands.describe(guild_id="Server ID to leave | آيدي السيرفر")
    async def leaveguild(self, interaction: discord.Interaction, guild_id: str):
        if not await self._ensure_bot_owner(interaction):
            return

        try:
            parsed_guild_id = int(guild_id.strip())
        except ValueError:
            return await interaction.response.send_message("Invalid server ID.", ephemeral=True)

        guild = self.bot.get_guild(parsed_guild_id)
        if guild is None:
            return await interaction.response.send_message("I am not in a server with that ID.", ephemeral=True)

        guild_name = guild.name
        member_count = guild.member_count or 0
        try:
            await guild.leave()
        except discord.HTTPException as exc:
            return await interaction.response.send_message(
                f"Failed to leave `{guild_name}` (`{parsed_guild_id}`): `{type(exc).__name__}`",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"Left server **{guild_name}** (`{parsed_guild_id}`) with `{member_count}` members.",
            ephemeral=True,
        )

    @app_commands.command(name="uptime", description="Show bot uptime | عرض مدة تشغيل البوت")
    async def uptime(self, interaction: discord.Interaction):
        """مدة تشغيل البوت"""
        uptime_seconds = int(time.time() - self.bot.start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        embed = discord.Embed(
            title="⏱️ Bot Uptime",
            description=f"**The bot has been running for:**\n**{uptime_str}**",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(
            name="Start Time",
            value=f"<t:{int(self.bot.start_time)}:F>",
            inline=True
        )
        
        embed.add_field(
            name="Current Time", 
            value=f"<t:{int(time.time())}:F>",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mute", description="Mute a member | كتم عضو")
    @app_commands.default_permissions(administrator=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """كتم عضو"""
        role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not role:
            role = await interaction.guild.create_role(name="Muted")
            for ch in interaction.guild.channels:
                await ch.set_permissions(role, send_messages=False, speak=False)
        
        await member.add_roles(role, reason=reason)
        await send_log(
            interaction.guild,
            "mute_add",
            f"{interaction.user.mention} muted {member.mention}.",
            actor=interaction.user,
            target=member,
            fields=[
                ("Actor", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
                ("Target", f"{member.mention} (`{member.id}`)", False),
                ("Mute Role", f"{role.mention} (`{role.id}`)", False),
                ("Reason", reason, False),
            ],
        )
        
        embed = discord.Embed(
            title="🔇 Member Muted",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/mute` on {member.mention}.",
            target=member,
            extra_fields=[("Reason", reason, False)],
        )

    @app_commands.command(name="unmute", description="Unmute a member | فك كتم عضو")
    @app_commands.default_permissions(administrator=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        """فك كتم عضو"""
        role = discord.utils.get(interaction.guild.roles, name="Muted")
        if role and role in member.roles:
            await member.remove_roles(role)
            await send_log(
                interaction.guild,
                "mute_remove",
                f"{interaction.user.mention} removed mute from {member.mention}.",
                actor=interaction.user,
                target=member,
                fields=[
                    ("Actor", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
                    ("Target", f"{member.mention} (`{member.id}`)", False),
                    ("Mute Role", f"{role.mention} (`{role.id}`)", False),
                ],
            )
            
            embed = discord.Embed(
                title="🔊 Member Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            await self._log_command_message(
                interaction,
                f"{interaction.user.mention} used `/unmute` on {member.mention}.",
                target=member,
            )
        else:
            await interaction.response.send_message("❌ User is not muted")

    @app_commands.command(name="kick", description="Kick a member | طرد عضو")
    @app_commands.default_permissions(administrator=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """طرد عضو"""
        await member.kick(reason=reason)
        
        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/kick` on {member.mention}.",
            target=member,
            extra_fields=[("Reason", reason, False)],
        )

    @app_commands.command(name="ban", description="Ban a member from the server | حظر عضو من السيرفر")
    @app_commands.default_permissions(administrator=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """حظر عضو"""
        await member.ban(reason=reason)
        
        embed = discord.Embed(
            title="⛔ Member Banned",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/ban` on {member.mention}.",
            target=member,
            extra_fields=[("Reason", reason, False)],
        )

    @app_commands.command(name="unban", description="Unban a user by ID | فك حظر مستخدم عبر الآيدي")
    @app_commands.default_permissions(administrator=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        """فك حظر عضو"""
        try:
            user_id_int = int(user_id)
            user = await self.bot.fetch_user(user_id_int)
            await interaction.guild.unban(user)
            
            embed = discord.Embed(
                title="✅ Member Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            embed.add_field(name="User", value=f"{user} ({user_id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            await self._log_command_message(
                interaction,
                f"{interaction.user.mention} used `/unban` on {user.mention}.",
                target=user,
            )
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned")
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID")

    @app_commands.command(name="setnick", description="Change a member's nickname | تغيير لقب عضو")
    @app_commands.default_permissions(administrator=True)
    async def setnick(self, interaction: discord.Interaction, member: discord.Member, nickname: str):
        """تغيير اسم عضو"""
        old_nick = member.nick or member.name
        await member.edit(nick=nickname)
        
        embed = discord.Embed(
            title="✏️ Nickname Changed",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Old Nickname", value=old_nick, inline=True)
        embed.add_field(name="New Nickname", value=nickname, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/setnick` on {member.mention}.",
            target=member,
            extra_fields=[
                ("Before", old_nick, False),
                ("After", nickname, False),
            ],
        )

    @app_commands.command(name="memberstats", description="Show detailed member statistics | عرض إحصائيات الأعضاء")
    @app_commands.default_permissions(administrator=True)
    async def memberstats(self, interaction: discord.Interaction):
        """عرض إحصائيات الأعضاء"""
        # تأجيل الرد فوراً لمنع timeout
        await interaction.response.defer(ephemeral=False, thinking=True)
        
        guild = interaction.guild
        
        try:
            # استخدام البيانات المخزنة مؤقتاً بدلاً من fetch_members لتسريع العملية
            total_members = guild.member_count
            members = guild.members
            
            bot_count = sum(1 for m in members if m.bot)
            human_count = total_members - bot_count
            
            # الأعضاء حسب الحالة (البشر فقط، بدون البوتات)
            online = sum(1 for m in members if m.status != discord.Status.offline and not m.bot)
            idle = sum(1 for m in members if m.status == discord.Status.idle and not m.bot)
            dnd = sum(1 for m in members if m.status == discord.Status.dnd and not m.bot)
            offline = sum(1 for m in members if m.status == discord.Status.offline and not m.bot)
            
            # الأعضاء الجدد في آخر 24 ساعة (البشر فقط)
            now = discord.utils.utcnow()
            one_day_ago = now - datetime.timedelta(days=1)
            new_members = sum(1 for m in members if m.joined_at and m.joined_at > one_day_ago and not m.bot)
            
            embed = discord.Embed(
                title="📊 Member Statistics",
                color=discord.Color.blue(),
                timestamp=now
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # الإحصائيات الأساسية
            embed.add_field(
                name="👥 Basic Stats",
                value=f"**Total Members:** {total_members}\n"
                      f"**👤 Humans:** {human_count}\n"
                      f"**🤖 Bots:** {bot_count}\n"
                      f"**🆕 New Humans (24h):** {new_members}",
                inline=True
            )
            
            # الحالات (البشر فقط)
            embed.add_field(
                name="🟢 Human Status",
                value=f"**Online:** {online}\n"
                      f"**🟡 Idle:** {idle}\n"
                      f"**🔴 DND:** {dnd}\n"
                      f"**⚫ Offline:** {offline}",
                inline=True
            )
            
            # النسب المئوية
            if total_members > 0:
                human_percent = (human_count / total_members) * 100
                bot_percent = (bot_count / total_members) * 100
                online_percent = (online / human_count) * 100 if human_count > 0 else 0
                
                embed.add_field(
                    name="📈 Percentages",
                    value=f"**Humans:** {human_percent:.1f}%\n"
                          f"**Bots:** {bot_percent:.1f}%\n"
                          f"**Humans Online:** {online_percent:.1f}%",
                    inline=True
                )
            
            embed.set_footer(text=f"Server: {guild.name} | Last refresh")
            
            view = View(timeout=300)  # 5 دقائق timeout
            view.add_item(Button(
                label="🔄 Refresh Statistics (Admins Only)",
                style=discord.ButtonStyle.primary,
                custom_id="refresh_stats_admin",
                emoji="🔄"
            ))
            
            # إرسال الرسالة باستخدام followup بعد defer
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to generate member statistics: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed)

    @app_commands.command(name="moveall", description="Move all members to your voice channel | سحب الجميع لرومك الصوتي")
    @app_commands.default_permissions(administrator=True)
    async def moveall(self, interaction: discord.Interaction):
        """سحب الجميع للروم الصوتي"""
        if not interaction.user.voice:
            embed = discord.Embed(
                title="❌ Error",
                description="You must be in a voice channel to use this command.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed)
        
        channel = interaction.user.voice.channel
        moved_count = 0
        
        for vc in interaction.guild.voice_channels:
            for m in vc.members:
                if m != interaction.user and vc != channel:
                    try:
                        await m.move_to(channel)
                        moved_count += 1
                    except:
                        pass
        
        embed = discord.Embed(
            title="📢 Members Moved",
            description=f"Moved **{moved_count}** members to {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/moveall` to move members to {channel.mention}.",
            target=channel,
            extra_fields=[("Moved Members", str(moved_count), False)],
        )

    @app_commands.command(name="close", description="Lock the current channel | قفل الروم الحالي")
    @app_commands.default_permissions(administrator=True)
    async def close(self, interaction: discord.Interaction):
        """قفل الشات"""
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{interaction.channel.mention} has been locked.",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/close` in {interaction.channel.mention}.",
            target=interaction.channel,
        )

    @app_commands.command(name="openchat", description="Unlock the current channel | فتح الروم الحالي")
    @app_commands.default_permissions(administrator=True)
    async def openchat(self, interaction: discord.Interaction):
        """فتح الشات"""
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{interaction.channel.mention} has been unlocked.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/openchat` in {interaction.channel.mention}.",
            target=interaction.channel,
        )

    @app_commands.command(name="createtext", description="Create a text channel | إنشاء روم كتابي")
    @app_commands.default_permissions(administrator=True)
    async def createtext(self, interaction: discord.Interaction, name: str):
        """إنشاء روم كتابي"""
        channel = await interaction.guild.create_text_channel(name)
        
        embed = discord.Embed(
            title="📘 Text Channel Created",
            description=f"Created text channel: {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/createtext`.",
            target=channel,
        )

    @app_commands.command(name="createvoice", description="Create a voice channel | إنشاء روم صوتي")
    @app_commands.default_permissions(administrator=True)
    async def createvoice(self, interaction: discord.Interaction, name: str):
        """إنشاء روم صوتي"""
        channel = await interaction.guild.create_voice_channel(name)
        
        embed = discord.Embed(
            title="🎙️ Voice Channel Created",
            description=f"Created voice channel: {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/createvoice`.",
            target=channel,
        )

    @app_commands.command(name="clear", description="Clear messages from the channel | مسح الرسائل من الروم")
    @app_commands.default_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, amount: int = 5):
        """مسح الرسائل"""
        if amount > 100:
            amount = 100
        
        # حذف الرسائل
        deleted = await interaction.channel.purge(limit=amount + 1)
        
        # إرسال رسالة تأكيد كرسالة عادية
        embed = discord.Embed(
            title="🧹 Messages Cleared",
            description=f"Deleted **{len(deleted) - 1}** messages",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
        
        # إرسال الرسالة كرساءة عادية
        message = await interaction.channel.send(embed=embed)
        await self._log_command_message(
            interaction,
            f"{interaction.user.mention} used `/clear` in {interaction.channel.mention}.",
            target=interaction.channel,
            extra_fields=[("Messages Deleted", str(len(deleted) - 1), False)],
        )
        
        # حذف رسالة التأكيد بعد 5 ثواني
        await asyncio.sleep(5)
        try:
            await message.delete()
        except:
            pass  # تجاهل الخطأ إذا لم نستطع حذف الرسالة

    @app_commands.command(name="slowmode", description="Set slowmode for a channel | ضبط وضع البطء للروم")
    @app_commands.default_permissions(administrator=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: Optional[discord.TextChannel] = None):
        """تعيين وضع البطء للروم"""
        target_channel = channel or interaction.channel
        
        if interaction.guild is None:
            lang = 'en'
        else:
            settings = await db.get_guild_settings(interaction.guild.id)
            lang = settings['language']
        
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message(strings[lang]['slowmode_invalid'])
            return
        
        try:
            await target_channel.edit(slowmode_delay=seconds)
            
            embed = discord.Embed(
                title="🐌 Slowmode Updated",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            if seconds == 0:
                embed.description = strings[lang]['slowmode_removed'].format(channel=target_channel.mention)
            else:
                embed.description = strings[lang]['slowmode_set'].format(seconds=seconds, channel=target_channel.mention)
            
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            await self._log_command_message(
                interaction,
                f"{interaction.user.mention} used `/slowmode` on {target_channel.mention}.",
                target=target_channel,
                extra_fields=[("Seconds", str(seconds), False)],
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to change slowmode for this channel")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error setting slowmode: {str(e)}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """معالج تفاعلات الأزرار"""
        if interaction.type == discord.InteractionType.component:
            if interaction.data['custom_id'] == 'refresh_stats_admin':
                # التحقق من صلاحيات الأدمن أولاً
                if not interaction.user.guild_permissions.administrator:
                    error_embed = discord.Embed(
                        title="❌ Permission Denied",
                        description="This button is only available for server administrators.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                    return
                
                # تأجيل الرد فوراً
                await interaction.response.defer(ephemeral=True)
                
                try:
                    # استخدام البيانات المخزنة مؤقتاً لتسريع العملية
                    guild = interaction.guild
                    members = guild.members
                    
                    # إعادة حساب الإحصائيات
                    total_members = guild.member_count
                    bot_count = sum(1 for m in members if m.bot)
                    human_count = total_members - bot_count
                    
                    online = sum(1 for m in members if m.status != discord.Status.offline and not m.bot)
                    idle = sum(1 for m in members if m.status == discord.Status.idle and not m.bot)
                    dnd = sum(1 for m in members if m.status == discord.Status.dnd and not m.bot)
                    offline = sum(1 for m in members if m.status == discord.Status.offline and not m.bot)
                    
                    now = discord.utils.utcnow()
                    one_day_ago = now - datetime.timedelta(days=1)
                    new_members = sum(1 for m in members if m.joined_at and m.joined_at > one_day_ago and not m.bot)
                    
                    embed = discord.Embed(
                        title="📊 Member Statistics (Refreshed)",
                        color=discord.Color.green(),
                        timestamp=now
                    )
                    
                    if guild.icon:
                        embed.set_thumbnail(url=guild.icon.url)
                    
                    # الإحصائيات الأساسية
                    embed.add_field(
                        name="👥 Basic Stats",
                        value=f"**Total Members:** {total_members}\n"
                              f"**👤 Humans:** {human_count}\n"
                              f"**🤖 Bots:** {bot_count}\n"
                              f"**🆕 New Humans (24h):** {new_members}",
                        inline=True
                    )
                    
                    # الحالات (البشر فقط)
                    embed.add_field(
                        name="🟢 Human Status",
                        value=f"**Online:** {online}\n"
                              f"**🟡 Idle:** {idle}\n"
                              f"**🔴 DND:** {dnd}\n"
                              f"**⚫ Offline:** {offline}",
                        inline=True
                    )
                    
                    # النسب المئوية
                    if total_members > 0:
                        human_percent = (human_count / total_members) * 100
                        bot_percent = (bot_count / total_members) * 100
                        online_percent = (online / human_count) * 100 if human_count > 0 else 0
                        
                        embed.add_field(
                            name="📈 Percentages",
                            value=f"**Humans:** {human_percent:.1f}%\n"
                                  f"**Bots:** {bot_percent:.1f}%\n"
                                  f"**Humans Online:** {online_percent:.1f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text=f"Server: {guild.name} | Refreshed by {interaction.user.display_name}")
                    
                    view = View(timeout=300)
                    view.add_item(Button(
                        label="🔄 Refresh Statistics (Admins Only)",
                        style=discord.ButtonStyle.primary,
                        custom_id="refresh_stats_admin",
                        emoji="🔄"
                    ))
                    
                    # تعديل الرسالة الأصلية بدلاً من إرسال رسالة جديدة
                    await interaction.message.edit(embed=embed, view=view)
                    
                    # إرسال رسالة نجاح للمستخدم (ستظهر بشكل مؤقت له فقط)
                    success_embed = discord.Embed(
                        title="✅ Refresh Complete",
                        description="Member statistics have been refreshed successfully!",
                        color=discord.Color.green()
                    )
                    await interaction.followup.send(embed=success_embed, ephemeral=True)
                    
                except Exception as e:
                    error_embed = discord.Embed(
                        title="❌ Refresh Failed",
                        description=f"Error refreshing statistics: {str(e)}",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
