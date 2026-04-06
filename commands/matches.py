# -----------------------
# Import statements
# -----------------------

import discord
from discord import app_commands

from bot_instance import bot
from config import TEST_GUILD
from data_manager import (
    load_json, save_json,
    PLAYERS_FILE, DEFAULT_PLAYERS,
    QUEUE_FILE, DEFAULT_QUEUE,
    ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES,
    MATCHES_FILE, DEFAULT_MATCHES,
)

from utils.player_utils import format_player_names
from services.matchmaking_service import (
    run_1v1_matchmaking_pass,
    run_2v2_matchmaking_pass,
    run_3v3_matchmaking_pass,
)
from utils.finalization_utils import (
    finalize_agreed_1v1_match,
    fail_rankup_if_needed,
)
from utils.permissions_utils import is_mod_or_admin
from utils.matchmaking_utils import (
    group_queue_entries_by_class,
    find_best_2v2_match_for_class,
    find_best_3v3_match_for_class,
)


# -----------------------
# FIND MY MATCH COMMAND
# -----------------------

@bot.tree.command(name="mymatch", description="View your current active match")
@app_commands.guilds(TEST_GUILD)
async def mymatch(interaction: discord.Interaction):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)

    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message(
            "You are not signed up.",
            ephemeral=True
        )
        return

    player = players[user_id]

    found_mode = None
    found_match_id = None

    for mode_name, mode_data in player["modes"].items():
        if mode_data["in_match"] and mode_data["active_match_id"]:
            found_mode = mode_name
            found_match_id = mode_data["active_match_id"]
            break

    if not found_match_id:
        await interaction.response.send_message(
            "You are not currently in an active match.",
            ephemeral=True
        )
        return

    match = active_matches.get(found_match_id)

    if not match:
        await interaction.response.send_message(
            "Your active match record could not be found.",
            ephemeral=True
        )
        return

    team1_names = format_player_names(players, match["team1"]["player_ids"])
    team2_names = format_player_names(players, match["team2"]["player_ids"])

    await interaction.response.send_message(
        f"Match ID: {match['match_id']}\n"
        f"Mode: {match['mode']}\n"
        f"Type: {match['match_type']}\n"
        f"Status: {match['status']}\n"
        f"Team 1: {team1_names}\n"
        f"Team 2: {team2_names}\n"
        f"Created At: {match['created_at']}",
        ephemeral=True
    )

@bot.tree.command(name="finalize1v1", description="Finalize an agreed 1v1 match")
@app_commands.guilds(TEST_GUILD)
async def finalize1v1(
    interaction: discord.Interaction,
    match_id: str,
):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)

    if not (
        interaction.user.guild_permissions.manage_guild
        or is_mod_or_admin(interaction.user)
    ):
        await interaction.response.send_message(
            "You do not have permission to finalize matches.",
            ephemeral=True
        )
        return

    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    completed_matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)

    match_record = active_matches.get(match_id)

    if not match_record:
        await interaction.response.send_message(
            f"No active match found with ID: {match_id}",
            ephemeral=True
        )
        return

    if match_record["mode"] != "1v1":
        await interaction.response.send_message(
            "This command only finalizes 1v1 matches.",
            ephemeral=True
        )
        return

    if match_record["status"] != "awaiting_confirmation":
        await interaction.response.send_message(
            "This match is not ready for finalization.",
            ephemeral=True
        )
        return

    if not match_record["confirmation"]["result_agreed"]:
        await interaction.response.send_message(
            "This match does not have an agreed result.",
            ephemeral=True
        )
        return

    try:
        finalized = finalize_agreed_1v1_match(players, match_record)
        failed_rankups = fail_rankup_if_needed(
            players,
            finalized["winner_ids"] + finalized["loser_ids"],
            "1v1"
        )
    except ValueError as e:
        await interaction.response.send_message(
            f"Finalization failed: {e}",
            ephemeral=True
        )
        return

    completed_matches[match_id] = finalized["completed_record"]
    del active_matches[match_id]

    save_json(PLAYERS_FILE, players)
    save_json(ACTIVE_MATCHES_FILE, active_matches)
    save_json(MATCHES_FILE, completed_matches)

    winner_names = format_player_names(players, finalized["winner_ids"])
    loser_names = format_player_names(players, finalized["loser_ids"])

    spr_lines = []

    for member_id in finalized["winner_ids"]:
        change = finalized["spr_changes"].get(member_id, 0)
        name = players[member_id]["display_name"]
        spr_lines.append(f"{name}: +{change}")

    for member_id in finalized["loser_ids"]:
        change = finalized["spr_changes"].get(member_id, 0)
        name = players[member_id]["display_name"]
        spr_lines.append(f"{name}: {change}")

    failure_lines = []

    for failed in failed_rankups:
        failure_lines.append(
            f"{failed['display_name']} rank-up failed (dropped below Elite)."
        )

    message = (
        f"Match finalized: {match_id}\n"
        f"Winner: {winner_names}\n"
        f"Loser: {loser_names}\n"
        f"SPR Changes:\n" + "\n".join(spr_lines) + "\n"
        f"Result saved to match history."
    )

    if failure_lines:
        message += "\n\nRank-up failures:\n" + "\n".join(failure_lines)

    await interaction.response.send_message(message)

