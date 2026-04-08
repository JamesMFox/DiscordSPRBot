from utils.time_utils import utc_now_iso


def create_new_player_profile(
    user_id: int,
    username: str,
    avatar_url: str,
    display_name: str,
    signup_rank_role: str,
    starting_spr: int,
) -> dict:
    # Create a new player profile using the agreed structure
    return {
        "user_id": str(user_id),
        "username": username,
        "avatar_url": avatar_url,
        "display_name": display_name,
        "signed_up": True,
        "signup_rank_role": signup_rank_role,
        "starting_spr": starting_spr,
        "joined_at": utc_now_iso(),
        "is_banned_from_ranked": False,
        "is_mod": False,
        "incorrect_reports": 0,
        "notes": "",
        "modes": {
            "1v1": {
                "spr": starting_spr,
                "wins": 0,
                "losses": 0,
                "matches_played": 0,
                "streak": 0,
                "peak_spr": starting_spr,
                "last_match_at": None,
                "in_queue": False,
                "in_match": False,
                "active_match_id": None,
                "rankup_active": False,
                "rankup_target_class": None,
                "rankup_wins": 0,
                "rankup_losses": 0,
                "rankup_history": []
            },
            "2v2": {
                "spr": starting_spr,
                "wins": 0,
                "losses": 0,
                "matches_played": 0,
                "streak": 0,
                "peak_spr": starting_spr,
                "last_match_at": None,
                "in_queue": False,
                "in_match": False,
                "active_match_id": None,
                "rankup_active": False,
                "rankup_target_class": None,
                "rankup_wins": 0,
                "rankup_losses": 0,
                "rankup_history": []
            },
            "3v3": {
                "spr": starting_spr,
                "wins": 0,
                "losses": 0,
                "matches_played": 0,
                "streak": 0,
                "peak_spr": starting_spr,
                "last_match_at": None,
                "in_queue": False,
                "in_match": False,
                "active_match_id": None,
                "rankup_active": False,
                "rankup_target_class": None,
                "rankup_wins": 0,
                "rankup_losses": 0,
                "rankup_history": []
            }
        },
        "status": {
            "has_unresolved_match": False,
            "needs_mod_review": False
        }
    }

def get_display_name(players_data: dict, user_id: str | int) -> str:
    # Safely get a player's display name

    user_id = str(user_id)
    player = players_data.get(user_id)

    if player:
        return player.get("display_name", user_id)

    return str(user_id)

def get_display_names(players_data: dict, member_ids: list[str | int]) -> list[str]:
    # Return list of display names

    return [
        get_display_name(players_data, member_id)
        for member_id in member_ids
    ]

def format_player_names(players_data: dict, member_ids: list[str | int]) -> str:
    # Return a comma-separated string of display names

    return ", ".join(
        get_display_name(players_data, member_id)
        for member_id in member_ids
    )

def player_is_in_match_record(match_record: dict, user_id: str) -> bool:
    user_id = str(user_id)

    for key in ("player_ids", "winner_ids", "loser_ids", "team1_ids", "team2_ids"):
        values = match_record.get(key, [])
        if isinstance(values, list) and user_id in [str(x) for x in values]:
            return True

    if str(match_record.get("player1_id", "")) == user_id:
        return True

    if str(match_record.get("player2_id", "")) == user_id:
        return True

    return False


def get_match_participant_ids(match_record: dict) -> list[str]:
    participant_ids = set()

    for key in ("player_ids", "team1_ids", "team2_ids", "winner_ids", "loser_ids"):
        values = match_record.get(key, [])
        if isinstance(values, list):
            for value in values:
                participant_ids.add(str(value))

    for key in ("player1_id", "player2_id"):
        value = match_record.get(key)
        if value is not None:
            participant_ids.add(str(value))

    participant_ids.discard("None")
    participant_ids.discard("")
    return list(participant_ids)
