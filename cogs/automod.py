import asyncio
import datetime
import os
import re
from collections import defaultdict, deque
from typing import Optional
from urllib.parse import quote

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config import DEFAULT_AUTOMOD_SETTINGS, OWNER_IDS
from database import db
from utils.helpers import create_embed, send_log
from utils.strings import strings

URL_REGEX = re.compile(
    r"(?:https?://|www\.|discord\.gg/|discord\.com/invite/)[^\s<>()]+",
    re.IGNORECASE,
)
INVITE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/[A-Za-z0-9-]+",
    re.IGNORECASE,
)

DISCORD_API_BASE = "https://discord.com/api/v10"
MANAGED_RULE_PREFIX = "Sir Bot AutoMod:"
OFFICIAL_SYNC_REASON = "Sir Bot AutoMod official rule sync"
OFFICIAL_KEYWORD_RULE_LIMIT = 6
OFFICIAL_KEYWORDS_PER_RULE = 100


class OfficialAutoModError(Exception):
    def __init__(self, status: int, payload):
        self.status = status
        self.payload = payload
        super().__init__(f"Discord AutoMod API failed with status {status}: {payload}")


def resolve_language(language: Optional[str]) -> str:
    return "ar" if language == "ar" else "en"


def tr(lang: str, en: str, ar: str) -> str:
    return ar if lang == "ar" else en


def message_content_intent_enabled(bot: commands.Bot) -> bool:
    intents = getattr(bot, "intents", None)
    return bool(intents and getattr(intents, "message_content", False))


def _parse_bool(value, default_value: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "off", "disabled"}:
            return False
    return default_value


