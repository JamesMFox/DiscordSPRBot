from typing import TypedDict
from itertools import combinations
from utils.time_utils import utc_now_iso


class MatchMakingResult(TypedDict):
    created_count: int
    created_summaries: list[str]

# -----------------------
# Match ID helper
# -----------------------

def generate_match_id(active_matches_data: dict, matches_data: dict) -> str:
    # Generate the next match ID like match_0001
    existing_numbers = []

    for match_id in active_matches_data.keys():
        if match_id.startswith("match_"):
            try:
                number = int(match_id.split("_")[1])
                existing_numbers.append(number)
            except (IndexError, ValueError):
                continue

    for match_id in matches_data.keys():
        if match_id.startswith("match_"):
            try:
                number = int(match_id.split("_")[1])
                existing_numbers.append(number)
            except (IndexError, ValueError):
                continue

    next_number = max(existing_numbers, default=0) + 1
    return f"match_{next_number:04d}"


# -----------------------
# Queue entry -> match team object
# -----------------------

def create_match_team_object(queue_entry: dict) -> dict:
    # Convert a queue entry into the standard team object used in match files
    entry_type = queue_entry["entry_type"]

    if entry_type == "premade":
        queue_entry_type = "premade"
        source_team_id = queue_entry["team_id"]
    else:
        queue_entry_type = "solo" if len(queue_entry["member_ids"]) == 1 else "solo_assembled"
        source_team_id = None

    return {
        "captain_id": str(queue_entry["captain_id"]),
        "player_ids": [str(member_id) for member_id in queue_entry["member_ids"]],
        "queue_entry_type": queue_entry_type,
        "source_team_id": source_team_id,
        "queue_class": queue_entry["queue_class"]
    }


# -----------------------
# Active match record builder
# -----------------------

def create_active_match_record(
    match_id: str,
    mode: str,
    match_type: str,
    team1: dict,
    team2: dict,
    ranked: bool = True,
    rankup_match: bool = False,
    rankup_player_id: str | None = None,
    rankup_target_class: str | None = None,
    is_rankup: bool = False,
    rankup_owner_id: str | None = None,
    rankup_participants: list[str] | None = None,
) -> dict:
    return {
        "match_id": match_id,
        "mode": mode,
        "match_type": match_type,
        "status": "awaiting_reports",
        "created_at": utc_now_iso(),

        "ranked": ranked,
        "rankup_match": rankup_match,
        "rankup_player_id": rankup_player_id,
        "rankup_target_class": rankup_target_class,

        "is_rankup": is_rankup,
        "rankup_owner_id": rankup_owner_id,
        "rankup_participants": rankup_participants or [],

        "team1": team1,
        "team2": team2,

        "reports": {
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
        },

        "confirmation": {
            "result_agreed": False,
            "confirmed_at": None
        },

        "metadata": {
            "notes": ""
        }
    }


# -----------------------
# Queue grouping helpers
# -----------------------

def group_queue_entries_by_class(queue_entries: list[dict]) -> dict:
    # Group queue entries by queue_class
    grouped = {}

    for entry in queue_entries:
        queue_class = entry["queue_class"]
        if queue_class not in grouped:
            grouped[queue_class] = []
        grouped[queue_class].append(entry)

    return grouped


def sort_queue_entries_by_average_spr(queue_entries: list[dict]) -> list[dict]:
    # Return queue entries sorted by average_spr from low to high
    return sorted(queue_entries, key=lambda entry: entry["average_spr"])


# -----------------------
# 1v1 matchmaking helper
# -----------------------

