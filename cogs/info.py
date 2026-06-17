import discord
import time
from discord import app_commands
from discord.ext import commands
import datetime
from datetime import timedelta

from utils.helpers import create_embed, format_time_delta
from utils.strings import strings
from database import db
from ui.views import EnhancedDeveloperView, InviteView

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="botinfo", description="Show detailed bot information | عرض معلومات البوت")
    async def botinfo(self, interaction: discord.Interaction):
        """معلومات البوت"""
        uptime_seconds = int(time.time() - self.bot.start_time)
        uptime_str = format_time_delta(uptime_seconds)  # تم الإصلاح: بدون await
        
        embed = discord.Embed(
            title="🤖 Bot Information",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        embed.add_field(
            name="📊 Basic Info",
            value=f"**Name:** {self.bot.user.name}\n"
                  f"**ID:** {self.bot.user.id}\n"
                  f"**Ping:** {round(self.bot.latency * 1000)}ms\n"
                  f"**Uptime:** {uptime_str}",
            inline=True
        )
        
        embed.add_field(
            name="🌐 Statistics",
            value=f"**Servers:** {len(self.bot.guilds)}\n"
                  f"**Users:** {len(self.bot.users)}\n"
                  f"**Commands:** {len(self.bot.tree.get_commands())}\n",
            inline=True
        )
        
        embed.add_field(
            name="👨‍💻 Development",
            value=f"**{strings['en']['bot_developer']}:** Ahmad Alhalabi\n"
                  f"**Library:** discord.py\n"
                  f"**Version:** 4.0.1\n"
                  f"**Started:** <t:{int(self.bot.start_time)}:R>",
            inline=True
        )
        
        view = InviteView('en')
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="invite", description="Get bot invite link | رابط دعوة البوت")
    async def invite(self, interaction: discord.Interaction):
        """دعوة البوت"""
        if interaction.guild is None:
            lang = 'en'
        else:
            settings = await db.get_guild_settings(interaction.guild.id)
            lang = settings['language']
        
        view = InviteView(lang)
        
        embed = discord.Embed(
            title=strings[lang]['invite_bot'],
            description="📩 Invite me to your server!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Features",
            value="• 🛡️ Advanced Protection\n• 📊 Server Management\n• 🔧 Moderation Tools\n• 📝 Logging System",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="developer", description="Show detailed developer information | معلومات المطور")
    async def developer(self, interaction: discord.Interaction):
        """معلومات المطور"""
        if interaction.guild is None:
            lang = 'en'
        else:
            settings = await db.get_guild_settings(interaction.guild.id)
            lang = settings['language']
        
        view = EnhancedDeveloperView(lang)
        
        embed = discord.Embed(
            title=strings[lang]['developer_info_title'],
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        embed.add_field(
            name="👨‍💻 Developer Information",
            value=f"**Name:** Ahmad Alhalabi\n"
                  f"**Specialization:** Discord Bot Development\n"
                  f"**Experience:** 6+ Years\n"
                  f"**Projects:** 10+ Bots Developed",
            inline=True
        )
        
        embed.add_field(
            name="🛠️ Technical Skills",
            value="• Python & Discord.py\n• JavaScript & Node.js\n• Database Management\n• Web Development\n• API Integration",
            inline=True
        )
        
        embed.add_field(
            name="🌟 Features",
            value="• Multi-language Support\n• Advanced Protection\n• Custom Logging System\n• User-friendly Interface\n• Regular Updates",
            inline=False
        )
        
        embed.add_field(
            name=strings[lang]['special_thanks'],
            value="Thank you for using our bot! We appreciate your support and feedback.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
