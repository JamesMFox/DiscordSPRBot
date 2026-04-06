from data_manager import (
    load_json, save_json,
    PLAYERS_FILE, DEFAULT_PLAYERS,
    QUEUE_FILE, DEFAULT_QUEUE,
    ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES,
    MATCHES_FILE, DEFAULT_MATCHES,
)
from utils.matchmaking_utils import (
    generate_match_id,
    create_match_team_object,
    create_active_match_record,
    group_queue_entries_by_class,
    find_best_1v1_match,
    set_players_in_match,
    remove_queue_entries_by_ids,
    build_match_summary_line,
    create_matchmaking_result,
    MatchMakingResult,
    find_best_2v2_match_for_class,
    find_best_3v3_match_for_class,
)
from utils.rankup_utils import (
    find_best_rankup_opponent_from_queue,
    find_best_rankup_2v2_opponent_from_queue,
    find_best_rankup_3v3_opponent_from_queue,
)

def _load_matchmaking_state():
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    matches = load_json(MATCHES_FILE, DEFAULT_MATCHES)
    return players, queue_data, active_matches, matches


def _save_matchmaking_state(players, queue_data, active_matches):
    save_json(QUEUE_FILE, queue_data)
    save_json(PLAYERS_FILE, players)
    save_json(ACTIVE_MATCHES_FILE, active_matches)

def _record_created_match(
    *,
    players,
    queue_data,
    active_matches,
    matches,
    result,
    mode: str,
    queue_class: str,
    team1: dict,
    team2: dict,
    used_entry_ids: list[str],
    match_type: str = "ranked",
):
    match_id = generate_match_id(active_matches, matches)

    active_matches[match_id] = create_active_match_record(
        match_id=match_id,
        mode=mode,
        match_type=match_type,
        team1=team1,
        team2=team2,
    )

    set_players_in_match(players, team1["player_ids"], mode, match_id)
    set_players_in_match(players, team2["player_ids"], mode, match_id)
    remove_queue_entries_by_ids(queue_data, mode, used_entry_ids)

    result["created_count"] += 1
    result["created_summaries"].append(
        build_match_summary_line(players, team1, team2, queue_class)
    )

def run_1v1_matchmaking_pass() -> MatchMakingResult:
    players, queue_data, active_matches, matches = _load_matchmaking_state()

    result = create_matchmaking_result()
    one_v_one_entries = queue_data.get("1v1", [])

    if len(one_v_one_entries) < 2:
        return result

    grouped = group_queue_entries_by_class(one_v_one_entries)

    for queue_class in list(grouped.keys()):
        while True:
            current_entries = [
                entry for entry in queue_data.get("1v1", [])
                if entry["queue_class"] == queue_class
            ]

            best_pair = find_best_1v1_match(current_entries)
            if not best_pair:
                break

            entry1, entry2 = best_pair
            team1 = create_match_team_object(entry1)
            team2 = create_match_team_object(entry2)

            _record_created_match(
                players=players,
                queue_data=queue_data,
                active_matches=active_matches,
                matches=matches,
                result=result,
                mode="1v1",
                queue_class=queue_class,
                team1=team1,
                team2=team2,
                used_entry_ids=[entry1["entry_id"], entry2["entry_id"]],
                match_type="solo",
            )

    _save_matchmaking_state(players, queue_data, active_matches)
    return result


