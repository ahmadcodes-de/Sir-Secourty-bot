import os
from dotenv import load_dotenv

load_dotenv()

# ============ الثوابت الأساسية ============
TOKEN = os.getenv("DISCORD_TOKEN")
DB_NAME = "bot_settings.db"

# ============ Music Bot Settings ============
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
DL_WORKERS = int(os.getenv("DL_WORKERS", "8"))
YT_REGION = 'US'  # <-- تمت الإضافة هنا

# Default Presence
DEFAULT_STATUS_STATE = (os.getenv("DEFAULT_STATUS_STATE") or "idle").lower()
DEFAULT_ACTIVITY_TYPE = (os.getenv("DEFAULT_ACTIVITY_TYPE") or "custom").lower()
DEFAULT_ACTIVITY_TEXT = os.getenv("DEFAULT_ACTIVITY_TEXT") or "Powered by SIR | /help"

# File paths
LANG_FILE = "data/guild_lang.json"
PRES_FILE = "data/presence.json"
VOICE_FILE = "data/voice_state.json"

# ============ Bot Owners ============
OWNER_IDS = [674783105541734439, 530786064995188737]

# ============ Developer Command Scope ============
DEVELOPER_PRESENCE_GUILD_ID = 902919852099010610

# ============ Allowed Guilds ============
ALLOWED_GUILDS = [674807325911154710, 902919852099010610]

# ============ Bot Settings ============
BOT_SETTINGS = {
    'private': True,
    'welcome_message': True,
    'music_enabled': True,  # تمكين ميزة الموسيقى
}

# ============ Default Protection Settings ============
DEFAULT_PROTECTION_SETTINGS = {
    "antibots": False,
    "antibots_action": "kick",  # kick | ban
    "antibots_allow_verified": True,
    "antibots_whitelist": [],   # list[int]
    "limitsban": 5,
    "limitskick": 5,
    "limitsroleC": 3,
    "limitsroleD": 3,
    "limitschannelD": 3
}

# ============ Log Events ============
LOG_EVENT_CATEGORIES = {
    "moderation": [
        "automod_action",
        "member_ban",
        "ban_remove",
        "member_kick",
        "mute_add",
        "mute_remove",
        "user_timed_out",
        "user_timeout_removed",
    ],
    "members": [
        "member_join",
        "member_remove",
        "user_name_update",
        "nickname_change",
        "user_avatar_update",
        "user_roles_update",
        "user_roles_add",
        "user_roles_remove",
    ],
    "messages": [
        "message_delete",
        "message_bulk_delete",
        "message_edit",
        "message_sent_command",
        "channel_pins_update",
    ],
    "voice": [
        "voice_join",
        "voice_leave",
        "voice_move",
        "voice_user_move",
        "voice_user_kick",
        "voice_channel_full",
    ],
    "channels": [
        "channel_create",
        "channel_delete",
        "channel_name_update",
        "channel_topic_update",
        "channel_nsfw_update",
        "channel_parent_update",
        "channel_permissions_update",
        "channel_type_update",
        "channel_bitrate_update",
        "channel_user_limit_update",
        "channel_slow_mode_update",
        "channel_rtc_region_update",
        "channel_video_quality_update",
        "channel_default_archive_duration_update",
        "channel_default_thread_slow_mode_update",
        "channel_default_reaction_emoji_update",
        "channel_default_sort_order_update",
        "channel_forum_tags_update",
        "channel_forum_layout_update",
        "channel_voice_status_update",
    ],
    "threads": [
        "thread_create",
        "thread_delete",
        "thread_name_update",
        "thread_slow_mode_update",
        "thread_archive_duration_update",
        "thread_archive",
        "thread_unarchive",
        "thread_lock",
        "thread_unlock",
    ],
    "server": [
        "afk_channel_update",
        "afk_timeout_update",
        "server_banner_update",
        "message_notifications_update",
        "server_discovery_splash_update",
        "server_content_filter_level_update",
        "server_features_update",
        "server_icon_update",
        "mfa_level_update",
        "server_name_update",
        "server_description_update",
        "server_owner_update",
        "partnered_update",
        "server_boost_level_update",
        "boost_progress_bar_toggle",
        "public_updates_channel_update",
        "server_rules_channel_update",
        "server_splash_update",
        "system_channel_update",
        "server_vanity_update",
        "verification_level_update",
        "verified_update",
        "server_widget_update",
        "server_preferred_locale_update",
    ],
    "onboarding": [
        "onboarding_toggle",
        "onboarding_channels_update",
        "onboarding_question_add",
        "onboarding_question_remove",
        "onboarding_question_update",
    ],
    "roles": [
        "role_create",
        "role_delete",
        "role_color_update",
        "role_hoist_update",
        "role_mentionable_update",
        "role_name_update",
        "role_permissions_update",
        "role_icon_update",
    ],
    "invites": [
        "invite_create",
        "invite_delete",
    ],
}

