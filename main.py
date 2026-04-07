import discord
from bot_instance import bot
from config import TOKEN, TEST_GUILD

import lifecycle
from views import SignupConfirmView, TeamConfirmView

from commands.spr_group import spr_group

# import command modules so decorators run
import commands.players
import commands.teams
import commands.queue
import commands.rankup
import commands.reporting
import commands.mod
import commands.matches
import commands.help


@bot.event
async def on_ready():
    try:
        bot.tree.clear_commands(guild=TEST_GUILD)
        bot.tree.add_command(spr_group, guild=TEST_GUILD)
        synced = await bot.tree.sync(guild=TEST_GUILD)
        print(f"Synced {len(synced)} command(s) to guild {TEST_GUILD.id}")
    except Exception as e:
        print(f"Sync failed: {e}")

    print(f"Logged in as {bot.user}")


bot.run(TOKEN)