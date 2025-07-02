import os
import discord
import json
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# تحميل Whitelist
def load_whitelist():
    with open("whitelist.json", "r") as file:
        return json.load(file)["whitelisted_users"]

def is_whitelisted(user_id):
    return str(user_id) in load_whitelist()

async def log_action(guild, message):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

@bot.event
async def on_ready():
    print(f"✅ Bot ready: {bot.user.name}")

# 🚨 الحماية من الطرد والحظر
@bot.event
async def on_member_remove(member):
    logs = await member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick).flatten()
    if logs:
        entry = logs[0]
        if entry.target.id == member.id and not is_whitelisted(entry.user.id):
            await log_action(member.guild, f"🚨 {entry.user.mention} طرد {member.mention} بدون إذن!")

@bot.event
async def on_member_ban(guild, user):
    logs = await guild.audit_logs(limit=1, action=discord.AuditLogAction.ban).flatten()
    if logs:
        entry = logs[0]
        if entry.target.id == user.id and not is_whitelisted(entry.user.id):
            await log_action(guild, f"🚨 {entry.user.mention} حظر {user.mention} بدون إذن!")

# 🧹 حذف القنوات والرتب
@bot.event
async def on_guild_channel_delete(channel):
    logs = await channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete).flatten()
    if logs:
        entry = logs[0]
        if not is_whitelisted(entry.user.id):
            await log_action(channel.guild, f"⚠️ {entry.user.mention} حذف قناة: {channel.name}")

@bot.event
async def on_guild_role_delete(role):
    logs = await role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete).flatten()
    if logs:
        entry = logs[0]
        if not is_whitelisted(entry.user.id):
            await log_action(role.guild, f"⚠️ {entry.user.mention} حذف رتبة: {role.name}")

# 🤖 منع إضافة بوتات
@bot.event
async def on_member_join(member):
    if member.bot:
        logs = await member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add).flatten()
        if logs:
            entry = logs[0]
            if not is_whitelisted(entry.user.id):
                await member.ban(reason="إضافة بوت بدون إذن")
                await log_action(member.guild, f"🚫 {entry.user.mention} حاول إضافة بوت وتم منعه.")

# 🔗 Anti-invite
@bot.event
async def on_message(message):
    if not message.author.bot and "discord.gg/" in message.content.lower() and not is_whitelisted(message.author.id):
        await message.delete()
        await log_action(message.guild, f"🔗 تم حذف دعوة من {message.author.mention}")
    await bot.process_commands(message)

# 🔧 أمر إضافة للقائمة البيضاء
@bot.command()
async def whitelist(ctx, member: discord.Member):
    if str(ctx.author.id) != str(ctx.guild.owner_id):
        return await ctx.send("❌ هذا الأمر فقط لمالك السيرفر.")
    data = load_whitelist()
    if str(member.id) not in data:
        data.append(str(member.id))
        with open("whitelist.json", "w") as file:
            json.dump({"whitelisted_users": data}, file, indent=4)
        await ctx.send(f"✅ تم إضافة {member.mention} للقائمة البيضاء.")
    else:
        await ctx.send("⚠️ هذا الشخص موجود بالفعل.")

# 🛑 قفل كل القنوات (Lockdown)
@bot.command()
async def lockdown(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ ليس لديك صلاحية.")
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 تم قفل جميع القنوات.")

# 🔓 فتح كل القنوات
@bot.command()
async def unlock(ctx):
    if not is_whitelisted(ctx.author.id):
        return await ctx.send("❌ ليس لديك صلاحية.")
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 تم فتح جميع القنوات.")

# 🚷 طرد كل الأعضاء غير الموثوقين (تحذير: خطير)
@bot.command()
async def kickall(ctx):
    if str(ctx.author.id) != str(ctx.guild.owner_id):
        return await ctx.send("❌ فقط المالك يمكنه استخدام هذا.")
    for member in ctx.guild.members:
        if not member.bot and not is_whitelisted(member.id) and member.id != ctx.author.id:
            try:
                await member.kick(reason="kickall by owner")
            except:
                pass
    await ctx.send("🚨 تم طرد جميع الأعضاء غير الموثوقين.")

bot.run(TOKEN)