LOG_EVENT_LABELS = {
    "automod_action": "Auto Moderation",
    "member_ban": "Ban Add",
    "ban_remove": "Ban Remove",
    "member_kick": "Kick Add",
    "mute_add": "Mute Add",
    "mute_remove": "Mute Remove",
    "user_timed_out": "User Timed Out",
    "user_timeout_removed": "User Timeout Removed",
    "member_join": "User Join",
    "member_remove": "User Leave",
    "user_name_update": "User Name Update",
    "nickname_change": "User Nickname Update",
    "user_avatar_update": "User Avatar Update",
    "user_roles_update": "User Roles Update",
    "user_roles_add": "User Roles Add",
    "user_roles_remove": "User Roles Remove",
    "message_delete": "Message Delete",
    "message_bulk_delete": "Message Bulk Delete",
    "message_edit": "Message Edit",
    "message_sent_command": "Message Sent Using Command",
    "channel_pins_update": "Channel Pins Update",
    "voice_join": "Voice User Join",
    "voice_leave": "Voice User Leave",
    "voice_move": "Voice User Switch",
    "voice_user_move": "Voice User Move",
    "voice_user_kick": "Voice User Kick",
    "voice_channel_full": "Voice Channel Full",
    "channel_create": "Channel Create",
    "channel_delete": "Channel Delete",
    "channel_name_update": "Channel Name Update",
    "channel_topic_update": "Channel Topic Update",
    "channel_nsfw_update": "Channel NSFW Update",
    "channel_parent_update": "Channel Parent Update",
    "channel_permissions_update": "Channel Permissions Update",
    "channel_type_update": "Channel Type Update",
    "channel_bitrate_update": "Channel Bitrate Update",
    "channel_user_limit_update": "Channel User Limit Update",
    "channel_slow_mode_update": "Channel Slow Mode Update",
    "channel_rtc_region_update": "Channel RTC Region Update",
    "channel_video_quality_update": "Channel Video Quality Update",
    "channel_default_archive_duration_update": "Channel Default Archive Duration Update",
    "channel_default_thread_slow_mode_update": "Channel Default Thread Slow Mode Update",
    "channel_default_reaction_emoji_update": "Channel Default Reaction Emoji Update",
    "channel_default_sort_order_update": "Channel Default Sort Order Update",
    "channel_forum_tags_update": "Channel Forum Tags Update",
    "channel_forum_layout_update": "Channel Forum Layout Update",
    "channel_voice_status_update": "Channel Voice Status Update",
    "thread_create": "Thread Create",
    "thread_delete": "Thread Delete",
    "thread_name_update": "Thread Name Update",
    "thread_slow_mode_update": "Thread Slow Mode Update",
    "thread_archive_duration_update": "Thread Archive Duration Update",
    "thread_archive": "Thread Archive",
    "thread_unarchive": "Thread Unarchive",
    "thread_lock": "Thread Lock",
    "thread_unlock": "Thread Unlock",
    "afk_channel_update": "AFK Channel Update",
    "afk_timeout_update": "AFK Timeout Update",
    "server_banner_update": "Server Banner Update",
    "message_notifications_update": "Message Notifications Update",
    "server_discovery_splash_update": "Server Discovery Splash Update",
    "server_content_filter_level_update": "Server Content Filter Level Update",
    "server_features_update": "Server Features Update",
    "server_icon_update": "Server Icon Update",
    "mfa_level_update": "MFA Level Update",
    "server_name_update": "Server Name Update",
    "server_description_update": "Server Description Update",
    "server_owner_update": "Server Owner Update",
    "partnered_update": "Partnered Update",
    "server_boost_level_update": "Server Boost Level Update",
    "boost_progress_bar_toggle": "Boost Progress Bar Toggle",
    "public_updates_channel_update": "Public Updates Channel Update",
    "server_rules_channel_update": "Server Rules Channel Update",
    "server_splash_update": "Server Splash Update",
    "system_channel_update": "System Channel Update",
    "server_vanity_update": "Server Vanity Update",
    "verification_level_update": "Verification Level Update",
    "verified_update": "Verified Update",
    "server_widget_update": "Server Widget Update",
    "server_preferred_locale_update": "Server Preferred Locale Update",
    "onboarding_toggle": "Onboarding Toggle",
    "onboarding_channels_update": "Onboarding Channels Update",
    "onboarding_question_add": "Onboarding Question Add",
    "onboarding_question_remove": "Onboarding Question Remove",
    "onboarding_question_update": "Onboarding Question Update",
    "role_create": "Role Create",
    "role_delete": "Role Delete",
    "role_color_update": "Role Color Update",
    "role_hoist_update": "Role Hoist Update",
    "role_mentionable_update": "Role Mentionable Update",
    "role_name_update": "Role Name Update",
    "role_permissions_update": "Role Permissions Update",
    "role_icon_update": "Role Icon Update",
    "invite_create": "Invite Create",
    "invite_delete": "Invite Delete",
    "music_events": "Music Events",
}