def run_rankup_1v1_matchmaking_pass() -> MatchMakingResult:
    players, queue_data, active_matches, matches = _load_matchmaking_state()

    result = create_matchmaking_result()
    rankup_queue = queue_data.get("rankup", {}).get("1v1", [])
    normal_queue = queue_data.get("1v1", [])

    if not rankup_queue or not normal_queue:
        return result

    used_rankup_ids: list[str] = []
    used_normal_ids: list[str] = []

    for rankup_entry in rankup_queue:
        rankup_player_id = str(rankup_entry["member_ids"][0])
        if rankup_player_id not in players:
            continue

        mode_data = players[rankup_player_id]["modes"]["1v1"]
        if not mode_data.get("rankup_active", False):
            continue

        target_class = mode_data.get("rankup_target_class")
        rankup_spr = mode_data.get("spr")
        if target_class is None or rankup_spr is None:
            continue

        available_normal_entries = [
            entry for entry in normal_queue
            if entry["entry_id"] not in used_normal_ids
        ]

        opponent_entry = find_best_rankup_opponent_from_queue(
            players_data=players,
            queue_entries=available_normal_entries,
            rankup_player_spr=rankup_spr,
            target_class=target_class,
        )
        if not opponent_entry:
            continue

        match_id = generate_match_id(active_matches, matches)
        rankup_team = create_match_team_object(rankup_entry)
        opponent_team = create_match_team_object(opponent_entry)

        active_matches[match_id] = create_active_match_record(
            match_id=match_id,
            mode="1v1",
            match_type="rankup",
            team1=rankup_team,
            team2=opponent_team,
            rankup_match=True,
            rankup_player_id=rankup_player_id,
            rankup_target_class=target_class,
        )

        used_rankup_ids.append(rankup_entry["entry_id"])
        used_normal_ids.append(opponent_entry["entry_id"])

        set_players_in_match(players, rankup_entry["member_ids"], "1v1", match_id)
        set_players_in_match(players, opponent_entry["member_ids"], "1v1", match_id)

        result["created_count"] += 1
        result["created_summaries"].append(
            build_match_summary_line(players, rankup_team, opponent_team, rankup_entry["queue_class"])
        )

    if not used_rankup_ids and not used_normal_ids:
        return result

    queue_data.setdefault("rankup", {}).setdefault("1v1", [])
    queue_data["rankup"]["1v1"] = [
        entry for entry in rankup_queue if entry["entry_id"] not in used_rankup_ids
    ]
    queue_data["1v1"] = [
        entry for entry in normal_queue if entry["entry_id"] not in used_normal_ids
    ]

    _save_matchmaking_state(players, queue_data, active_matches)
    return result


def run_2v2_matchmaking_pass() -> MatchMakingResult:
    players, queue_data, active_matches, matches = _load_matchmaking_state()

    result = create_matchmaking_result()
    queue_entries = queue_data.get("2v2", [])
    if len(queue_entries) < 2:
        return result

    grouped = group_queue_entries_by_class(queue_entries)

    for queue_class in list(grouped.keys()):
        while True:
            class_entries = [
                entry for entry in queue_data.get("2v2", [])
                if entry["queue_class"] == queue_class
            ]

            match_result = find_best_2v2_match_for_class(class_entries, queue_class)
            if not match_result:
                break

            team1 = match_result["team1"]
            team2 = match_result["team2"]
            used_entry_ids = match_result["team1_entry_ids"] + match_result["team2_entry_ids"]

            _record_created_match(
                players=players,
                queue_data=queue_data,
                active_matches=active_matches,
                matches=matches,
                result=result,
                mode="2v2",
                queue_class=queue_class,
                team1=team1,
                team2=team2,
                used_entry_ids=used_entry_ids,
                match_type="ranked",
            )

    _save_matchmaking_state(players, queue_data, active_matches)
    return result

def run_rankup_2v2_matchmaking_pass():
    players, queue_data, active_matches, matches = _load_matchmaking_state()

    result = {
        "created_count": 0,
        "created_summaries": [],
    }

    rankup_entries = queue_data.get("rankup", {}).get("2v2", [])
    normal_entries = queue_data.get("2v2", [])

    used_rankup_entry_ids = set()
    used_normal_entry_ids = set()

    for rankup_entry in rankup_entries:
        rankup_entry_id = rankup_entry.get("entry_id")
        if rankup_entry_id in used_rankup_entry_ids:
            continue

        opponent_entry = find_best_rankup_2v2_opponent_from_queue(
            players=players,
            rankup_entry=rankup_entry,
            normal_queue_entries=[
                e for e in normal_entries
                if e.get("entry_id") not in used_normal_entry_ids
            ],
        )
        if not opponent_entry:
            continue

        rankup_team = create_match_team_object(rankup_entry)
        opponent_team = create_match_team_object(opponent_entry)
        match_id = generate_match_id(active_matches, matches)

        active_matches[match_id] = create_active_match_record(
            match_id=match_id,
            mode="2v2",
            match_type="rankup",
            team1=rankup_team,
            team2=opponent_team,
            is_rankup=True,
            rankup_owner_id=rankup_entry.get("rankup_owner_id"),
            rankup_participants=rankup_entry.get("rankup_participants", []),
            rankup_target_class=rankup_entry.get("rankup_target_class"),
        )

        set_players_in_match(players, rankup_team["player_ids"], "2v2", match_id)
        set_players_in_match(players, opponent_team["player_ids"], "2v2", match_id)

        used_rankup_entry_ids.add(rankup_entry_id)
        used_normal_entry_ids.add(opponent_entry.get("entry_id"))

        result["created_count"] += 1
        result["created_summaries"].append(
            build_match_summary_line(
                players,
                rankup_team,
                opponent_team,
                rankup_entry.get("queue_class", "unknown"),
            )
        )

    if used_rankup_entry_ids:
        queue_data["rankup"]["2v2"] = [
            e for e in queue_data.get("rankup", {}).get("2v2", [])
            if e.get("entry_id") not in used_rankup_entry_ids
        ]

    if used_normal_entry_ids:
        queue_data["2v2"] = [
            e for e in queue_data.get("2v2", [])
            if e.get("entry_id") not in used_normal_entry_ids
        ]

    _save_matchmaking_state(players, queue_data, active_matches)
    return result


