from utils.rank_utils import clamp_spr_to_class_cap
from utils.rankup_utils import (
    should_fail_rankup_for_spr,
    record_rankup_history_entry,
    clear_rankup_for_mode,
    apply_rankup_match_loss,
    apply_rankup_match_win,
    get_rankup_series_status,
    get_promoted_spr,
    apply_team_rankup_progress_to_participants,
)
from utils.time_utils import utc_now_iso


# -----------------------
# Winner / loser helpers
# -----------------------

def get_winner_and_loser_team_keys_from_reports(match_record: dict) -> tuple[str, str] | None:
    # Determine winner and loser from agreed 1v1 reports

    team1_result = match_record["reports"]["team1"]["result"]
    team2_result = match_record["reports"]["team2"]["result"]

    if team1_result == "win" and team2_result == "loss":
        return "team1", "team2"

    if team1_result == "loss" and team2_result == "win":
        return "team2", "team1"

    return None


# -----------------------
# SPR helpers
# -----------------------

def get_win_spr_gain(current_streak: int) -> int:
    # Win = 10 SPR
    # Streak bonus starts after more than three wins, so if current streak >= 3 before this win, gain 15
    if current_streak >= 3:
        return 15
    return 10


def get_loss_spr_change() -> int:
    # Loss = -8 SPR
    return -8


def apply_win_to_player_mode(mode_data: dict) -> int:
    # Apply a win to one mode block and return SPR gain used

    old_spr = mode_data["spr"]
    spr_gain = get_win_spr_gain(mode_data["streak"])

    new_spr = old_spr + spr_gain
    mode_data["spr"] = clamp_spr_to_class_cap(old_spr, new_spr)

    actual_gain = mode_data["spr"] - old_spr

    mode_data["wins"] += 1
    mode_data["matches_played"] += 1
    mode_data["streak"] += 1

    if mode_data["spr"] > mode_data["peak_spr"]:
        mode_data["peak_spr"] = mode_data["spr"]

    mode_data["last_match_at"] = utc_now_iso()

    return actual_gain


def apply_loss_to_player_mode(mode_data: dict) -> int:
    # Apply a loss to one mode block and return SPR change used

    old_spr = mode_data["spr"]
    spr_change = get_loss_spr_change()

    new_spr = old_spr + spr_change
    mode_data["spr"] = clamp_spr_to_class_cap(old_spr, new_spr)

    actual_change = mode_data["spr"] - old_spr

    mode_data["losses"] += 1
    mode_data["matches_played"] += 1
    mode_data["streak"] = 0
    mode_data["last_match_at"] = utc_now_iso()

    return actual_change


# -----------------------
# Player match-state helpers
# -----------------------
def get_match_participant_ids(match_record: dict) -> list[str]:
    return (
        [str(x) for x in match_record.get("team1", {}).get("player_ids", [])]
        + [str(x) for x in match_record.get("team2", {}).get("player_ids", [])]
    )
def clear_players_from_match(players_data: dict, member_ids: list[str], mode: str) -> None:
    # Clear active match state for players in one mode

    for member_id in member_ids:
        member_id = str(member_id)

        if member_id not in players_data:
            continue

        mode_data = players_data[member_id]["modes"][mode]
        mode_data["in_match"] = False
        mode_data["active_match_id"] = None



# -----------------------
# Rank-up series progress
# -----------------------