DEFAULT_LOG_SETTINGS = {event: True for events in LOG_EVENT_CATEGORIES.values() for event in events}
DEFAULT_LOG_SETTINGS["music_events"] = False

# ============ Default AutoMod Settings ============
DEFAULT_AUTOMOD_SETTINGS = {
    'enabled': False,
    'sync_discord_automod': True,
    'anti_spam': True,
    'anti_mention': True,
    'anti_links': False,
    'bad_words': False,
    'bad_words_list': [],
    'spam_max_messages': 5,
    'spam_window_seconds': 10,
    'max_mentions': 5,
    'max_links_per_message': 0,
    'allow_discord_invites': False,
    'violation_threshold': 3,
    'violation_window_seconds': 600,
    'repeat_action': 'timeout',     # warn | timeout | kick | ban
    'repeat_timeout_minutes': 10,
    'delete_violating_message': True,
}

# ============ Auto Refresh Settings ============
AUTO_REFRESH_SETTINGS = {
    'member_refresh_interval': 30,  # دقائق
    'presence_update_interval': 5,  # دقائق
    'enable_auto_refresh': True,
    'music_cleanup_interval': 60,  # دقائق (تنظيف الذاكرة)
}

# ============ Bad Words List ============
BAD_WORDS = ["spam", "badword1", "badword2"]

