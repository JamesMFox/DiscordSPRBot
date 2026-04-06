def rebuild_player_state_from_files(player_id: str, players: dict, queue_data: dict, active_matches: dict) -> dict:
    player = players.get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found in players data.")

    modes = ["1v1", "2v2", "3v3"]

    for mode in modes:
        if mode not in player.get("modes", {}):
            continue
        player["modes"][mode]["in_queue"] = False
        player["modes"][mode]["in_match"] = False
        player["modes"][mode]["active_match_id"] = None

    queue_hits = []
    active_match_hits = []

    # normal queues
    for mode in modes:
        for entry in queue_data.get(mode, []):
            member_ids = [str(x) for x in entry.get("member_ids", [])]
            if player_id in member_ids:
                if mode in player["modes"]:
                    player["modes"][mode]["in_queue"] = True

                if entry.get("entry_type") == "premade":
                    queue_hits.append(f"{mode} premade")
                else:
                    queue_hits.append(f"{mode} solo")

    # rankup queues
    rankup_bucket = queue_data.get("rankup", {})
    for mode, entries in rankup_bucket.items():
        if mode not in modes:
            continue

        for entry in entries:
            member_ids = [str(x) for x in entry.get("member_ids", [])]
            if player_id in member_ids:
                if mode in player["modes"]:
                    player["modes"][mode]["in_queue"] = True
                queue_hits.append(f"{mode} rankup")

    # active matches
    for match_id, match_record in active_matches.items():
        mode = match_record.get("mode")
        if mode not in modes:
            continue

        team1_ids = [str(x) for x in match_record.get("team1", {}).get("player_ids", [])]
        team2_ids = [str(x) for x in match_record.get("team2", {}).get("player_ids", [])]
        participant_ids = team1_ids + team2_ids

        if player_id in participant_ids:
            if mode in player["modes"]:
                player["modes"][mode]["in_match"] = True
                player["modes"][mode]["active_match_id"] = match_id
                player["modes"][mode]["in_queue"] = False

            active_match_hits.append(f"{mode} -> {match_id}")

    return {
        "player_id": player_id,
        "queue_hits": queue_hits,
        "active_match_hits": active_match_hits,
    }

def rebuild_multiple_players_state(player_ids: list[str], players: dict, queue_data: dict, active_matches: dict) -> None:
    for player_id in player_ids:
        if player_id in players:
            rebuild_player_state_from_files(
                player_id=player_id,
                players=players,
                queue_data=queue_data,
                active_matches=active_matches,
            )

def clear_player_runtime_flags(player: dict) -> None:
    for mode in ["1v1", "2v2", "3v3"]:
        if mode not in player.get("modes", {}):
            continue

        player["modes"][mode]["in_queue"] = False
        player["modes"][mode]["in_match"] = False
        player["modes"][mode]["active_match_id"] = None