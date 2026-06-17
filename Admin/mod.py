# mod.py
# Requirements:
#   discord.py==2.4.0
#   python-dotenv==1.0.1
#   openpyxl (optional, for .xlsx)

import os
import io
import csv
import platform
import datetime
from typing import List, Tuple

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ===== ENV / Config =====
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_IDS = {580025217708064782, 530786064995188737}
START_TIME = datetime.datetime.now(datetime.UTC)

# ===== Bot / Intents =====
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="^", intents=intents, help_command=None)

# ===== Utils =====
def _is_owner(ctx: commands.Context) -> bool:
    allowed = bool(ctx.author and int(ctx.author.id) in OWNER_IDS)
    who = f"{ctx.author} (ID: {ctx.author.id}) in '{ctx.guild.name if ctx.guild else 'DM'}'"
    print(f"[{'ALLOW' if allowed else 'DENY '}] {who} -> {ctx.command}")
    return allowed

def _ordered_guilds() -> List[discord.Guild]:
    return sorted(bot.guilds, key=lambda g: (g.member_count or 0), reverse=True)

def _chunk_guilds(guilds: List[discord.Guild], page_size: int = 20) -> List[List[Tuple[int, str, int]]]:
    data = [(g.id, g.name, g.member_count or 0) for g in guilds]
    return [data[i:i+page_size] for i in range(0, len(data), page_size)]

def _format_page(page: List[Tuple[int, str, int]], start_index: int) -> str:
    lines = []
    for idx, (gid, name, members) in enumerate(page, start=start_index):
        # clean one line per guild, plus meta line
        lines.append(f"**{idx}. {name}**`ID:` {gid} • `Members:` {members}")
    return "\n".join(lines)

def _build_embed(page_text: str, page_idx: int, total_pages: int, total_guilds: int) -> discord.Embed:
    e = discord.Embed(
        title="Server List",
        description=page_text or "_No servers_",
        color=0x5865F2,
    )
    e.set_footer(text=f"Page {page_idx+1}/{total_pages} • Total servers: {total_guilds}")
    return e

def _export_excel_bytes(rows: List[Tuple[int, str, int]]) -> tuple[io.BytesIO, str]:
    # Try XLSX first
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Servers"
        ws.append(["Name", "ID", "Members"])
        for gid, name, members in rows:
            ws.append([name, str(gid), int(members)])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf, "servers.xlsx"
    except Exception:
        # CSV fallback; keep BytesIO open by detaching wrapper
        buf = io.BytesIO()
        tw = io.TextIOWrapper(buf, encoding="utf-8", newline="")
        writer = csv.writer(tw)
        writer.writerow(["Name", "ID", "Members"])
        for gid, name, members in rows:
            writer.writerow([name, str(gid), int(members)])
        tw.flush()
        tw.detach()          # prevent closing underlying BytesIO
        buf.seek(0)
        return buf, "servers.csv"

# ===== View with pagination + export =====
class GuildsView(discord.ui.View):
    def __init__(self, author_id: int, guilds: List[discord.Guild], page_size: int = 20):
        super().__init__(timeout=180)
        self.author_id = author_id
        # snapshot (id, name, members) to keep order stable during view lifetime
        self.pages: List[List[Tuple[int, str, int]]] = _chunk_guilds(
            sorted(guilds, key=lambda g: (g.member_count or 0), reverse=True), page_size
        )
        self.total = sum(len(p) for p in self.pages)
        self.page_idx = 0

    def _current_embed(self) -> discord.Embed:
        total_pages = max(1, len(self.pages))
        page = self.pages[self.page_idx] if self.pages else []
        start_index = (self.page_idx * len(page)) - (len(page) - 1) if page else 1
        # simpler start index calc:
        start_index = self.page_idx * 20 + 1
        txt = _format_page(page, start_index)
        return _build_embed(txt, self.page_idx, total_pages, self.total)

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if not interaction.user or int(interaction.user.id) not in OWNER_IDS:
            await interaction.response.defer()  # silent
            return False
        return True

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_owner(interaction): return
        if not self.pages: return await interaction.response.defer()
        self.page_idx = (self.page_idx - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_owner(interaction): return
        if not self.pages: return await interaction.response.defer()
        self.page_idx = (self.page_idx + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    @discord.ui.button(label="Export Excel", style=discord.ButtonStyle.primary)
    async def export_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_owner(interaction): return
        # flatten rows in current order
        rows: List[Tuple[int, str, int]] = [row for page in self.pages for row in page]
        buf, fname = _export_excel_bytes(rows)
        await interaction.response.send_message(file=discord.File(buf, filename=fname), ephemeral=True)

# ===== Events =====
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# ===== Commands =====
@bot.command(name="help")
@commands.check(_is_owner)
async def help_cmd(ctx: commands.Context):
    e = discord.Embed(title="Owner Commands", color=0x2f3136)
    e.add_field(name="^help", value="Show this help", inline=False)
    e.add_field(name="^bot", value="Bot info and stats", inline=False)
    e.add_field(name="^guilds", value="Server list with paging + Export", inline=False)
    e.add_field(name="^latency", value="Show bot ping", inline=False)
    await ctx.send(embed=e)

@bot.command(name="bot")
@commands.check(_is_owner)
async def bot_info(ctx: commands.Context):
    guilds = bot.guilds
    servers_count = len(guilds)
    members_total = sum((g.member_count or 0) for g in guilds)
    uptime = datetime.datetime.now(datetime.UTC) - START_TIME
    ping_ms = round(bot.latency * 1000)

    e = discord.Embed(title="Bot Information", color=0x57F287)
    e.set_thumbnail(url=bot.user.display_avatar.url if bot.user else discord.Embed.Empty)
    e.add_field(name="Bot", value=str(bot.user), inline=True)
    e.add_field(name="ID", value=str(bot.user.id if bot.user else "N/A"), inline=True)
    e.add_field(name="Servers", value=str(servers_count), inline=True)
    e.add_field(name="Members (approx)", value=str(members_total), inline=True)
    e.add_field(name="Ping", value=f"{ping_ms} ms", inline=True)
    e.add_field(name="Uptime", value=str(uptime).split(".")[0], inline=True)
    e.add_field(name="discord.py", value=discord.__version__, inline=True)
    e.add_field(name="Python", value=platform.python_version(), inline=True)
    await ctx.send(embed=e)

@bot.command(name="latency")
@commands.check(_is_owner)
async def latency_cmd(ctx: commands.Context):
    await ctx.send(f"Ping: {round(bot.latency * 1000)} ms")

@bot.command(name="guilds")
@commands.check(_is_owner)
async def guilds_cmd(ctx: commands.Context):
    guilds = _ordered_guilds()
    view = GuildsView(ctx.author.id, guilds, page_size=10)
    await ctx.send(embed=view._current_embed(), view=view)

# ===== Errors (silent for non-owners) =====
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure): return
    if isinstance(error, commands.CommandNotFound): return
    raise error

# ===== Run =====
if not TOKEN:
    raise SystemExit("DISCORD_TOKEN not found in .env")
bot.run(TOKEN)