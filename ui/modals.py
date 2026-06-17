import discord
from discord.ui import Modal, TextInput
from utils.strings import strings
from database import db

class ProtectionSettingModal(Modal, title='🛡️ Protection Setting'):
    def __init__(self, language: str, current_settings: dict, setting: str):
        super().__init__(title=f'🛡️ Protection Setting: {setting}')
        self.language = language
        self.current_settings = current_settings
        self.setting = setting
        
        if setting == "antibots":
            self.value_input = TextInput(
                label="Value (true/false)",
                placeholder="Enter 'true' to enable or 'false' to disable...",
                default=str(current_settings[setting]).lower(),
                required=True,
                max_length=5
            )
        else:
            self.value_input = TextInput(
                label="Value (number)",
                placeholder=f"Enter a number (current: {current_settings[setting]})...",
                default=str(current_settings[setting]),
                required=True,
                max_length=3
            )
        
        self.add_item(self.value_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = self.value_input.value.strip()
            protection_settings = self.current_settings.copy()
            
            if self.setting == "antibots":
                if value.lower() in ['true', '1', 'yes', 'on', 'enable']:
                    protection_settings[self.setting] = True
                    result_msg = "✅ Anti-bots protection enabled"
                elif value.lower() in ['false', '0', 'no', 'off', 'disable']:
                    protection_settings[self.setting] = False
                    result_msg = "✅ Anti-bots protection disabled"
                else:
                    await interaction.response.send_message("❌ Invalid value. Use 'true' or 'false'", ephemeral=True)
                    return
            else:
                try:
                    protection_settings[self.setting] = int(value)
                    if protection_settings[self.setting] < 0:
                        await interaction.response.send_message("❌ Value must be a positive number", ephemeral=True)
                        return
                    result_msg = f"✅ `{self.setting}` set to `{value}`"
                except ValueError:
                    await interaction.response.send_message("❌ Value must be a number", ephemeral=True)
                    return
            
            await db.update_protection_settings(interaction.guild_id, protection_settings)
            
            # تحديث الواجهة
            settings = await db.get_guild_settings(interaction.guild_id)
            from ui.views import AdvancedProtectionView
            view = AdvancedProtectionView(settings['language'], settings['protection_settings'])
            
            embed = discord.Embed(
                title="🛡️ Protection Settings",
                description=result_msg,
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class AddLogChannelModal(Modal, title='Add Log Channel'):
    def __init__(self, language: str):
        super().__init__()
        self.language = language
    
    channel_id = TextInput(
        label='Channel ID',
        placeholder='Enter the channel ID...',
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message(strings[self.language]['channel_not_found'], ephemeral=True)
                return
            
            success = await db.add_log_channel(interaction.guild_id, channel_id)
            if success:
                await interaction.response.send_message(
                    strings[self.language]['channel_added'].format(channel=channel.mention), 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    strings[self.language]['channel_exists'].format(channel=channel.mention), 
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(strings[self.language]['invalid_channel_id'], ephemeral=True)

class RemoveLogChannelModal(Modal, title='Remove Log Channel'):
    def __init__(self, language: str):
        super().__init__()
        self.language = language
    
    channel_id = TextInput(
        label='Channel ID',
        placeholder='Enter the channel ID to remove...',
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            success = await db.remove_log_channel(interaction.guild_id, channel_id)
            
            if success:
                await interaction.response.send_message(
                    strings[self.language]['channel_removed'].format(channel_id=channel_id), 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    strings[self.language]['channel_not_found'], 
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(strings[self.language]['invalid_channel_id'], ephemeral=True)

class SettingsModal(Modal, title='Change Protection Settings'):
    def __init__(self, language: str, current_settings: dict):
        super().__init__()
        self.language = language
        self.current_settings = current_settings
        
        self.setting_input = TextInput(
            label=strings[language]['select_setting'],
            placeholder="antibots, limitsban, limitskick, limitsroleC, limitsroleD, limitschannelD",
            required=True,
            max_length=50
        )
        
        self.value_input = TextInput(
            label=strings[language]['enter_value'],
            placeholder="true/false for antibots, or number for limits...",
            required=True,
            max_length=10
        )
        
        self.add_item(self.setting_input)
        self.add_item(self.value_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        setting = self.setting_input.value.strip().lower()
        value = self.value_input.value.strip()
        
        try:
            protection_settings = self.current_settings.copy()
            
            if setting not in protection_settings:
                await interaction.response.send_message(
                    f"❌ Invalid setting. Available settings: {', '.join(protection_settings.keys())}",
                    ephemeral=True
                )
                return
            
            if setting == "antibots":
                if value.lower() in ['true', '1', 'yes', 'on', 'enable']:
                    protection_settings[setting] = True
                elif value.lower() in ['false', '0', 'no', 'off', 'disable']:
                    protection_settings[setting] = False
                else:
                    await interaction.response.send_message("❌ Invalid value for antibots. Use 'true' or 'false'", ephemeral=True)
                    return
            else:
                # For numeric settings
                try:
                    protection_settings[setting] = int(value)
                    if protection_settings[setting] < 0:
                        await interaction.response.send_message("❌ Value must be a positive number", ephemeral=True)
                        return
                except ValueError:
                    await interaction.response.send_message("❌ Value must be a number", ephemeral=True)
                    return
            
            await db.update_protection_settings(interaction.guild_id, protection_settings)
            await interaction.response.send_message(
                strings[self.language]['setting_updated'].format(setting=setting, value=protection_settings[setting]),
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating setting: {str(e)}", ephemeral=True)