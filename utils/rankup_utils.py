from utils.time_utils import utc_now_iso

from utils.rank_utils import (
    get_class_from_spr,
    get_next_class,
    get_tier_from_spr,
    get_lowest_tier_of_class
)

# -----------------------
# Eligibility helpers
# -----------------------

def is_rankup_eligible(mode_data: dict, spr: int) -> bool:
    # Player is eligible if:
    # - they are currently in an ELITE tier
    # - they do not already have an active rank-up

    tier_name = get_tier_from_spr(spr)

    if tier_name is None:
        return False

    if "ELITE" not in tier_name:
        return False

    if mode_data.get("rankup_active", False):
        return False

    return True

def captain_can_start_team_rankup(players: dict, captain_id: str, mode: str):
    player = players.get(str(captain_id))
    if not player:
        return False, "Captain is not signed up.", None

    mode_state = player.get("modes", {}).get(mode, {})

    if not mode_state.get("rankup_active", False):
        return False, f"You do not have an active {mode} rank-up attempt.", None

    current_class = get_class_from_spr(mode_state.get("spr"))
    target_class = mode_state.get("rankup_target_class")

    if not current_class or not target_class:
        return False, "Your rank-up state is missing class information.", None

    return True, None, {
        "captain_id": str(captain_id),
        "current_class": current_class,
        "target_class": target_class,
    }

def player_can_join_team_rankup_as_participant(
    players: dict,
    player_id: str,
    mode: str,
    target_class: str,
):
    player = players.get(str(player_id))
    if not player:
        return False, "Player is not signed up."

    mode_state = player.get("modes", {}).get(mode, {})

    if not mode_state.get("rankup_active", False):
        return False, f"<@{player_id}> does not have an active {mode} rank-up attempt."

    player_target_class = mode_state.get("rankup_target_class")
    if player_target_class != target_class:
        return False, (
            f"<@{player_id}> has a {mode} rank-up attempt, but it targets "
            f"`{player_target_class}` instead of `{target_class}`."
        )

    return True, None

def get_rankup_target_class(spr: int) -> str | None:
    # Return the next class above the player's current class
    current_class = get_class_from_spr(spr)

    if current_class is None:
        return None

    return get_next_class(current_class)


# -----------------------
# Rank-up state helpers
# -----------------------

def start_rankup_for_mode(mode_data: dict, target_class: str) -> None:
    # Start a rank-up attempt in this mode
    mode_data["rankup_active"] = True
    mode_data["rankup_target_class"] = target_class
    mode_data["rankup_started_at"] = utc_now_iso()
    mode_data["rankup_wins"] = 0
    mode_data["rankup_losses"] = 0



def clear_rankup_for_mode(mode_data: dict) -> None:
    # Clear the current rank-up state in this mode
    mode_data["rankup_active"] = False
    mode_data["rankup_target_class"] = None
    mode_data["rankup_started_at"] = None
    mode_data["rankup_wins"] = 0
    mode_data["rankup_losses"] = 0


def record_rankup_history_entry(mode_data: dict, result: str) -> None:
    # Save the current rank-up attempt into rankup_history
    mode_data["rankup_history"].append({
        "started_at": mode_data.get("rankup_started_at"),
        "ended_at": utc_now_iso(),
        "target_class": mode_data.get("rankup_target_class"),
        "wins": mode_data.get("rankup_wins", 0),
        "losses": mode_data.get("rankup_losses", 0),
        "result": result
    })


# -----------------------
# Rank-up opponent helpers
# -----------------------

def is_player_in_lowest_tier_of_class(spr: int, class_name: str) -> bool:
    # Return True if the player's SPR is inside the lowest tier of the given class

    lowest_tier = get_lowest_tier_of_class(class_name)

    if lowest_tier is None:
        return False

    min_spr = lowest_tier["min"]
    max_spr = lowest_tier["max"]

    if max_spr is None:
        return spr >= min_spr

    return min_spr <= spr <= max_spr


def is_valid_rankup_opponent(opponent_spr: int, target_class: str) -> bool:
    # Return True if the opponent belongs to the lowest tier of the target class
    return is_player_in_lowest_tier_of_class(opponent_spr, target_class)

def find_best_rankup_2v2_opponent_from_queue(
    players: dict,
    rankup_entry: dict,
    normal_queue_entries: list[dict],
):
    target_class = rankup_entry.get("rankup_target_class")
    challenger_ids = [str(x) for x in rankup_entry.get("member_ids", [])]

    best_entry = None
    best_gap = None

    challenger_avg = calculate_team_average_spr(players, challenger_ids, "2v2")

    for entry in normal_queue_entries:
        if entry.get("entry_type") != "premade":
            continue

        opponent_ids = [str(x) for x in entry.get("member_ids", [])]
        if len(opponent_ids) != 2:
            continue

        if not is_valid_rankup_opponent_team(players, opponent_ids, target_class, "2v2"):
            continue

        opponent_avg = calculate_team_average_spr(players, opponent_ids, "2v2")
        gap = abs(challenger_avg - opponent_avg)

        if best_entry is None or gap < best_gap:
            best_entry = entry
            best_gap = gap

    return best_entry

