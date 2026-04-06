# -----------------------
# Match/team lookup helpers
# -----------------------

def find_player_team_key(match_record: dict, user_id: int | str) -> str | None:
    # Return "team1" or "team2" if the player is in that team
    user_id = str(user_id)

    if user_id in match_record["team1"]["player_ids"]:
        return "team1"

    if user_id in match_record["team2"]["player_ids"]:
        return "team2"

    return None


def get_opposite_team_key(team_key: str) -> str | None:
    # Return the opposite team key
    if team_key == "team1":
        return "team2"

    if team_key == "team2":
        return "team1"

    return None


# -----------------------
# Report state helpers
# -----------------------

def build_team_report(team_key: str, user_id: int | str, result: str, timestamp: str) -> dict:
    # Build a report payload for one team
    return {
        "reported_by": str(user_id),
        "result": result,
        "reported_at": timestamp
    }


def reports_are_complete_for_1v1(match_record: dict) -> bool:
    # Return True if both team1 and team2 have submitted reports
    return (
        match_record["reports"]["team1"]["result"] is not None
        and match_record["reports"]["team2"]["result"] is not None
    )


def reports_agree_for_1v1(match_record: dict) -> bool:
    # Return True if the reports are logically consistent
    team1_result = match_record["reports"]["team1"]["result"]
    team2_result = match_record["reports"]["team2"]["result"]

    if team1_result is None or team2_result is None:
        return False

    return (
        (team1_result == "win" and team2_result == "loss")
        or (team1_result == "loss" and team2_result == "win")
    )

# -----------------------
# Team report helpers
# -----------------------

def has_team_already_reported(match_record: dict, team_key: str) -> bool:
    # Return True if this team already has a stored report

    return match_record["reports"][team_key]["result"] is not None


def reports_are_complete_for_team_match(match_record: dict) -> bool:
    # Return True if both teams have submitted reports

    return (
        match_record["reports"]["team1"]["result"] is not None
        and match_record["reports"]["team2"]["result"] is not None
    )


def reports_agree_for_team_match(match_record: dict) -> bool:
    # Return True if the two team reports are logically consistent

    team1_result = match_record["reports"]["team1"]["result"]
    team2_result = match_record["reports"]["team2"]["result"]

    if team1_result is None or team2_result is None:
        return False

    return (
        (team1_result == "win" and team2_result == "loss")
        or (team1_result == "loss" and team2_result == "win")
    )