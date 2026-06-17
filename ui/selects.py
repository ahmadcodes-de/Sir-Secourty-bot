import discord
from discord.ui import Select
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