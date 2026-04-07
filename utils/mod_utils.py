import discord

def remove_player_from_queue_data(queue_data: dict, user_id: str) -> int:
    """
    Remove a player from all queue buckets.

    Returns:
        int: number of queue entries removed
    """
    user_id = str(user_id)
    removed_count = 0

    # Ensure expected top-level keys exist
    queue_data.setdefault("1v1", [])
    queue_data.setdefault("2v2", [])
    queue_data.setdefault("3v3", [])
    queue_data.setdefault("rankup", {})
    queue_data["rankup"].setdefault("1v1", [])
    queue_data["rankup"].setdefault("2v2", [])
    queue_data["rankup"].setdefault("3v3", [])

    def entry_contains_player(entry: dict, target_user_id: str) -> bool:
        if str(entry.get("player_id", "")) == target_user_id:
            return True

        if str(entry.get("captain_id", "")) == target_user_id:
            return True

        member_ids = [str(x) for x in entry.get("member_ids", [])]
        if target_user_id in member_ids:
            return True

        rankup_participants = [str(x) for x in entry.get("rankup_participants", [])]
        if target_user_id in rankup_participants:
            return True

        return False

    # Normal ranked queues
    for mode in ("1v1", "2v2", "3v3"):
        original_entries = queue_data.get(mode, [])
        filtered_entries = []

        for entry in original_entries:
            if entry_contains_player(entry, user_id):
                removed_count += 1
            else:
                filtered_entries.append(entry)

        queue_data[mode] = filtered_entries

    # Rank-up queues
    for mode in ("1v1", "2v2", "3v3"):
        original_entries = queue_data["rankup"].get(mode, [])
        filtered_entries = []

        for entry in original_entries:
            if entry_contains_player(entry, user_id):
                removed_count += 1
            else:
                filtered_entries.append(entry)

        queue_data["rankup"][mode] = filtered_entries

    return removed_count

def remove_player_from_active_matches(active_matches: dict, user_id: str) -> list[str]:
    affected_match_ids = []

    for match_id, match_record in active_matches.items():
        found = False

        for key in ("player_ids", "winner_ids", "loser_ids"):
            values = match_record.get(key, [])
            if isinstance(values, list) and user_id in [str(x) for x in values]:
                found = True

        for key in ("team1_ids", "team2_ids"):
            values = match_record.get(key, [])
            if isinstance(values, list) and user_id in [str(x) for x in values]:
                found = True

        if str(match_record.get("player1_id", "")) == user_id:
            found = True

        if str(match_record.get("player2_id", "")) == user_id:
            found = True

        if found:
            affected_match_ids.append(match_id)

    return affected_match_ids

def build_modhelp_embed(user: discord.abc.User) -> discord.Embed:
    embed = discord.Embed(
        title="SPR Moderator Command Center",
        description=(
            "These commands are restricted to moderators (`spr-MOD` role).\n\n"
            "Use these tools to manage players, resolve disputes, and control matchmaking."
        ),
        color=discord.Color.orange(),
    )

    # PLAYER MANAGEMENT
    embed.add_field(
        name="👤 Player Management",
        value=(
            "`/spr mod playerinfo @player` — View full player data (SPR, queues, matches)\n"
            "`/spr mod repairplayer @player` — Hard reset queue/match state for a player\n"
            "`/spr mod repairstate @player` — Fix stuck flags without wiping stats"
        ),
        inline=False,
    )

    # MATCH CONTROL
    embed.add_field(
        name="⚔️ Match Control",
        value=(
            "`/spr admin active1v1matches` — View all active 1v1 matches\n"
            "`/spr mod cancelmatch match_id` — Cancel a match and reset players\n"
            "`/spr admin finalize1v1 match_id` — Force finalize a 1v1 match result"
        ),
        inline=False,
    )

    # DISPUTES
    embed.add_field(
        name="🚨 Disputes",
        value=(
            "`/spr mod viewdisputes` — View all disputed matches\n"
            "`/spr mod resolve match_id` — Resolve a disputed match manually"
        ),
        inline=False,
    )

    # MATCHMAKING CONTROL
    embed.add_field(
        name="🎯 Matchmaking Control",
        value=(
            "`/spr mod runmatchmaking1v1` — Force a matchmaking pass for 1v1\n"
            "`/spr mod runmatchmaking2v2` — Force a matchmaking pass for 2v2\n"
            "`/spr mod runmatchmaking3v3` — Force a matchmaking pass for 3v3"
        ),
        inline=False,
    )

    # TESTING / DEV TOOLS
    embed.add_field(
        name="🧪 Testing Tools",
        value=(
            "`/spr admin matchtest2v2` — Create a test 2v2 match instantly\n"
            "`/spr admin matchtest3v3` — Create a test 3v3 match instantly"
        ),
        inline=False,
    )

    # RANK-UP DEBUG CONTEXT
    embed.add_field(
        name="📈 Rank-Up Moderation Notes",
        value=(
            "• 1v1 rank-up is tracked per player\n"
            "• 2v2 / 3v3 rank-up is tracked per participant list\n"
            "• Captain owns the queue, but multiple players may progress\n"
            "• Use `/spr mod repairplayer` if a player gets stuck mid-series"
        ),
        inline=False,
    )

    # COMMON FIXES
    embed.add_field(
        name="🛠️ Common Fixes",
        value=(
            "• Player stuck in queue → `/spr mod repairplayer`\n"
            "• Match not resolving → `/spr mod resolve`\n"
            "• Match bugged → `/spr mod cancelmatch`\n"
            "• Queue not popping → `/spr mod runmatchmaking1v1` (or 2v2/3v3)"
        ),
        inline=False,
    )

    embed.set_footer(text=f"Requested by {user.display_name}")
    return embed