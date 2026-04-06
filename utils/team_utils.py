from typing import Optional

from utils.rank_utils import get_class_from_spr
from utils.time_utils import utc_now_iso


def generate_team_id(teams_data: dict) -> str:
    # Generate the next team ID like team_0001.
    if not teams_data:
        return "team_0001"

    existing_numbers = []

    for team_id in teams_data.keys():
        if team_id.startswith("team_"):
            try:
                number = int(team_id.split("_")[1])
                existing_numbers.append(number)
            except (IndexError, ValueError):
                continue

    next_number = max(existing_numbers, default=0) + 1
    return f"team_{next_number:04d}"


def create_team_profile(
    team_id: str,
    mode: str,
    captain_id: int,
    member_ids: list[int],
    name: Optional[str] = None,
) -> dict:
    # Create a premade team profile.
    return {
        "team_id": team_id,
        "mode": mode,
        "captain_id": str(captain_id),
        "member_ids": [str(member_id) for member_id in member_ids],
        "created_at": utc_now_iso(),
        "last_used_at": None,
        "active": True,
        "name": name
    }


def get_required_team_size(mode: str) -> Optional[int]:
    # Return the exact required premade size for a mode.
    if mode == "2v2":
        return 2
    if mode == "3v3":
        return 3
    return None


def player_is_available_for_team(player_profile: dict, mode: str) -> bool:
    # Return True if the player is available to join a premade in this mode.
    mode_data = player_profile["modes"][mode]

    return (
        not player_profile.get("is_banned_from_ranked", False)
        and not mode_data["in_queue"]
        and not mode_data["in_match"]
    )


def get_player_class_for_mode(player_profile: dict, mode: str) -> Optional[str]:
    #Return the player's current class in the requested mode.
    spr = player_profile["modes"][mode]["spr"]
    return get_class_from_spr(spr)

def all_players_same_class(players_data: dict, member_ids: list[str], mode: str) -> bool:
    # Return True if all listed players are in the same class for the mode.
    classes = set()

    for member_id in member_ids:
        player_profile = players_data.get(str(member_id))
        if not player_profile:
            return False

        class_name = get_player_class_for_mode(player_profile, mode)
        if class_name is None:
            return False

        classes.add(class_name)

    return len(classes) == 1

def find_team_by_captain_and_mode(teams_data: dict, captain_id: int, mode: str) -> Optional[dict]:
    # Find an active team by captain and mode.
    for team in teams_data.values():
        if (
            team["captain_id"] == str(captain_id)
            and team["mode"] == mode
            and team["active"] is True
        ):
            return team
    return None


def member_has_active_team_in_mode(teams_data: dict, member_id: int | str, mode: str) -> bool:
    """Return True if the member is already in an active team for the mode."""
    member_id = str(member_id)

    for team in teams_data.values():
        if team["mode"] == mode and team["active"] is True:
            if member_id in team["member_ids"]:
                return True

    return False


def any_member_already_on_active_team(teams_data: dict, member_ids: list[str], mode: str) -> bool:
    """Return True if any member is already in an active team for the mode."""
    for member_id in member_ids:
        if member_has_active_team_in_mode(teams_data, member_id, mode):
            return True
    return False

def find_team_by_member_and_mode(teams_data: dict, member_id: int | str, mode: str) -> Optional[dict]:
    # Find an active team by member and mode
    member_id = str(member_id)

    for team in teams_data.values():
        if (
            team["mode"] == mode
            and team["active"] is True
            and member_id in team["member_ids"]
        ):
            return team

    return None

def calculate_team_average_spr(players: dict, member_ids: list[str], mode: str) -> float:
    spr_values = []

    for player_id in member_ids:
        player = players.get(str(player_id))
        if not player:
            continue

        spr = player.get("modes", {}).get(mode, {}).get("spr")
        if isinstance(spr, (int, float)):
            spr_values.append(float(spr))

    if not spr_values:
        return 0.0

    return sum(spr_values) / len(spr_values)

