import aiosqlite
import json
from copy import deepcopy
from config import (
    DB_NAME,
    DEFAULT_PROTECTION_SETTINGS,
    DEFAULT_LOG_SETTINGS,
    DEFAULT_AUTOMOD_SETTINGS,
)

class Database:
    def __init__(self):
        self.db_name = DB_NAME

    @staticmethod
    def _parse_bool(value, default_value: bool) -> bool:
        """تحويل القيم إلى bool بشكل آمن"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "enabled"}:
                return True
            if normalized in {"0", "false", "no", "off", "disabled"}:
                return False
        return default_value

    @staticmethod
    def _parse_int(value, default_value: int, min_value: int, max_value: int) -> int:
        """تحويل القيم إلى int بشكل آمن ضمن حدود"""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default_value
        return max(min_value, min(parsed, max_value))

    @staticmethod
    def _safe_json_load(raw_value, fallback):
        """قراءة JSON مع fallback آمن"""
        if raw_value is None or raw_value == "":
            return deepcopy(fallback)

        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return deepcopy(fallback)

    def _normalize_log_routing(self, raw_log_channels, raw_advanced_logs):
        """تطبيع إعدادات اللوجات إلى نموذج primary + overrides."""
        parsed_log_channels = []
        seen_channels = set()
        for channel_id in raw_log_channels or []:
            try:
                int_channel_id = int(channel_id)
            except (TypeError, ValueError):
                continue

            if int_channel_id <= 0 or int_channel_id in seen_channels:
                continue

            seen_channels.add(int_channel_id)
            parsed_log_channels.append(int_channel_id)

        primary_channel_id = parsed_log_channels[0] if parsed_log_channels else None
        event_overrides_raw = {}

        if isinstance(raw_advanced_logs, dict) and "event_overrides" in raw_advanced_logs:
            try:
                candidate_primary = int(raw_advanced_logs.get("primary_channel_id"))
            except (TypeError, ValueError):
                candidate_primary = None

            if candidate_primary and candidate_primary > 0:
                primary_channel_id = candidate_primary

            raw_event_overrides = raw_advanced_logs.get("event_overrides", {})
            if isinstance(raw_event_overrides, dict):
                event_overrides_raw = raw_event_overrides
        elif isinstance(raw_advanced_logs, dict):
            legacy_channel_ids = []
            for key in raw_advanced_logs.keys():
                try:
                    int_channel_id = int(key)
                except (TypeError, ValueError):
                    continue
                if int_channel_id > 0:
                    legacy_channel_ids.append(int_channel_id)

            if primary_channel_id is None and legacy_channel_ids:
                primary_channel_id = legacy_channel_ids[0]

            for event_name in DEFAULT_LOG_SETTINGS.keys():
                for channel_id in parsed_log_channels[1:]:
                    channel_settings = raw_advanced_logs.get(str(channel_id))
                    if isinstance(channel_settings, dict) and channel_settings.get(event_name):
                        event_overrides_raw[event_name] = channel_id
                        break

        cleaned_overrides = {}
        for event_name, channel_id in event_overrides_raw.items():
            if event_name not in DEFAULT_LOG_SETTINGS:
                continue

            try:
                int_channel_id = int(channel_id)
            except (TypeError, ValueError):
                continue

            if int_channel_id <= 0 or int_channel_id == primary_channel_id:
                continue

            cleaned_overrides[event_name] = int_channel_id

        normalized_log_channels = [primary_channel_id] if primary_channel_id else []
        normalized_advanced_logs = {
            "version": 2,
            "primary_channel_id": primary_channel_id,
            "event_overrides": cleaned_overrides,
        }
        return normalized_log_channels, normalized_advanced_logs

    def _normalize_automod_settings(self, raw_settings):
        """تطبيع إعدادات AutoMod لتجنب فقدان القيم أو فسادها"""
        normalized = deepcopy(DEFAULT_AUTOMOD_SETTINGS)

        if isinstance(raw_settings, dict):
            normalized.update(raw_settings)

        for key in ("enabled", "anti_spam", "anti_mention", "anti_links", "bad_words"):
            normalized[key] = self._parse_bool(
                normalized.get(key),
                DEFAULT_AUTOMOD_SETTINGS.get(key, False)
            )

        normalized["delete_violating_message"] = self._parse_bool(
            normalized.get("delete_violating_message"),
            DEFAULT_AUTOMOD_SETTINGS.get("delete_violating_message", True)
        )
        normalized["allow_discord_invites"] = self._parse_bool(
            normalized.get("allow_discord_invites"),
            DEFAULT_AUTOMOD_SETTINGS.get("allow_discord_invites", False)
        )

        normalized["spam_max_messages"] = self._parse_int(
            normalized.get("spam_max_messages"),
            DEFAULT_AUTOMOD_SETTINGS.get("spam_max_messages", 5),
            2,
            25
        )
        normalized["spam_window_seconds"] = self._parse_int(
            normalized.get("spam_window_seconds"),
            DEFAULT_AUTOMOD_SETTINGS.get("spam_window_seconds", 10),
            3,
            120
        )
        normalized["max_mentions"] = self._parse_int(
            normalized.get("max_mentions"),
            DEFAULT_AUTOMOD_SETTINGS.get("max_mentions", 5),
            1,
            25
        )
        normalized["max_links_per_message"] = self._parse_int(
            normalized.get("max_links_per_message"),
            DEFAULT_AUTOMOD_SETTINGS.get("max_links_per_message", 0),
            0,
            20
        )
        normalized["violation_threshold"] = self._parse_int(
            normalized.get("violation_threshold"),
            DEFAULT_AUTOMOD_SETTINGS.get("violation_threshold", 3),
            1,
            20
        )
        normalized["violation_window_seconds"] = self._parse_int(
            normalized.get("violation_window_seconds"),
            DEFAULT_AUTOMOD_SETTINGS.get("violation_window_seconds", 600),
            30,
            86400
        )
        normalized["repeat_timeout_minutes"] = self._parse_int(
            normalized.get("repeat_timeout_minutes"),
            DEFAULT_AUTOMOD_SETTINGS.get("repeat_timeout_minutes", 10),
            1,
            10080
        )

        repeat_action = str(normalized.get("repeat_action", "timeout")).lower().strip()
        if repeat_action not in {"warn", "timeout", "kick", "ban"}:
            repeat_action = DEFAULT_AUTOMOD_SETTINGS.get("repeat_action", "timeout")
        normalized["repeat_action"] = repeat_action

        bad_words = normalized.get("bad_words_list", [])
        if isinstance(bad_words, str):
            bad_words = [word.strip() for word in bad_words.split(",")]
        elif not isinstance(bad_words, list):
            bad_words = []

        cleaned_bad_words = []
        seen = set()
        for word in bad_words:
            if not isinstance(word, str):
                continue
            cleaned_word = word.strip()
            if not cleaned_word:
                continue

            unique_key = cleaned_word.casefold()
            if unique_key in seen:
                continue

            seen.add(unique_key)
            cleaned_bad_words.append(cleaned_word)

        normalized["bad_words_list"] = cleaned_bad_words
        return normalized

    def _normalize_protection_settings(self, raw_settings):
        """تطبيع إعدادات الحماية"""
        normalized = deepcopy(DEFAULT_PROTECTION_SETTINGS)

        if isinstance(raw_settings, dict):
            normalized.update(raw_settings)

        normalized["antibots"] = self._parse_bool(
            normalized.get("antibots"),
            DEFAULT_PROTECTION_SETTINGS.get("antibots", False)
        )
        normalized["antibots_allow_verified"] = self._parse_bool(
            normalized.get("antibots_allow_verified"),
            DEFAULT_PROTECTION_SETTINGS.get("antibots_allow_verified", True)
        )

        antibots_action = str(normalized.get("antibots_action", "kick")).lower().strip()
        if antibots_action not in {"kick", "ban"}:
            antibots_action = DEFAULT_PROTECTION_SETTINGS.get("antibots_action", "kick")
        normalized["antibots_action"] = antibots_action

        raw_whitelist = normalized.get("antibots_whitelist", [])
        if not isinstance(raw_whitelist, list):
            raw_whitelist = []

        cleaned_whitelist = []
        seen = set()
        for bot_id in raw_whitelist:
            try:
                int_id = int(bot_id)
            except (TypeError, ValueError):
                continue

            if int_id <= 0 or int_id in seen:
                continue

            seen.add(int_id)
            cleaned_whitelist.append(int_id)

        normalized["antibots_whitelist"] = cleaned_whitelist

        normalized["limitsban"] = self._parse_int(
            normalized.get("limitsban"),
            DEFAULT_PROTECTION_SETTINGS.get("limitsban", 5),
            1,
            20
        )
        normalized["limitskick"] = self._parse_int(
            normalized.get("limitskick"),
            DEFAULT_PROTECTION_SETTINGS.get("limitskick", 5),
            1,
            20
        )
        normalized["limitsroleC"] = self._parse_int(
            normalized.get("limitsroleC"),
            DEFAULT_PROTECTION_SETTINGS.get("limitsroleC", 3),
            1,
            20
        )
        normalized["limitsroleD"] = self._parse_int(
            normalized.get("limitsroleD"),
            DEFAULT_PROTECTION_SETTINGS.get("limitsroleD", 3),
            1,
            20
        )
        normalized["limitschannelD"] = self._parse_int(
            normalized.get("limitschannelD"),
            DEFAULT_PROTECTION_SETTINGS.get("limitschannelD", 3),
            1,
            20
        )

        return normalized
    
    async def init_db(self):
        """تهيئة قاعدة البيانات"""
        print("🔄 Initializing database...")
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'en',
                    log_channels TEXT,
                    protection_settings TEXT,
                    advanced_logs TEXT,
                    automod_settings TEXT
                )
            ''')
            await self._upgrade_database(db)
            await db.commit()
            print("✅ Database initialized successfully")
    
    async def _upgrade_database(self, db):
        """ترقية قاعدة البيانات"""
        try:
            async with db.execute("PRAGMA table_info(guild_settings)") as cursor:
                columns = [column[1] for column in await cursor.fetchall()]
            
            upgrades = []
            
            if 'log_channels' not in columns:
                upgrades.append('log_channels')
            if 'protection_settings' not in columns:
                upgrades.append('protection_settings')
            if 'advanced_logs' not in columns:
                upgrades.append('advanced_logs')
            if 'automod_settings' not in columns:
                upgrades.append('automod_settings')
            
            if upgrades:
                print("🔄 Upgrading database to new version...")
                await db.execute('''
                    CREATE TABLE guild_settings_temp (
                        guild_id INTEGER PRIMARY KEY,
                        language TEXT DEFAULT 'en',
                        log_channels TEXT,
                        protection_settings TEXT,
                        advanced_logs TEXT,
                        automod_settings TEXT
                    )
                ''')
                
                existing_columns = [col for col in ['guild_id', 'language'] if col in columns]
                select_columns = existing_columns.copy()
                
                if 'log_channels' in columns:
                    select_columns.append('log_channels')
                else:
                    select_columns.append('NULL as log_channels')
                
                if 'protection_settings' in columns:
                    select_columns.append('protection_settings')
                else:
                    select_columns.append('NULL as protection_settings')
                
                if 'advanced_logs' in columns:
                    select_columns.append('advanced_logs')
                else:
                    select_columns.append('NULL as advanced_logs')
                
                if 'automod_settings' in columns:
                    select_columns.append('automod_settings')
                else:
                    select_columns.append('NULL as automod_settings')
                
                await db.execute(f'''
                    INSERT INTO guild_settings_temp (guild_id, language, log_channels, protection_settings, advanced_logs, automod_settings)
                    SELECT {', '.join(select_columns)} FROM guild_settings
                ''')
                
                await db.execute('DROP TABLE guild_settings')
                await db.execute('ALTER TABLE guild_settings_temp RENAME TO guild_settings')
                
                if 'log_channels' in upgrades:
                    await db.execute('UPDATE guild_settings SET log_channels = ? WHERE log_channels IS NULL', (json.dumps([]),))
                if 'protection_settings' in upgrades:
                    default_protection = json.dumps(DEFAULT_PROTECTION_SETTINGS)
                    await db.execute('UPDATE guild_settings SET protection_settings = ? WHERE protection_settings IS NULL', (default_protection,))
                if 'advanced_logs' in upgrades:
                    await db.execute('UPDATE guild_settings SET advanced_logs = ? WHERE advanced_logs IS NULL', (json.dumps({}),))
                if 'automod_settings' in upgrades:
                    default_automod = json.dumps(DEFAULT_AUTOMOD_SETTINGS)
                    await db.execute('UPDATE guild_settings SET automod_settings = ? WHERE automod_settings IS NULL', (default_automod,))
                
                print("✅ Database upgrade completed!")
                
        except Exception as e:
            print(f"❌ Database upgrade error: {e}")
            await db.execute('DROP TABLE IF EXISTS guild_settings')
            await db.execute('''
                CREATE TABLE guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'en',
                    log_channels TEXT,
                    protection_settings TEXT,
                    advanced_logs TEXT,
                    automod_settings TEXT
                )
            ''')
    
    async def get_guild_settings(self, guild_id: int):
        """الحصول على إعدادات السيرفر"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                'SELECT language, log_channels, protection_settings, advanced_logs, automod_settings FROM guild_settings WHERE guild_id = ?',
                (guild_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    language, log_channels, protection_settings, advanced_logs, automod_settings = result

                    raw_log_channels = self._safe_json_load(log_channels, [])
                    if not isinstance(raw_log_channels, list):
                        raw_log_channels = []

                    parsed_protection = self._safe_json_load(protection_settings, DEFAULT_PROTECTION_SETTINGS)
                    if not isinstance(parsed_protection, dict):
                        parsed_protection = deepcopy(DEFAULT_PROTECTION_SETTINGS)
                    normalized_protection = self._normalize_protection_settings(parsed_protection)

                    parsed_advanced_logs = self._safe_json_load(advanced_logs, {})
                    if not isinstance(parsed_advanced_logs, dict):
                        parsed_advanced_logs = {}
                    normalized_log_channels, normalized_advanced_logs = self._normalize_log_routing(
                        raw_log_channels,
                        parsed_advanced_logs,
                    )

                    parsed_automod = self._safe_json_load(automod_settings, DEFAULT_AUTOMOD_SETTINGS)
                    normalized_automod = self._normalize_automod_settings(parsed_automod)
                    normalized_language = language if language in {"en", "ar"} else "en"

                    return {
                        'language': normalized_language,
                        'log_channels': normalized_log_channels,
                        'protection_settings': normalized_protection,
                        'advanced_logs': normalized_advanced_logs,
                        'automod_settings': normalized_automod
                    }
                else:
                    default_protection = self._normalize_protection_settings(DEFAULT_PROTECTION_SETTINGS)
                    default_automod = self._normalize_automod_settings(DEFAULT_AUTOMOD_SETTINGS)
                    await self.set_guild_settings(
                        guild_id,
                        'en',
                        [],
                        default_protection,
                        {"version": 2, "primary_channel_id": None, "event_overrides": {}},
                        default_automod,
                    )
                    return {
                        'language': 'en',
                        'log_channels': [],
                        'protection_settings': default_protection,
                        'advanced_logs': {"version": 2, "primary_channel_id": None, "event_overrides": {}},
                        'automod_settings': default_automod
                    }
    
    async def set_guild_settings(self, guild_id: int, language: str, log_channels: list, protection_settings: dict, advanced_logs: dict = None, automod_settings: dict = None):
        """حفظ إعدادات السيرفر"""
        if language not in {"en", "ar"}:
            language = "en"

        if not isinstance(log_channels, list):
            log_channels = []
        cleaned_log_channels = []
        seen_log_channels = set()
        for channel_id in log_channels:
            try:
                int_channel_id = int(channel_id)
            except (TypeError, ValueError):
                continue
            if int_channel_id <= 0 or int_channel_id in seen_log_channels:
                continue
            seen_log_channels.add(int_channel_id)
            cleaned_log_channels.append(int_channel_id)
        log_channels = cleaned_log_channels

        if not isinstance(protection_settings, dict):
            protection_settings = deepcopy(DEFAULT_PROTECTION_SETTINGS)
        normalized_protection = self._normalize_protection_settings(protection_settings)
             
        async with aiosqlite.connect(self.db_name) as db:
            if advanced_logs is None:
                async with db.execute(
                    'SELECT advanced_logs FROM guild_settings WHERE guild_id = ?',
                    (guild_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        advanced_logs = self._safe_json_load(row[0], {})
                    else:
                        advanced_logs = {}
            elif not isinstance(advanced_logs, dict):
                advanced_logs = {}

            if automod_settings is None:
                async with db.execute(
                    'SELECT automod_settings FROM guild_settings WHERE guild_id = ?',
                    (guild_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        automod_settings = self._safe_json_load(row[0], DEFAULT_AUTOMOD_SETTINGS)
                    else:
                        automod_settings = deepcopy(DEFAULT_AUTOMOD_SETTINGS)

            normalized_log_channels, normalized_advanced_logs = self._normalize_log_routing(
                log_channels,
                advanced_logs,
            )
            normalized_automod = self._normalize_automod_settings(automod_settings)

            await db.execute('''
                INSERT OR REPLACE INTO guild_settings 
                (guild_id, language, log_channels, protection_settings, advanced_logs, automod_settings) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                guild_id,
                language,
                json.dumps(normalized_log_channels),
                json.dumps(normalized_protection),
                json.dumps(normalized_advanced_logs),
                json.dumps(normalized_automod)
            ))
            await db.commit()
    
    async def update_protection_settings(self, guild_id: int, protection_settings: dict):
        """تحديث إعدادات الحماية"""
        settings = await self.get_guild_settings(guild_id)
        await self.set_guild_settings(guild_id, settings['language'], settings['log_channels'], protection_settings, settings['advanced_logs'], settings['automod_settings'])

    async def update_automod_settings(self, guild_id: int, automod_settings: dict):
        """تحديث إعدادات AutoMod"""
        settings = await self.get_guild_settings(guild_id)
        await self.set_guild_settings(guild_id, settings['language'], settings['log_channels'], settings['protection_settings'], settings['advanced_logs'], automod_settings)

    async def update_language(self, guild_id: int, language: str):
        """تحديث اللغة"""
        settings = await self.get_guild_settings(guild_id)
        await self.set_guild_settings(guild_id, language, settings['log_channels'], settings['protection_settings'], settings['advanced_logs'], settings['automod_settings'])
    
    async def update_advanced_logs(self, guild_id: int, advanced_logs: dict):
        """تحديث إعدادات السجلات المتقدمة"""
        settings = await self.get_guild_settings(guild_id)
        await self.set_guild_settings(guild_id, settings['language'], settings['log_channels'], settings['protection_settings'], advanced_logs, settings['automod_settings'])

    async def update_primary_log_channel(self, guild_id: int, channel_id: int | None):
        """تحديث القناة الرئيسية للسجلات."""
        settings = await self.get_guild_settings(guild_id)
        advanced_logs = deepcopy(settings['advanced_logs'])
        advanced_logs["primary_channel_id"] = int(channel_id) if channel_id else None
        await self.set_guild_settings(
            guild_id,
            settings['language'],
            [int(channel_id)] if channel_id else [],
            settings['protection_settings'],
            advanced_logs,
            settings['automod_settings'],
        )

    async def get_event_log_overrides(self, guild_id: int) -> dict:
        settings = await self.get_guild_settings(guild_id)
        advanced_logs = settings['advanced_logs']
        overrides = advanced_logs.get("event_overrides", {})
        return overrides.copy() if isinstance(overrides, dict) else {}

    async def update_event_log_override(self, guild_id: int, event_name: str, channel_id: int):
        settings = await self.get_guild_settings(guild_id)
        advanced_logs = deepcopy(settings['advanced_logs'])
        overrides = advanced_logs.get("event_overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}
        overrides[event_name] = int(channel_id)
        advanced_logs["event_overrides"] = overrides
        await self.set_guild_settings(
            guild_id,
            settings['language'],
            settings['log_channels'],
            settings['protection_settings'],
            advanced_logs,
            settings['automod_settings'],
        )

    async def remove_event_log_override(self, guild_id: int, event_name: str):
        settings = await self.get_guild_settings(guild_id)
        advanced_logs = deepcopy(settings['advanced_logs'])
        overrides = advanced_logs.get("event_overrides", {})
        if isinstance(overrides, dict):
            overrides.pop(event_name, None)
        advanced_logs["event_overrides"] = overrides if isinstance(overrides, dict) else {}
        await self.set_guild_settings(
            guild_id,
            settings['language'],
            settings['log_channels'],
            settings['protection_settings'],
            advanced_logs,
            settings['automod_settings'],
        )

    async def clear_event_log_overrides(self, guild_id: int):
        settings = await self.get_guild_settings(guild_id)
        advanced_logs = deepcopy(settings['advanced_logs'])
        advanced_logs["event_overrides"] = {}
        await self.set_guild_settings(
            guild_id,
            settings['language'],
            settings['log_channels'],
            settings['protection_settings'],
            advanced_logs,
            settings['automod_settings'],
        )
    
    async def get_channel_log_settings(self, guild_id: int, channel_id: int):
        """الحصول على إعدادات السجلات لقناة محددة"""
        return deepcopy(DEFAULT_LOG_SETTINGS)
    
    async def update_channel_log_settings(self, guild_id: int, channel_id: int, log_settings: dict):
        """تحديث إعدادات السجلات لقناة محددة"""
        return None
    
    async def add_log_channel(self, guild_id: int, channel_id: int):
        """إضافة قناة سجلات جديدة"""
        settings = await self.get_guild_settings(guild_id)
        current_primary = settings['log_channels'][0] if settings['log_channels'] else None
        if current_primary == channel_id:
            return False
        await self.update_primary_log_channel(guild_id, channel_id)
        return True

    async def remove_log_channel(self, guild_id: int, channel_id: int):
        """إزالة قناة سجلات"""
        settings = await self.get_guild_settings(guild_id)
        log_channels = settings['log_channels']
        if channel_id in log_channels:
            await self.update_primary_log_channel(guild_id, None)
            return True
        return False
