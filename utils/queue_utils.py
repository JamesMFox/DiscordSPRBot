from typing import Optional
from utils.rank_utils import get_class_from_spr
from utils.time_utils import utc_now_iso

STANDARD_QUEUE_MODES = ("1v1", "2v2", "3v3")


def iter_standard_queue_buckets(queue_data: dict):
    for mode in STANDARD_QUEUE_MODES:
        yield mode, queue_data.get(mode, [])


def iter_all_queue_buckets(queue_data: dict):
    for mode, entries in iter_standard_queue_buckets(queue_data):
        yield mode, entries

    rankup_data = queue_data.get("rankup", {})
    for mode in STANDARD_QUEUE_MODES:
        yield f"rankup:{mode}", rankup_data.get(mode, [])


def generate_queue_entry_id(queue_data: dict) -> str:
    # Generate the next queue entry ID like queue_0001.
    existing_numbers = []

    for _, entries in iter_all_queue_buckets(queue_data):
        for entry in entries:
            entry_id = entry.get("entry_id", "")
            if entry_id.startswith("queue_"):
                try:
                    number = int(entry_id.split("_")[1])
                    existing_numbers.append(number)
                except (IndexError, ValueError):
                    continue

    next_number = max(existing_numbers, default=0) + 1
    return f"queue_{next_number:04d}"


def create_solo_queue_entry(
    entry_id: str,
    mode: str,
    user_id: int,
    spr: int,
    queue_class: str,
) -> dict:
    return {
        "entry_id": entry_id,
        "mode": mode,
        "entry_type": "solo",
        "captain_id": str(user_id),
        "member_ids": [str(user_id)],
        "team_id": None,
        "average_spr": spr,
        "queue_class": queue_class,
        "queued_at": utc_now_iso(),
    }


def create_premade_queue_entry(
    entry_id: str,
    mode: str,
    captain_id: int,
    member_ids: list[str],
    team_id: str,
    average_spr: int,
    queue_class: str,
) -> dict:
    return {
        "entry_id": entry_id,
        "mode": mode,
        "entry_type": "premade",
        "captain_id": str(captain_id),
        "member_ids": [str(member_id) for member_id in member_ids],
        "team_id": team_id,
        "average_spr": average_spr,
        "queue_class": queue_class,
        "queued_at": utc_now_iso(),
    }


def get_player_spr_for_mode(player_profile: dict, mode: str) -> int:
    return player_profile["modes"][mode]["spr"]


def get_player_queue_class_for_mode(player_profile: dict, mode: str) -> Optional[str]:
    spr = get_player_spr_for_mode(player_profile, mode)
    return get_class_from_spr(spr)


def player_is_queued_anywhere(player_profile: dict) -> bool:
    return any(mode_data["in_queue"] for mode_data in player_profile["modes"].values())


def find_any_queue_entry_for_member_any_mode(queue_data: dict, member_id: int | str) -> Optional[dict]:
    member_id = str(member_id)

    for _, entries in iter_all_queue_buckets(queue_data):
        for entry in entries:
            if member_id in entry["member_ids"]:
                return entry

    return None


def calculate_average_spr(players_data: dict, member_ids: list[str], mode: str) -> int:
    spr_values = []

    for member_id in member_ids:
        player_profile = players_data[str(member_id)]
        spr_values.append(get_player_spr_for_mode(player_profile, mode))

    return sum(spr_values) // len(spr_values)


def find_solo_queue_entry(queue_data: dict, mode: str, user_id: int | str) -> Optional[dict]:
    user_id = str(user_id)

    for entry in queue_data.get(mode, []):
        if entry["entry_type"] == "solo" and user_id in entry["member_ids"]:
            return entry

    return None


def find_premade_queue_entry_by_captain(queue_data: dict, mode: str, captain_id: int | str) -> Optional[dict]:
    captain_id = str(captain_id)

    for entry in queue_data.get(mode, []):
        if entry["entry_type"] == "premade" and entry["captain_id"] == captain_id:
            return entry

    return None


