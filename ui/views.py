import discord
from discord.ui import View, Select, Button, Modal, TextInput
from config import DEFAULT_LOG_SETTINGS
from utils.strings import strings
from utils.helpers import get_available_log_channels, sanitize_log_channels
from database import db
from ui.modals import ProtectionSettingModal, AddLogChannelModal, RemoveLogChannelModal

# =============== واجهات متطورة للإعدادات المتعددة ===============

def _t(language: str, en: str, ar: str) -> str:
    return ar if language == "ar" else en


def _event_label(language: str, event_key: str) -> str:
    return strings[language].get(
        f"log_event_{event_key}",
        strings[language].get(event_key, event_key)
    )


def _normalize_log_settings(current_settings: dict) -> dict:
    normalized = dict(DEFAULT_LOG_SETTINGS)
    if isinstance(current_settings, dict):
        normalized.update(current_settings)
    return normalized


class MultiLogChannelSelect(Select):
    def __init__(self, language: str, current_log_channels: list, guild: discord.Guild):
        self.language = language
        self.guild = guild
        self.current_log_channels = current_log_channels
        
        # إنشاء خيارات من جميع قنوات النص في السيرفر (محدودة إلى 25 قناة)
        options = []
        text_channels = get_available_log_channels(guild)
        
        # تحديد الحد الأقصى للقنوات المعروضة (25 كحد أقصى)
        max_channels = min(25, len(text_channels))
        
        for i, channel in enumerate(text_channels[:max_channels]):
            is_selected = channel.id in current_log_channels
            options.append(discord.SelectOption(
                label=f"#{channel.name}"[:25],  # الحد من طول الاسم
                value=str(channel.id),
                description=f"ID: {channel.id}"[:50],  # الحد من طول الوصف
                default=is_selected,
                emoji="📝" if is_selected else "📄"
            ))
        
        has_options = bool(options)
        if not has_options:
            options.append(discord.SelectOption(
                label=_t(language, "No usable text channels", "لا توجد قنوات نصية متاحة"),
                value="0",
                description=_t(language, "Bot needs View + Send permissions", "البوت يحتاج صلاحيات العرض والإرسال"),
            ))

        super().__init__(
            placeholder=strings[language]['select_log_channels'],
            options=options,
            min_values=0,
            max_values=min(25, len(options)),  # التأكد من أن max_values <= 25
            custom_id="multi_log_select",
            disabled=not has_options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # تحديث القنوات المختارة
        selected_channels = []
        for channel_id in self.values:
            try:
                parsed_id = int(channel_id)
            except (TypeError, ValueError):
                continue
            if parsed_id > 0:
                selected_channels.append(parsed_id)
        selected_channels, removed_channels = sanitize_log_channels(interaction.guild, selected_channels)
        
        # حفظ الإعدادات
        selected_channels = [channel.id if hasattr(channel, "id") else int(channel) for channel in selected_channels]
        settings = await db.get_guild_settings(interaction.guild_id)
        await db.set_guild_settings(
            interaction.guild_id,
            settings['language'],
            selected_channels,
            settings['protection_settings'],
            settings['advanced_logs'],
            settings['automod_settings']
        )
        
        # تحديث الواجهة
        view = AdvancedLogsView(self.language, selected_channels, interaction.guild)
        
        embed = discord.Embed(
            title=strings[self.language]['logs_management'],
            description=f"✅ **Updated!** Selected {len(selected_channels)} log channels",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class AdvancedLogsView(View):
    def __init__(self, language: str, current_log_channels: list, guild: discord.Guild):
        super().__init__(timeout=180)
        self.language = language
        self.add_item(MultiLogChannelSelect(language, current_log_channels, guild))
        self.configure_events.label = _t(language, "Configure Events", "ضبط الأحداث")
        self.view_selected.label = _t(language, "View Selected", "عرض المختارة")
        self.search_channels.label = _t(language, "Search Channels", "بحث القنوات")
        self.select_all.label = _t(language, "Select All", "اختيار الكل")
        self.clear_all.label = _t(language, "Clear All", "مسح الكل")
    
    @discord.ui.button(label="Configure Log Events", style=discord.ButtonStyle.primary, emoji="🔧", row=1)
    async def configure_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        """تكوين أحداث السجلات للقنوات"""
        settings = await db.get_guild_settings(interaction.guild_id)
        log_channels, removed_channels = sanitize_log_channels(interaction.guild, settings['log_channels'])
        if log_channels != settings['log_channels']:
            await db.set_guild_settings(
                interaction.guild_id,
                settings['language'],
                log_channels,
                settings['protection_settings'],
                settings['advanced_logs'],
                settings['automod_settings']
            )
        
        if not log_channels:
            await interaction.response.send_message(
                _t(
                    self.language,
                    "❌ No valid log channels set. Please add channels where the bot can send.",
                    "❌ لا توجد قنوات سجلات صالحة. أضف قنوات يستطيع البوت الإرسال فيها.",
                ),
                ephemeral=True
            )
            return
        if not log_channels:
            await interaction.response.send_message("❌ No log channels set. Please add log channels first.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=strings[self.language]['advanced_logs_title'],
            description=strings[self.language]['advanced_logs_desc'],
            color=discord.Color.blue()
        )
        
        view = View(timeout=180)
        view.add_item(ChannelSelectForLogs(self.language, log_channels, interaction.guild))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="View Selected", style=discord.ButtonStyle.primary, emoji="👁️", row=1)
    async def view_selected(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await db.get_guild_settings(interaction.guild_id)
        log_channels = settings['log_channels']
        
        if not log_channels:
            embed = discord.Embed(
                title="📋 Current Log Channels",
                description="❌ No log channels selected",
                color=discord.Color.red()
            )
        else:
            channels_list = []
            for channel_id in log_channels:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    # الحصول على إعدادات السجلات للقناة
                    log_settings = await db.get_channel_log_settings(interaction.guild_id, channel_id)
                    enabled_count = sum(1 for enabled in log_settings.values() if enabled)
                    total_count = len(log_settings)
                    
                    channels_list.append(f"• {channel.mention} (`{channel.id}`) - {enabled_count}/{total_count} events")
                else:
                    channels_list.append(f"• ⚠️ Deleted Channel (`{channel_id}`)")
            
            embed = discord.Embed(
                title="📋 Current Log Channels",
                description="\n".join(channels_list),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Total: {len(log_channels)} channels")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Search Channels", style=discord.ButtonStyle.secondary, emoji="🔍", row=2)
    async def search_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """فتح نافذة البحث عن القنوات"""
        modal = ChannelSearchModal(self.language, interaction.guild)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Select All", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def select_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        # اختيار جميع القنوات (محدودة إلى 25 قناة)
        all_text_channels = get_available_log_channels(interaction.guild)
        all_channels = [channel.id for channel in all_text_channels[:25]]
        all_channels = all_text_channels[:25]  # الحد إلى 25 قناة كحد أقصى
        
        settings = await db.get_guild_settings(interaction.guild_id)
        await db.set_guild_settings(
            interaction.guild_id,
            settings['language'],
            [channel.id if hasattr(channel, "id") else int(channel) for channel in all_channels],
            settings['protection_settings'],
            settings['advanced_logs'],
            settings['automod_settings']
        )
        
        # تحديث الواجهة
        view = AdvancedLogsView(
            self.language,
            [channel.id if hasattr(channel, "id") else int(channel) for channel in all_channels],
            interaction.guild
        )
        
        embed = discord.Embed(
            title=strings[self.language]['logs_management'],
            description=f"✅ **All channels selected!** ({len(all_channels)} channels)",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        # مسح جميع القنوات
        settings = await db.get_guild_settings(interaction.guild_id)
        await db.set_guild_settings(
            interaction.guild_id,
            settings['language'],
            [],
            settings['protection_settings'],
            settings['advanced_logs'],
            settings['automod_settings']
        )
        
        # تحديث الواجهة
        view = AdvancedLogsView(self.language, [], interaction.guild)
        
        embed = discord.Embed(
            title=strings[self.language]['logs_management'],
            description="✅ **All log channels cleared!**",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

# =============== واجهات السجلات المتقدمة ===============

class ChannelLogSettingsSelect(Select):
    def __init__(self, language: str, channel_id: int, current_settings: dict):
        self.language = language
        self.channel_id = channel_id
        self.current_settings = _normalize_log_settings(current_settings)
        
        options = [
            discord.SelectOption(
                label=_event_label(language, "member_join"),
                value="member_join",
                description="When members join the server",
                default=self.current_settings.get('member_join', True),
                emoji="🟢"
            ),
            discord.SelectOption(
                label=_event_label(language, "member_remove"),
                value="member_remove", 
                description="When members leave the server",
                default=self.current_settings.get('member_remove', True),
                emoji="🔴"
            ),
            discord.SelectOption(
                label=_event_label(language, "member_ban"),
                value="member_ban",
                description="When members are banned",
                default=self.current_settings.get('member_ban', True),
                emoji="🔨"
            ),
            discord.SelectOption(
                label=_event_label(language, "member_kick"),
                value="member_kick",
                description="When members are kicked",
                default=self.current_settings.get('member_kick', True),
                emoji="👢"
            ),
            discord.SelectOption(
                label=_event_label(language, "message_delete"),
                value="message_delete",
                description="When messages are deleted",
                default=self.current_settings.get('message_delete', True),
                emoji="🗑️"
            ),
            discord.SelectOption(
                label=_event_label(language, "channel_create"),
                value="channel_create",
                description="When channels are created",
                default=self.current_settings.get('channel_create', True),
                emoji="📘"
            ),
            discord.SelectOption(
                label=_event_label(language, "channel_delete"),
                value="channel_delete",
                description="When channels are deleted",
                default=self.current_settings.get('channel_delete', True),
                emoji="🗑️"
            ),
            discord.SelectOption(
                label=_event_label(language, "role_create"),
                value="role_create",
                description="When roles are created",
                default=self.current_settings.get('role_create', True),
                emoji="🎨"
            ),
            discord.SelectOption(
                label=_event_label(language, "role_delete"),
                value="role_delete",
                description="When roles are deleted",
                default=self.current_settings.get('role_delete', True),
                emoji="🗑️"
            ),
            discord.SelectOption(
                label=_event_label(language, "message_edit"),
                value="message_edit",
                description="When messages are edited",
                default=self.current_settings.get('message_edit', False),
                emoji="✏️"
            ),
            discord.SelectOption(
                label=_event_label(language, "voice_join"),
                value="voice_join",
                description="When members join voice channels",
                default=self.current_settings.get('voice_join', False),
                emoji="🎤"
            ),
            discord.SelectOption(
                label=_event_label(language, "voice_leave"),
                value="voice_leave",
                description="When members leave voice channels",
                default=self.current_settings.get('voice_leave', False),
                emoji="🚪"
            ),
            discord.SelectOption(
                label=_event_label(language, "nickname_change"),
                value="nickname_change",
                description="When members change nicknames",
                default=self.current_settings.get('nickname_change', False),
                emoji="👤"
            ),
            discord.SelectOption(
                label=_event_label(language, "role_update"),
                value="role_update",
                description="When roles are updated",
                default=self.current_settings.get('role_update', False),
                emoji="🔄"
            )
        ]
        
        super().__init__(
            placeholder="Select events to log...",
            options=options,
            min_values=0,
            max_values=len(options),
            custom_id="channel_log_settings"
        )
    
    async def callback(self, interaction: discord.Interaction):
        # تحديث الإعدادات بناءً على الاختيارات
        new_settings = dict(self.current_settings)
        managed_keys = [
            "member_join",
            "member_remove",
            "member_ban",
            "member_kick",
            "message_delete",
            "channel_create",
            "channel_delete",
            "role_create",
            "role_delete",
            "message_edit",
            "voice_join",
            "voice_leave",
            "nickname_change",
            "role_update",
        ]
        for key in managed_keys:
            new_settings[key] = key in self.values
        
        await db.update_channel_log_settings(interaction.guild_id, self.channel_id, new_settings)
        
        # تحديث الواجهة
        channel = interaction.guild.get_channel(self.channel_id)
        view = ChannelLogSettingsView(self.language, self.channel_id, new_settings)
        
        embed = discord.Embed(
            title=strings[self.language]['log_settings_for'].format(channel=channel.mention),
            description=strings[self.language]['events_updated'].format(channel=channel.mention),
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class ChannelLogSettingsView(View):
    def __init__(self, language: str, channel_id: int, current_settings: dict):
        super().__init__(timeout=180)
        self.language = language
        self.channel_id = channel_id
        self.current_settings = _normalize_log_settings(current_settings)
        
        self.add_item(ChannelLogSettingsSelect(language, channel_id, self.current_settings))
        self.enable_all.label = _t(language, "Enable All", "تفعيل الكل")
        self.disable_all.label = _t(language, "Disable All", "تعطيل الكل")
        self.back_to_channels.label = _t(language, "Back to Channels", "العودة للقنوات")
    
    @discord.ui.button(label="Enable All", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def enable_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        # تفعيل جميع الأحداث
        all_enabled = {key: True for key in self.current_settings.keys()}
        await db.update_channel_log_settings(interaction.guild_id, self.channel_id, all_enabled)
        
        # تحديث الواجهة
        channel = interaction.guild.get_channel(self.channel_id)
        view = ChannelLogSettingsView(self.language, self.channel_id, all_enabled)
        
        embed = discord.Embed(
            title=strings[self.language]['log_settings_for'].format(channel=channel.mention),
            description=f"✅ **All events enabled** for {channel.mention}",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Disable All", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def disable_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        # تعطيل جميع الأحداث
        all_disabled = {key: False for key in self.current_settings.keys()}
        await db.update_channel_log_settings(interaction.guild_id, self.channel_id, all_disabled)
        
        # تحديث الواجهة
        channel = interaction.guild.get_channel(self.channel_id)
        view = ChannelLogSettingsView(self.language, self.channel_id, all_disabled)
        
        embed = discord.Embed(
            title=strings[self.language]['log_settings_for'].format(channel=channel.mention),
            description=f"❌ **All events disabled** for {channel.mention}",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Back to Channels", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back_to_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        # العودة إلى قائمة القنوات
        settings = await db.get_guild_settings(interaction.guild_id)
        log_channels = settings['log_channels']
        
        embed = discord.Embed(
            title=strings[self.language]['advanced_logs_title'],
            description=strings[self.language]['advanced_logs_desc'],
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📊 Current Status",
            value=f"**{len(log_channels)}** log channels configured",
            inline=True
        )
        
        view = AdvancedLogsView(self.language, log_channels, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)

class ChannelSelectForLogs(Select):
    def __init__(self, language: str, log_channels: list, guild: discord.Guild):
        self.language = language
        self.guild = guild
        
        options = []
        for channel_id in log_channels:
            channel = guild.get_channel(channel_id)
            if channel:
                options.append(discord.SelectOption(
                    label=f"#{channel.name}",
                    value=str(channel_id),
                    description=f"Configure logs for {channel.name}",
                    emoji="⚙️"
                ))
        
        has_options = bool(options)
        if not has_options:
            options.append(discord.SelectOption(
                label=_t(language, "No configurable channels", "لا توجد قنوات قابلة للضبط"),
                value="0",
                description=_t(language, "Add log channels first", "قم بإضافة قنوات سجلات أولاً"),
            ))

        super().__init__(
            placeholder=strings[language]['select_channel_configure'],
            options=options,
            max_values=1,
            custom_id="channel_select_logs",
            disabled=not has_options
        )
    
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = self.guild.get_channel(channel_id)
        
        if not channel:
            await interaction.response.send_message(
                _t(self.language, "❌ Channel not found!", "❌ القناة غير موجودة!"),
                ephemeral=True,
            )
            return
        if not channel:
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return
        
        # الحصول على الإعدادات الحالية للقناة
        current_settings = _normalize_log_settings(
            await db.get_channel_log_settings(interaction.guild_id, channel_id)
        )
        
        # إنشاء واجهة إعدادات القناة
        view = ChannelLogSettingsView(self.language, channel_id, current_settings)
        
        embed = discord.Embed(
            title=strings[self.language]['log_settings_for'].format(channel=channel.mention),
            description=strings[self.language]['log_settings_desc'],
            color=discord.Color.blue()
        )
        
        # عرض الإعدادات الحالية
        enabled_events = [_event_label(self.language, key) for key, value in current_settings.items() if value]
        disabled_events = [_event_label(self.language, key) for key, value in current_settings.items() if not value]
        
        if enabled_events:
            embed.add_field(
                name="✅ Enabled Events",
                value="\n".join([f"• {event}" for event in enabled_events]),
                inline=True
            )
        
        if disabled_events:
            embed.add_field(
                name="❌ Disabled Events", 
                value="\n".join([f"• {event}" for event in disabled_events]),
                inline=True
            )
        
        await interaction.response.edit_message(embed=embed, view=view)

# =============== واجهة متطورة لإعدادات الحماية ===============

class ProtectionSettingsSelect(Select):
    def __init__(self, language: str, current_settings: dict):
        self.language = language
        self.current_settings = current_settings
        
        options = [
            discord.SelectOption(
                label=strings[language]['setting_antibots'],
                value="antibots",
                description=f"Current: {'✅ Enabled' if current_settings['antibots'] else '❌ Disabled'}",
                emoji="🤖",
                default=False
            ),
            discord.SelectOption(
                label=strings[language]['setting_limitsban'],
                value="limitsban",
                description=f"Current: {current_settings['limitsban']} bans",
                emoji="🔨",
                default=False
            ),
            discord.SelectOption(
                label=strings[language]['setting_limitskick'],
                value="limitskick", 
                description=f"Current: {current_settings['limitskick']} kicks",
                emoji="👢",
                default=False
            ),
            discord.SelectOption(
                label=strings[language]['setting_limitsroleC'],
                value="limitsroleC",
                description=f"Current: {current_settings['limitsroleC']} role creations", 
                emoji="🎨",
                default=False
            ),
            discord.SelectOption(
                label=strings[language]['setting_limitsroleD'],
                value="limitsroleD",
                description=f"Current: {current_settings['limitsroleD']} role deletions",
                emoji="🗑️",
                default=False
            ),
            discord.SelectOption(
                label=strings[language]['setting_limitschannelD'],
                value="limitschannelD", 
                description=f"Current: {current_settings['limitschannelD']} channel deletions",
                emoji="📁",
                default=False
            )
        ]
        
        super().__init__(
            placeholder="🎛️ Select setting to modify...",
            options=options,
            max_values=1,
            custom_id="protection_setting_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_setting = self.values[0]
        modal = ProtectionSettingModal(self.language, self.current_settings, selected_setting)
        await interaction.response.send_modal(modal)

class AdvancedProtectionView(View):
    def __init__(self, language: str, current_settings: dict):
        super().__init__(timeout=180)
        self.language = language
        self.current_settings = current_settings
        self.add_item(ProtectionSettingsSelect(language, current_settings))
    
    @discord.ui.button(label="View All Settings", style=discord.ButtonStyle.primary, emoji="📊", row=1)
    async def view_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings_list = []
        for key, value in self.current_settings.items():
            if key == "antibots":
                display_value = "✅ Enabled" if value else "❌ Disabled"
            else:
                display_value = f"`{value}`"
            
            setting_names = {
                'antibots': strings[self.language]['setting_antibots'],
                'limitsban': strings[self.language]['setting_limitsban'],
                'limitskick': strings[self.language]['setting_limitskick'],
                'limitsroleC': strings[self.language]['setting_limitsroleC'],
                'limitsroleD': strings[self.language]['setting_limitsroleD'],
                'limitschannelD': strings[self.language]['setting_limitschannelD']
            }
            
            settings_list.append(f"• **{setting_names[key]}**: {display_value}")
        
        embed = discord.Embed(
            title="🛡️ Current Protection Settings",
            description="\n".join(settings_list),
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📖 Usage Guide",
            value=strings[self.language]['settings_guide'],
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Reset to Default", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def reset_default(self, interaction: discord.Interaction, button: discord.ui.Button):
        from config import DEFAULT_PROTECTION_SETTINGS
        
        await db.update_protection_settings(interaction.guild_id, DEFAULT_PROTECTION_SETTINGS)
        
        # تحديث الواجهة
        view = AdvancedProtectionView(self.language, DEFAULT_PROTECTION_SETTINGS)
        
        embed = discord.Embed(
            title="🛡️ Protection Settings",
            description="✅ **All settings reset to default values!**",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

# =============== نظام البحث عن القنوات ===============

class ChannelSearchModal(discord.ui.Modal, title='🔍 بحث عن قناة'):
    """نافذة البحث عن القنوات"""
    def __init__(self, language: str, guild: discord.Guild):
        super().__init__()
        self.language = language
        self.guild = guild
        
        self.search_input = discord.ui.TextInput(
            label='اسم القناة أو ID',
            placeholder='اكتب اسم القناة أو ID (مثال: general أو 1234567890)...',
            required=True,
            max_length=100
        )
        
        self.add_item(self.search_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        search_term = self.search_input.value.strip().lower()
        
        # جلب جميع القنوات
        all_channels = []
        for channel in self.guild.channels:
            try:
                # التحقق من أن البوت يستطيع رؤية القناة
                if channel.permissions_for(self.guild.me).view_channel:
                    all_channels.append(channel)
            except:
                continue
        
        # تصنيف القنوات حسب النوع
        text_channels = [ch for ch in all_channels if isinstance(ch, discord.TextChannel)]
        voice_channels = [ch for ch in all_channels if isinstance(ch, discord.VoiceChannel)]
        stage_channels = [ch for ch in all_channels if isinstance(ch, discord.StageChannel)]
        forum_channels = [ch for ch in all_channels if isinstance(ch, discord.ForumChannel)]
        category_channels = [ch for ch in all_channels if isinstance(ch, discord.CategoryChannel)]
        
        # البحث حسب الاسم
        channels_by_name = []
        for channel in all_channels:
            if search_term in channel.name.lower():
                channels_by_name.append(channel)
        
        # البحث حسب ID
        channel_by_id = None
        try:
            channel_id = int(search_term)
            channel_by_id = self.guild.get_channel(channel_id)
        except ValueError:
            pass
        
        # جمع النتائج
        results = []
        
        # إذا بحث بالـ ID ووجدت القناة
        if channel_by_id:
            emoji = self.get_channel_emoji(channel_by_id)
            results.append(f"{emoji} **بحث بالـ ID:** {self.format_channel_info(channel_by_id)}")
        
        # إذا بحث بالاسم
        if channels_by_name:
            results.append("🔍 **نتائج البحث بالاسم:**")
            for channel in channels_by_name[:15]:  # عرض أول 15 نتيجة فقط
                emoji = self.get_channel_emoji(channel)
                results.append(f"{emoji} {self.format_channel_info(channel)}")
        
        # إذا لم توجد نتائج
        if not results:
            embed = discord.Embed(
                title="🔍 نتائج البحث",
                description=f"❌ **لم يتم العثور على قنوات تطابق:** `{search_term}`",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 نصائح للبحث",
                value="• اكتب اسم القناة (مثال: general)\n• أو اكتب ID القناة (مثال: 1234567890)\n• البحث غير حساس لحالة الأحرف",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # إنشاء embed للنتائج
        embed = discord.Embed(
            title="🔍 نتائج البحث عن القنوات",
            description="\n".join(results),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # إضافة إحصاءات
        total_found = len(channels_by_name) + (1 if channel_by_id else 0)
        embed.set_footer(text=f"تم العثور على {total_found} قناة | البحث: {search_term}")
        
        # إنشاء view مع أزرار الإجراءات
        view = SearchResultsView(self.language, self.guild, all_channels, search_term)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    def get_channel_emoji(self, channel):
        """الحصول على الإيموجي المناسب لنوع القناة"""
        if isinstance(channel, discord.TextChannel):
            return "💬"
        elif isinstance(channel, discord.VoiceChannel):
            return "🔊"
        elif isinstance(channel, discord.StageChannel):
            return "📢"
        elif isinstance(channel, discord.ForumChannel):
            return "📝"
        elif isinstance(channel, discord.CategoryChannel):
            return "📂"
        else:
            return "📄"
    
    def format_channel_info(self, channel):
        """تنسيق معلومات القناة"""
        if isinstance(channel, discord.TextChannel):
            return f"{channel.mention} (`{channel.id}`) - 📍 {channel.category.name if channel.category else 'بدون فئة'}"
        elif isinstance(channel, discord.VoiceChannel):
            return f"**{channel.name}** (`{channel.id}`) 🔊 {channel.category.name if channel.category else 'بدون فئة'}"
        else:
            return f"**{channel.name}** (`{channel.id}`)"


class SearchResultsView(discord.ui.View):
    """واجهة نتائج البحث"""
    def __init__(self, language: str, guild: discord.Guild, channels: list, search_term: str):
        super().__init__(timeout=120)
        self.language = language
        self.guild = guild
        self.channels = channels
        self.search_term = search_term
    
    @discord.ui.button(label="إضافة إلى السجلات", style=discord.ButtonStyle.success, emoji="➕", row=0)
    async def add_to_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """فتح نافذة لإضافة القنوات إلى السجلات"""
        # إنشاء قائمة منسدلة للقنوات
        options = []
        for channel in self.channels[:25]:  # حد 25 قناة
            if self.search_term.lower() in channel.name.lower():
                emoji = "💬" if isinstance(channel, discord.TextChannel) else "🔊"
                options.append(discord.SelectOption(
                    label=f"{emoji} {channel.name[:25]}",
                    value=str(channel.id),
                    description=f"ID: {channel.id}",
                    emoji=emoji
                ))
        
        if not options:
            await interaction.response.send_message("❌ لا توجد قنوات للعرض", ephemeral=True)
            return
        
        select = ChannelAddSelect(self.language, self.guild, options)
        view = discord.ui.View(timeout=120)
        view.add_item(select)
        
        embed = discord.Embed(
            title="➕ إضافة قنوات إلى السجلات",
            description="اختر القنوات التي تريد إضافتها إلى قنوات السجلات:",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="إظهار كل القنوات", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def show_all_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """عرض جميع القنوات مع تصنيفها"""
        # تصنيف القنوات
        text_channels = [ch for ch in self.channels if isinstance(ch, discord.TextChannel)]
        voice_channels = [ch for ch in self.channels if isinstance(ch, discord.VoiceChannel)]
        other_channels = [ch for ch in self.channels if not isinstance(ch, (discord.TextChannel, discord.VoiceChannel))]
        
        embed = discord.Embed(
            title="📋 جميع القنوات في السيرفر",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # عرض القنوات النصية
        if text_channels:
            text_list = []
            for channel in text_channels[:20]:  # عرض أول 20 قناة فقط
                text_list.append(f"• {channel.mention} (`{channel.id}`)")
            
            embed.add_field(
                name=f"💬 قنوات نصية ({len(text_channels)})",
                value="\n".join(text_list) if text_list else "لا توجد قنوات نصية",
                inline=False
            )
        
        # عرض القنوات الصوتية
        if voice_channels:
            voice_list = []
            for channel in voice_channels[:20]:  # عرض أول 20 قناة فقط
                voice_list.append(f"• **{channel.name}** (`{channel.id}`)")
            
            embed.add_field(
                name=f"🔊 قنوات صوتية ({len(voice_channels)})",
                value="\n".join(voice_list) if voice_list else "لا توجد قنوات صوتية",
                inline=False
            )
        
        # عرض القنوات الأخرى
        if other_channels:
            other_list = []
            for channel in other_channels[:10]:
                channel_type = "📢 مرحلة" if isinstance(channel, discord.StageChannel) else \
                             "📂 فئة" if isinstance(channel, discord.CategoryChannel) else \
                             "📝 منتدى" if isinstance(channel, discord.ForumChannel) else "❓ أخرى"
                other_list.append(f"• **{channel.name}** (`{channel.id}`) - {channel_type}")
            
            embed.add_field(
                name=f"📁 قنوات أخرى ({len(other_channels)})",
                value="\n".join(other_list) if other_list else "لا توجد قنوات أخرى",
                inline=False
            )
        
        embed.set_footer(text=f"إجمالي القنوات: {len(self.channels)} | السيرفر: {self.guild.name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="بحث جديد", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def new_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        """فتح نافذة بحث جديدة"""
        modal = ChannelSearchModal(self.language, self.guild)
        await interaction.response.send_modal(modal)


class ChannelAddSelect(discord.ui.Select):
    """قائمة اختيار القنوات للإضافة"""
    def __init__(self, language: str, guild: discord.Guild, options: list):
        super().__init__(
            placeholder="اختر القنوات للإضافة...",
            options=options,
            min_values=1,
            max_values=min(10, len(options)),  # يمكن اختيار حتى 10 قنوات
            custom_id="channel_add_select"
        )
        self.language = language
        self.guild = guild
    
    async def callback(self, interaction: discord.Interaction):
        from database import db
        
        added_channels = []
        already_exists = []
        
        for channel_id_str in self.values:
            channel_id = int(channel_id_str)
            channel = self.guild.get_channel(channel_id)
            
            if channel:
                # التحقق إذا كانت القناة موجودة بالفعل
                settings = await db.get_guild_settings(self.guild.id)
                log_channels = settings['log_channels']
                
                if channel_id in log_channels:
                    already_exists.append(channel)
                else:
                    # إضافة القناة
                    await db.add_log_channel(self.guild.id, channel_id)
                    added_channels.append(channel)
        
        # إنشاء رسالة النتيجة
        result_embed = discord.Embed(
            title="➕ نتيجة الإضافة",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        if added_channels:
            added_list = []
            for channel in added_channels:
                emoji = "💬" if isinstance(channel, discord.TextChannel) else "🔊"
                added_list.append(f"{emoji} {channel.mention if isinstance(channel, discord.TextChannel) else f'**{channel.name}**'}")
            
            result_embed.add_field(
                name=f"✅ تمت الإضافة ({len(added_channels)})",
                value="\n".join(added_list),
                inline=False
            )
        
        if already_exists:
            exists_list = []
            for channel in already_exists:
                emoji = "💬" if isinstance(channel, discord.TextChannel) else "🔊"
                exists_list.append(f"{emoji} {channel.mention if isinstance(channel, discord.TextChannel) else f'**{channel.name}**'}")
            
            result_embed.add_field(
                name=f"⚠️ موجودة مسبقاً ({len(already_exists)})",
                value="\n".join(exists_list),
                inline=False
            )
        
        result_embed.set_footer(text="سيتم تحديث قائمة السجلات تلقائياً")
        
        # تحديث واجهة السجلات الرئيسية
        try:
            settings = await db.get_guild_settings(self.guild.id)
            log_channels = settings['log_channels']
            
            # البحث عن رسالة السجلات الأصلية وتحديثها
            from ui.views import AdvancedLogsView
            original_view = AdvancedLogsView(self.language, log_channels, self.guild)
            
            # محاولة تحديث الرسالة الأصلية
            await interaction.message.edit(view=original_view)
        except:
            pass  # تجاهل الخطأ إذا لم نستطع تحديث الرسالة الأصلية
        
        await interaction.response.send_message(embed=result_embed, ephemeral=True)

# =============== واجهات مساعدة إضافية ===============

class HelpView(View):
    def __init__(self, language: str, is_admin: bool = False):
        super().__init__(timeout=60)
        self.language = language
        self.is_admin = is_admin
        from cogs.general import HelpSelect
        self.add_item(HelpSelect(language, is_admin))

class LanguageView(View):
    def __init__(self, admin_id: int):
        super().__init__(timeout=60)
        self.admin_id = admin_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """التحقق من أن المستخدم هو المسؤول فقط"""
        return interaction.user.id == self.admin_id
    
    @discord.ui.button(label="English 🇺🇸", style=discord.ButtonStyle.primary)
    async def english_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message(strings['en']['only_command_user'], ephemeral=True)
            return
            
        await db.update_language(interaction.guild_id, "en")
        await interaction.response.send_message(strings['en']['language_set'], ephemeral=True)
    
    @discord.ui.button(label="Arabic 🇸🇦", style=discord.ButtonStyle.primary)
    async def arabic_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message(strings['ar']['only_command_user'], ephemeral=True)
            return
            
        await db.update_language(interaction.guild_id, "ar")
        await interaction.response.send_message(strings['ar']['language_set_ar'], ephemeral=True)

class EnhancedServerView(View):
    def __init__(self, language: str):
        super().__init__(timeout=60)
        self.language = language
        
        self.add_item(Button(
            label=strings[language]['invite_bot_button'],
            style=discord.ButtonStyle.link,
            url="https://discord.com/oauth2/authorize?client_id=716015608369643630&permissions=8&scope=bot%20applications.commands",
            emoji="📩"
        ))
        
        self.add_item(Button(
            label=strings[language]['support_server'],
            style=discord.ButtonStyle.link,
            url="https://discord.gg/BRMvw6CXmx",
            emoji="🆘"
        ))

class EnhancedDeveloperView(View):
    def __init__(self, language: str):
        super().__init__(timeout=60)
        self.language = language
        
        self.add_item(Button(
            label=strings[language]['contact_developer'],
            style=discord.ButtonStyle.link,
            url="https://www.instagram.com/963sir/",
            emoji="👨‍💻"
        ))
        
        self.add_item(Button(
            label=strings[language]['website'],
            style=discord.ButtonStyle.link,
            url="https://www.ahmadalhalabi.com/",
            emoji="🌐"
        ))
        
        self.add_item(Button(
            label=strings[language]['support_server'],
            style=discord.ButtonStyle.link,
            url="https://discord.gg/BRMvw6CXmx",
            emoji="🆘"
        ))

class InviteView(View):
    def __init__(self, language: str):
        super().__init__(timeout=60)
        self.language = language
        
        self.add_item(Button(
            label=strings[language]['invite_bot_button'],
            style=discord.ButtonStyle.link,
            url="https://discord.com/oauth2/authorize?client_id=716015608369643630&permissions=8&scope=bot%20applications.commands",
            emoji="📩"
        ))