def apply_rankup_progress_if_needed(
    players_data: dict,
    match_record: dict,
    winner_ids: list[str],
    loser_ids: list[str],
) -> dict | None:
    mode = match_record["mode"]

    # 1v1 rank-up path
    if match_record.get("rankup_match", False):
        rankup_player_id = match_record.get("rankup_player_id")
        if not rankup_player_id:
            return None

        rankup_player_id = str(rankup_player_id)
        if rankup_player_id not in players_data:
            return None

        mode_data = players_data[rankup_player_id]["modes"][mode]
        if not mode_data.get("rankup_active", False):
            return None

        if rankup_player_id in winner_ids:
            apply_rankup_match_win(mode_data)
        elif rankup_player_id in loser_ids:
            apply_rankup_match_loss(mode_data)
        else:
            return None

        wins_after_match = mode_data["rankup_wins"]
        losses_after_match = mode_data["rankup_losses"]
        series_status = get_rankup_series_status(mode_data)

        if series_status == "success":
            target_class = mode_data.get("rankup_target_class")
            promoted_spr = get_promoted_spr(target_class) if target_class else None
            if promoted_spr is not None:
                mode_data["spr"] = promoted_spr
                if mode_data["spr"] > mode_data["peak_spr"]:
                    mode_data["peak_spr"] = mode_data["spr"]

            record_rankup_history_entry(mode_data, "success")
            clear_rankup_for_mode(mode_data)

        elif series_status == "failed":
            record_rankup_history_entry(mode_data, "failed")
            clear_rankup_for_mode(mode_data)

        return {
            "rankup_player_id": rankup_player_id,
            "rankup_participants": [rankup_player_id],
            "series_wins_after_match": wins_after_match,
            "series_losses_after_match": losses_after_match,
            "series_status": series_status,
        }

    # 2v2 / 3v3 rank-up path
    if match_record.get("is_rankup", False):
        rankup_participants = [str(x) for x in match_record.get("rankup_participants", [])]
        if not rankup_participants:
            return None

        did_win = any(player_id in winner_ids for player_id in rankup_participants)

        progress = apply_team_rankup_progress_to_participants(
            players=players_data,
            participant_ids=rankup_participants,
            did_win=did_win,
            mode=mode,
        )

        return {
            "rankup_player_id": match_record.get("rankup_owner_id"),
            "rankup_participants": rankup_participants,
            "series_wins_after_match": None,
            "series_losses_after_match": None,
            "series_status": "ongoing",
            "team_progress": progress,
        }

    return None


# -----------------------
# Completed match builder
# -----------------------

def create_completed_match_record(
    match_record: dict,
    completed_at: str,
    winner_team: dict | None,
    loser_team: dict | None,
    resolved_by: str = "system",
    was_disputed: bool = False,
    dispute_reason: str | None = None,
    final_outcome: str | None = None,
    spr_changes: dict | None = None,
    pre_match_spr: dict | None = None,
    post_match_spr: dict | None = None,
    rankup_result: dict | None = None,
    
    ) -> dict:
    # Build the completed-match archive record using the agreed fixed schema

    return {
        "match_id": match_record["match_id"],
        "mode": match_record["mode"],
        "match_type": match_record["match_type"],
        "status": "completed",

        "created_at": match_record["created_at"],
        "completed_at": completed_at,

        "ranked": match_record.get("ranked", True),
        "rankup_match": match_record.get("rankup_match", False),
        "rankup_player_id": match_record.get("rankup_player_id"),
        "rankup_target_class": match_record.get("rankup_target_class"),
        "is_rankup": match_record.get("is_rankup", False),
        "rankup_owner_id": match_record.get("rankup_owner_id"),
        "rankup_participants": match_record.get("rankup_participants", []),

        "team1": match_record.get("team1"),
        "team2": match_record.get("team2"),

        "winner": winner_team,
        "loser": loser_team,

        "reports": match_record["reports"],

        "resolution": {
            "resolved_by": resolved_by,
            "was_disputed": was_disputed,
            "dispute_reason": dispute_reason,
            "final_outcome": final_outcome
        },

        "spr_changes": spr_changes if spr_changes is not None else {},
        "pre_match_spr": pre_match_spr if pre_match_spr is not None else {},
        "post_match_spr": post_match_spr if post_match_spr is not None else {},

        "rankup_result": rankup_result if rankup_result is not None else {
            "series_wins_after_match": None,
            "series_losses_after_match": None,
            "series_status": None
        }
    }

# -----------------------
# Cancelled match builder
# -----------------------

def create_cancelled_match_record(
    match_record: dict,
    cancelled_at: str,
    cancelled_by: str,
    ) -> dict:
    # Build a cancelled-match archive record

    return {
        "match_id": match_record["match_id"],
        "mode": match_record["mode"],
        "match_type": match_record["match_type"],
        "status": "cancelled",

        "created_at": match_record["created_at"],
        "completed_at": None,
        "cancelled_at": cancelled_at,

        "ranked": match_record.get("ranked", True),
        "rankup_match": match_record.get("rankup_match", False),
        "rankup_player_id": match_record.get("rankup_player_id"),
        "rankup_target_class": match_record.get("rankup_target_class"),
        "is_rankup": match_record.get("is_rankup", False),
        "rankup_owner_id": match_record.get("rankup_owner_id"),
        "rankup_participants": match_record.get("rankup_participants", []),

        "team1": match_record["team1"],
        "team2": match_record["team2"],

        "winner": None,
        "loser": None,

        "reports": match_record.get("reports", {
            "team1": {
                "reported_by": None,
                "result": None,
                "reported_at": None
            },
            "team2": {
                "reported_by": None,
                "result": None,
                "reported_at": None
            }
        }),

        "resolution": {
            "resolved_by": cancelled_by,
            "was_disputed": False,
            "dispute_reason": None,
            "final_outcome": "cancelled"
        },

        "spr_changes": {},
        "pre_match_spr": {},
        "post_match_spr": {},

        "rankup_result": {
            "series_wins_after_match": None,
            "series_losses_after_match": None,
            "series_status": None
        }
    }

