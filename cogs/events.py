"""
Cog لمعالجة أحداث الأعضاء والسيرفر
"""

import discord
from discord.ext import commands
from datetime import timezone

from utils.helpers import create_embed, get_relative_time, format_dt
from utils.protection import ProtectionSystem
from config import COLORS, EMOJIS

class EventsHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.protection = ProtectionSystem(bot)
    
    # =============== أحداث الأعضاء ===============
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """عند انضمام عضو جديد"""
        
        # فحص الحماية من البوتات
        if member.bot:
            antibot_passed = await self.protection.check_antibot(member.guild, member)
            if not antibot_passed:
                # تم طرد البوت - إرسال سجل
                log_channel_id = await self.bot.db.get_log_channel(member.guild.id, 'member_join')
                if log_channel_id:
                    channel = member.guild.get_channel(log_channel_id)
                    if channel:
                        embed = create_embed(
                            title=f"{EMOJIS['shield']} تم طرد بوت",
                            description=f"**البوت:** {member.mention}\n"
                                      f"**الاسم:** `{member.name}`\n"
                                      f"**السبب:** الحماية من البوتات مفعلة",
                            color=COLORS['warning']
                        )
                        await channel.send(embed=embed)
                return
        
        # فحص الحماية من الإغارات
        antiraid_passed = await self.protection.check_antiraid(member.guild, member)
        if not antiraid_passed:
            # محاولة إغارة مكتشفة
            log_channel_id = await self.bot.db.get_log_channel(member.guild.id, 'member_join')
            if log_channel_id:
                channel = member.guild.get_channel(log_channel_id)
                if channel:
                    embed = create_embed(
                        title=f"{EMOJIS['warning']} تحذير: محاولة إغارة محتملة",
                        description=f"تم اكتشاف انضمام سريع لعدد كبير من الأعضاء\n"
                                  f"**آخر عضو:** {member.mention}\n"
                                  f"**الاسم:** `{member.name}`",
                        color=COLORS['error']
                    )
                    await channel.send(embed=embed)
        
        # إرسال سجل الانضمام
        log_channel_id = await self.bot.db.get_log_channel(member.guild.id, 'member_join')
        if log_channel_id:
            channel = member.guild.get_channel(log_channel_id)
            if channel:
                embed = create_embed(
                    title=f"{EMOJIS['member']} عضو جديد",
                    color=COLORS['success']
                )
                
                embed.set_thumbnail(url=member.display_avatar.url)
                
                embed.add_field(
                    name="العضو",
                    value=f"{member.mention}\n`{member.name}`",
                    inline=True
                )
                
                embed.add_field(
                    name="المعرف",
                    value=f"`{member.id}`",
                    inline=True
                )
                
                embed.add_field(
                    name="تاريخ إنشاء الحساب",
                    value=f"{format_dt(member.created_at, 'R')}\n{get_relative_time(member.created_at)}",
                    inline=False
                )
                
                # التحقق من عمر الحساب
                account_age = (discord.utils.utcnow() - member.created_at).days
                if account_age < 7:
                    embed.add_field(
                        name="⚠️ تحذير",
                        value=f"حساب جديد (عمره {account_age} أيام)",
                        inline=False
                    )
                
                embed.set_footer(text=f"العدد الكلي: {member.guild.member_count}")
                
                await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """عند مغادرة عضو"""
        
        log_channel_id = await self.bot.db.get_log_channel(member.guild.id, 'member_leave')
        if log_channel_id:
            channel = member.guild.get_channel(log_channel_id)
            if channel:
                embed = create_embed(
                    title=f"{EMOJIS['member']} عضو غادر",
                    color=COLORS['error']
                )
                
                embed.set_thumbnail(url=member.display_avatar.url)
                
                embed.add_field(
                    name="العضو",
                    value=f"{member.mention}\n`{member.name}`",
                    inline=True
                )
                
                embed.add_field(
                    name="المعرف",
                    value=f"`{member.id}`",
                    inline=True
                )
                
                if member.joined_at:
                    embed.add_field(
                        name="كان عضواً لمدة",
                        value=get_relative_time(member.joined_at),
                        inline=False
                    )
                
                # عرض الرتب
                roles = [role.mention for role in member.roles[1:]]
                if roles:
                    roles_text = ', '.join(roles[:5])
                    if len(roles) > 5:
                        roles_text += f' *و {len(roles) - 5} أخرى*'
                    embed.add_field(
                        name="الرتب",
                        value=roles_text,
                        inline=False
                    )
                
                embed.set_footer(text=f"العدد الكلي: {member.guild.member_count}")
                
                await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """عند تحديث معلومات عضو"""
        
        log_channel_id = await self.bot.db.get_log_channel(after.guild.id, 'member_update')
        if not log_channel_id:
            return
        
        channel = after.guild.get_channel(log_channel_id)
        if not channel:
            return
        
        changes = []
        
        # تغيير الاسم
        if before.nick != after.nick:
            old_nick = before.nick or "لا يوجد"
            new_nick = after.nick or "لا يوجد"
            changes.append(f"**الاسم المستعار:**\n`{old_nick}` → `{new_nick}`")
        
        # تغيير الرتب
        if before.roles != after.roles:
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]
            
            if added_roles:
                changes.append(f"**رتب مضافة:**\n{', '.join(r.mention for r in added_roles)}")
            if removed_roles:
                changes.append(f"**رتب محذوفة:**\n{', '.join(r.mention for r in removed_roles)}")
        
        # إرسال السجل فقط إذا كان هناك تغييرات
        if changes:
            embed = create_embed(
                title=f"{EMOJIS['member']} تحديث عضو",
                description=f"**العضو:** {after.mention}\n\n" + "\n\n".join(changes),
                color=COLORS['info']
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            await channel.send(embed=embed)
    
    # =============== أحداث القنوات ===============
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """عند إنشاء قناة"""
        
        log_channel_id = await self.bot.db.get_log_channel(channel.guild.id, 'channel_create')
        if log_channel_id:
            log_channel = channel.guild.get_channel(log_channel_id)
            if log_channel:
                channel_type = "نصية" if isinstance(channel, discord.TextChannel) else "صوتية"
                
                embed = create_embed(
                    title=f"{EMOJIS['channel']} قناة جديدة",
                    description=f"**القناة:** {channel.mention}\n"
                              f"**الاسم:** `{channel.name}`\n"
                              f"**النوع:** {channel_type}",
                    color=COLORS['success']
                )
                
                await log_channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """عند حذف قناة"""
        
        log_channel_id = await self.bot.db.get_log_channel(channel.guild.id, 'channel_delete')
        if log_channel_id:
            log_channel = channel.guild.get_channel(log_channel_id)
            if log_channel:
                channel_type = "نصية" if isinstance(channel, discord.TextChannel) else "صوتية"
                
                embed = create_embed(
                    title=f"{EMOJIS['channel']} قناة محذوفة",
                    description=f"**الاسم:** `{channel.name}`\n"
                              f"**المعرف:** `{channel.id}`\n"
                              f"**النوع:** {channel_type}",
                    color=COLORS['error']
                )
                
                await log_channel.send(embed=embed)
    
    # =============== أحداث الرتب ===============
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """عند إنشاء رتبة"""
        
        log_channel_id = await self.bot.db.get_log_channel(role.guild.id, 'role_create')
        if log_channel_id:
            channel = role.guild.get_channel(log_channel_id)
            if channel:
                embed = create_embed(
                    title=f"{EMOJIS['role']} رتبة جديدة",
                    description=f"**الرتبة:** {role.mention}\n"
                              f"**الاسم:** `{role.name}`\n"
                              f"**اللون:** `{role.color}`",
                    color=COLORS['success']
                )
                
                await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """عند حذف رتبة"""
        
        log_channel_id = await self.bot.db.get_log_channel(role.guild.id, 'role_delete')
        if log_channel_id:
            channel = role.guild.get_channel(log_channel_id)
            if channel:
                embed = create_embed(
                    title=f"{EMOJIS['role']} رتبة محذوفة",
                    description=f"**الاسم:** `{role.name}`\n"
                              f"**المعرف:** `{role.id}`",
                    color=COLORS['error']
                )
                
                await channel.send(embed=embed)
    
    # =============== أحداث السيرفر ===============
    
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """عند تحديث معلومات السيرفر"""
        
        log_channel_id = await self.bot.db.get_log_channel(after.id, 'server_update')
        if not log_channel_id:
            return
        
        channel = after.get_channel(log_channel_id)
        if not channel:
            return
        
        changes = []
        
        if before.name != after.name:
            changes.append(f"**الاسم:**\n`{before.name}` → `{after.name}`")
        
        if before.icon != after.icon:
            changes.append("**الأيقونة:** تم التغيير")
        
        if before.owner != after.owner:
            changes.append(f"**المالك:**\n{before.owner.mention} → {after.owner.mention}")
        
        if changes:
            embed = create_embed(
                title=f"{EMOJIS['settings']} تحديث السيرفر",
                description="\n\n".join(changes),
                color=COLORS['info']
            )
            
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EventsHandler(bot))