def find_best_1v1_match(queue_entries: list[dict]) -> tuple[dict, dict] | None:
    # Find the closest 1v1 solo-vs-solo match from valid queue entries
    # Returns a tuple: (entry1, entry2) or None if no valid pair exists

    # Only solo entries belong in 1v1 matchmaking
    solo_entries = [entry for entry in queue_entries if entry["entry_type"] == "solo"]

    if len(solo_entries) < 2:
        return None

    # Entries should already be grouped by class before this is called,
    # but this helper still picks the smallest SPR gap among the available entries.
    best_pair = None
    best_gap = None

    sorted_entries = sort_queue_entries_by_average_spr(solo_entries)

    for i in range(len(sorted_entries)):
        for j in range(i + 1, len(sorted_entries)):
            entry1 = sorted_entries[i]
            entry2 = sorted_entries[j]

            gap = abs(entry1["average_spr"] - entry2["average_spr"])

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_pair = (entry1, entry2)

    return best_pair


# -----------------------
# 2v2 queue split helpers
# -----------------------

def split_2v2_entries(queue_entries: list[dict]) -> tuple[list[dict], list[dict]]:
    # Split 2v2 queue entries into premades and solos

    premades = []
    solos = []

    for entry in queue_entries:
        if entry["entry_type"] == "premade" and len(entry["member_ids"]) == 2:
            premades.append(entry)
        elif entry["entry_type"] == "solo" and len(entry["member_ids"]) == 1:
            solos.append(entry)

    return premades, solos

def split_3v3_entries(queue_entries: list[dict]) -> tuple[list[dict], list[dict]]:
    # Split 3v3 queue entries into premades and solos

    premades = []
    solos = []

    for entry in queue_entries:
        if entry["entry_type"] == "premade" and len(entry["member_ids"]) == 3:
            premades.append(entry)
        elif entry["entry_type"] == "solo" and len(entry["member_ids"]) == 1:
            solos.append(entry)

    return premades, solos

# -----------------------
# 2v2 team average helpers
# -----------------------

def get_entries_average_spr(entries: list[dict]) -> float:
    # Average the average_spr values from queue entries

    if not entries:
        return 0.0

    total = sum(entry["average_spr"] for entry in entries)
    return total / len(entries)

def build_solo_assembled_team_from_entries(entries: list[dict], queue_class: str) -> dict:
    # Build a temporary solo-assembled team object from solo queue entries

    member_ids = []
    captain_id = None

    for entry in entries:
        member_ids.extend([str(member_id) for member_id in entry["member_ids"]])

    if member_ids:
        captain_id = member_ids[0]

    return {
        "captain_id": captain_id,
        "player_ids": member_ids,
        "queue_entry_type": "solo_assembled",
        "source_team_id": None,
        "queue_class": queue_class
    }

def build_solo_assembled_3v3_team_from_entries(entries: list[dict], queue_class: str) -> dict:
    # Build a temporary solo-assembled 3v3 team object from solo queue entries

    member_ids = []

    for entry in entries:
        member_ids.extend([str(member_id) for member_id in entry["member_ids"]])

    captain_id = member_ids[0] if member_ids else None

    return {
        "captain_id": captain_id,
        "player_ids": member_ids,
        "queue_entry_type": "solo_assembled",
        "source_team_id": None,
        "queue_class": queue_class
    }

def build_premade_team_from_entry(entry: dict) -> dict:
    # Build a premade team object from one premade queue entry

    return {
        "captain_id": str(entry["captain_id"]),
        "player_ids": [str(member_id) for member_id in entry["member_ids"]],
        "queue_entry_type": "premade",
        "source_team_id": entry["team_id"],
        "queue_class": entry["queue_class"]
    }


# -----------------------
# premade vs premade
# -----------------------

def find_best_premade_vs_premade_2v2(premade_entries: list[dict]) -> dict | None:
    # Find the best premade vs premade match by smallest average SPR gap

    if len(premade_entries) < 2:
        return None

    best_result = None
    best_gap = None

    for entry1, entry2 in combinations(premade_entries, 2):
        gap = abs(entry1["average_spr"] - entry2["average_spr"])

        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_result = {
                "match_kind": "premade_vs_premade",
                "team1_entry_ids": [entry1["entry_id"]],
                "team2_entry_ids": [entry2["entry_id"]],
                "team1_member_ids": [str(member_id) for member_id in entry1["member_ids"]],
                "team2_member_ids": [str(member_id) for member_id in entry2["member_ids"]],
                "team1": build_premade_team_from_entry(entry1),
                "team2": build_premade_team_from_entry(entry2),
                "average_gap": gap
            }

    return best_result

