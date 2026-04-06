
from bot_instance import bot
from config import TEST_GUILD, GUILD_ID
from data_manager import initialize_data_files

@bot.event
async def on_ready():
    initialize_data_files()

    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        bot.tree.copy_global_to(guild=TEST_GUILD)
        synced = await bot.tree.sync(guild=TEST_GUILD)
        print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
