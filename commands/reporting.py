import discord
from discord import app_commands

from bot_instance import bot
from config import TEST_GUILD
from choices import REPORT_RESULT_CHOICES
from data_manager import (
    load_json, save_json,
    PLAYERS_FILE, DEFAULT_PLAYERS,
    ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES,
    DISPUTED_FILE, DEFAULT_DISPUTED,
    MATCHES_FILE, DEFAULT_MATCHES,
)
from utils.player_utils import format_player_names
from utils.reporting_utils import (
    find_player_team_key,
    build_team_report,
    reports_are_complete_for_1v1,
    reports_agree_for_1v1,
    has_team_already_reported,
    reports_are_complete_for_team_match,
    reports_agree_for_team_match,
)
from utils.finalization_utils import (
    finalize_agreed_1v1_match,
    finalize_agreed_2v2_match,
    finalize_agreed_3v3_match,
    fail_rankup_if_needed,
)
from utils.time_utils import utc_now_iso


def build_spr_lines(players: dict, finalized: dict) -> list[str]:
    spr_lines = []

    for member_id in finalized["winner_ids"]:
        change = finalized["spr_changes"].get(member_id, 0)
        name = players[member_id]["display_name"]
        spr_lines.append(f"{name}: +{change}")

    for member_id in finalized["loser_ids"]:
        change = finalized["spr_changes"].get(member_id, 0)
        name = players[member_id]["display_name"]
        spr_lines.append(f"{name}: {change}")

    return spr_lines


@bot.tree.command(name="report1v1", description="Report the result of your active 1v1 match")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(result=REPORT_RESULT_CHOICES)
async def report1v1(
    interaction: discord.Interaction,
    result: app_commands.Choice[str],
):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    disputed_matches = load_json(DISPUTED_FILE, DEFAULT_DISPUTED)
    completed_matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)

    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message("You are not signed up.", ephemeral=True)
        return

    player = players[user_id]
    mode_data = player["modes"]["1v1"]

    if not mode_data["in_match"] or not mode_data["active_match_id"]:
        await interaction.response.send_message(
            "You are not currently in an active 1v1 match.",
            ephemeral=True,
        )
        return

    match_id = mode_data["active_match_id"]
    match_record = active_matches.get(match_id)

    if not match_record:
        await interaction.response.send_message(
            "Your active 1v1 match record could not be found.",
            ephemeral=True,
        )
        return

    if match_record["mode"] != "1v1":
        await interaction.response.send_message(
            "This command only works for 1v1 matches.",
            ephemeral=True,
        )
        return

    team_key = find_player_team_key(match_record, user_id)

    if team_key is None:
        await interaction.response.send_message(
            "You are not part of this match.",
            ephemeral=True,
        )
        return

    timestamp = utc_now_iso()

    match_record["reports"][team_key] = build_team_report(
        team_key=team_key,
        user_id=user_id,
        result=result.value,
        timestamp=timestamp,
    )

    if reports_are_complete_for_1v1(match_record):
        if reports_agree_for_1v1(match_record):
            match_record["status"] = "awaiting_confirmation"
            match_record["confirmation"]["result_agreed"] = True
            match_record["confirmation"]["confirmed_at"] = timestamp

            try:
                finalized = finalize_agreed_1v1_match(players, match_record)
                failed_rankups = fail_rankup_if_needed(
                    players,
                    finalized["winner_ids"] + finalized["loser_ids"],
                    "1v1",
                )
            except ValueError as e:
                save_json(ACTIVE_MATCHES_FILE, active_matches)
                await interaction.response.send_message(
                    f"Reports agreed, but finalization failed: {e}",
                    ephemeral=True,
                )
                return

            completed_matches[match_id] = finalized["completed_record"]
            del active_matches[match_id]

            save_json(PLAYERS_FILE, players)
            save_json(ACTIVE_MATCHES_FILE, active_matches)
            save_json(MATCHES_FILE, completed_matches)

            winner_names = format_player_names(players, finalized["winner_ids"])
            loser_names = format_player_names(players, finalized["loser_ids"])
            spr_lines = build_spr_lines(players, finalized)

            failure_lines = []
            for failed in failed_rankups:
                failure_lines.append(
                    f"{failed['display_name']} rank-up failed (dropped below Elite)."
                )

            rankup_lines = []
            rankup_result = finalized["completed_record"]["rankup_result"]
            if rankup_result["series_status"] is not None:
                rankup_player_id = rankup_result["rankup_player_id"]
                rankup_name = players[rankup_player_id]["display_name"]
                rankup_lines.append(
                    f"Rank-up: {rankup_name} is now "
                    f"{rankup_result['series_wins_after_match']}-"
                    f"{rankup_result['series_losses_after_match']} "
                    f"({rankup_result['series_status']})"
                )

            extra_sections = []
            if failure_lines:
                extra_sections.append("\n".join(failure_lines))
            if rankup_lines:
                extra_sections.append("\n".join(rankup_lines))

            extra_text = ""
            if extra_sections:
                extra_text = "\n\n" + "\n\n".join(extra_sections)

            await interaction.response.send_message(
                f"Report accepted.\n"
                f"Both players agreed on the result.\n"
                f"Match finalized automatically.\n"
                f"Winner: {winner_names}\n"
                f"Loser: {loser_names}\n\n"
                f"SPR Changes:\n" + "\n".join(spr_lines) + extra_text
            )
            return

        match_record["status"] = "mod_review"
        match_record["moved_to_disputed_at"] = timestamp
        match_record["dispute"] = {
            "reason": "conflicting_reports",
            "resolved": False,
            "resolved_by": None,
            "resolved_at": None,
            "final_winner": None,
            "notes": "",
        }

        disputed_matches[match_id] = match_record
        del active_matches[match_id]

        save_json(ACTIVE_MATCHES_FILE, active_matches)
        save_json(DISPUTED_FILE, disputed_matches)

        await interaction.response.send_message(
            "Report accepted, but the match has conflicting results and was moved to moderator review."
        )
        return

    save_json(ACTIVE_MATCHES_FILE, active_matches)
    await interaction.response.send_message(
        f"Your result was recorded as {result.value}. Waiting for the other player to report."
    )