def find_best_rankup_3v3_opponent_from_queue(
    players: dict,
    rankup_entry: dict,
    normal_queue_entries: list[dict],
):
    target_class = rankup_entry.get("rankup_target_class")
    challenger_ids = [str(x) for x in rankup_entry.get("member_ids", [])]

    best_entry = None
    best_gap = None

    challenger_avg = calculate_team_average_spr(players, challenger_ids, "3v3")

    for entry in normal_queue_entries:
        if entry.get("entry_type") != "premade":
            continue

        opponent_ids = [str(x) for x in entry.get("member_ids", [])]
        if len(opponent_ids) != 3:
            continue

        if not is_valid_rankup_opponent_team(players, opponent_ids, target_class, "3v3"):
            continue

        opponent_avg = calculate_team_average_spr(players, opponent_ids, "3v3")
        gap = abs(challenger_avg - opponent_avg)

        if best_entry is None or gap < best_gap:
            best_entry = entry
            best_gap = gap

    return best_entry

# -----------------------
# Rank-up queue search helpers
# -----------------------

def find_best_rankup_opponent_from_queue(
    players_data: dict,
    queue_entries: list[dict],
    rankup_player_spr: int,
    target_class: str,
) -> dict | None:
    # Find the closest queued solo 1v1 opponent who is in the lowest tier
    # of the rank-up target class.

    valid_entries = []

    for entry in queue_entries:
        if entry["entry_type"] != "solo":
            continue

        if len(entry["member_ids"]) != 1:
            continue

        opponent_id = str(entry["member_ids"][0])

        if opponent_id not in players_data:
            continue

        opponent_profile = players_data[opponent_id]
        opponent_spr = opponent_profile["modes"]["1v1"]["spr"]

        if not is_valid_rankup_opponent(opponent_spr, target_class):
            continue

        valid_entries.append(entry)

    if not valid_entries:
        return None

    best_entry = None
    best_gap = None

    for entry in valid_entries:
        gap = abs(entry["average_spr"] - rankup_player_spr)

        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_entry = entry

    return best_entry


# -----------------------
# Failure checks
# -----------------------

def should_fail_rankup_for_spr(mode_data: dict, spr: int) -> bool:
    # If rank-up is active but player is no longer in an ELITE tier,
    # the rank-up should fail immediately

    if not mode_data.get("rankup_active", False):
        return False

    tier_name = get_tier_from_spr(spr)

    if tier_name is None:
        return True

    return "ELITE" not in tier_name


# -----------------------
# Rank-up series progress helpers
# -----------------------

def apply_rankup_match_win(mode_data: dict) -> None:
    # Count one rank-up win
    mode_data["rankup_wins"] += 1


def apply_rankup_match_loss(mode_data: dict) -> None:
    # Count one rank-up loss
    mode_data["rankup_losses"] += 1


def get_rankup_series_status(mode_data: dict) -> str:
    # Return the current best-of-5 series status

    if mode_data["rankup_wins"] >= 3:
        return "success"

    if mode_data["rankup_losses"] >= 3:
        return "failed"

    return "ongoing"

def apply_team_rankup_progress_to_participants(
    players: dict,
    participant_ids: list[str],
    did_win: bool,
    mode: str,
):
    promoted_ids = []
    failed_ids = []
    updated_ids = []

    for player_id in participant_ids:
        player = players.get(str(player_id))
        if not player:
            continue

        mode_state = player.get("modes", {}).get(mode, {})
        if not mode_state.get("rankup_active", False):
            continue

        if did_win:
            mode_state["rankup_wins"] = int(mode_state.get("rankup_wins", 0)) + 1
        else:
            mode_state["rankup_losses"] = int(mode_state.get("rankup_losses", 0)) + 1

        wins = int(mode_state.get("rankup_wins", 0))
        losses = int(mode_state.get("rankup_losses", 0))

        updated_ids.append(str(player_id))

        if wins >= 3:
            target_class = mode_state.get("rankup_target_class")
            promoted_spr = get_promoted_spr(target_class) if target_class else None

            if promoted_spr is not None:
                mode_state["spr"] = promoted_spr
                if mode_state["spr"] > mode_state["peak_spr"]:
                    mode_state["peak_spr"] = mode_state["spr"]

            record_rankup_history_entry(mode_state, "success")
            clear_rankup_for_mode(mode_state)
            promoted_ids.append(str(player_id))

        elif losses >= 3:
            record_rankup_history_entry(mode_state, "failed")
            clear_rankup_for_mode(mode_state)
            failed_ids.append(str(player_id))

    return {
        "updated_ids": updated_ids,
        "promoted_ids": promoted_ids,
        "failed_ids": failed_ids,
    }

# -----------------------
# Promotion SPR helpers
# -----------------------

def get_class_min_spr(class_name: str) -> int | None:
    # Return the minimum SPR of the lowest tier in a class

    lowest_tier = get_lowest_tier_of_class(class_name)

    if lowest_tier is None:
        return None

    return lowest_tier["min"]


def get_promoted_spr(target_class: str) -> int | None:
    # On successful promotion, player is set to:
    # target class minimum + 16

    class_min = get_class_min_spr(target_class)

    if class_min is None:
        return None

    return class_min + 16