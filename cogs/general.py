import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
import datetime
from typing import Optional

from utils.helpers import create_embed, format_time_delta
from utils.strings import strings
from database import db

class HelpSelect(Select):
    def __init__(self, language: str, is_admin: bool = False):
        self.language = language
        self.is_admin = is_admin
        
        options = [
            discord.SelectOption(
                label=strings[language]['protection_commands'],
                value="protection",
                emoji="🛡️",
                description="Server security and moderation"
            ),
            discord.SelectOption(
                label=strings[language]['general_commands'],
                value="general", 
                emoji="📋",
                description="Everyday utility commands"
            ),
            discord.SelectOption(
                label=strings[language]['info_commands'],
                value="info",
                emoji="ℹ️",
                description="Bot and developer information"
            ),
        ]
        
        if is_admin:
            options.append(discord.SelectOption(
                label=strings[language]['admin_commands'],
                value="admin",
                emoji="⚙️",
                description="Administrative tools"
            ))
        
        super().__init__(
            placeholder=strings[language]['select_category'],
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        lang = self.language
        
        if self.values[0] == "protection":
            embed = discord.Embed(
                title=strings[lang]['protection_title'],
                color=discord.Color.red()
            )
            embed.description = strings[lang]['protection_description']
            embed.description += f"• `/antibots on` - {strings[lang]['antibots_on']}\n"
            embed.description += f"• `/antibots off` - {strings[lang]['antibots_off']}\n"
            embed.description += f"• `/settings` - {strings[lang]['settings_view']}\n"
            embed.description += f"• `/setlogs` - {strings[lang]['set_logs']}\n"
            
        elif self.values[0] == "general":
            embed = discord.Embed(
                title=strings[lang]['general_title'],
                color=discord.Color.blue()
            )
            embed.description = strings[lang]['general_description']
            embed.description += f"• `/avatar` - {strings[lang]['avatar']}\n"
            embed.description += f"• `/servericon` - {strings[lang]['server_icon']}\n"
            embed.description += f"• `/user` - {strings[lang]['user_info']}\n"
            embed.description += f"• `/server` - {strings[lang]['server_info']}\n"
            embed.description += f"• `/botcount` - {strings[lang]['bot_count']}\n"
            embed.description += f"• `/ping` - {strings[lang]['ping']}\n"
            
        elif self.values[0] == "admin":
            if not self.is_admin:
                await interaction.response.send_message(
                    strings[lang]['not_admin'], 
                    ephemeral=True
                )
                return
                
            embed = discord.Embed(
                title=strings[lang]['admin_title'],
                color=discord.Color.green()
            )
            embed.description = strings[lang]['admin_description']
            embed.description += f"• `/uptime` - {strings[lang]['uptime_cmd']}\n"
            embed.description += f"• `/mute @user` - {strings[lang]['mute_cmd']}\n"
            embed.description += f"• `/unmute @user` - {strings[lang]['unmute_cmd']}\n"
            embed.description += f"• `/kick @user` - {strings[lang]['kick_cmd']}\n"
            embed.description += f"• `/ban @user` - {strings[lang]['ban_cmd']}\n"
            embed.description += f"• `/unban ID` - {strings[lang]['unban_cmd']}\n"
            embed.description += f"• `/setnick @user name` - {strings[lang]['setnick_cmd']}\n"
            embed.description += f"• `/moveall` - {strings[lang]['moveall_cmd']}\n"
            embed.description += f"• `/close` - {strings[lang]['close_cmd']}\n"
            embed.description += f"• `/openchat` - {strings[lang]['openchat_cmd']}\n"
            embed.description += f"• `/createtext name` - {strings[lang]['create_text']}\n"
            embed.description += f"• `/createvoice name` - {strings[lang]['create_voice']}\n"
            embed.description += f"• `/clear amount` - {strings[lang]['clear_cmd']}\n"
            embed.description += f"• `/setlang` - {strings[lang]['set_language']}\n"
            embed.description += f"• `/slowmode seconds` - {strings[lang]['slowmode_cmd']}\n"
            
        elif self.values[0] == "info":
            embed = discord.Embed(
                title=strings[lang]['info_title'],
                color=discord.Color.purple()
            )
            embed.description = strings[lang]['info_description']
            embed.description += f"• `/botinfo` - {strings[lang]['bot_info']}\n"
            embed.description += f"• `/invite` - {strings[lang]['invite_bot']}\n"
            embed.description += f"• `/developer` - {strings[lang]['developer_info']}\n"
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class HelpView(View):
    def __init__(self, language: str, is_admin: bool = False):
        super().__init__(timeout=60)
        self.language = language
        self.is_admin = is_admin
        self.add_item(HelpSelect(language, is_admin))

class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show the help menu with all commands | عرض قائمة المساعدة")
    async def help_command(self, interaction: discord.Interaction):
        """عرض قائمة المساعدة"""
        if interaction.guild is None:
            lang = 'en'
            is_admin = False
        else:
            settings = await db.get_guild_settings(interaction.guild.id)
            lang = settings['language']
            is_admin = interaction.user.guild_permissions.administrator
        
        view = HelpView(lang, is_admin)
        
        embed = discord.Embed(
            title=strings[lang]['help_title'],
            description=strings[lang]['help_description'],
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="ping", description="Check bot latency | فحص سرعة استجابة البوت")
    async def ping(self, interaction: discord.Interaction):
        """فحص سرعة البوت"""
        if interaction.guild is None:
            lang = 'en'
        else:
            settings = await db.get_guild_settings(interaction.guild.id)
            lang = settings['language']
        
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(strings[lang]['ping_response'].format(latency=latency))

    @app_commands.command(name="avatar", description="Show your avatar | عرض صورتك الشخصية")
    async def avatar(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """عرض الصورة الشخصية"""
        target = member or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ {target.display_name}'s Avatar",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        view = View()
        view.add_item(Button(
            label="Download Avatar",
            style=discord.ButtonStyle.link,
            url=target.display_avatar.url,
            emoji="📥"
        ))
        
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="servericon", description="Show server icon | عرض أيقونة السيرفر")
    async def servericon(self, interaction: discord.Interaction):
        """عرض أيقونة السيرفر"""
        if not interaction.guild.icon:
            await interaction.response.send_message("🚫 No server icon found")
            return
        
        embed = discord.Embed(
            title="🏰 Server Icon",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_image(url=interaction.guild.icon.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        view = View()
        view.add_item(Button(
            label="Download Icon",
            style=discord.ButtonStyle.link,
            url=interaction.guild.icon.url,
            emoji="📥"
        ))
        
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="user", description="Show detailed user information | عرض معلومات العضو")
    async def user_info(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """معلومات العضو"""
        target = member or interaction.user
        
        if interaction.guild is None:
            lang = 'en'
        else:
            settings = await db.get_guild_settings(interaction.guild.id)
            lang = settings['language']
        
        # حساب مدة الانضمام
        joined_days = (datetime.datetime.now(datetime.timezone.utc) - target.joined_at.replace(tzinfo=datetime.timezone.utc)).days if target.joined_at else 0
        created_days = (datetime.datetime.now(datetime.timezone.utc) - target.created_at.replace(tzinfo=datetime.timezone.utc)).days
        
        # الحالة والنشاط
        status_emoji = {
            'online': '🟢',
            'idle': '🟡',
            'dnd': '🔴',
            'offline': '⚫'
        }
        
        status = status_emoji.get(str(target.status), '⚫')
        activity = target.activity.name if target.activity else "None"
        
        embed = discord.Embed(
            title=strings[lang]['user_info_title'],
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"ID: {target.id}")
        
        # المعلومات الأساسية
        embed.add_field(
            name="👤 Basic Info",
            value=f"**Name:** {target.display_name}\n"
                  f"**Discriminator:** #{target.discriminator}\n"
                  f"**Bot:** {'✅ Yes' if target.bot else '❌ No'}\n"
                  f"**Status:** {status} {str(target.status).title()}",
            inline=True
        )
        
        # التواريخ
        embed.add_field(
            name="📅 Dates",
            value=f"**{strings[lang]['created']}:** <t:{int(target.created_at.timestamp())}:R>\n"
                  f"**{strings[lang]['joined']}:** <t:{int(target.joined_at.timestamp())}:R>\n"
                  f"**Account Age:** {created_days} days\n"
                  f"**Server Member:** {joined_days} days",
            inline=True
        )
        
        # الرتب
        roles = [role for role in target.roles[1:]]  # استبعاد @everyone
        roles_text = ", ".join([role.mention for role in roles[:10]])  # عرض أول 10 رتب فقط
        if len(roles) > 10:
            roles_text += f" ... and {len(roles) - 10} more"
        
        embed.add_field(
            name=f"🎨 Roles ({len(roles)})",
            value=roles_text if roles else "No roles",
            inline=False
        )
        
        # النشاط
        if target.activity:
            embed.add_field(
                name="🎮 Activity",
                value=f"**{activity}**",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server", description="Show detailed server information | عرض معلومات السيرفر")
    async def server_info(self, interaction: discord.Interaction):
        """معلومات السيرفر"""
        guild = interaction.guild
        
        if guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server!")
            return
        else:
            settings = await db.get_guild_settings(guild.id)
            lang = settings['language']
        
        # الإحصائيات
        total_members = guild.member_count
        bot_count = sum(1 for m in guild.members if m.bot)
        human_count = total_members - bot_count
        
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        total_channels = text_channels + voice_channels
        roles_count = len(guild.roles)
        
        # مستوى التحقق
        verification_levels = {
            discord.VerificationLevel.none: "None",
            discord.VerificationLevel.low: "Low",
            discord.VerificationLevel.medium: "Medium",
            discord.VerificationLevel.high: "High",
            discord.VerificationLevel.highest: "Highest"
        }
        
        embed = discord.Embed(
            title=strings[lang]['server_info_title'],
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"ID: {guild.id} | Server Created")
        
        # استخدام طريقة آمنة للإشارة إلى المالك
        owner_mention = guild.owner.mention if guild.owner else f"<@{guild.owner_id}>"
        
        # المعلومات الأساسية
        embed.add_field(
            name="🏰 Basic Info",
            value=f"**Name:** {guild.name}\n"
                  f"**{strings[lang]['owner']}:** {owner_mention}\n"
                  f"**{strings[lang]['created']}:** <t:{int(guild.created_at.timestamp())}:R>\n"
                  f"**{strings[lang]['verification']}:** {verification_levels.get(guild.verification_level, 'Unknown')}",
            inline=True
        )
        
        # الإحصائيات
        embed.add_field(
            name="📊 Statistics",
            value=f"**{strings[lang]['members']}:** {total_members}\n"
                  f"**👥 Humans:** {human_count}\n"
                  f"**🤖 Bots:** {bot_count}\n"
                  f"**🟢 Online:** {online_members}",
            inline=True
        )
        
        # القنوات والرتب
        embed.add_field(
            name="📁 Structure",
            value=f"**{strings[lang]['channels']}:** {total_channels}\n"
                  f"**💬 Text:** {text_channels}\n"
                  f"**🎙️ Voice:** {voice_channels}\n"
                  f"**📂 Categories:** {categories}\n"
                  f"**🎨 {strings[lang]['roles']}:** {roles_count}",
            inline=True
        )
        
        # البوستات والميزات
        if guild.premium_tier > 0:
            embed.add_field(
                name="🚀 Boosting",
                value=f"**{strings[lang]['boosts']}:** {guild.premium_subscription_count}\n"
                      f"**Level:** {guild.premium_tier}\n"
                      f"**Boosters:** {len(guild.premium_subscribers)}",
                inline=True
            )
        
        # الميزات
        if guild.features:
            features = ", ".join([f"`{feat.replace('_', ' ').title()}`" for feat in guild.features[:5]])
            if len(guild.features) > 5:
                features += f" ... and {len(guild.features) - 5} more"
            
            embed.add_field(
                name="✨ Features",
                value=features,
                inline=False
            )
        
        from ui.views import EnhancedServerView
        view = EnhancedServerView(lang)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="botcount", description="Show bot count in server | عرض عدد البوتات في السيرفر")
    async def botcount(self, interaction: discord.Interaction):
        """عدد البوتات في السيرفر"""
        count = sum(1 for m in interaction.guild.members if m.bot)
        human_count = interaction.guild.member_count - count
        
        embed = discord.Embed(
            title="🤖 Bot Statistics",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(
            name="Members Breakdown",
            value=f"**🤖 Bots:** {count}\n"
                  f"**👥 Humans:** {human_count}\n"
                  f"**📊 Total:** {interaction.guild.member_count}\n"
                  f"**📈 Bot Percentage:** {round((count/interaction.guild.member_count)*100, 1)}%",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