@bot.tree.command(name="report2v2", description="Report the result of your active 2v2 match")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(result=REPORT_RESULT_CHOICES)
async def report2v2(
    interaction: discord.Interaction,
    result: app_commands.Choice[str],
):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    disputed_matches = load_json(DISPUTED_FILE, DEFAULT_DISPUTED)
    completed_matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)

    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message("You are not signed up.", ephemeral=True)
        return

    player = players[user_id]
    mode_data = player["modes"]["2v2"]

    if not mode_data["in_match"] or not mode_data["active_match_id"]:
        await interaction.response.send_message(
            "You are not currently in an active 2v2 match.",
            ephemeral=True,
        )
        return

    match_id = mode_data["active_match_id"]
    match_record = active_matches.get(match_id)

    if not match_record:
        await interaction.response.send_message(
            "Your active 2v2 match record could not be found.",
            ephemeral=True,
        )
        return

    if match_record["mode"] != "2v2":
        await interaction.response.send_message(
            "This command only works for 2v2 matches.",
            ephemeral=True,
        )
        return

    team_key = find_player_team_key(match_record, user_id)

    if team_key is None:
        await interaction.response.send_message(
            "You are not part of this match.",
            ephemeral=True,
        )
        return

    if has_team_already_reported(match_record, team_key):
        await interaction.response.send_message(
            "Your team has already submitted a report for this match.",
            ephemeral=True,
        )
        return

    timestamp = utc_now_iso()

    match_record["reports"][team_key] = build_team_report(
        team_key=team_key,
        user_id=user_id,
        result=result.value,
        timestamp=timestamp,
    )

    if reports_are_complete_for_team_match(match_record):
        if reports_agree_for_team_match(match_record):
            match_record["status"] = "awaiting_confirmation"
            match_record["confirmation"]["result_agreed"] = True
            match_record["confirmation"]["confirmed_at"] = timestamp

            try:
                finalized = finalize_agreed_2v2_match(players, match_record)
            except ValueError as e:
                save_json(ACTIVE_MATCHES_FILE, active_matches)
                await interaction.response.send_message(
                    f"Reports agreed, but finalization failed: {e}",
                    ephemeral=True,
                )
                return

            completed_matches[match_id] = finalized["completed_record"]
            del active_matches[match_id]

            save_json(PLAYERS_FILE, players)
            save_json(ACTIVE_MATCHES_FILE, active_matches)
            save_json(MATCHES_FILE, completed_matches)

            winner_names = format_player_names(players, finalized["winner_ids"])
            loser_names = format_player_names(players, finalized["loser_ids"])
            spr_lines = build_spr_lines(players, finalized)

            await interaction.response.send_message(
                f"Report accepted.\n"
                f"Both teams agreed on the result.\n"
                f"Match finalized automatically.\n"
                f"Winner: {winner_names}\n"
                f"Loser: {loser_names}\n\n"
                f"SPR Changes:\n" + "\n".join(spr_lines)
            )
            return

        match_record["status"] = "mod_review"
        match_record["moved_to_disputed_at"] = timestamp
        match_record["dispute"] = {
            "reason": "conflicting_reports",
            "resolved": False,
            "resolved_by": None,
            "resolved_at": None,
            "final_winner": None,
            "notes": "",
        }

        disputed_matches[match_id] = match_record
        del active_matches[match_id]

        save_json(ACTIVE_MATCHES_FILE, active_matches)
        save_json(DISPUTED_FILE, disputed_matches)

        await interaction.response.send_message(
            "Report accepted, but the match has conflicting team reports and was moved to moderator review."
        )
        return

    save_json(ACTIVE_MATCHES_FILE, active_matches)
    await interaction.response.send_message(
        f"Your team's result was recorded as {result.value}. Waiting for the other team to report."
    )