# -----------------------
# Dispute resolution helpers
# -----------------------

def increment_incorrect_reports_for_resolved_match(
    players_data: dict,
    match_record: dict,
    final_outcome: str,
    ) -> None:
    # Increase incorrect_reports for players whose submitted report conflicts
    # with the moderator-selected final outcome.
    #
    # final_outcome should be:
    # - "team1"
    # - "team2"
    # - "disregard"

    if final_outcome == "disregard":
        return

    correct_team_key = final_outcome
    incorrect_team_key = "team2" if final_outcome == "team1" else "team1"

    correct_result = "win"
    incorrect_result = "loss"

    for team_key in ["team1", "team2"]:
        report = match_record["reports"][team_key]
        reported_by = report.get("reported_by")
        reported_result = report.get("result")

        if not reported_by or reported_result is None:
            continue

        if reported_by not in players_data:
            continue

        was_correct = False

        if team_key == correct_team_key and reported_result == correct_result:
            was_correct = True
        elif team_key == incorrect_team_key and reported_result == incorrect_result:
            was_correct = True

        if not was_correct:
            if "incorrect_reports" not in players_data[reported_by]:
                players_data[reported_by]["incorrect_reports"] = 0

            players_data[reported_by]["incorrect_reports"] += 1

def clear_players_from_disputed_match(players_data: dict, match_record: dict, mode: str) -> None:
    member_ids = (
        [str(x) for x in match_record["team1"]["player_ids"]]
        + [str(x) for x in match_record["team2"]["player_ids"]]
    )
    clear_players_from_match(players_data, member_ids, mode)

# -----------------------
# Agreed finalization helper
# -----------------------

def finalize_agreed_1v1_match(
    players: dict,
    match_record: dict,
) -> dict:
    # Finalize an agreed 1v1 match in memory and return the completed record pieces

    winner_loser = get_winner_and_loser_team_keys_from_reports(match_record)

    if not winner_loser:
        raise ValueError("Could not determine winner and loser from agreed reports.")

    winner_key, loser_key = winner_loser
    winner_team = match_record[winner_key]
    loser_team = match_record[loser_key]

    winner_ids = [str(member_id) for member_id in winner_team["player_ids"]]
    loser_ids = [str(member_id) for member_id in loser_team["player_ids"]]
    all_member_ids = winner_ids + loser_ids

    pre_match_spr = {}
    spr_changes = {}
    post_match_spr = {}

    # -----------------------
    # Capture pre-match SPR
    # -----------------------
    for member_id in all_member_ids:
        if member_id not in players:
            raise ValueError(f"Player data missing for {member_id}.")

        pre_match_spr[member_id] = players[member_id]["modes"]["1v1"]["spr"]

    # -----------------------
    # Apply win/loss updates
    # -----------------------
    for member_id in winner_ids:
        mode_data = players[member_id]["modes"]["1v1"]
        spr_changes[member_id] = apply_win_to_player_mode(mode_data)

    for member_id in loser_ids:
        mode_data = players[member_id]["modes"]["1v1"]
        spr_changes[member_id] = apply_loss_to_player_mode(mode_data)

    
    # -----------------------
    # Apply rank-up series progress if needed
    # -----------------------
    rankup_result = apply_rankup_progress_if_needed(
        players_data=players,
        match_record=match_record,
        winner_ids=winner_ids,
        loser_ids=loser_ids,
    )

    # -----------------------
    # capture post-match SPR
    # -----------------------

    for member_id in all_member_ids:
        post_match_spr[member_id] = players[member_id]["modes"]["1v1"]["spr"]

   
    # -----------------------
    # Clear match state
    # -----------------------
    clear_players_from_match(players, winner_ids, "1v1")
    clear_players_from_match(players, loser_ids, "1v1")

    completed_record = create_completed_match_record(
        match_record=match_record,
        completed_at=utc_now_iso(),
        winner_team=winner_team,
        loser_team=loser_team,
        resolved_by="system",
        was_disputed=False,
        dispute_reason=None,
        final_outcome=winner_key,
        spr_changes=spr_changes,
        pre_match_spr=pre_match_spr,
        post_match_spr=post_match_spr,
        rankup_result=rankup_result,
    )

    return {
        "winner_ids": winner_ids,
        "loser_ids": loser_ids,
        "completed_record": completed_record,
        "spr_changes": spr_changes,
        "rankup_result": rankup_result,
    }

