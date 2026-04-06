import discord
from discord import app_commands
from bot_instance import bot
from config import TEST_GUILD
from choices import TEAM_MODE_CHOICES
from data_manager import load_json, save_json, PLAYERS_FILE, DEFAULT_PLAYERS, TEAMS_FILE, DEFAULT_TEAMS
from utils.team_utils import (
    get_required_team_size,
    player_is_available_for_team,
    all_players_same_class,
    find_team_by_captain_and_mode,
    member_has_active_team_in_mode,
    find_team_by_member_and_mode,
)
from views import TeamConfirmView

@bot.tree.command(name="createteam", description="Create a team")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(mode=TEAM_MODE_CHOICES)
async def createteam(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
    player2: discord.Member,
    player3: discord.Member | None = None,
    team_name: str | None = None,
):
    selected_mode = mode.value

    if selected_mode not in ["2v2", "3v3"]:
        await interaction.response.send_message(
            "Premade teams are only allowed for 2v2 and 3v3.",
            ephemeral=True
        )
        return

    required_size = get_required_team_size(selected_mode)
    if required_size is None:
        await interaction.response.send_message(
            "Invalid mode for premade teams.",
            ephemeral=True
        )
        return

    member_objects = [interaction.user, player2]

    if selected_mode == "3v3":
        if player3 is None:
            await interaction.response.send_message(
                "3v3 teams require a third player.",
                ephemeral=True
            )
            return
        member_objects.append(player3)

    member_ids = [str(member.id) for member in member_objects]

    if len(set(member_ids)) != len(member_ids):
        await interaction.response.send_message(
            "You cannot add the same player more than once.",
            ephemeral=True
        )
        return

    if len(member_ids) != required_size:
        await interaction.response.send_message(
            f"{selected_mode} teams must have exactly {required_size} players.",
            ephemeral=True
        )
        return

    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    teams = load_json(TEAMS_FILE, DEFAULT_TEAMS)

    # Captain cannot already own an active team for this mode.
    existing_team = find_team_by_captain_and_mode(
        teams_data=teams,
        captain_id=interaction.user.id,
        mode=selected_mode
    )
    if existing_team:
        await interaction.response.send_message(
            f"You already have an active {selected_mode} team.",
            ephemeral=True
        )
        return

    # No member can already be on another active team for this mode.
    for member in member_objects:
        member_id = str(member.id)

        if member_id not in players:
            await interaction.response.send_message(
                f"{member.display_name} is not signed up.",
                ephemeral=True
            )
            return

        if not player_is_available_for_team(players[member_id], selected_mode):
            await interaction.response.send_message(
                f"{member.display_name} is not currently available for a team in {selected_mode}.",
                ephemeral=True
            )
            return

        if member_has_active_team_in_mode(teams, member_id, selected_mode):
            await interaction.response.send_message(
                f"{member.display_name} is already on another active {selected_mode} team.",
                ephemeral=True
            )
            return

    if not all_players_same_class(players, member_ids, selected_mode):
        await interaction.response.send_message(
            "All team members must be in the same class for that mode.",
            ephemeral=True
        )
        return

    view = TeamConfirmView(
        mode=selected_mode,
        captain=interaction.user,
        member_objects=member_objects,
        team_name=team_name
    )

    await interaction.response.send_message(
        content=view._build_status_message(),
        view=view
    )

    view.message = await interaction.original_response()


# -----------------------
# View Team Info Command
# -----------------------


@bot.tree.command(name="teaminfo", description="View your premade team")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(mode=TEAM_MODE_CHOICES)
async def teaminfo(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    selected_mode = mode.value
    teams = load_json(TEAMS_FILE, DEFAULT_TEAMS)
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)

    team = find_team_by_member_and_mode(
        teams_data=teams,
        member_id=interaction.user.id,
        mode=selected_mode
    )

    if not team:
        await interaction.response.send_message(
            f"You are not on an active {selected_mode} team.",
            ephemeral=True
        )
        return

    guild = interaction.guild
    member_names = []

    for member_id in team["member_ids"]:
        member_id = str(member_id)

        if member_id in players:
            member_names.append(players[member_id]["display_name"])
        else:
            member_names.append(member_id) # fallback to ID if not found in players data

    members_str = ", ".join(member_names)

    captain_id = str(team["captain_id"])

    if captain_id in players:
        captain_name = players[captain_id]["display_name"]
    else:
        captain_name = captain_id

    await interaction.response.send_message(
        f"Team ID: {team['team_id']}\n"
        f"Mode: {team['mode']}\n"
        f"Captain: {captain_name}\n"
        f"Members: {members_str}\n"
        f"Name: {team['name'] if team['name'] else 'None'}\n"
        f"Created At: {team['created_at']}\n"
        f"Last Used At: {team['last_used_at']}",
        ephemeral=True
    )


# -----------------------
# Disband Team Command
# -----------------------


@bot.tree.command(name="disbandteam", description="Disband your premade team")
@app_commands.guilds(TEST_GUILD)
@app_commands.choices(mode=TEAM_MODE_CHOICES)
async def disbandteam(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    selected_mode = mode.value
    teams = load_json(TEAMS_FILE, DEFAULT_TEAMS)

    team = find_team_by_captain_and_mode(
        teams_data=teams,
        captain_id=interaction.user.id,
        mode=selected_mode
    )

    if not team:
        await interaction.response.send_message(
            f"You do not have an active {selected_mode} team to disband.",
            ephemeral=True
        )
        return

    team["active"] = False
    save_json(TEAMS_FILE, teams)

    await interaction.response.send_message(
        f"Your {selected_mode} team ({team['team_id']}) has been disbanded.",
        ephemeral=True
    )
