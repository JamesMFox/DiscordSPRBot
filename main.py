from bot_instance import bot
from config import TOKEN, TEST_GUILD
import lifecycle
from views import SignupConfirmView, TeamConfirmView  # ensure views load
import commands.players
import commands.teams
import commands.queue
import commands.rankup
import commands.reporting
import commands.mod
import commands.matches
import commands.help
from services.matchmaking_service import run_1v1_matchmaking_pass, run_3v3_matchmaking_pass


bot.run(TOKEN)