def finalize_agreed_2v2_match(
    players: dict,
    match_record: dict,
) -> dict:
    # Finalize an agreed 2v2 match in memory and return the completed record pieces

    winner_loser = get_winner_and_loser_team_keys_from_reports(match_record)

    if not winner_loser:
        raise ValueError("Could not determine winner and loser from agreed reports.")

    winner_key, loser_key = winner_loser
    winner_team = match_record[winner_key]
    loser_team = match_record[loser_key]

    winner_ids = [str(member_id) for member_id in winner_team["player_ids"]]
    loser_ids = [str(member_id) for member_id in loser_team["player_ids"]]
    all_member_ids = winner_ids + loser_ids

    pre_match_spr = {}
    spr_changes = {}
    post_match_spr = {}

    # -----------------------
    # Capture pre-match SPR
    # -----------------------
    for member_id in all_member_ids:
        if member_id not in players:
            raise ValueError(f"Player data missing for {member_id}.")

        pre_match_spr[member_id] = players[member_id]["modes"]["2v2"]["spr"]

    # -----------------------
    # Apply win/loss updates
    # -----------------------
    for member_id in winner_ids:
        mode_data = players[member_id]["modes"]["2v2"]
        spr_changes[member_id] = apply_win_to_player_mode(mode_data)

    for member_id in loser_ids:
        mode_data = players[member_id]["modes"]["2v2"]
        spr_changes[member_id] = apply_loss_to_player_mode(mode_data)

    
    # -----------------------
    # Apply rank-up series progress if needed
    # -----------------------
    if match_record.get("is_rankup") and mode in ("2v2", "3v3"):
        rankup_owner_id = str(match_record.get("rankup_owner_id"))
        rankup_participants = [str(x) for x in match_record.get("rankup_participants", [])]

        team1_ids = [str(x) for x in match_record.get("team1", {}).get("player_ids", [])]
        team2_ids = [str(x) for x in match_record.get("team2", {}).get("player_ids", [])]

        owner_on_team1 = rankup_owner_id in team1_ids
        rankup_team_won = (
            (owner_on_team1 and winning_team == "team1") or
            ((not owner_on_team1) and winning_team == "team2")
        )

        team_rankup_result = apply_team_rankup_progress_to_participants(
            players=players,
            participant_ids=rankup_participants,
            did_win=rankup_team_won,
            mode=mode,
        )

        failure_lines = []
        
        for failed in failed_rankups:
            failure_lines.append(
                f"{failed['display_name']} rank-up failed (dropped below Elite)."
            )

        rankup_summary_lines = []

        if team_rankup_result["updated_ids"]:
            rankup_summary_lines.append(
                f"Rank-up updated for: {', '.join(f'<@{x}>' for x in team_rankup_result['updated_ids'])}"
            )

        if team_rankup_result["promoted_ids"]:
            rankup_summary_lines.append(
                f"Promoted: {', '.join(f'<@{x}>' for x in team_rankup_result['promoted_ids'])}"
            )

        if team_rankup_result["failed_ids"]:
            rankup_summary_lines.append(
                f"Rank-up failed: {', '.join(f'<@{x}>' for x in team_rankup_result['failed_ids'])}"
            )

    # -----------------------
    # Capture post-match SPR
    # -----------------------
    for member_id in all_member_ids:
        post_match_spr[member_id] = players[member_id]["modes"]["2v2"]["spr"]

    # -----------------------
    # Clear match state
    # -----------------------
    clear_players_from_match(players, winner_ids, "2v2")
    clear_players_from_match(players, loser_ids, "2v2")

    completed_record = create_completed_match_record(
        match_record=match_record,
        completed_at=utc_now_iso(),
        winner_team=winner_team,
        loser_team=loser_team,
        resolved_by="system",
        was_disputed=False,
        dispute_reason=None,
        final_outcome=winner_key,
        spr_changes=spr_changes,
        pre_match_spr=pre_match_spr,
        post_match_spr=post_match_spr,
        rankup_result=rankup_result,
    )

    return {
        "winner_ids": winner_ids,
        "loser_ids": loser_ids,
        "completed_record": completed_record,
        "spr_changes": spr_changes,
        "rankup_summary_lines": rankup_summary_lines,
        "failure_lines": failure_lines,
    }