def find_best_premade_vs_premade_3v3(premade_entries: list[dict]) -> dict | None:
    # Find the best premade vs premade 3v3 match by smallest average SPR gap

    if len(premade_entries) < 2:
        return None

    best_result = None
    best_gap = None

    for entry1, entry2 in combinations(premade_entries, 2):
        gap = abs(entry1["average_spr"] - entry2["average_spr"])

        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_result = {
                "match_kind": "premade_vs_premade",
                "team1_entry_ids": [entry1["entry_id"]],
                "team2_entry_ids": [entry2["entry_id"]],
                "team1_member_ids": [str(member_id) for member_id in entry1["member_ids"]],
                "team2_member_ids": [str(member_id) for member_id in entry2["member_ids"]],
                "team1": build_premade_3v3_team_from_entry(entry1),
                "team2": build_premade_3v3_team_from_entry(entry2),
                "average_gap": gap
            }

    return best_result

# -----------------------
# solo-assembled vs solo-assembled
# -----------------------

def find_best_solo_vs_solo_2v2(solo_entries: list[dict], queue_class: str) -> dict | None:
    # Find the best 2v2 solo-assembled vs solo-assembled match
    #
    # We choose 4 solos, then evaluate the 3 unique team splits.

    if len(solo_entries) < 4:
        return None

    best_result = None
    best_gap = None

    for selected_four in combinations(solo_entries, 4):
        a, b, c, d = selected_four

        possible_splits = [
            ([a, b], [c, d]),
            ([a, c], [b, d]),
            ([a, d], [b, c]),
        ]

        for team1_entries, team2_entries in possible_splits:
            team1_avg = get_entries_average_spr(team1_entries)
            team2_avg = get_entries_average_spr(team2_entries)
            gap = abs(team1_avg - team2_avg)

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_result = {
                    "match_kind": "solo_vs_solo",
                    "team1_entry_ids": [entry["entry_id"] for entry in team1_entries],
                    "team2_entry_ids": [entry["entry_id"] for entry in team2_entries],
                    "team1_member_ids": [
                        str(member_id)
                        for entry in team1_entries
                        for member_id in entry["member_ids"]
                    ],
                    "team2_member_ids": [
                        str(member_id)
                        for entry in team2_entries
                        for member_id in entry["member_ids"]
                    ],
                    "team1": build_solo_assembled_team_from_entries(team1_entries, queue_class),
                    "team2": build_solo_assembled_team_from_entries(team2_entries, queue_class),
                    "average_gap": gap
                }

    return best_result

def find_best_solo_vs_solo_3v3(solo_entries: list[dict], queue_class: str) -> dict | None:
    # Find the best 3v3 solo-assembled vs solo-assembled match
    #
    # We choose 6 solos, then evaluate the 10 unique 3v3 splits.

    if len(solo_entries) < 6:
        return None

    best_result = None
    best_gap = None

    for selected_six in combinations(solo_entries, 6):
        selected_six = list(selected_six)

        # All 3-player combinations from the 6 selected
        for team1_entries_tuple in combinations(selected_six, 3):
            team1_entries = list(team1_entries_tuple)
            team1_entry_ids = {entry["entry_id"] for entry in team1_entries}

            # Remaining 3 entries become team 2
            team2_entries = [
                entry for entry in selected_six
                if entry["entry_id"] not in team1_entry_ids
            ]

            # Skip mirrored duplicate splits by enforcing a stable ordering rule
            team1_sorted_ids = sorted(entry["entry_id"] for entry in team1_entries)
            team2_sorted_ids = sorted(entry["entry_id"] for entry in team2_entries)

            if team1_sorted_ids > team2_sorted_ids:
                continue

            team1_avg = get_entries_average_spr(team1_entries)
            team2_avg = get_entries_average_spr(team2_entries)
            gap = abs(team1_avg - team2_avg)

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_result = {
                    "match_kind": "solo_vs_solo",
                    "team1_entry_ids": [entry["entry_id"] for entry in team1_entries],
                    "team2_entry_ids": [entry["entry_id"] for entry in team2_entries],
                    "team1_member_ids": [
                        str(member_id)
                        for entry in team1_entries
                        for member_id in entry["member_ids"]
                    ],
                    "team2_member_ids": [
                        str(member_id)
                        for entry in team2_entries
                        for member_id in entry["member_ids"]
                    ],
                    "team1": build_solo_assembled_3v3_team_from_entries(team1_entries, queue_class),
                    "team2": build_solo_assembled_3v3_team_from_entries(team2_entries, queue_class),
                    "average_gap": gap
                }

    return best_result