@bot.tree.command(name="report3v3", description="Report the result of your active 3v3 match")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(result=REPORT_RESULT_CHOICES)
async def report3v3(
    interaction: discord.Interaction,
    result: app_commands.Choice[str],
):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    disputed_matches = load_json(DISPUTED_FILE, DEFAULT_DISPUTED)
    completed_matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)

    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message("You are not signed up.", ephemeral=True)
        return

    player = players[user_id]
    mode_data = player["modes"]["3v3"]

    if not mode_data["in_match"] or not mode_data["active_match_id"]:
        await interaction.response.send_message(
            "You are not currently in an active 3v3 match.",
            ephemeral=True,
        )
        return

    match_id = mode_data["active_match_id"]
    match_record = active_matches.get(match_id)

    if not match_record:
        await interaction.response.send_message(
            "Your active 3v3 match record could not be found.",
            ephemeral=True,
        )
        return

    if match_record["mode"] != "3v3":
        await interaction.response.send_message(
            "This command only works for 3v3 matches.",
            ephemeral=True,
        )
        return

    team_key = find_player_team_key(match_record, user_id)

    if team_key is None:
        await interaction.response.send_message(
            "You are not part of this match.",
            ephemeral=True,
        )
        return

    if has_team_already_reported(match_record, team_key):
        await interaction.response.send_message(
            "Your team has already submitted a report for this match.",
            ephemeral=True,
        )
        return

    timestamp = utc_now_iso()

    match_record["reports"][team_key] = build_team_report(
        team_key=team_key,
        user_id=user_id,
        result=result.value,
        timestamp=timestamp,
    )

    if reports_are_complete_for_team_match(match_record):
        if reports_agree_for_team_match(match_record):
            match_record["status"] = "awaiting_confirmation"
            match_record["confirmation"]["result_agreed"] = True
            match_record["confirmation"]["confirmed_at"] = timestamp

            try:
                finalized = finalize_agreed_3v3_match(players, match_record)
            except ValueError as e:
                save_json(ACTIVE_MATCHES_FILE, active_matches)
                await interaction.response.send_message(
                    f"Reports agreed, but finalization failed: {e}",
                    ephemeral=True,
                )
                return

            completed_matches[match_id] = finalized["completed_record"]
            del active_matches[match_id]

            save_json(PLAYERS_FILE, players)
            save_json(ACTIVE_MATCHES_FILE, active_matches)
            save_json(MATCHES_FILE, completed_matches)

            winner_names = format_player_names(players, finalized["winner_ids"])
            loser_names = format_player_names(players, finalized["loser_ids"])
            spr_lines = build_spr_lines(players, finalized)

            await interaction.response.send_message(
                f"Report accepted.\n"
                f"Both teams agreed on the result.\n"
                f"Match finalized automatically.\n"
                f"Winner: {winner_names}\n"
                f"Loser: {loser_names}\n\n"
                f"SPR Changes:\n" + "\n".join(spr_lines)
            )
            return

        match_record["status"] = "mod_review"
        match_record["moved_to_disputed_at"] = timestamp
        match_record["dispute"] = {
            "reason": "conflicting_reports",
            "resolved": False,
            "resolved_by": None,
            "resolved_at": None,
            "final_winner": None,
            "notes": "",
        }

        disputed_matches[match_id] = match_record
        del active_matches[match_id]

        save_json(ACTIVE_MATCHES_FILE, active_matches)
        save_json(DISPUTED_FILE, disputed_matches)

        await interaction.response.send_message(
            "Report accepted, but the match has conflicting team reports and was moved to moderator review."
        )
        return

    save_json(ACTIVE_MATCHES_FILE, active_matches)
    await interaction.response.send_message(
        f"Your team's result was recorded as {result.value}. Waiting for the other team to report."
    )