def finalize_agreed_3v3_match(
    players: dict,
    match_record: dict,
) -> dict:
    # Finalize an agreed 3v3 match in memory and return the completed record pieces

    winner_loser = get_winner_and_loser_team_keys_from_reports(match_record)

    if not winner_loser:
        raise ValueError("Could not determine winner and loser from agreed reports.")

    winner_key, loser_key = winner_loser
    winner_team = match_record[winner_key]
    loser_team = match_record[loser_key]

    winner_ids = [str(member_id) for member_id in winner_team["player_ids"]]
    loser_ids = [str(member_id) for member_id in loser_team["player_ids"]]
    all_member_ids = winner_ids + loser_ids

    pre_match_spr = {}
    spr_changes = {}
    post_match_spr = {}

    # -----------------------
    # Capture pre-match SPR
    # -----------------------
    for member_id in all_member_ids:
        if member_id not in players:
            raise ValueError(f"Player data missing for {member_id}.")

        pre_match_spr[member_id] = players[member_id]["modes"]["3v3"]["spr"]

    # -----------------------
    # Apply win/loss updates
    # -----------------------
    for member_id in winner_ids:
        mode_data = players[member_id]["modes"]["3v3"]
        spr_changes[member_id] = apply_win_to_player_mode(mode_data)

    for member_id in loser_ids:
        mode_data = players[member_id]["modes"]["3v3"]
        spr_changes[member_id] = apply_loss_to_player_mode(mode_data)

    
    # -----------------------
    # Apply rank-up series progress if needed
    # -----------------------
    if match_record.get("is_rankup") and mode in ("2v2", "3v3"):
        rankup_owner_id = str(match_record.get("rankup_owner_id"))
        rankup_participants = [str(x) for x in match_record.get("rankup_participants", [])]

        team1_ids = [str(x) for x in match_record.get("team1", {}).get("player_ids", [])]
        team2_ids = [str(x) for x in match_record.get("team2", {}).get("player_ids", [])]

        owner_on_team1 = rankup_owner_id in team1_ids
        rankup_team_won = (
            (owner_on_team1 and winning_team == "team1") or
            ((not owner_on_team1) and winning_team == "team2")
        )

        team_rankup_result = apply_team_rankup_progress_to_participants(
            players=players,
            participant_ids=rankup_participants,
            did_win=rankup_team_won,
            mode=mode,
        )


    # -----------------------
    # Capture post-match SPR
    # -----------------------
    for member_id in all_member_ids:
        post_match_spr[member_id] = players[member_id]["modes"]["3v3"]["spr"]

    # -----------------------
    # Clear match state
    # -----------------------
    clear_players_from_match(players, winner_ids, "3v3")
    clear_players_from_match(players, loser_ids, "3v3")

    completed_record = create_completed_match_record(
        match_record=match_record,
        completed_at=utc_now_iso(),
        winner_team=winner_team,
        loser_team=loser_team,
        resolved_by="system",
        was_disputed=False,
        dispute_reason=None,
        final_outcome=winner_key,
        spr_changes=spr_changes,
        pre_match_spr=pre_match_spr,
        post_match_spr=post_match_spr,
        rankup_result=None,
    )

    return {
        "winner_ids": winner_ids,
        "loser_ids": loser_ids,
        "completed_record": completed_record,
        "spr_changes": spr_changes,
    }

