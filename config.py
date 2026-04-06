import os
import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN_RAW = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")
MOD_ROLE_ID_RAW = os.getenv("MOD_ROLE_ID")

if not TOKEN_RAW:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set.")
if not GUILD_ID_RAW:
    raise ValueError("Missing GUILD_ID in .env")
if not MOD_ROLE_ID_RAW:
    raise ValueError("Missing MOD_ROLE_ID in .env")

TOKEN = TOKEN_RAW
GUILD_ID = int(GUILD_ID_RAW)
MOD_ROLE_ID = int(MOD_ROLE_ID_RAW)
TEST_GUILD = discord.Object(id=GUILD_ID)