# -----------------------
# premade vs solo-assembled
# -----------------------

def find_best_premade_vs_solo_2v2(
    premade_entries: list[dict],
    solo_entries: list[dict],
    queue_class: str,
) -> dict | None:
    # Find the best premade vs solo-assembled match by smallest average SPR gap

    if len(premade_entries) < 1 or len(solo_entries) < 2:
        return None

    best_result = None
    best_gap = None

    for premade_entry in premade_entries:
        for solo_pair in combinations(solo_entries, 2):
            solo_pair = list(solo_pair)

            solo_avg = get_entries_average_spr(solo_pair)
            gap = abs(premade_entry["average_spr"] - solo_avg)

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_result = {
                    "match_kind": "premade_vs_solo",
                    "team1_entry_ids": [premade_entry["entry_id"]],
                    "team2_entry_ids": [entry["entry_id"] for entry in solo_pair],
                    "team1_member_ids": [str(member_id) for member_id in premade_entry["member_ids"]],
                    "team2_member_ids": [
                        str(member_id)
                        for entry in solo_pair
                        for member_id in entry["member_ids"]
                    ],
                    "team1": build_premade_team_from_entry(premade_entry),
                    "team2": build_solo_assembled_team_from_entries(solo_pair, queue_class),
                    "average_gap": gap
                }

    return best_result

def find_best_premade_vs_solo_3v3(
    premade_entries: list[dict],
    solo_entries: list[dict],
    queue_class: str,
) -> dict | None:
    # Find the best premade vs solo-assembled 3v3 match by smallest average SPR gap

    if len(premade_entries) < 1 or len(solo_entries) < 3:
        return None

    best_result = None
    best_gap = None

    for premade_entry in premade_entries:
        for solo_trio_tuple in combinations(solo_entries, 3):
            solo_trio = list(solo_trio_tuple)

            solo_avg = get_entries_average_spr(solo_trio)
            gap = abs(premade_entry["average_spr"] - solo_avg)

            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_result = {
                    "match_kind": "premade_vs_solo",
                    "team1_entry_ids": [premade_entry["entry_id"]],
                    "team2_entry_ids": [entry["entry_id"] for entry in solo_trio],
                    "team1_member_ids": [str(member_id) for member_id in premade_entry["member_ids"]],
                    "team2_member_ids": [
                        str(member_id)
                        for entry in solo_trio
                        for member_id in entry["member_ids"]
                    ],
                    "team1": build_premade_3v3_team_from_entry(premade_entry),
                    "team2": build_solo_assembled_3v3_team_from_entries(solo_trio, queue_class),
                    "average_gap": gap
                }

    return best_result

# -----------------------
# class-level match chooser
# -----------------------

