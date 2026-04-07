import discord
from discord import app_commands

from bot_instance import bot
from config import TEST_GUILD
from utils.player_utils import utc_now_iso
from choices import RESOLVE_OUTCOME_CHOICES
from data_manager import (
    load_json, save_json,
    PLAYERS_FILE, DEFAULT_PLAYERS,
    QUEUE_FILE, DEFAULT_QUEUE,
    DISPUTED_FILE, DEFAULT_DISPUTED,
    MATCHES_FILE, DEFAULT_MATCHES,
    ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES
)
from utils.player_utils import format_player_names
from utils.finalization_utils import (
    clear_players_from_disputed_match,
    create_completed_match_record,
    finalize_resolved_team_match,
)
from utils.match_utils import get_match_participant_ids
from utils.rank_utils import get_class_from_spr, get_tier_from_spr
from utils.permissions_utils import is_mod_or_admin
from utils.mod_utils import build_modhelp_embed, remove_player_from_queue_data
from utils.state_utils import rebuild_player_state_from_files, rebuild_multiple_players_state, clear_player_runtime_flags
from commands.spr_group import mod_group

MODES = ["1v1", "2v2", "3v3"]


@mod_group.command(name="playerinfo", description="View detailed info for a player")
async def playerinfo(
    interaction: discord.Interaction,
    member: discord.Member,
):
    # -----------------------
    # Permission check
    # -----------------------
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)

    user_id = str(member.id)

    if user_id not in players:
        await interaction.response.send_message(
            f"{member.display_name} is not signed up.",
            ephemeral=True
        )
        return

    player = players[user_id]

    lines = []

    # -----------------------
    # Basic info
    # -----------------------
    lines.append(f"Player: {player['display_name']}")
    lines.append(f"User ID: {player['user_id']}")
    lines.append(f"Signup Rank Role: {player['signup_rank_role']}")
    lines.append(f"Signed Up: {player['signed_up']}")
    lines.append(f"Is Mod: {player.get('is_mod', False)}")
    lines.append(f"Incorrect Reports: {player.get('incorrect_reports', 0)}")
    lines.append(f"Banned From Ranked: {player.get('is_banned_from_ranked', False)}")
    lines.append(f"Joined At: {player.get('joined_at', 'None')}")
    lines.append("")

    # -----------------------
    # Mode data
    # -----------------------
    for mode in MODES:
        mode_data = player["modes"][mode]
        spr = mode_data["spr"]

        class_name = get_class_from_spr(spr)
        tier_name = get_tier_from_spr(spr)

        lines.append(f"{mode}")
        lines.append(f"SPR: {spr}")
        lines.append(f"Class: {class_name}")
        lines.append(f"Tier: {tier_name}")
        lines.append(
            f"W/L: {mode_data['wins']}/{mode_data['losses']} "
            f"(Matches: {mode_data['matches_played']})"
        )
        lines.append(f"Streak: {mode_data['streak']}")
        lines.append(f"Peak SPR: {mode_data['peak_spr']}")
        lines.append(f"Last Match At: {mode_data['last_match_at']}")
        lines.append(f"In Queue: {mode_data['in_queue']}")
        lines.append(f"In Match: {mode_data['in_match']}")
        lines.append(f"Active Match ID: {mode_data['active_match_id']}")

        lines.append(f"Rank-up Active: {mode_data.get('rankup_active', False)}")
        lines.append(f"Rank-up Target Class: {mode_data.get('rankup_target_class')}")
        lines.append(f"Rank-up Started At: {mode_data.get('rankup_started_at')}")
        lines.append(f"Rank-up Wins: {mode_data.get('rankup_wins', 0)}")
        lines.append(f"Rank-up Losses: {mode_data.get('rankup_losses', 0)}")
        lines.append(f"Rank-up History Count: {len(mode_data.get('rankup_history', []))}")
        lines.append("")

    await interaction.response.send_message(
        "\n".join(lines),
        ephemeral=True
    )