def run_3v3_matchmaking_pass() -> MatchMakingResult:
    players, queue_data, active_matches, matches = _load_matchmaking_state()

    result = create_matchmaking_result()
    queue_entries = queue_data.get("3v3", [])
    if len(queue_entries) < 2:
        return result

    grouped = group_queue_entries_by_class(queue_entries)

    for queue_class in list(grouped.keys()):
        while True:
            class_entries = [
                entry for entry in queue_data.get("3v3", [])
                if entry["queue_class"] == queue_class
            ]

            match_result = find_best_3v3_match_for_class(class_entries, queue_class)
            if not match_result:
                break

            team1 = match_result["team1"]
            team2 = match_result["team2"]
            used_entry_ids = match_result["team1_entry_ids"] + match_result["team2_entry_ids"]

            _record_created_match(
                players=players,
                queue_data=queue_data,
                active_matches=active_matches,
                matches=matches,
                result=result,
                mode="3v3",
                queue_class=queue_class,
                team1=team1,
                team2=team2,
                used_entry_ids=used_entry_ids,
                match_type="ranked",
            )

    _save_matchmaking_state(players, queue_data, active_matches)
    return result

def run_rankup_3v3_matchmaking_pass():
    players, queue_data, active_matches, matches = _load_matchmaking_state()

    result = {
        "created_count": 0,
        "created_summaries": [],
    }

    rankup_entries = queue_data.get("rankup", {}).get("3v3", [])
    normal_entries = queue_data.get("3v3", [])

    used_rankup_entry_ids = set()
    used_normal_entry_ids = set()

    for rankup_entry in rankup_entries:
        rankup_entry_id = rankup_entry.get("entry_id")
        if rankup_entry_id in used_rankup_entry_ids:
            continue

        opponent_entry = find_best_rankup_3v3_opponent_from_queue(
            players=players,
            rankup_entry=rankup_entry,
            normal_queue_entries=[
                e for e in normal_entries
                if e.get("entry_id") not in used_normal_entry_ids
            ],
        )
        if not opponent_entry:
            continue

        rankup_team = create_match_team_object(rankup_entry)
        opponent_team = create_match_team_object(opponent_entry)
        match_id = generate_match_id(active_matches, matches)

        active_matches[match_id] = create_active_match_record(
            match_id=match_id,
            mode="3v3",
            match_type="rankup",
            team1=rankup_team,
            team2=opponent_team,
            is_rankup=True,
            rankup_owner_id=rankup_entry.get("rankup_owner_id"),
            rankup_participants=rankup_entry.get("rankup_participants", []),
            rankup_target_class=rankup_entry.get("rankup_target_class"),
        )

        set_players_in_match(players, rankup_team["player_ids"], "3v3", match_id)
        set_players_in_match(players, opponent_team["player_ids"], "3v3", match_id)

        used_rankup_entry_ids.add(rankup_entry_id)
        used_normal_entry_ids.add(opponent_entry.get("entry_id"))

        result["created_count"] += 1
        result["created_summaries"].append(
            build_match_summary_line(
                players,
                rankup_team,
                opponent_team,
                rankup_entry.get("queue_class", "unknown"),
            )
        )

    if used_rankup_entry_ids:
        queue_data["rankup"]["3v3"] = [
            e for e in queue_data.get("rankup", {}).get("3v3", [])
            if e.get("entry_id") not in used_rankup_entry_ids
        ]

    if used_normal_entry_ids:
        queue_data["3v3"] = [
            e for e in queue_data.get("3v3", [])
            if e.get("entry_id") not in used_normal_entry_ids
        ]

    _save_matchmaking_state(players, queue_data, active_matches)
    return result

