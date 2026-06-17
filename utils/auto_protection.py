import time
from collections import defaultdict
from discord import Guild, User, Member, Role, Forbidden, HTTPException, Embed
import discord
import asyncio

try:
    from database import db
except ImportError:
    print("⚠️ Database module not found")

try:
    from utils.helpers import send_log
except ImportError:
    async def send_log(guild, log_type, message, user=None, before=None, after=None):
        print(f"[LOG] {log_type}: {message}")

user_action_tracker = defaultdict(lambda: defaultdict(list))

async def check_action_limit(guild: Guild, user: User, action_type: str, limit: int):
    """التحقق مما إذا تجاوز المستخدم الحد المسموح للإجراءات"""
    try:
        current_time = time.time()
        user_key = f"{guild.id}_{user.id}"
        
        # تنظيف الإجراءات القديمة
        user_action_tracker[user_key][action_type] = [
            timestamp for timestamp in user_action_tracker[user_key][action_type]
            if current_time - timestamp < 10
        ]
        
        # إضافة الإجراء الحالي
        user_action_tracker[user_key][action_type].append(current_time)
        
        # التحقق من تجاوز الحد
        if len(user_action_tracker[user_key][action_type]) > limit:
            # اتخاذ إجراء فوري
            asyncio.create_task(take_protective_action(guild, user, action_type, limit))
            return True
            
        return False
        
    except Exception as e:
        print(f"Error in check_action_limit: {e}")
        return False

async def take_protective_action(guild: Guild, user: User, action_type: str, limit: int):
    """اتخاذ إجراء وقائي عندما يتجاوز المستخدم الحد"""
    try:
        action_names = {
            'role_create': "إنشاء الرتب",
            'role_delete': "حذف الرتب", 
            'channel_delete': "حذف القنوات",
            'channel_create': "إنشاء القنوات"
        }
        
        action_name = action_names.get(action_type, action_type)
        
        # إرسال إنذار
        alert_message = f"🚨 **تم تفعيل الحماية** - {user.mention} تجاوز حد {action_name} ({limit} في 10 ثواني)"
        
        try:
            await send_log(guild, 'protection', alert_message, user=user)
        except:
            print(f"Failed to send log: {alert_message}")
        
        # محاولة سحب الرتب
        try:
            member = await guild.fetch_member(user.id) if not guild.get_member(user.id) else guild.get_member(user.id)
            if member:
                bot_member = guild.get_member(guild.me.id)
                
                if not bot_member.guild_permissions.manage_roles:
                    error_msg = f"❌ البوت لا يملك صلاحية إدارة الرتب!"
                    await send_log(guild, 'protection', error_msg, user=user)
                    return
                
                # سحب جميع الرتب ما عدا @everyone
                roles_to_remove = [role for role in member.roles if role != guild.default_role]
                
                if roles_to_remove:
                    success_count = 0
                    failed_roles = []
                    
                    for role in roles_to_remove:
                        try:
                            # التحقق إذا كانت الرتبة تحت رتبة البوت
                            if role.position < bot_member.top_role.position:
                                await member.remove_roles(role, reason=f"تجاوز حد الأمان: {action_type}")
                                success_count += 1
                            else:
                                failed_roles.append(f"{role.name} (أعلى من البوت)")
                        except Exception as e:
                            failed_roles.append(f"{role.name} (خطأ: {str(e)[:50]})")
                    
                    # تسجيل النتائج
                    result_msg = f"🛡️ **نتيجة الحماية** - {user.mention}: تمت إزالة {success_count} رتبة"
                    if failed_roles:
                        result_msg += f"\n❌ فشل إزالة: {', '.join(failed_roles[:3])}"
                    
                    await send_log(guild, 'protection', result_msg, user=user)
                    
                    # إرسال رسالة للمالك
                    await notify_owner(guild, user, action_name, limit, success_count, failed_roles)
                    
        except Exception as e:
            print(f"Error in protective action: {e}")
            
    except Exception as e:
        print(f"Error in take_protective_action: {e}")

async def notify_owner(guild: Guild, user: User, action_name: str, limit: int, success: int, failed: list):
    """إرسال إشعار لمالك السيرفر"""
    try:
        owner = guild.owner
        if owner:
            embed = discord.Embed(
                title="🚨 إشعار أمني",
                description=f"تم تفعيل الحماية في **{guild.name}**",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="👤 العضو", value=user.mention, inline=False)
            embed.add_field(name="📛 المخالفة", value=f"تجاوز حد {action_name} ({limit} في 10 ثواني)", inline=False)
            embed.add_field(name="⚡ الإجراء", value=f"تمت إزالة {success} رتبة", inline=False)
            
            if failed:
                embed.add_field(name="⚠️ ملاحظات", value="\n".join(failed[:3]), inline=False)
            
            try:
                await owner.send(embed=embed)
            except:
                pass
    except Exception as e:
        print(f"Error notifying owner: {e}")