@mod_group.command(name="repairplayer", description="Reset a player's queue and match state to match files. If match needs cancel use /spr cancelmatch")
async def repairplayer(interaction: discord.Interaction, member: discord.Member):
    

    player_id = str(member.id)

    if not is_mod_or_admin(interaction.user):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True
            )
            return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)

    if player_id not in players:
        await interaction.response.send_message(
            f"{member.display_name} is not signed up.",
            ephemeral=True
        )
        return

    player = players[player_id]

    removed_count = remove_player_from_queue_data(queue_data, player_id)

    clear_player_runtime_flags(player)

    rebuild_player_state_from_files(
        player_id=player_id,
        players=players,
        queue_data=queue_data,
        active_matches=active_matches,
    )

    save_json(QUEUE_FILE, queue_data)
    save_json(ACTIVE_MATCHES_FILE, active_matches)
    save_json(PLAYERS_FILE, players)

    await interaction.response.send_message(
        f"Repaired state for {member.display_name}.\n"
        f"Removed from {removed_count} queue entries.",
        ephemeral=True
    )

@mod_group.command(name="viewdisputes", description="View disputed matches")
async def viewdisputes(interaction: discord.Interaction):
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    disputed_matches = load_json(DISPUTED_FILE, DEFAULT_DISPUTED)

    if not disputed_matches:
        await interaction.response.send_message(
            "There are no disputed matches right now.",
            ephemeral=True
        )
        return

    lines = []

    for match in disputed_matches.values():
        team1_names = format_player_names(players, match["team1"]["player_ids"])
        team2_names = format_player_names(players, match["team2"]["player_ids"])

        dispute = match.get("dispute", {})
        kind = dispute.get("kind", "unknown")
        reason = dispute.get("reason", "unknown")

        lines.append(
            f"Match ID: {match['match_id']}\n"
            f"Mode: {match['mode']}\n"
            f"Status: {match.get('status', 'disputed')}\n"
            f"{team1_names} vs {team2_names}\n"
            f"Dispute Type: {kind}\n"
            f"Reason: {reason}\n"
        )
        
    
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

    

    

