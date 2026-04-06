import discord
from config import MOD_ROLE_ID

def is_user_mod(member: discord.Member) -> bool:
    if not member:
        return False

    return any(role.id == MOD_ROLE_ID for role in member.roles)

def is_admin(member: discord.Member) -> bool:
    if not member:
        return False

    return member.guild_permissions.manage_guild

def is_mod_or_admin(member: discord.Member) -> bool:
    return is_admin(member) or is_user_mod(member)