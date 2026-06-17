import asyncio
import os
import time
import discord
from discord import app_commands  # تمت إضافة هذا الاستيراد
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from config import ALLOWED_GUILDS, DEVELOPER_PRESENCE_GUILD_ID

# تحميل البيئة
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN not found in environment variables")

# إعدادات البوت
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
bot.start_time = time.time()
bot.custom_presence = False

# خادم ويب لإبقاء البوت شغال
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=3000)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# تحميل الكوجات
async def load_cogs():
    cogs = [
        'cogs.general',
        'cogs.admin', 
        'cogs.protection',
        'cogs.logs',
        'cogs.info',
        'cogs.automod',
        'cogs.developer_presence',
        'events.guild_events',
        'events.member_events',
        'events.channel_events',
        'events.role_events'
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded cog: {cog}")
        except commands.ExtensionNotFound:
            print(f"⚠️ Cog not found: {cog}")
        except commands.ExtensionAlreadyLoaded:
            print(f"ℹ️ Cog already loaded: {cog}")
        except Exception as e:
            print(f"❌ Failed to load cog {cog}: {type(e).__name__}: {e}")

# مهمة تحديث الأعضاء كل 30 دقيقة (بدلاً من 10) مع تحسينات الأداء
@tasks.loop(minutes=30)
async def refresh_members():
    """تحديث قائمة الأعضاء كل 30 دقيقة مع تحسين الأداء"""
    try:
        print("🔄 Refreshing members list...")
        refreshed_servers = 0
        total_members = 0
        
        for guild in bot.guilds:
            try:
                # تخطي السيرفرات الصغيرة أو التي لا تحتاج تحديث مستمر
                if guild.member_count < 100:
                    continue
                    
                # إضافة تأخير بين السيرفرات لتجنب rate limits
                await asyncio.sleep(2)
                
                # استخدام fetch_members بحذر مع limit معقول
                member_count = 0
                async for member in guild.fetch_members(limit=500):  # تحديد حد أعلى
                    member_count += 1
                    # مجرد تمرير على الأعضاء لتحديث الكاش
                    pass
                    
                refreshed_servers += 1
                total_members += member_count
                print(f"✅ Refreshed {member_count} members for {guild.name}")
                
            except discord.HTTPException as e:
                print(f"⚠️ Rate limit for {guild.name}, skipping: {e}")
                await asyncio.sleep(10)  # انتظار أطول في حالة rate limit
            except Exception as e:
                print(f"❌ Failed to refresh members for {guild.name}: {type(e).__name__}: {e}")
        
        print(f"✅ Successfully refreshed {total_members} members across {refreshed_servers}/{len(bot.guilds)} servers")
        
    except Exception as e:
        print(f"❌ Error in refresh_members task: {type(e).__name__}: {e}")

# مهمة جديدة لتحديث الحضور كل 5 دقائق (اختياري)
@tasks.loop(minutes=5)
async def update_presence():
    """تحديث إحصائيات الحضور"""
    try:
        if getattr(bot, "custom_presence", False):
            return

        total_servers = len(bot.guilds)
        total_members = sum(guild.member_count for guild in bot.guilds if guild.member_count)
        
        activity = discord.Activity(
            type=discord.ActivityType.watching, 
            name=f"{total_servers} servers | /help"
        )
        await bot.change_presence(activity=activity)
        
    except Exception as e:
        print(f"❌ Error updating presence: {type(e).__name__}: {e}")

# الأحداث الرئيسية
@bot.event
async def on_ready():
    print(f"✅ Logged in as: {bot.user}")
    print(f"✅ Connected to {len(bot.guilds)} servers")
    
    # عرض إحصائيات السيرفرات
    total_members = sum(guild.member_count for guild in bot.guilds if guild.member_count)
    large_servers = sum(1 for guild in bot.guilds if guild.member_count and guild.member_count > 100)
    
    print(f"📊 Total members: {total_members}")
    print(f"🏢 Large servers (100+ members): {large_servers}")
    
    # تهيئة قاعدة البيانات أولاً (إذا كانت موجودة)
    try:
        from database import db
        await db.init_db()
        print("✅ Database initialized successfully")
    except ImportError:
        print("ℹ️ No database module found, skipping database initialization")
    except Exception as e:
        print(f"❌ Database initialization failed: {type(e).__name__}: {e}")
    
    # بدء المهام الدورية
    if not refresh_members.is_running():
        refresh_members.start()
        print("✅ Started auto-refresh members task (every 30 minutes)")
    
    if not update_presence.is_running():
        update_presence.start()
        print("✅ Started presence update task (every 5 minutes)")
    
    # مزامنة الأوامر
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
        
        # عرض الأوامر المتزامنة
        for cmd in synced:
            print(f"   └─ /{cmd.name}")

        try:
            dev_guild_id = int(DEVELOPER_PRESENCE_GUILD_ID)
        except (TypeError, ValueError):
            dev_guild_id = 0

        if dev_guild_id > 0:
            dev_synced = await bot.tree.sync(guild=discord.Object(id=dev_guild_id))
            print(f"✅ Synced {len(dev_synced)} guild command(s) for developer guild {dev_guild_id}")
            for cmd in dev_synced:
                print(f"   └─ [guild:{dev_guild_id}] /{cmd.name}")
    except Exception as e:
        print(f"❌ Error syncing commands: {type(e).__name__}: {e}")

# إضافة أمر يدوي للتحديث
@bot.tree.command(name="refresh", description="Manually refresh members list | تحديث يدوي لقائمة الأعضاء")
@app_commands.checks.has_permissions(administrator=True)  # تم التعديل هنا
async def refresh_command(interaction: discord.Interaction):
    """أمر يدوي لتحديث قائمة الأعضاء"""
    # تأجيل الرد فوراً
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        member_count_before = guild.member_count
        
        # تحديث الأعضاء مع معالجة الأخطاء
        try:
            async for member in guild.fetch_members(limit=1000):
                pass
        except discord.HTTPException as e:
            error_embed = discord.Embed(
                title="❌ Rate Limit",
                description="Please try again in a few minutes.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=error_embed, ephemeral=True)
        
        member_count_after = guild.member_count
        difference = member_count_after - member_count_before
        
        embed = discord.Embed(
            title="🔄 Members Refresh",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Server", value=guild.name, inline=True)
        embed.add_field(name="Members Before", value=member_count_before, inline=True)
        embed.add_field(name="Members After", value=member_count_after, inline=True)
        
        if difference != 0:
            embed.add_field(
                name="Change", 
                value=f"**{difference:+}** members", 
                inline=True
            )
        
        embed.set_footer(text="Auto-refresh runs every 30 minutes")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Refresh Failed",
            description=f"Error: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

# معالج أخطاء الأمر اليدوي
@refresh_command.error
async def refresh_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need administrator permissions to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# معالج الأخطاء العام
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"❌ Error in event {event}: {args} {kwargs}")

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    """معالج أخطاء الأوامر"""
    if isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏰ Cooldown",
            description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You don't have permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="❌ Unexpected Error",
            description="An error occurred while processing your command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"❌ Command error: {type(error).__name__}: {error}")

# تشغيل البوت
async def main():
    await load_cogs()
    keep_alive()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
