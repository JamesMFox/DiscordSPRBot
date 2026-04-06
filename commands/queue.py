import discord
from discord import app_commands
from bot_instance import bot
from data_manager import (
    load_json, save_json,
    PLAYERS_FILE, DEFAULT_PLAYERS,
    QUEUE_FILE, DEFAULT_QUEUE,
    TEAMS_FILE, DEFAULT_TEAMS,
)
from config import TEST_GUILD
from choices import QUEUE_MODE_CHOICES, TEAM_MODE_CHOICES
from utils.queue_utils import (
    generate_queue_entry_id,
    create_solo_queue_entry,
    create_premade_queue_entry,
    get_player_spr_for_mode,
    get_player_queue_class_for_mode,
    calculate_average_spr,
    find_any_queue_entry_for_member_any_mode,
    get_queue_block_reason,
    get_team_queue_block_reason,
    set_player_queue_state,
    find_solo_queue_entry_any_mode,
    find_premade_queue_entry_by_captain_any_mode,
    find_any_queue_entry_for_member_any_mode_with_mode,
    remove_queue_entry_by_id,
    set_multiple_players_queue_state,
)
from utils.team_utils import find_team_by_captain_and_mode, all_players_same_class
from utils.rankup_utils import captain_can_start_team_rankup
from views import TeamRankupConfirmView
from services.matchmaking_service import (
    run_1v1_matchmaking_pass,
    run_2v2_matchmaking_pass,
    run_3v3_matchmaking_pass,
    run_rankup_1v1_matchmaking_pass,
)