def find_any_queue_entry_for_member(queue_data: dict, mode: str, member_id: int | str) -> Optional[dict]:
    member_id = str(member_id)

    for entry in queue_data.get(mode, []):
        if member_id in entry["member_ids"]:
            return entry

    return None


def remove_queue_entry_by_id(queue_data: dict, mode: str, entry_id: str) -> bool:
    entries = queue_data.get(mode, [])

    for index, entry in enumerate(entries):
        if entry.get("entry_id") == entry_id:
            del entries[index]
            return True

    return False


def player_can_queue(player_profile: dict, mode: str) -> bool:
    mode_data = player_profile["modes"][mode]

    return (
        not player_profile.get("is_banned_from_ranked", False)
        and not mode_data["in_match"]
        and not player_is_queued_anywhere(player_profile)
    )

def is_valid_rankup_opponent_team(
    players: dict,
    opponent_member_ids: list[str],
    target_class: str,
    mode: str,
) -> bool:
    for player_id in opponent_member_ids:
        player = players.get(str(player_id))
        if not player:
            return False

        mode_state = player.get("modes", {}).get(mode, {})
        rank_role = mode_state.get("rank_role")

        if not is_lowest_tier_of_class(rank_role, target_class):
            return False

    return True


def set_player_queue_state(player_profile: dict, mode: str, in_queue: bool) -> None:
    player_profile["modes"][mode]["in_queue"] = in_queue


def get_queue_block_reason(player_profile: dict, mode: str) -> str | None:
    if player_profile.get("is_banned_from_ranked", False):
        return "You are banned from ranked."

    mode_data = player_profile["modes"][mode]

    if mode_data["in_match"]:
        return "You are currently in a match."

    for m, m_data in player_profile["modes"].items():
        if m_data["in_queue"]:
            return f"You are already queued in {m}."

    return None


def get_team_queue_block_reason(players_data: dict, member_ids: list[str], mode: str) -> str | None:
    for member_id in member_ids:
        player_profile = players_data.get(member_id)

        if not player_profile:
            return "A team member is not signed up."

        display_name = player_profile.get("display_name", member_id)

        if player_profile.get("is_banned_from_ranked", False):
            return f"{display_name} is banned from ranked."

        mode_data = player_profile["modes"][mode]

        if mode_data["in_match"]:
            return f"{display_name} is currently in a match."

        for mode_name, mode_info in player_profile["modes"].items():
            if mode_info["in_queue"]:
                return f"{display_name} is already queued in {mode_name}."

    return None


def set_multiple_players_queue_state(players_data: dict, member_ids: list[str], mode: str, in_queue: bool) -> None:
    for member_id in member_ids:
        if member_id in players_data:
            players_data[member_id]["modes"][mode]["in_queue"] = in_queue


def find_solo_queue_entry_any_mode(queue_data: dict, user_id: int | str) -> tuple[str, dict] | None:
    user_id = str(user_id)

    for mode, entries in iter_all_queue_buckets(queue_data):
        for entry in entries:
            if entry["entry_type"] == "solo" and user_id in entry["member_ids"]:
                return mode, entry

    return None


def find_premade_queue_entry_by_captain_any_mode(queue_data: dict, captain_id: int | str) -> tuple[str, dict] | None:
    captain_id = str(captain_id)

    for mode, entries in iter_all_queue_buckets(queue_data):
        for entry in entries:
            if entry["entry_type"] == "premade" and entry["captain_id"] == captain_id:
                return mode, entry

    return None


def find_any_queue_entry_for_member_any_mode_with_mode(queue_data: dict, member_id: int | str) -> tuple[str, dict] | None:
    member_id = str(member_id)

    for mode, entries in iter_all_queue_buckets(queue_data):
        for entry in entries:
            if member_id in entry["member_ids"]:
                return mode, entry

    return None