@mod_group.command(name="resolve", description="Resolve a disputed match")
@app_commands.choices(outcome=RESOLVE_OUTCOME_CHOICES)
async def resolve(
    interaction: discord.Interaction,
    match_id: str,
    outcome: app_commands.Choice[str],
):
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    disputed_matches = load_json(DISPUTED_FILE, DEFAULT_DISPUTED)
    completed_matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)

    match_record = disputed_matches.get(match_id)

    if not match_record:
        await interaction.response.send_message(
            f"No disputed match found with ID: {match_id}",
            ephemeral=True
        )
        return

    mode = match_record.get("mode")
    if mode not in MODES:
        await interaction.response.send_message(
            "This dispute has an invalid or unsupported mode.",
            ephemeral=True
        )
        return

    selected_outcome = outcome.value
    completed_at = utc_now_iso()

    team1_ids = [str(x) for x in match_record["team1"]["player_ids"]]
    team2_ids = [str(x) for x in match_record["team2"]["player_ids"]]
    all_member_ids = team1_ids + team2_ids

    dispute_reason = "unknown"
    if match_record.get("dispute"):
        dispute_reason = match_record["dispute"].get("reason", "unknown")

    # Validate players exist and capture pre-match SPR for the correct mode
    pre_match_spr = {}
    for member_id in all_member_ids:
        if member_id not in players:
            await interaction.response.send_message(
                f"Resolve failed: player data missing for {member_id}.",
                ephemeral=True
            )
            return

        players[member_id].setdefault("incorrect_reports", 0)
        pre_match_spr[member_id] = players[member_id]["modes"][mode]["spr"]

    # -----------------------
    # Outcome: disregard
    # -----------------------
    if selected_outcome == "disregard":
        clear_players_from_disputed_match(players, match_record, mode)

        post_match_spr = {
            member_id: players[member_id]["modes"][mode]["spr"]
            for member_id in all_member_ids
        }

        completed_record = create_completed_match_record(
            match_record=match_record,
            completed_at=completed_at,
            winner_team=None,
            loser_team=None,
            resolved_by=str(interaction.user.id),
            was_disputed=True,
            dispute_reason=dispute_reason,
            final_outcome="disregard",
            spr_changes={},
            pre_match_spr=pre_match_spr,
            post_match_spr=post_match_spr,
            rankup_result=None,
        )

        completed_matches[match_id] = completed_record
        del disputed_matches[match_id]

        queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
        active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)

        participant_ids = get_match_participant_ids(match_record)

        rebuild_multiple_players_state(
            player_ids=participant_ids,
            players=players,
            queue_data=queue_data,
            active_matches=active_matches,
        )

        save_json(PLAYERS_FILE, players)
        save_json(DISPUTED_FILE, disputed_matches)
        save_json(MATCHES_FILE, completed_matches)

        await interaction.response.send_message(
            f"Dispute resolved for {match_id}.\n"
            f"Mode: {mode}\n"
            f"Outcome: disregard\n"
            f"No SPR or stats were changed.",
            ephemeral=True
        )
        return

    # -----------------------
    # Outcome: team1 / team2
    # -----------------------
    if selected_outcome not in ["team1", "team2"]:
        await interaction.response.send_message(
            "Invalid outcome.",
            ephemeral=True
        )
        return

    try:
        finalized = finalize_resolved_team_match(
            players=players,
            match_record=match_record,
            selected_outcome=selected_outcome,
        )
    except ValueError as e:
        await interaction.response.send_message(
            f"Resolve failed: {e}",
            ephemeral=True
        )
        return

    completed_record = create_completed_match_record(
        match_record=match_record,
        completed_at=completed_at,
        winner_team=finalized["winner_team"],
        loser_team=finalized["loser_team"],
        resolved_by=str(interaction.user.id),
        was_disputed=True,
        dispute_reason=dispute_reason,
        final_outcome=selected_outcome,
        spr_changes=finalized["spr_changes"],
        pre_match_spr=finalized["pre_match_spr"],
        post_match_spr=finalized["post_match_spr"],
        rankup_result=finalized["rankup_result"],
    )

    completed_matches[match_id] = completed_record
    del disputed_matches[match_id]

    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)

    participant_ids = get_match_participant_ids(match_record)

    rebuild_multiple_players_state(
        player_ids=participant_ids,
        players=players,
        queue_data=queue_data,
        active_matches=active_matches,
    )

    save_json(PLAYERS_FILE, players)
    save_json(DISPUTED_FILE, disputed_matches)
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

    failure_lines = [
        f"{item['display_name']} rank-up failed (dropped below Elite)."
        for item in finalized["failed_rankups"]
    ]

    incorrect_report_lines = [
        players[rid]["display_name"] if rid in players else rid
        for rid in finalized["incorrect_reporter_ids"]
    ]

    extra = []
    if incorrect_report_lines:
        extra.append("Incorrect Reports Given To: " + ", ".join(incorrect_report_lines))
    if failure_lines:
        extra.extend(failure_lines)

    message = (
        f"Dispute resolved for {match_id}.\n"
        f"Mode: {mode}\n"
        f"Outcome: {selected_outcome}\n"
        f"Winner: {winner_names}\n"
        f"Loser: {loser_names}\n\n"
        f"SPR Changes:\n" + "\n".join(spr_lines)
    )

    if extra:
        message += "\n\n" + "\n".join(extra)

    await interaction.response.send_message(message, ephemeral=True)

# -----------------------
# active matches command
# -----------------------

@mod_group.command(name="active1v1matches", description="View active 1v1 matches")
async def active1v1matches(interaction: discord.Interaction):
    # -----------------------
    # Permission check
    # -----------------------

    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)

    one_v_one_matches = [
        match for match in active_matches.values()
        if match["mode"] == "1v1"
    ]

    if not one_v_one_matches:
        await interaction.response.send_message(
            "There are no active 1v1 matches right now.",
            ephemeral=True
        )
        return

    lines = []

    for match in one_v_one_matches:
        team1_names = format_player_names(players, match["team1"]["player_ids"])
        team2_names = format_player_names(players, match["team2"]["player_ids"])

        lines.append(
            f"Match ID: {match['match_id']}\n"
            f"{team1_names} vs {team2_names}\n"
            f"Status: {match['status']}\n"
            f"Class: {match['team1']['queue_class']}\n"
        )

    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@mod_group.command(name="cancelmatch", description="Cancel an active match")