@bot.tree.command(name="queuesolo", description="Join queue for solo matchmaking")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(mode=QUEUE_MODE_CHOICES)
async def queuesolo(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    selected_mode = mode.value

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message(
            "You are not signed up. Use /signup first.",
            ephemeral=True,
        )
        return

    for required_mode in ["1v1", "2v2", "3v3"]:
        if required_mode not in queue_data:
            queue_data[required_mode] = []
    queue_data.setdefault("rankup", {"1v1": [], "2v2": [], "3v3": []})

    player_profile = players[user_id]

    if selected_mode not in player_profile.get("modes", {}):
        await interaction.response.send_message(
            f"Your profile is missing data for {selected_mode}. Contact a moderator.",
            ephemeral=True,
        )
        return

    block_reason = get_queue_block_reason(player_profile, selected_mode)
    if block_reason:
        await interaction.response.send_message(
            f"Queue failed: {block_reason}",
            ephemeral=True,
        )
        return

    existing_entry = find_any_queue_entry_for_member_any_mode(queue_data, user_id)
    if existing_entry:
        await interaction.response.send_message(
            "Queue failed: You are already in queue.",
            ephemeral=True,
        )
        return

    spr = get_player_spr_for_mode(player_profile, selected_mode)
    queue_class = get_player_queue_class_for_mode(player_profile, selected_mode)
    if queue_class is None:
        await interaction.response.send_message(
            "Queue failed: Could not determine your class.",
            ephemeral=True,
        )
        return

    entry_id = generate_queue_entry_id(queue_data)
    queue_entry = create_solo_queue_entry(
        entry_id=entry_id,
        mode=selected_mode,
        user_id=interaction.user.id,
        spr=spr,
        queue_class=queue_class,
    )
    queue_data[selected_mode].append(queue_entry)
    set_player_queue_state(player_profile, selected_mode, True)

    save_json(QUEUE_FILE, queue_data)
    save_json(PLAYERS_FILE, players)

    matchmaking_result = None
    if selected_mode == "1v1":
        matchmaking_result = run_rankup_1v1_matchmaking_pass()
        if matchmaking_result["created_count"] == 0:
            matchmaking_result = run_1v1_matchmaking_pass()
    elif selected_mode == "2v2":
        matchmaking_result = run_2v2_matchmaking_pass()
    elif selected_mode == "3v3":
        matchmaking_result = run_3v3_matchmaking_pass()

    if matchmaking_result and matchmaking_result["created_count"] > 0:
        await interaction.response.send_message(
            f"Queued for {selected_mode}\n"
            f"SPR: {spr}\n"
            f"Class: {queue_class}\n"
            f"Entry ID: {entry_id}\n\n"
            f"Matchmaking found:\n" + "\n".join(matchmaking_result["created_summaries"]),
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"Queued for {selected_mode}\n"
        f"SPR: {spr}\n"
        f"Class: {queue_class}\n"
        f"Entry ID: {entry_id}",
        ephemeral=True,
    )


@bot.tree.command(name="queueteam", description="Join queue with your premade team")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(mode=TEAM_MODE_CHOICES)
async def queueteam(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    selected_mode = mode.value

    if selected_mode not in ["2v2", "3v3"]:
        await interaction.response.send_message(
            "Team queue is only available for 2v2 and 3v3.",
            ephemeral=True,
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    teams = load_json(TEAMS_FILE, DEFAULT_TEAMS)
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    captain_id = str(interaction.user.id)

    for required_mode in ["1v1", "2v2", "3v3"]:
        if required_mode not in queue_data:
            queue_data[required_mode] = []
    queue_data.setdefault("rankup", {"1v1": [], "2v2": [], "3v3": []})

    team = find_team_by_captain_and_mode(
        teams_data=teams,
        captain_id=interaction.user.id,
        mode=selected_mode,
    )
    if not team:
        await interaction.response.send_message(
            f"You do not have an active {selected_mode} team.",
            ephemeral=True,
        )
        return

    member_ids = [str(member_id) for member_id in team["member_ids"]]
    block_reason = get_team_queue_block_reason(players, member_ids, selected_mode)
    if block_reason:
        await interaction.response.send_message(
            f"Team queue failed: {block_reason}",
            ephemeral=True,
        )
        return

    for member_id in member_ids:
        existing_entry = find_any_queue_entry_for_member_any_mode(queue_data, member_id)
        if existing_entry:
            display_name = players[member_id]["display_name"]
            await interaction.response.send_message(
                f"Team queue failed: {display_name} is already in queue.",
                ephemeral=True,
            )
            return

    if not all_players_same_class(players, member_ids, selected_mode):
        await interaction.response.send_message(
            "Team queue failed: All team members must still be in the same class for this mode.",
            ephemeral=True,
        )
        return

    average_spr = calculate_average_spr(players, member_ids, selected_mode)
    captain_profile = players[captain_id]
    queue_class = get_player_queue_class_for_mode(captain_profile, selected_mode)
    if queue_class is None:
        await interaction.response.send_message(
            "Team queue failed: Could not determine the team's class.",
            ephemeral=True,
        )
        return

    entry_id = generate_queue_entry_id(queue_data)
    queue_entry = create_premade_queue_entry(
        entry_id=entry_id,
        mode=selected_mode,
        captain_id=interaction.user.id,
        member_ids=member_ids,
        team_id=team["team_id"],
        average_spr=average_spr,
        queue_class=queue_class,
    )
    queue_data[selected_mode].append(queue_entry)

    for member_id in member_ids:
        set_player_queue_state(players[member_id], selected_mode, True)

    save_json(QUEUE_FILE, queue_data)
    save_json(PLAYERS_FILE, players)

    member_names = ", ".join(players[member_id]["display_name"] for member_id in member_ids)

    if selected_mode == "2v2":
        matchmaking_result = run_2v2_matchmaking_pass()
        if matchmaking_result["created_count"] > 0:
            await interaction.response.send_message(
                f"Your team joined queue for {selected_mode}.\n"
                f"Team ID: {team['team_id']}\n"
                f"Members: {member_names}\n"
                f"Average SPR: {average_spr}\n"
                f"Queue Class: {queue_class}\n"
                f"Entry ID: {entry_id}\n\n"
                f"Matchmaking found:\n" + "\n".join(matchmaking_result["created_summaries"]),
                ephemeral=True,
            )
            return

    if selected_mode == "3v3":
        matchmaking_result = run_3v3_matchmaking_pass()
        if matchmaking_result["created_count"] > 0:
            await interaction.response.send_message(
                f"Your team joined queue for {selected_mode}.\n"
                f"Team ID: {team['team_id']}\n"
                f"Members: {member_names}\n"
                f"Average SPR: {average_spr}\n"
                f"Queue Class: {queue_class}\n"
                f"Entry ID: {entry_id}\n\n"
                f"Matchmaking found:\n" + "\n".join(matchmaking_result["created_summaries"]),
                ephemeral=True,
            )
            return

    await interaction.response.send_message(
        f"Your team joined queue for {selected_mode}.\n"
        f"Team ID: {team['team_id']}\n"
        f"Members: {member_names}\n"
        f"Average SPR: {average_spr}\n"
        f"Queue Class: {queue_class}\n"
        f"Entry ID: {entry_id}",
        ephemeral=True,
    )


@bot.tree.command(name="queuerankup", description="Queue for a 1v1 rank-up series")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(mode=[
    app_commands.Choice(name="1v1", value="1v1"),
    app_commands.Choice(name="2v2", value="2v2"),
    app_commands.Choice(name="3v3", value="3v3"),
    ])
async def queuerankup(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    selected_mode = mode.value
    user_id = str(interaction.user.id)

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)

    if user_id not in players:
        await interaction.response.send_message("You are not signed up.", ephemeral=True)
        return

    player = players[user_id]
    mode_data = player["modes"][selected_mode]

    if not mode_data.get("rankup_active", False):
        await interaction.response.send_message(
            f"You do not have an active {selected_mode} rank-up. Use `/rankup mode:{selected_mode}` first.",
            ephemeral=True,
        )
        return

    if mode_data.get("in_match", False):
        await interaction.response.send_message(
            "You cannot queue rank-up while in a match.",
            ephemeral=True,
        )
        return

    if mode_data.get("in_queue", False):
        await interaction.response.send_message(
            "You are already in a queue.",
            ephemeral=True,
        )
        return

    queue_data.setdefault("rankup", {})
    queue_data["rankup"].setdefault(selected_mode, [])

    existing_entry = find_any_queue_entry_for_member_any_mode(queue_data, user_id)
    if existing_entry:
        await interaction.response.send_message(
            "Queue failed: You are already queued.",
            ephemeral=True,
        )
        return

    spr = get_player_spr_for_mode(player, selected_mode)
    queue_class = get_player_queue_class_for_mode(player, selected_mode)
    if queue_class is None:
        await interaction.response.send_message(
            "Queue failed: Could not determine your class.",
            ephemeral=True,
        )
        return

    

    if selected_mode in ("2v2", "3v3"):
        players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
        teams = load_json(TEAMS_FILE, DEFAULT_TEAMS)

        ok, error_message, captain_info = captain_can_start_team_rankup(
            players=players,
            captain_id=str(interaction.user.id),
            mode=selected_mode,
        )
        if not ok:
            await interaction.response.send_message(error_message, ephemeral=True)
            return

        team_record = find_team_by_captain_and_mode(
            teams=teams,
            captain_id=str(interaction.user.id),
            mode=selected_mode,
        )
        if not team_record:
            await interaction.response.send_message(
                f"You are not the captain of a {selected_mode} team.",
                ephemeral=True,
            )
            return

        team_member_ids = [str(x) for x in team_record.get("member_ids", [])]
        required_size = 2 if selected_mode == "2v2" else 3
        if len(team_member_ids) != required_size:
            await interaction.response.send_message(
                f"Your team must have exactly {required_size} members for {selected_mode} rank-up.",
                ephemeral=True,
            )
            return

        view = TeamRankupConfirmView(
            mode=selected_mode,
            captain=interaction.user,
            team_record=team_record,
            rankup_target_class=captain_info["target_class"],
        )

        await interaction.response.send_message(
            content=view._build_status_message(),
            view=view,
        )
        view.message = await interaction.original_response()
        return

    entry_id = generate_queue_entry_id(queue_data)
    queue_entry = create_solo_queue_entry(
        entry_id=entry_id,
        mode=selected_mode,
        user_id=interaction.user.id,
        spr=spr,
        queue_class=queue_class,
    )

    queue_data["rankup"]["1v1"].append(queue_entry)
    set_player_queue_state(player, selected_mode, True)

    save_json(QUEUE_FILE, queue_data)
    save_json(PLAYERS_FILE, players)

    matchmaking_result = run_rankup_1v1_matchmaking_pass()
    if matchmaking_result["created_count"] > 0:
        await interaction.response.send_message(
            f"Queued for 1v1 rank-up.\n"
            f"SPR: {spr}\n"
            f"Class: {queue_class}\n"
            f"Entry ID: {entry_id}\n\n"
            f"Match found:\n" + "\n".join(matchmaking_result["created_summaries"]),
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"Queued for 1v1 rank-up.\n"
        f"SPR: {spr}\n"
        f"Class: {queue_class}\n"
        f"Entry ID: {entry_id}\n"
        f"Target Class: {mode_data.get('rankup_target_class')}",
        ephemeral=True,
    )


@bot.tree.command(name="leavequeue", description="Leave your current queue")
@app_commands.guilds(TEST_GUILD)
async def leavequeue(interaction: discord.Interaction):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)
    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message(
            "You are not signed up.",
            ephemeral=True,
        )
        return

    for required_mode in ["1v1", "2v2", "3v3"]:
        if required_mode not in queue_data:
            queue_data[required_mode] = []
    queue_data.setdefault("rankup", {"1v1": [], "2v2": [], "3v3": []})

    solo_result = find_solo_queue_entry_any_mode(queue_data, user_id)
    if solo_result:
        mode_name, solo_entry = solo_result
        if mode_name.startswith("rankup:"):
            actual_mode = mode_name.split(":", 1)[1]
            rankup_entries = queue_data["rankup"].get(actual_mode, [])
            for index, entry in enumerate(rankup_entries):
                if entry.get("entry_id") == solo_entry["entry_id"]:
                    del rankup_entries[index]
                    set_player_queue_state(players[user_id], actual_mode, False)
                    save_json(QUEUE_FILE, queue_data)
                    save_json(PLAYERS_FILE, players)
                    await interaction.response.send_message(
                        f"You left the {actual_mode} rank-up queue.",
                        ephemeral=True,
                    )
                    return

        removed = remove_queue_entry_by_id(queue_data, mode_name, solo_entry["entry_id"])
        if removed:
            set_player_queue_state(players[user_id], mode_name, False)
            save_json(QUEUE_FILE, queue_data)
            save_json(PLAYERS_FILE, players)
            await interaction.response.send_message(
                f"You left solo queue for {mode_name}.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Failed to remove your solo queue entry.",
            ephemeral=True,
        )
        return

    premade_result = find_premade_queue_entry_by_captain_any_mode(queue_data, user_id)
    if premade_result:
        mode_name, premade_entry = premade_result
        if mode_name.startswith("rankup:"):
            await interaction.response.send_message(
                "Rank-up queue only supports solo entries.",
                ephemeral=True,
            )
            return

        removed = remove_queue_entry_by_id(queue_data, mode_name, premade_entry["entry_id"])
        if removed:
            member_ids = [str(member_id) for member_id in premade_entry["member_ids"]]
            set_multiple_players_queue_state(players, member_ids, mode_name, False)
            save_json(QUEUE_FILE, queue_data)
            save_json(PLAYERS_FILE, players)
            await interaction.response.send_message(
                f"Your team left queue for {mode_name}.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Failed to remove your team queue entry.",
            ephemeral=True,
        )
        return

    any_result = find_any_queue_entry_for_member_any_mode_with_mode(queue_data, user_id)
    if any_result:
        mode_name, entry = any_result
        if entry["entry_type"] == "premade" and entry["captain_id"] != user_id:
            visible_mode = mode_name.split(":", 1)[1] if mode_name.startswith("rankup:") else mode_name
            await interaction.response.send_message(
                f"Your team is queued in {visible_mode} mode, but only the team captain can remove the team from queue.",
                ephemeral=True,
            )
            return

    await interaction.response.send_message(
        "You are not currently queued.",
        ephemeral=True,
    )