# -----------------------
# DEBUGGING COMMANDS
# -----------------------

@bot.tree.command(name="runmatchmaking1v1", description="Run 1v1 matchmaking")
@app_commands.guilds(TEST_GUILD)
async def runmatchmaking1v1(interaction: discord.Interaction):

    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You dont have permission to use this command.",
            ephemeral=True
        )
        return

    result = run_1v1_matchmaking_pass()

    if result["created_count"] == 0:
        await interaction.response.send_message(
            "No valid 1v1 matches found.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Matches created:\n" + "\n".join(result["created_summaries"])
    )

@bot.tree.command(name="matchtest2v2", description="Test finding the best 2v2 queue match")
@app_commands.guilds(TEST_GUILD)
async def matchtest2v2(interaction: discord.Interaction):
    
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You dont have permission to use this command.",
            ephemeral=True
        )
        return

    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)

    two_v_two_entries = queue_data.get("2v2", [])
    grouped = group_queue_entries_by_class(two_v_two_entries)

    results = []

    for queue_class, entries in grouped.items():
        best_match = find_best_2v2_match_for_class(entries, queue_class)

        if best_match:
            results.append(
                f"Class {queue_class}: "
                f"{best_match['match_kind']} "
                f"(gap: {best_match['average_gap']})"
            )

    if not results:
        await interaction.response.send_message(
            "No valid 2v2 matches found.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "\n".join(results),
        ephemeral=True
    )

@bot.tree.command(name="runmatchmaking2v2", description="Run 2v2 matchmaking")
@app_commands.guilds(TEST_GUILD)
async def runmatchmaking2v2(interaction: discord.Interaction):
    
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You dont have permission to use this command.",
            ephemeral=True
        )
        return

    result = run_2v2_matchmaking_pass()

    if result["created_count"] == 0:
        await interaction.response.send_message(
            "No valid 2v2 matches found.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "2v2 Matches created:\n" + "\n".join(result["created_summaries"]),
        ephemeral=True
    )

@bot.tree.command(name="matchtest3v3", description="Test finding the best 3v3 queue match")
@app_commands.guilds(TEST_GUILD)
async def matchtest3v3(interaction: discord.Interaction):
    
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You dont have permission to use this command.",
            ephemeral=True
        )
        return

    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)

    three_v_three_entries = queue_data.get("3v3", [])
    grouped = group_queue_entries_by_class(three_v_three_entries)

    results = []

    for queue_class, entries in grouped.items():
        best_match = find_best_3v3_match_for_class(entries, queue_class)

        if best_match:
            results.append(
                f"Class {queue_class}: "
                f"{best_match['match_kind']} "
                f"(gap: {best_match['average_gap']})"
            )

    if not results:
        await interaction.response.send_message(
            "No valid 3v3 matches found.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "\n".join(results),
        ephemeral=True
    )

@bot.tree.command(name="runmatchmaking3v3", description="Run 3v3 matchmaking")
@app_commands.guilds(TEST_GUILD)
async def runmatchmaking3v3(interaction: discord.Interaction):
    
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You dont have permission to use this command.",
            ephemeral=True
        )
        return

    result = run_3v3_matchmaking_pass()

    if result["created_count"] == 0:
        await interaction.response.send_message(
            "No valid 3v3 matches found.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "3v3 Matches created:\n" + "\n".join(result["created_summaries"]),
        ephemeral=True
    )