def finalize_resolved_team_match(
    players: dict,
    match_record: dict,
    selected_outcome: str,
) -> dict:
    # Finalize a resolved team match (1v1 or 2v2) in memory and return
    # the pieces needed for archive + messaging.

    mode = match_record["mode"]

    if selected_outcome == "team1":
        winner_team = match_record["team1"]
        loser_team = match_record["team2"]
    elif selected_outcome == "team2":
        winner_team = match_record["team2"]
        loser_team = match_record["team1"]
    else:
        raise ValueError("selected_outcome must be 'team1' or 'team2'")

    winner_ids = [str(member_id) for member_id in winner_team["player_ids"]]
    loser_ids = [str(member_id) for member_id in loser_team["player_ids"]]
    all_member_ids = winner_ids + loser_ids

    pre_match_spr = {}
    spr_changes = {}
    post_match_spr = {}

    # -----------------------
    # Capture pre-match SPR
    # -----------------------
    for member_id in all_member_ids:
        if member_id not in players:
            raise ValueError(f"Player data missing for {member_id}.")

        pre_match_spr[member_id] = players[member_id]["modes"][mode]["spr"]

    # -----------------------
    # Apply win/loss updates
    # -----------------------
    for member_id in winner_ids:
        mode_data = players[member_id]["modes"][mode]
        spr_changes[member_id] = apply_win_to_player_mode(mode_data)

    for member_id in loser_ids:
        mode_data = players[member_id]["modes"][mode]
        spr_changes[member_id] = apply_loss_to_player_mode(mode_data)

    # -----------------------
    # Only 1v1 uses rank-up logic right now
    # -----------------------
    failed_rankups = []
    rankup_result = None

    if mode == "1v1":
        failed_rankups = fail_rankup_if_needed(players, all_member_ids, "1v1")

        rankup_result = apply_rankup_progress_if_needed(
            players_data=players,
            match_record=match_record,
            winner_ids=winner_ids,
            loser_ids=loser_ids,
        )

    # -----------------------
    # Capture post-match SPR
    # -----------------------
    for member_id in all_member_ids:
        post_match_spr[member_id] = players[member_id]["modes"][mode]["spr"]

    # -----------------------
    # Apply incorrect report penalties
    # -----------------------
    incorrect_reporter_ids = get_incorrect_reporter_ids_for_resolved_match(
        match_record=match_record,
        final_outcome=selected_outcome,
    )

    increment_incorrect_reports_for_resolved_match(
        players_data=players,
        match_record=match_record,
        final_outcome=selected_outcome,
    )

    # -----------------------
    # Clear match state
    # -----------------------
    clear_players_from_disputed_match(players, match_record, mode)

    return {
        "winner_ids": winner_ids,
        "loser_ids": loser_ids,
        "winner_team": winner_team,
        "loser_team": loser_team,
        "spr_changes": spr_changes,
        "pre_match_spr": pre_match_spr,
        "post_match_spr": post_match_spr,
        "incorrect_reporter_ids": incorrect_reporter_ids,
        "failed_rankups": failed_rankups,
        "rankup_result": rankup_result,
    }

# -----------------------
# Rank-up failure enforcement
# -----------------------

def fail_rankup_if_needed(players_data: dict, member_ids: list[str], mode: str) -> list[dict]:
    # Check all listed players. If any have an active rank-up and no longer meet
    # Elite-tier requirements after their SPR update, fail the rank-up immediately.
    #
    # Returns a list of failure info objects:
    # [{"user_id": str, "display_name": str}, ...]

    failed_players = []

    for member_id in member_ids:
        member_id = str(member_id)

        if member_id not in players_data:
            continue

        player = players_data[member_id]
        mode_data = player["modes"][mode]
        spr = mode_data["spr"]

        if should_fail_rankup_for_spr(mode_data, spr):
            record_rankup_history_entry(mode_data, "failed_dropped_below_elite")
            clear_rankup_for_mode(mode_data)

            failed_players.append({
                "user_id": member_id,
                "display_name": player.get("display_name", member_id)
            })

    return failed_players


# -----------------------
# Incorrect report helpers
# -----------------------

def get_incorrect_reporter_ids_for_resolved_match(
    match_record: dict,
    final_outcome: str,
    ) -> list[str]:
    # Return the user IDs of players whose submitted report conflicts
    # with the moderator-selected final outcome.
    #
    # final_outcome should be:
    # - "team1"
    # - "team2"
    # - "disregard"

    if final_outcome == "disregard":
        return []

    incorrect_ids = []

    correct_team_key = final_outcome
    incorrect_team_key = "team2" if final_outcome == "team1" else "team1"

    for team_key in ["team1", "team2"]:
        report = match_record["reports"][team_key]
        reported_by = report.get("reported_by")
        reported_result = report.get("result")

        if not reported_by or reported_result is None:
            continue

        was_correct = False

        if team_key == correct_team_key and reported_result == "win":
            was_correct = True
        elif team_key == incorrect_team_key and reported_result == "loss":
            was_correct = True

        if not was_correct:
            incorrect_ids.append(str(reported_by))

    return incorrect_ids