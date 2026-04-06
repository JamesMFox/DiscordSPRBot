
# rankup_queue.py
# Unified rankup queue system (no separate team mode)

rankup_attempts = {}  
# user_id: {"mode": "2v2"/"3v3", "accepted_higher": bool}

team_confirmations = {}  
# captain_id: set(teammate_ids)

def start_rankup(user_id, mode):
    rankup_attempts[user_id] = {
        "mode": mode,
        "accepted_higher": False
    }

def confirm_teammate(captain_id, teammate_id):
    if captain_id not in team_confirmations:
        team_confirmations[captain_id] = set()
    team_confirmations[captain_id].add(teammate_id)
    return True, "Teammate confirmed."

def accept_higher_class(teammate_id):
    rankup_attempts[teammate_id] = {
        "mode": None,
        "accepted_higher": True
    }

def can_queue_rankup(captain_id, team_ids):
    # Captain MUST have active rankup
    if captain_id not in rankup_attempts:
        return False, "Captain must have active rankup."

    mode = rankup_attempts[captain_id]["mode"]
    required_size = 2 if mode == "2v2" else 3

    if len(team_ids) != required_size:
        return False, "Invalid team size."

    # Check confirmations
    confirmed = team_confirmations.get(captain_id, set())
    for member in team_ids:
        if member == captain_id:
            continue
        if member not in confirmed:
            return False, f"{member} has not confirmed."

        # Teammate logic:
        if member not in rankup_attempts:
            return False, f"{member} must accept higher class."

    return True, "Queue valid."

def get_match_target_class(current_class):
    # Always match against lowest tier of next class
    return current_class + 1