def find_best_2v2_match_for_class(queue_entries: list[dict], queue_class: str) -> dict | None:
    # Choose the best valid 2v2 match for one class using the agreed priority:
    # 1. premade vs premade
    # 2. solo vs solo
    # 3. premade vs solo

    premades, solos = split_2v2_entries(queue_entries)

    premade_vs_premade = find_best_premade_vs_premade_2v2(premades)
    if premade_vs_premade:
        return premade_vs_premade

    solo_vs_solo = find_best_solo_vs_solo_2v2(solos, queue_class)
    if solo_vs_solo:
        return solo_vs_solo

    premade_vs_solo = find_best_premade_vs_solo_2v2(premades, solos, queue_class)
    if premade_vs_solo:
        return premade_vs_solo

    return None

def find_best_3v3_match_for_class(queue_entries: list[dict], queue_class: str) -> dict | None:
    # Choose the best valid 3v3 match for one class using the agreed priority:
    # 1. premade vs premade
    # 2. solo vs solo
    # 3. premade vs solo

    premades, solos = split_3v3_entries(queue_entries)

    premade_vs_premade = find_best_premade_vs_premade_3v3(premades)
    if premade_vs_premade:
        return premade_vs_premade

    solo_vs_solo = find_best_solo_vs_solo_3v3(solos, queue_class)
    if solo_vs_solo:
        return solo_vs_solo

    premade_vs_solo = find_best_premade_vs_solo_3v3(premades, solos, queue_class)
    if premade_vs_solo:
        return premade_vs_solo

    return None

# -----------------------
# Player state helpers
# -----------------------

def set_players_in_match(
    players_data: dict,
    member_ids: list[str],
    mode: str,
    match_id: str,
    ) -> None:
    # Mark players as no longer queued and now in a match

    for member_id in member_ids:
        member_id = str(member_id)

        if member_id not in players_data:
            continue

        mode_data = players_data[member_id]["modes"][mode]
        
        mode_data["in_queue"] = False
        mode_data["in_match"] = True
        mode_data["active_match_id"] = match_id


def clear_players_from_queue(
    players_data: dict,
    member_ids: list[str],
    mode: str,
    ) -> None:
    # Clear queued state for players in a mode

    for member_id in member_ids:
        member_id = str(member_id)

        if member_id not in players_data:
            continue

        players_data[member_id]["modes"][mode]["in_queue"] = False

def build_premade_3v3_team_from_entry(entry: dict) -> dict:
    # Build a premade 3v3 team object from one premade queue entry

    return {
        "captain_id": str(entry["captain_id"]),
        "player_ids": [str(member_id) for member_id in entry["member_ids"]],
        "queue_entry_type": "premade",
        "source_team_id": entry["team_id"],
        "queue_class": entry["queue_class"]
    }

# -----------------------
# Queue removal helpers
# -----------------------

def remove_queue_entries_by_ids(
    queue_data: dict,
    mode: str,
    entry_ids: list[str],
    ) -> None:
    # Remove multiple queue entries from a mode queue by entry_id

    entry_ids_set = set(entry_ids)

    queue_data[mode] = [
        entry for entry in queue_data.get(mode, [])
        if entry["entry_id"] not in entry_ids_set
    ]

# -----------------------
# User-facing summary helpers
# -----------------------

def build_match_summary_line(
    players_data: dict,
    team1: dict,
    team2: dict,
    queue_class: str,
    ) -> str:
    # Build a readable summary line for a created match

    def get_display_name_from_players(user_id: str) -> str:
        player = players_data.get(str(user_id))
        if player:
            return player.get("display_name", str(user_id))
        return str(user_id)

    team1_names = ", ".join(
        get_display_name_from_players(member_id)
        for member_id in team1["player_ids"]
    )

    team2_names = ", ".join(
        get_display_name_from_players(member_id)
        for member_id in team2["player_ids"]
    )

    return f"{team1_names} vs {team2_names} (Class {queue_class})"


# -----------------------
# New AutoMatch helper
# -----------------------

# -----------------------
# Matchmaking pass result helper
# -----------------------

def create_matchmaking_result() -> MatchMakingResult:
    # Standard result container for matchmaking passes

    return {
        "created_count": 0,
        "created_summaries": []
    }