def _parse_int(value, default_value: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default_value
    return max(min_value, min(parsed, max_value))


def normalize_automod_settings(raw_settings: Optional[dict]) -> dict:
    normalized = dict(DEFAULT_AUTOMOD_SETTINGS)
    if isinstance(raw_settings, dict):
        normalized.update(raw_settings)

    for key in ("enabled", "sync_discord_automod", "anti_spam", "anti_mention", "anti_links", "bad_words"):
        normalized[key] = _parse_bool(normalized.get(key), DEFAULT_AUTOMOD_SETTINGS.get(key, False))

    normalized["allow_discord_invites"] = _parse_bool(
        normalized.get("allow_discord_invites"),
        DEFAULT_AUTOMOD_SETTINGS.get("allow_discord_invites", False),
    )
    normalized["delete_violating_message"] = _parse_bool(
        normalized.get("delete_violating_message"),
        DEFAULT_AUTOMOD_SETTINGS.get("delete_violating_message", True),
    )

    normalized["spam_max_messages"] = _parse_int(
        normalized.get("spam_max_messages"),
        DEFAULT_AUTOMOD_SETTINGS.get("spam_max_messages", 5),
        2,
        25,
    )
    normalized["spam_window_seconds"] = _parse_int(
        normalized.get("spam_window_seconds"),
        DEFAULT_AUTOMOD_SETTINGS.get("spam_window_seconds", 10),
        3,
        120,
    )
    normalized["max_mentions"] = _parse_int(
        normalized.get("max_mentions"),
        DEFAULT_AUTOMOD_SETTINGS.get("max_mentions", 5),
        1,
        25,
    )
    normalized["max_links_per_message"] = _parse_int(
        normalized.get("max_links_per_message"),
        DEFAULT_AUTOMOD_SETTINGS.get("max_links_per_message", 0),
        0,
        20,
    )
    normalized["violation_threshold"] = _parse_int(
        normalized.get("violation_threshold"),
        DEFAULT_AUTOMOD_SETTINGS.get("violation_threshold", 3),
        1,
        20,
    )
    normalized["violation_window_seconds"] = _parse_int(
        normalized.get("violation_window_seconds"),
        DEFAULT_AUTOMOD_SETTINGS.get("violation_window_seconds", 600),
        30,
        86400,
    )
    normalized["repeat_timeout_minutes"] = _parse_int(
        normalized.get("repeat_timeout_minutes"),
        DEFAULT_AUTOMOD_SETTINGS.get("repeat_timeout_minutes", 10),
        1,
        10080,
    )

    repeat_action = str(normalized.get("repeat_action", "timeout")).lower().strip()
    if repeat_action not in {"warn", "timeout", "kick", "ban"}:
        repeat_action = DEFAULT_AUTOMOD_SETTINGS.get("repeat_action", "timeout")
    normalized["repeat_action"] = repeat_action

    words = normalized.get("bad_words_list", [])
    if isinstance(words, str):
        words = [w.strip() for w in words.split(",")]
    elif not isinstance(words, list):
        words = []

    cleaned = []
    seen = set()
    for word in words:
        if not isinstance(word, str):
            continue
        value = word.strip()
        if not value:
            continue
        folded = value.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        cleaned.append(value)
    normalized["bad_words_list"] = cleaned

    return normalized


def parse_words(raw_words: Optional[str]) -> list[str]:
    if not raw_words:
        return []
    parts = [part.strip() for part in re.split(r"[,\n\r]+", raw_words) if part.strip()]
    result = []
    seen = set()
    for part in parts:
        lowered = part.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(part)
    return result


def _official_block_action() -> list[dict]:
    return [
        {
            "type": 1,
            "metadata": {"custom_message": "Blocked by Sir Bot AutoMod."},
        }
    ]


def _clean_official_keywords(words: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for word in words:
        if not isinstance(word, str):
            continue
        value = word.strip()
        if not value:
            continue
        value = value[:60]
        folded = value.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        cleaned.append(value)
    return cleaned


def _keyword_chunks(words: list[str], size: int) -> list[list[str]]:
    return [words[index:index + size] for index in range(0, len(words), size)]


def build_official_automod_payloads(settings: dict) -> list[dict]:
    if not settings.get("enabled", False):
        return []

    payloads = []
    action = _official_block_action()

    if settings.get("anti_spam", True):
        payloads.append(
            {
                "managed_key": "spam",
                "name": f"{MANAGED_RULE_PREFIX} Spam",
                "event_type": 1,
                "trigger_type": 3,
                "actions": action,
                "enabled": True,
            }
        )

    if settings.get("anti_mention", True):
        payloads.append(
            {
                "managed_key": "mentions",
                "name": f"{MANAGED_RULE_PREFIX} Mentions",
                "event_type": 1,
                "trigger_type": 5,
                "trigger_metadata": {
                    "mention_total_limit": settings.get("max_mentions", 5),
                    "mention_raid_protection_enabled": True,
                },
                "actions": action,
                "enabled": True,
            }
        )

    keyword_payloads = []
    if settings.get("anti_links", False):
        link_keywords = ["http://*", "https://*", "www.*"]
        if not settings.get("allow_discord_invites", False):
            link_keywords.extend(["discord.gg/*", "discord.com/invite/*"])
        keyword_payloads.append(("links", "Links", link_keywords))

    if settings.get("bad_words", False):
        bad_words = _clean_official_keywords(settings.get("bad_words_list", []))
        for index, chunk in enumerate(_keyword_chunks(bad_words, OFFICIAL_KEYWORDS_PER_RULE), start=1):
            keyword_payloads.append((f"bad_words_{index}", f"Bad Words {index}", chunk))

        payloads.append(
            {
                "managed_key": "preset_filters",
                "name": f"{MANAGED_RULE_PREFIX} Preset Filters",
                "event_type": 1,
                "trigger_type": 4,
                "trigger_metadata": {"presets": [1, 2, 3]},
                "actions": action,
                "enabled": True,
            }
        )
        if bad_words:
            payloads.append(
                {
                    "managed_key": "member_profile",
                    "name": f"{MANAGED_RULE_PREFIX} Member Profile",
                    "event_type": 2,
                    "trigger_type": 6,
                    "trigger_metadata": {"keyword_filter": bad_words[:OFFICIAL_KEYWORDS_PER_RULE]},
                    "actions": [{"type": 4}],
                    "enabled": True,
                }
            )

    for managed_key, label, keywords in keyword_payloads[:OFFICIAL_KEYWORD_RULE_LIMIT]:
        keywords = _clean_official_keywords(keywords)
        if not keywords:
            continue
        payloads.append(
            {
                "managed_key": managed_key,
                "name": f"{MANAGED_RULE_PREFIX} {label}",
                "event_type": 1,
                "trigger_type": 1,
                "trigger_metadata": {"keyword_filter": keywords},
                "actions": action,
                "enabled": True,
            }
        )

    return payloads


def official_sync_field_value(language: str, result: Optional[dict]) -> str:
    if not result:
        return tr(language, "Not run.", "Not run.")
    if result.get("skipped"):
        return result.get("reason", "skipped")
    parts = [
        f"created={result.get('created', 0)}",
        f"updated={result.get('updated', 0)}",
        f"disabled={result.get('disabled', 0)}",
        f"active={result.get('active', 0)}",
    ]
    if result.get("failed"):
        parts.append(f"failed={result.get('failed')}")
    if result.get("error"):
        parts.append(f"error={result.get('error')}")
    if result.get("failed_rules"):
        failed_rules = ", ".join(result["failed_rules"][:3])
        if len(result["failed_rules"]) > 3:
            failed_rules += f", +{len(result['failed_rules']) - 3}"
        parts.append(f"rules={failed_rules}")
    return " | ".join(parts)


def official_error_summary(exc: Exception) -> str:
    if isinstance(exc, OfficialAutoModError):
        payload = exc.payload
        if isinstance(payload, dict):
            message = payload.get("message")
            code = payload.get("code")
            errors = payload.get("errors")
            details = message or str(payload)
            if errors:
                details = f"{details}: {errors}"
            return f"{exc.status}/{code}: {details}"[:220]
        return f"{exc.status}: {payload}"[:220]
    return type(exc).__name__


def official_rule_type(rule: dict) -> str:
    trigger_names = {
        1: "Keyword",
        3: "Spam",
        4: "Preset",
        5: "Mention Spam",
        6: "Member Profile",
    }
    trigger_type = rule.get("trigger_type")
    return trigger_names.get(trigger_type, f"Trigger {trigger_type}")


def format_official_rule_line(index: int, rule: dict) -> str:
    status = "ON" if rule.get("enabled") else "OFF"
    creator_id = rule.get("creator_id", "unknown")
    return (
        f"`{index:02}` **{rule.get('name', 'Unnamed')}**\n"
        f"ID: `{rule.get('id')}` | Type: `{official_rule_type(rule)}` | Status: `{status}` | Creator: `{creator_id}`"
    )


def status_text(language: str, enabled: bool) -> str:
    return strings[language]["enabled"] if enabled else strings[language]["disabled"]


def build_automod_embed(
    language: str,
    settings: dict,
    *,
    updated: bool = False,
    can_read_message_content: bool = True,
) -> discord.Embed:
    embed = create_embed(
        title=strings[language]["automod_title"],
        description=strings[language]["automod_updated"] if updated else strings[language]["automod_description"],
        color=discord.Color.green() if updated else discord.Color.blue(),
    )
    embed.add_field(
        name=strings[language].get("current_settings", "Current Settings"),
        value=(
            f"**{strings[language]['automod_enabled']}:** `{status_text(language, settings.get('enabled', False))}`\n"
            f"**Discord AutoMod Sync:** `{status_text(language, settings.get('sync_discord_automod', True))}`\n"
            f"**{strings[language]['anti_spam']}:** `{status_text(language, settings.get('anti_spam', True))}`\n"
            f"**{strings[language]['anti_mention']}:** `{status_text(language, settings.get('anti_mention', True))}`\n"
            f"**{strings[language]['anti_links']}:** `{status_text(language, settings.get('anti_links', False))}`\n"
            f"**{strings[language]['bad_words']}:** `{status_text(language, settings.get('bad_words', False))}`"
        ),
        inline=False,
    )
    embed.add_field(
        name=tr(language, "Advanced", "إعدادات متقدمة"),
        value=(
            f"Spam: `{settings.get('spam_max_messages', 5)} / {settings.get('spam_window_seconds', 10)}s`\n"
            f"Mentions: `{settings.get('max_mentions', 5)}`\n"
            f"Links Allowed: `{settings.get('max_links_per_message', 0)}`\n"
            f"Allow Invites: `{status_text(language, settings.get('allow_discord_invites', False))}`\n"
            f"Repeat: `{settings.get('repeat_action', 'timeout')} @ {settings.get('violation_threshold', 3)} / {settings.get('violation_window_seconds', 600)}s`\n"
            f"Delete Message: `{status_text(language, settings.get('delete_violating_message', True))}`"
        ),
        inline=False,
    )
    words = settings.get("bad_words_list", [])
    if words:
        preview = ", ".join(words[:8]) + ("..." if len(words) > 8 else "")
        embed.add_field(name=tr(language, "Bad Words", "الكلمات الممنوعة"), value=preview, inline=False)

    if not can_read_message_content:
        embed.add_field(
            name=tr(language, "Public Bot Limitation", "قيد البوت العام"),
            value=tr(
                language,
                "Message Content intent is disabled, so link and bad-words checks need this intent.",
                "صلاحية قراءة محتوى الرسائل غير مفعلة، لذلك فحص الروابط والكلمات الممنوعة يحتاج تفعيلها.",
            ),
            inline=False,
        )
    return embed


class AutoModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = defaultdict(deque)
        self.violation_tracker = defaultdict(deque)

    def _bot_token(self) -> str:
        token = getattr(getattr(self.bot, "http", None), "token", None) or os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_TOKEN is not available for Discord AutoMod sync")
        return token

    @staticmethod
    def _is_bot_owner(user_id: int) -> bool:
        return int(user_id) in OWNER_IDS

    async def _discord_api(self, method: str, path: str, payload: Optional[dict] = None):
        headers = {
            "Authorization": f"Bot {self._bot_token()}",
            "Content-Type": "application/json",
            "User-Agent": "Sir Bot AutoMod Sync",
            "X-Audit-Log-Reason": quote(OFFICIAL_SYNC_REASON),
        }
        url = f"{DISCORD_API_BASE}{path}"
        for attempt in range(2):
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.request(method, url, json=payload) as response:
                    if response.status == 204:
                        return None
                    try:
                        data = await response.json()
                    except aiohttp.ContentTypeError:
                        data = await response.text()
                    if response.status == 429 and attempt == 0:
                        retry_after = 1.0
                        if isinstance(data, dict):
                            retry_after = float(data.get("retry_after", retry_after))
                        await asyncio.sleep(min(retry_after, 5.0))
                        continue
                    if 200 <= response.status < 300:
                        return data
                    raise OfficialAutoModError(response.status, data)
        return None

    async def sync_official_automod_rules(self, guild: discord.Guild, settings: dict) -> dict:
        settings = normalize_automod_settings(settings)
        result = {"created": 0, "updated": 0, "disabled": 0, "active": 0, "failed": 0, "failed_rules": []}

        if not settings.get("sync_discord_automod", True):
            result.update({"skipped": True, "reason": "Discord AutoMod sync is disabled"})
            return result

        me = guild.me
        if me is None or not me.guild_permissions.manage_guild:
            result.update({"skipped": True, "reason": "Bot needs Manage Server permission"})
            return result

        try:
            existing_rules = await self._discord_api("GET", f"/guilds/{guild.id}/auto-moderation/rules")
        except (OfficialAutoModError, RuntimeError, aiohttp.ClientError) as exc:
            result.update({"skipped": True, "reason": f"list_failed:{type(exc).__name__}"})
            return result

        managed_rules = {
            rule.get("name"): rule
            for rule in existing_rules or []
            if isinstance(rule, dict) and str(rule.get("name", "")).startswith(MANAGED_RULE_PREFIX)
        }
        desired_payloads = build_official_automod_payloads(settings)
        desired_names = {payload["name"] for payload in desired_payloads}

        for payload in desired_payloads:
            api_payload = {key: value for key, value in payload.items() if key != "managed_key"}
            existing = managed_rules.get(payload["name"])
            try:
                if existing:
                    await self._discord_api(
                        "PATCH",
                        f"/guilds/{guild.id}/auto-moderation/rules/{existing['id']}",
                        api_payload,
                    )
                    result["updated"] += 1
                else:
                    await self._discord_api("POST", f"/guilds/{guild.id}/auto-moderation/rules", api_payload)
                    result["created"] += 1
                result["active"] += 1
                await asyncio.sleep(0.35)
            except (OfficialAutoModError, RuntimeError, aiohttp.ClientError) as exc:
                result["failed"] += 1
                result["error"] = official_error_summary(exc)
                result["failed_rules"].append(payload["name"])

        for name, rule in managed_rules.items():
            if name in desired_names or not rule.get("enabled", False):
                continue
            try:
                await self._discord_api(
                    "PATCH",
                    f"/guilds/{guild.id}/auto-moderation/rules/{rule['id']}",
                    {"enabled": False},
                )
                result["disabled"] += 1
                await asyncio.sleep(0.35)
            except (OfficialAutoModError, RuntimeError, aiohttp.ClientError) as exc:
                result["failed"] += 1
                result["error"] = official_error_summary(exc)
                result["failed_rules"].append(name)

        return result

    async def fetch_official_automod_rules(self, guild: discord.Guild) -> list[dict]:
        return await self._discord_api("GET", f"/guilds/{guild.id}/auto-moderation/rules") or []

    @staticmethod
    def _is_exempt(member: discord.Member) -> bool:
        perms = member.guild_permissions
        return bool(member.bot or perms.administrator or perms.manage_guild or perms.manage_messages)

    def _count_links(self, content: str, allow_invites: bool) -> int:
        links = URL_REGEX.findall(content or "")
        if allow_invites:
            links = [link for link in links if not INVITE_REGEX.search(link)]
        return len(links)

    @staticmethod
    def _contains_bad_word(content: str, words: list[str]) -> bool:
        text = (content or "").casefold()
        if not text:
            return False
        for word in words:
            token = word.strip().casefold()
            if not token or token not in text:
                continue
            if token.isalnum():
                if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text):
                    return True
            else:
                return True
        return False

    async def _delete_violating_message(self, message: discord.Message, settings: dict) -> tuple[bool, str]:
        if not settings.get("delete_violating_message", True):
            return False, "disabled"

        me = message.guild.me
        if me is None or not me.guild_permissions.manage_messages:
            return False, "no_permission"

        try:
            await message.delete()
            return True, "deleted"
        except discord.NotFound:
            return True, "already_deleted"
        except discord.Forbidden:
            return False, "forbidden"
        except discord.HTTPException as e:
            return False, f"http:{e.status}"

    def _register_violation(self, guild_id: int, user_id: int, window_seconds: int) -> int:
        key = (guild_id, user_id)
        bucket = self.violation_tracker[key]
        now = discord.utils.utcnow().timestamp()
        while bucket and (now - bucket[0]) > window_seconds:
            bucket.popleft()
        bucket.append(now)
        return len(bucket)

    async def _apply_repeat_action(self, member: discord.Member, settings: dict) -> tuple[bool, str]:
        action = settings.get("repeat_action", "timeout")
        me = member.guild.me
        if me is None:
            return False, "bot_not_found"
        if action == "warn":
            return True, "warn"
        if me.top_role <= member.top_role:
            return False, "hierarchy"
        try:
            if action == "timeout":
                if not me.guild_permissions.moderate_members:
                    return False, "no_moderate_perm"
                duration = datetime.timedelta(minutes=settings.get("repeat_timeout_minutes", 10))
                await member.timeout(duration, reason="AutoMod repeated violations")
                return True, f"timeout:{settings.get('repeat_timeout_minutes', 10)}m"
            if action == "kick":
                if not me.guild_permissions.kick_members:
                    return False, "no_kick_perm"
                await member.kick(reason="AutoMod repeated violations")
                return True, "kick"
            if action == "ban":
                if not me.guild_permissions.ban_members:
                    return False, "no_ban_perm"
                await member.ban(reason="AutoMod repeated violations")
                return True, "ban"
            return False, "unknown_action"
        except (discord.Forbidden, discord.HTTPException) as e:
            return False, f"failed:{type(e).__name__}"

    async def _handle_violation(
        self,
        message: discord.Message,
        language: str,
        warning_key: str,
        action_key: str,
        settings: dict,
    ) -> bool:
        deleted, delete_reason = await self._delete_violating_message(message, settings)
        warning_text = strings[language].get(warning_key, strings[language]["automod_message_blocked"])
        if not deleted:
            warning_text += f" (`delete:{delete_reason}`)"
        try:
            await message.channel.send(f"{message.author.mention} {warning_text}", delete_after=5)
        except (discord.Forbidden, discord.HTTPException):
            pass

        violation_count = self._register_violation(
            message.guild.id,
            message.author.id,
            settings.get("violation_window_seconds", 600),
        )
        threshold = settings.get("violation_threshold", 3)
        repeat_note = None
        if violation_count >= threshold:
            ok, note = await self._apply_repeat_action(message.author, settings)
            repeat_note = f"{'enforced' if ok else 'failed'}:{note}"
            if ok:
                self.violation_tracker[(message.guild.id, message.author.id)].clear()

        details = f"deleted={deleted} | reason={delete_reason} | violations={violation_count}/{threshold}"
        if repeat_note:
            details += f" | repeat={repeat_note}"
        safe_content = message.content if isinstance(message.content, str) else ""
        await self.log_automod_action(
            message.guild,
            message.author,
            strings[language].get(action_key, action_key),
            safe_content,
            language,
            details=details,
        )
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not isinstance(message.author, discord.Member):
            return
        if self._is_exempt(message.author):
            return

        data = await db.get_guild_settings(message.guild.id)
        language = resolve_language(data.get("language", "en"))
        settings = normalize_automod_settings(data.get("automod_settings"))

        if not settings.get("enabled", False):
            return

        can_read_message_content = message_content_intent_enabled(self.bot)
        message_content = message.content or ""

        user_key = (message.guild.id, message.author.id)
        now = discord.utils.utcnow().timestamp()

        if settings.get("anti_spam", True):
            bucket = self.spam_tracker[user_key]
            window = settings.get("spam_window_seconds", 10)
            while bucket and (now - bucket[0]) > window:
                bucket.popleft()
            bucket.append(now)
            if len(bucket) > settings.get("spam_max_messages", 5):
                if await self._handle_violation(message, language, "automod_spam_blocked", "spam_detection", settings):
                    return

        if settings.get("anti_mention", True):
            mention_count = len(message.mentions) + len(message.role_mentions) + (1 if message.mention_everyone else 0)
            if mention_count > settings.get("max_mentions", 5):
                if await self._handle_violation(message, language, "automod_mentions_blocked", "mass_mention", settings):
                    return

        if settings.get("anti_links", False):
            if not can_read_message_content:
                links_count = 0
            else:
                links_count = self._count_links(message_content, settings.get("allow_discord_invites", False))
            if links_count > settings.get("max_links_per_message", 0):
                if await self._handle_violation(message, language, "automod_links_blocked", "link_posted", settings):
                    return

        if settings.get("bad_words", False):
            if can_read_message_content and self._contains_bad_word(message_content, settings.get("bad_words_list", [])):
                await self._handle_violation(message, language, "automod_words_blocked", "bad_word", settings)

    async def log_automod_action(
        self,
        guild: discord.Guild,
        user: discord.Member,
        action_type: str,
        content: str,
        language: str,
        details: Optional[str] = None,
    ):
        value = (content or "").strip() or "[Attachment / Empty message]"
        if len(value) > 1000:
            value = f"{value[:997]}..."
        fields = [
            ("Actor", f"{user.mention} (`{user.id}`)", False),
            ("Target", f"{user.mention} (`{user.id}`)", False),
            ("Action", action_type, False),
            ("Content", value, False),
        ]
        if details:
            fields.append(("Details", details[:1024], False))

        await send_log(
            guild,
            "automod_action",
            f"Auto moderation triggered for {user.mention}.",
            actor=user,
            target=user,
            fields=fields,
        )

    @app_commands.command(name="automod", description="Open AutoMod panel | فتح لوحة الأوتو مود")
    @app_commands.default_permissions(administrator=True)
    async def automod(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                tr("en", "This command works in servers only.", "هذا الأمر يعمل داخل السيرفر فقط."),
                ephemeral=True,
            )
        data = await db.get_guild_settings(interaction.guild.id)
        language = resolve_language(data.get("language", "en"))
        settings = normalize_automod_settings(data.get("automod_settings"))
        can_read_message_content = message_content_intent_enabled(self.bot)
        embed = build_automod_embed(
            language,
            settings,
            can_read_message_content=can_read_message_content,
        )
        view = AutoModView(
            interaction.user.id,
            language,
            settings,
            can_read_message_content=can_read_message_content,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except (discord.NotFound, discord.HTTPException):
            view.message = None

    @app_commands.command(name="automodsync", description="Sync Discord official AutoMod rules")
    @app_commands.default_permissions(administrator=True)
    async def automodsync(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                tr("en", "This command works in servers only.", "This command works in servers only."),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        data = await db.get_guild_settings(interaction.guild.id)
        language = resolve_language(data.get("language", "en"))
        settings = normalize_automod_settings(data.get("automod_settings"))
        sync_result = await self.sync_official_automod_rules(interaction.guild, settings)
        embed = build_automod_embed(
            language,
            settings,
            updated=True,
            can_read_message_content=message_content_intent_enabled(self.bot),
        )
        embed.add_field(
            name="Discord AutoMod Sync",
            value=official_sync_field_value(language, sync_result),
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="automodrules", description="Show official Discord AutoMod rules in this server")
    @app_commands.default_permissions(administrator=True)
    async def automodrules(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command works in servers only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        try:
            rules = await self.fetch_official_automod_rules(interaction.guild)
        except (OfficialAutoModError, RuntimeError, aiohttp.ClientError) as exc:
            return await interaction.followup.send(
                f"Failed to fetch AutoMod rules: `{official_error_summary(exc)}`",
                ephemeral=True,
            )

        enabled_count = sum(1 for rule in rules if rule.get("enabled"))
        managed_count = sum(1 for rule in rules if str(rule.get("name", "")).startswith(MANAGED_RULE_PREFIX))
        lines = [format_official_rule_line(index, rule) for index, rule in enumerate(rules, start=1)]
        description = "\n\n".join(lines) if lines else "No official Discord AutoMod rules found."
        if len(description) > 3900:
            description = description[:3850] + "\n\n... truncated"

        embed = discord.Embed(
            title=f"Official AutoMod Rules: {interaction.guild.name}",
            description=description,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Total", value=f"`{len(rules)}`", inline=True)
        embed.add_field(name="Enabled", value=f"`{enabled_count}`", inline=True)
        embed.add_field(name="Created by Sir Bot", value=f"`{managed_count}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="automodrulesall", description="Owner only: count official AutoMod rules across all bot servers")
    async def automodrulesall(self, interaction: discord.Interaction):
        if not interaction.user or not self._is_bot_owner(interaction.user.id):
            return await interaction.response.send_message("This command is for bot owners only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        rows = []
        total_rules = 0
        total_enabled = 0
        failed = 0

        for guild in sorted(self.bot.guilds, key=lambda item: item.name.casefold()):
            try:
                rules = await self.fetch_official_automod_rules(guild)
                enabled_count = sum(1 for rule in rules if rule.get("enabled"))
                total_rules += len(rules)
                total_enabled += enabled_count
                rows.append(f"**{guild.name}** (`{guild.id}`): `{enabled_count}` enabled / `{len(rules)}` total")
            except (OfficialAutoModError, RuntimeError, aiohttp.ClientError) as exc:
                failed += 1
                rows.append(f"**{guild.name}** (`{guild.id}`): failed `{official_error_summary(exc)}`")
            await asyncio.sleep(0.35)

        description = "\n".join(rows) if rows else "Bot is not in any servers."
        pages = [description[index:index + 3900] for index in range(0, len(description), 3900)] or [description]

        for page_number, page in enumerate(pages, start=1):
            embed = discord.Embed(
                title="Official AutoMod Rules Across Servers",
                description=page,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Enabled Rules", value=f"`{total_enabled}`", inline=True)
            embed.add_field(name="Total Rules", value=f"`{total_rules}`", inline=True)
            embed.add_field(name="Failed Servers", value=f"`{failed}`", inline=True)
            embed.set_footer(text=f"Page {page_number}/{len(pages)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="automodconfig", description="Configure AutoMod options | تخصيص إعدادات الأوتو مود")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        spam_messages="Spam messages limit (2-25) | حد رسائل السبام",
        spam_seconds="Spam window in seconds (3-120) | نافذة السبام بالثواني",
        max_mentions="Max mentions per message (1-25) | حد المنشن للرسالة",
        max_links="Allowed links per message (0-20) | عدد الروابط المسموح",
        allow_discord_invites="Allow discord invite links | السماح بروابط الدعوات",
        violation_count="Repeat violations count (1-20) | عدد المخالفات للتكرار",
        violation_window_seconds="Repeat window seconds (30-86400) | نافذة التكرار بالثواني",
        repeat_action="Action for repeat violations | إجراء التكرار",
        repeat_timeout_minutes="Timeout duration | مدة التايم أوت",
        delete_violating_message="Delete violating messages | حذف الرسائل المخالفة",
    )
    @app_commands.choices(
        repeat_action=[
            app_commands.Choice(name="Warn | تحذير", value="warn"),
            app_commands.Choice(name="Timeout | تايم أوت", value="timeout"),
            app_commands.Choice(name="Kick | طرد", value="kick"),
            app_commands.Choice(name="Ban | حظر", value="ban"),
        ]
    )
    async def automodconfig(
        self,
        interaction: discord.Interaction,
        spam_messages: Optional[app_commands.Range[int, 2, 25]] = None,
        spam_seconds: Optional[app_commands.Range[int, 3, 120]] = None,
        max_mentions: Optional[app_commands.Range[int, 1, 25]] = None,
        max_links: Optional[app_commands.Range[int, 0, 20]] = None,
        allow_discord_invites: Optional[bool] = None,
        violation_count: Optional[app_commands.Range[int, 1, 20]] = None,
        violation_window_seconds: Optional[app_commands.Range[int, 30, 86400]] = None,
        repeat_action: Optional[app_commands.Choice[str]] = None,
        repeat_timeout_minutes: Optional[app_commands.Range[int, 1, 10080]] = None,
        delete_violating_message: Optional[bool] = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                tr("en", "This command works in servers only.", "هذا الأمر يعمل داخل السيرفر فقط."),
                ephemeral=True,
            )

        data = await db.get_guild_settings(interaction.guild.id)
        language = resolve_language(data.get("language", "en"))
        settings = normalize_automod_settings(data.get("automod_settings"))
        changed = False

        if spam_messages is not None:
            settings["spam_max_messages"] = int(spam_messages)
            changed = True
        if spam_seconds is not None:
            settings["spam_window_seconds"] = int(spam_seconds)
            changed = True
        if max_mentions is not None:
            settings["max_mentions"] = int(max_mentions)
            changed = True
        if max_links is not None:
            settings["max_links_per_message"] = int(max_links)
            changed = True
        if allow_discord_invites is not None:
            settings["allow_discord_invites"] = bool(allow_discord_invites)
            changed = True
        if violation_count is not None:
            settings["violation_threshold"] = int(violation_count)
            changed = True
        if violation_window_seconds is not None:
            settings["violation_window_seconds"] = int(violation_window_seconds)
            changed = True
        if repeat_action is not None:
            settings["repeat_action"] = repeat_action.value
            changed = True
        if repeat_timeout_minutes is not None:
            settings["repeat_timeout_minutes"] = int(repeat_timeout_minutes)
            changed = True
        if delete_violating_message is not None:
            settings["delete_violating_message"] = bool(delete_violating_message)
            changed = True

        settings = normalize_automod_settings(settings)
        sync_result = None
        if changed:
            await interaction.response.defer(ephemeral=True)
            await db.update_automod_settings(interaction.guild.id, settings)
            sync_result = await self.sync_official_automod_rules(interaction.guild, settings)

        embed = build_automod_embed(
            language,
            settings,
            updated=changed,
            can_read_message_content=message_content_intent_enabled(self.bot),
        )
        if sync_result is not None:
            embed.add_field(
                name="Discord AutoMod Sync",
                value=official_sync_field_value(language, sync_result),
                inline=False,
            )
        if not changed:
            embed.description = tr(language, "No changes provided. Showing current settings.", "لم يتم إرسال تغييرات. هذه هي الإعدادات الحالية.")
        if changed:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="automodwords", description="Manage bad words | إدارة الكلمات الممنوعة")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        operation="add/remove/set/clear/show | إضافة/إزالة/استبدال/مسح/عرض",
        words="Comma separated words | كلمات مفصولة بفواصل",
    )
    @app_commands.choices(
        operation=[
            app_commands.Choice(name="Add | إضافة", value="add"),
            app_commands.Choice(name="Remove | إزالة", value="remove"),
            app_commands.Choice(name="Set | استبدال", value="set"),
            app_commands.Choice(name="Clear | مسح", value="clear"),
            app_commands.Choice(name="Show | عرض", value="show"),
        ]
    )
    async def automodwords(
        self,
        interaction: discord.Interaction,
        operation: app_commands.Choice[str],
        words: Optional[str] = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                tr("en", "This command works in servers only.", "هذا الأمر يعمل داخل السيرفر فقط."),
                ephemeral=True,
            )
        data = await db.get_guild_settings(interaction.guild.id)
        language = resolve_language(data.get("language", "en"))
        settings = normalize_automod_settings(data.get("automod_settings"))
        current_words = list(settings.get("bad_words_list", []))
        before = list(current_words)

        mode = operation.value
        if mode in {"add", "remove", "set"}:
            parsed = parse_words(words)
            if not parsed:
                return await interaction.response.send_message(
                    tr(language, "Please provide words separated by commas.", "يرجى إدخال كلمات مفصولة بفواصل."),
                    ephemeral=True,
                )
            if mode == "set":
                current_words = parsed
            elif mode == "add":
                existing = {w.casefold() for w in current_words}
                for word in parsed:
                    if word.casefold() not in existing:
                        current_words.append(word)
                        existing.add(word.casefold())
            elif mode == "remove":
                remove_set = {w.casefold() for w in parsed}
                current_words = [w for w in current_words if w.casefold() not in remove_set]
        elif mode == "clear":
            current_words = []
        elif mode != "show":
            return await interaction.response.send_message(
                tr(language, "Invalid operation.", "العملية غير صالحة."),
                ephemeral=True,
            )

        changed = current_words != before
        sync_result = None
        if changed and mode != "show":
            await interaction.response.defer(ephemeral=True)
        if mode != "show":
            settings["bad_words_list"] = current_words
            if mode in {"add", "set"} and current_words:
                settings["bad_words"] = True
            if mode == "clear":
                settings["bad_words"] = False
            settings = normalize_automod_settings(settings)
            if changed:
                await db.update_automod_settings(interaction.guild.id, settings)
                sync_result = await self.sync_official_automod_rules(interaction.guild, settings)

        embed = discord.Embed(
            title=tr(language, "Bad Words List", "قائمة الكلمات الممنوعة"),
            color=discord.Color.green() if changed else discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.description = tr(
            language,
            "Bad words list updated." if changed else "No changes made.",
            "تم تحديث قائمة الكلمات الممنوعة." if changed else "لم يتم إجراء تغييرات.",
        )
        if current_words:
            preview = ", ".join(current_words[:30]) + (f", ... ({len(current_words)})" if len(current_words) > 30 else "")
        else:
            preview = tr(language, "No bad words set.", "لا توجد كلمات ممنوعة.")
        embed.add_field(name=tr(language, "Words", "الكلمات"), value=preview, inline=False)
        if sync_result is not None:
            embed.add_field(
                name="Discord AutoMod Sync",
                value=official_sync_field_value(language, sync_result),
                inline=False,
            )
        if changed and mode != "show":
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AutoModView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        language: str,
        automod_settings: dict,
        *,
        can_read_message_content: bool = True,
    ):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.language = resolve_language(language)
        self.automod_settings = normalize_automod_settings(automod_settings)
        self.can_read_message_content = can_read_message_content
        self.message: Optional[discord.Message] = None
        self._sync_buttons()

    def _button_label(self, key: str) -> str:
        return "ON" if self.automod_settings.get(key, False) else "OFF"

    def _button_style(self, key: str) -> discord.ButtonStyle:
        return discord.ButtonStyle.success if self.automod_settings.get(key, False) else discord.ButtonStyle.danger

    def _sync_buttons(self):
        self.toggle_automod.label = f"AutoMod {self._button_label('enabled')}"
        self.toggle_automod.style = self._button_style("enabled")
        self.toggle_spam.label = f"Spam {self._button_label('anti_spam')}"
        self.toggle_spam.style = self._button_style("anti_spam")
        self.toggle_mention.label = f"Mentions {self._button_label('anti_mention')}"
        self.toggle_mention.style = self._button_style("anti_mention")
        self.toggle_links.label = f"Links {self._button_label('anti_links')}"
        self.toggle_links.style = self._button_style("anti_links")
        self.toggle_bad_words.label = f"Bad Words {self._button_label('bad_words')}"
        self.toggle_bad_words.style = self._button_style("bad_words")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            msg = strings[self.language].get("only_command_user", "Only the command user can use this panel.")
            await interaction.response.send_message(msg, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

    @discord.ui.button(label="AutoMod", style=discord.ButtonStyle.primary, emoji="🛡️", row=0)
    async def toggle_automod(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.automod_settings["enabled"] = not self.automod_settings.get("enabled", False)
        await self.update_settings(interaction)

    @discord.ui.button(label="Spam", style=discord.ButtonStyle.secondary, emoji="🔨", row=0)
    async def toggle_spam(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.automod_settings["anti_spam"] = not self.automod_settings.get("anti_spam", True)
        await self.update_settings(interaction)

    @discord.ui.button(label="Mentions", style=discord.ButtonStyle.secondary, emoji="👥", row=0)
    async def toggle_mention(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.automod_settings["anti_mention"] = not self.automod_settings.get("anti_mention", True)
        await self.update_settings(interaction)

    @discord.ui.button(label="Links", style=discord.ButtonStyle.secondary, emoji="🔗", row=0)
    async def toggle_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.automod_settings["anti_links"] = not self.automod_settings.get("anti_links", False)
        await self.update_settings(interaction)

    @discord.ui.button(label="Bad Words", style=discord.ButtonStyle.secondary, emoji="🤬", row=0)
    async def toggle_bad_words(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.automod_settings["bad_words"] = not self.automod_settings.get("bad_words", False)
        await self.update_settings(interaction)

    @discord.ui.button(label="Sync Discord", style=discord.ButtonStyle.primary, row=1)
    async def sync_discord(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_settings(interaction, save_settings=False)

    async def update_settings(self, interaction: discord.Interaction, *, save_settings: bool = True):
        if not interaction.guild:
            return await interaction.response.send_message("This interaction works in servers only.", ephemeral=True)
        await interaction.response.defer()
        self.automod_settings = normalize_automod_settings(self.automod_settings)
        if save_settings:
            await db.update_automod_settings(interaction.guild.id, self.automod_settings)
        sync_result = None
        cog = interaction.client.get_cog("AutoModCog")
        if cog is not None and hasattr(cog, "sync_official_automod_rules"):
            sync_result = await cog.sync_official_automod_rules(interaction.guild, self.automod_settings)
        self._sync_buttons()
        embed = build_automod_embed(
            self.language,
            self.automod_settings,
            updated=True,
            can_read_message_content=self.can_read_message_content,
        )
        if sync_result is not None:
            embed.add_field(
                name="Discord AutoMod Sync",
                value=official_sync_field_value(self.language, sync_result),
                inline=False,
            )
        await interaction.edit_original_response(embed=embed, view=self)


async def setup(bot):
    await bot.add_cog(AutoModCog(bot))
