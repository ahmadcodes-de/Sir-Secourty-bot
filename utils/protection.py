import time
from collections import defaultdict
from discord import Guild, User
from database import db
from utils.helpers import send_log

user_action_tracker = defaultdict(lambda: defaultdict(list))

async def check_action_limit(guild: Guild, user: User, action_type: str, limit: int):
    """التحقق مما إذا تجاوز المستخدم الحد المسموح للإجراءات"""
    try:
        current_time = time.time()
        user_key = f"{guild.id}_{user.id}"
        
        # تنظيف الإجراءات القديمة (أقدم من 10 ثواني)
        user_action_tracker[user_key][action_type] = [
            timestamp for timestamp in user_action_tracker[user_key][action_type]
            if current_time - timestamp < 10  # نافذة زمنية 10 ثواني
        ]
        
        # إضافة الإجراء الحالي
        user_action_tracker[user_key][action_type].append(current_time)
        
        # التحقق من تجاوز الحد
        if len(user_action_tracker[user_key][action_type]) > limit:
            # تجاوز الحد - اتخاذ إجراء
            await take_protective_action(guild, user, action_type, limit)
            return True
            
        return False
        
    except Exception as e:
        print(f"Error in check_action_limit: {e}")
        return False

async def take_protective_action(guild: Guild, user: User, action_type: str, limit: int):
    """اتخاذ إجراء وقائي عندما يتجاوز المستخدم الحد - سحب الرتب بدلاً من الحظر"""
    try:
        settings = await db.get_guild_settings(guild.id)
        lang = settings['language']
        
        action_names = {
            'role_create': "Role Creation",
            'role_delete': "Role Deletion", 
            'channel_delete': "Channel Deletion"
        }
        
        action_name = action_names.get(action_type, action_type)
        
        # إرسال إنذار إلى قنوات السجلات
        alert_message = f"🚨 **PROTECTION TRIGGERED** - {user.mention} exceeded {action_name} limit ({limit} in 10s). Removing all roles!"
        
        await send_log(guild, 'member_ban', alert_message, user=user)
        
        # محاولة سحب جميع الرتب من المستخدم (عدا الرتب المحمية)
        try:
            member = guild.get_member(user.id)
            if member:
                # الحصول على جميع رتب المستخدم (عدا الرتبة الأساسية @everyone)
                roles_to_remove = [role for role in member.roles if role != guild.default_role]
                
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason=f"Exceeded {action_type} limit ({limit} actions)")
                    
                    # سجل الإجراء
                    roles_removed = len(roles_to_remove)
                    action_message = f"🎭 **Roles Removed** - {user.mention} lost {roles_removed} roles for exceeding {action_name} limit"
                    await send_log(guild, 'member_ban', action_message, user=user)
                    
                    # إرسال رسالة تأكيد
                    try:
                        embed = discord.Embed(
                            title="🛡️ Protection Action Taken",
                            description=f"All roles have been removed from you for exceeding {action_name} limit in {guild.name}",
                            color=discord.Color.orange()
                        )
                        await member.send(embed=embed)
                    except:
                        pass  # إذا كان المستخدم مغلق الرسائل المباشرة
                else:
                    warn_message = f"⚠️ **Warning** - {user.mention} exceeded {action_name} limit but has no roles to remove"
                    await send_log(guild, 'member_ban', warn_message, user=user)
        except discord.Forbidden:
            # إذا لم يكن لدى البوت صلاحية إدارة الرتب
            warn_message = f"⚠️ **Warning** - Cannot remove roles from {user.mention} (missing permissions), but they exceeded {action_name} limit"
            await send_log(guild, 'member_ban', warn_message, user=user)
        except Exception as e:
            print(f"Error removing roles: {e}")
            
    except Exception as e:
        print(f"Error in take_protective_action: {e}")