async def cancelmatch(
    interaction: discord.Interaction,
    match_id: str,
):
    # -----------------------
    # Permission check
    # -----------------------
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)

    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    completed_matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)

    match_record = active_matches.get(match_id)
    if not match_record:
        await interaction.response.send_message("Match not found.", ephemeral=True)
        return

    participant_ids = get_match_participant_ids(match_record)

    match_record["status"] = "cancelled"
    match_record["completed_at"] = utc_now_iso()
    completed_matches[match_id] = match_record

    del active_matches[match_id]

    rebuild_multiple_players_state(
        player_ids=participant_ids,
        players=players,
        queue_data=queue_data,
        active_matches=active_matches,
    )

    save_json(ACTIVE_MATCHES_FILE, active_matches)
    save_json(MATCHES_FILE, completed_matches)
    save_json(PLAYERS_FILE, players)

    
    mode = match_record["mode"]
    team1_ids = match_record["team1"]["player_ids"]
    team2_ids = match_record["team2"]["player_ids"]

    team1_names = format_player_names(players, team1_ids)
    team2_names = format_player_names(players, team2_ids)
    resolver_name = interaction.user.display_name


    await interaction.response.send_message(
        f"Active match cancelled.\n"
        f"Match ID: {match_id}\n"
        f"Cancelled By: {resolver_name}\n"
        f"Mode: {mode}\n"
        f"Team 1: {team1_names}\n"
        f"Team 2: {team2_names}\n"
        f"Status Saved: cancelled\n"
        f"No SPR or stats were changed.",
        ephemeral=True
    )

@mod_group.command(name="repairstate", description="Repair one player's queue and match flags from queue.json and active_matches.json")
async def repairstate(interaction: discord.Interaction, member: discord.Member):
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    player_id = str(member.id)

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)

    if player_id not in players:
        await interaction.response.send_message(
            f"{member.display_name} is not signed up.",
            ephemeral=True
        )
        return

    # Snapshot old state for response
    old_lines = []
    for mode in MODES:
        mode_data = players[player_id].get("modes", {}).get(mode)
        if not mode_data:
            continue

        old_lines.append(
            f"{mode}: in_queue={mode_data.get('in_queue')}, "
            f"in_match={mode_data.get('in_match')}, "
            f"active_match_id={mode_data.get('active_match_id')}"
        )

    try:
        summary = rebuild_player_state_from_files(
            player_id=player_id,
            players=players,
            queue_data=queue_data,
            active_matches=active_matches,
        )
    except ValueError as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return

    save_json(PLAYERS_FILE, players)

    # Snapshot new state for response
    new_lines = []
    for mode in MODES:
        mode_data = players[player_id].get("modes", {}).get(mode)
        if not mode_data:
            continue

        new_lines.append(
            f"{mode}: in_queue={mode_data.get('in_queue')}, "
            f"in_match={mode_data.get('in_match')}, "
            f"active_match_id={mode_data.get('active_match_id')}"
        )

    queue_hits = summary["queue_hits"]
    active_hits = summary["active_match_hits"]

    details = []
    details.append(f"Repaired state for **{member.display_name}** (`{player_id}`)\n")
    details.append("**Before:**")
    details.extend(old_lines)
    details.append("")
    details.append("**After:**")
    details.extend(new_lines)
    details.append("")

    if queue_hits:
        details.append("**Found in queue.json:**")
        details.extend(f"- {x}" for x in queue_hits)
        details.append("")
    else:
        details.append("**Found in queue.json:** none\n")

    if active_hits:
        details.append("**Found in active_matches.json:**")
        details.extend(f"- {x}" for x in active_hits)
    else:
        details.append("**Found in active_matches.json:** none")

    await interaction.response.send_message("\n".join(details), ephemeral=True)


@mod_group.command(name="modhelp", description="Show moderator commands and tools")
async def modhelp_command(interaction: discord.Interaction):
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True,
        )
        return

    embed = build_modhelp_embed(interaction.user)
    await interaction.response.send_message(embed=embed, ephemeral=True)