# ============ Event Colors ============
EVENT_COLORS = {
    'member_join': 0x00ff00,
    'member_remove': 0xff0000,
    'member_ban': 0x8b0000,
    'ban_remove': 0x57F287,
    'member_kick': 0xffa500,
    'mute_add': 0xE67E22,
    'mute_remove': 0x2ECC71,
    'user_timed_out': 0xF39C12,
    'user_timeout_removed': 0x2ECC71,
    'message_delete': 0xd3d3d3,
    'message_bulk_delete': 0x95A5A6,
    'channel_create': 0x00ff00,
    'channel_delete': 0xff0000,
    'role_create': 0x0000ff,
    'role_delete': 0xff0000,
    'message_edit': 0xffd700,
    'message_sent_command': 0x5865F2,
    'channel_pins_update': 0x3498DB,
    'voice_join': 0x00ff00,
    'voice_leave': 0xff0000,
    'voice_move': 0x3498DB,
    'voice_user_move': 0x5865F2,
    'voice_user_kick': 0xE74C3C,
    'voice_channel_full': 0xE67E22,
    'channel_update': 0x1ABC9C,
    'channel_name_update': 0x1ABC9C,
    'channel_topic_update': 0x1ABC9C,
    'channel_nsfw_update': 0x8E44AD,
    'channel_parent_update': 0x16A085,
    'channel_permissions_update': 0xE67E22,
    'channel_type_update': 0x3498DB,
    'channel_bitrate_update': 0x3498DB,
    'channel_user_limit_update': 0x3498DB,
    'channel_slow_mode_update': 0xF1C40F,
    'channel_rtc_region_update': 0x3498DB,
    'channel_video_quality_update': 0x3498DB,
    'channel_default_archive_duration_update': 0x1ABC9C,
    'channel_default_thread_slow_mode_update': 0x1ABC9C,
    'channel_default_reaction_emoji_update': 0x1ABC9C,
    'channel_default_sort_order_update': 0x1ABC9C,
    'channel_forum_tags_update': 0x1ABC9C,
    'channel_forum_layout_update': 0x1ABC9C,
    'channel_voice_status_update': 0x3498DB,
    'thread_create': 0x2ECC71,
    'thread_delete': 0xE74C3C,
    'thread_name_update': 0x1ABC9C,
    'thread_slow_mode_update': 0xF1C40F,
    'thread_archive_duration_update': 0x1ABC9C,
    'thread_archive': 0x95A5A6,
    'thread_unarchive': 0x2ECC71,
    'thread_lock': 0xE67E22,
    'thread_unlock': 0x2ECC71,
    'nickname_change': 0x800080,
    'user_name_update': 0x9B59B6,
    'user_avatar_update': 0x9B59B6,
    'user_roles_update': 0x2980B9,
    'user_roles_add': 0x2ECC71,
    'user_roles_remove': 0xE74C3C,
    'role_update': 0x0000ff,
    'role_color_update': 0x2980B9,
    'role_hoist_update': 0x2980B9,
    'role_mentionable_update': 0x2980B9,
    'role_name_update': 0x2980B9,
    'role_permissions_update': 0xE67E22,
    'role_icon_update': 0x2980B9,
    'automod_action': 0xffa500,
    'invite_create': 0x2ECC71,
    'invite_delete': 0xE74C3C,
    'afk_channel_update': 0x3498DB,
    'afk_timeout_update': 0x3498DB,
    'server_banner_update': 0x1ABC9C,
    'message_notifications_update': 0x3498DB,
    'server_discovery_splash_update': 0x1ABC9C,
    'server_content_filter_level_update': 0xE67E22,
    'server_features_update': 0x1ABC9C,
    'server_icon_update': 0x1ABC9C,
    'mfa_level_update': 0xE67E22,
    'server_name_update': 0x3498DB,
    'server_description_update': 0x3498DB,
    'server_owner_update': 0xE74C3C,
    'partnered_update': 0x9B59B6,
    'server_boost_level_update': 0xFF73FA,
    'boost_progress_bar_toggle': 0xFF73FA,
    'public_updates_channel_update': 0x3498DB,
    'server_rules_channel_update': 0x3498DB,
    'server_splash_update': 0x1ABC9C,
    'system_channel_update': 0x3498DB,
    'server_vanity_update': 0x9B59B6,
    'verification_level_update': 0xE67E22,
    'verified_update': 0x2ECC71,
    'server_widget_update': 0x3498DB,
    'server_preferred_locale_update': 0x3498DB,
    'onboarding_toggle': 0x1ABC9C,
    'onboarding_channels_update': 0x1ABC9C,
    'onboarding_question_add': 0x2ECC71,
    'onboarding_question_remove': 0xE74C3C,
    'onboarding_question_update': 0xF1C40F,
    
    # Music Colors
    'music_join': 0x57F287,
    'music_leave': 0xED4245,
    'music_play': 0x5865F2,
    'music_pause': 0xFEE75C,
    'music_queue': 0x9B59B6,
}

# ============ Music Defaults ============
MUSIC_DEFAULTS = {
    'volume': 0.8,
    'loop_mode': 'off',
    'max_queue_size': 100,
    'max_playlist_tracks': 25,
    'timeout_seconds': 30,
}

# ============ FFmpeg Options ============
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn',
}

# ============ YouTube DL Options ============
YDL_OPTS = {
    'format': 'bestaudio/best',
    'default_search': 'auto',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'source_address': '0.0.0.0',
    'socket_timeout': 10,
    'retries': 2,
    'cachedir': False,
}
