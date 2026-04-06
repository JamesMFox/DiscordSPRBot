def get_match_participant_ids(match_record: dict) -> list[str]:
    return (
        [str(x) for x in match_record.get("team1", {}).get("player_ids", [])]
        + [str(x) for x in match_record.get("team2", {}).get("player_ids", [])]
    )