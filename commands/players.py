import discord
from discord import app_commands
from bot_instance import bot
from config import TEST_GUILD
from data_manager import (
    load_json,
    save_json,
    PLAYERS_FILE,
    DEFAULT_PLAYERS,
    ACTIVE_MATCHES_FILE,
    DEFAULT_ACTIVE_MATCHES,
    DISPUTED_FILE,
    DEFAULT_DISPUTED,
)
from utils.rank_utils import get_rank_data_from_discord_roles, get_class_from_spr, get_tier_from_spr
from views import SignupConfirmView
from utils.player_utils import player_is_in_match_record, get_match_participant_ids
from utils.time_utils import utc_now_iso

@bot.tree.command(name="signup", description="Sign up to participate in the competitive ladder")
@app_commands.guilds(TEST_GUILD)
async def signup(interaction: discord.Interaction):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    user_id = str(interaction.user.id)

    if user_id in players:
        await interaction.response.send_message(
            "You are already signed up.",
            ephemeral=True
        )
        return

    rank_data = get_rank_data_from_discord_roles(interaction.user.roles)

    if rank_data is None:
        await interaction.response.send_message(
            "Signup failed. You need a valid rank role before signing up.",
            ephemeral=True
        )
        return

    # print("DEBUG rank_data:", rank_data)
    rank_role = rank_data["rank_role"]
    starting_spr = rank_data["spr"]

    view = SignupConfirmView(
        user_id=interaction.user.id,
        rank_role=rank_role,
        starting_spr=starting_spr
    )

    await interaction.response.send_message(
        content=(
            f"I found your highest valid rank role as **{rank_role}**.\n"
            f"Starting SPR will be **{starting_spr}** for 1v1, 2v2, and 3v3.\n\n"
            f"Click **Confirm Signup** to continue."
        ),
        view=view,
        ephemeral=True
    )

    view.message = await interaction.original_response()


# -----------------------
# profile Command
# -----------------------

@bot.tree.command(name="profile", description="View your player profile")
@app_commands.guilds(TEST_GUILD)
async def profile(interaction: discord.Interaction):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)

    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message(
            "You are not signed up.",
            ephemeral=True
        )
        return

    player = players[user_id]

    lines = []

    # -----------------------
    # Basic info
    # -----------------------
    lines.append(f"Player: {player['display_name']}")
    lines.append(f"Signup Rank Role: {player['signup_rank_role']}")
    lines.append(f"Incorrect Reports: {player.get('incorrect_reports', 0)}")
    lines.append("")

    # -----------------------
    # Mode data
    # -----------------------
    for mode in ["1v1", "2v2", "3v3"]:
        mode_data = player["modes"][mode]
        spr = mode_data["spr"]

        class_name = get_class_from_spr(spr)
        tier_name = get_tier_from_spr(spr)

        lines.append(f"{mode}")
        lines.append(f"SPR: {spr} ({class_name} - {tier_name})")
        lines.append(f"W/L: {mode_data['wins']}/{mode_data['losses']} (Matches: {mode_data['matches_played']})")
        lines.append(f"Streak: {mode_data['streak']}")
        lines.append(f"Peak SPR: {mode_data['peak_spr']}")

        # -----------------------
        # Rank-up info
        # -----------------------
        if mode_data.get("rankup_active"):
            lines.append("Rank-up Active")
            lines.append(f"Target Class: {mode_data['rankup_target_class']}")
            lines.append(f"Wins: {mode_data['rankup_wins']}")
            lines.append(f"Losses: {mode_data['rankup_losses']}")
        else:
            lines.append("Rank-up: Not active")

        lines.append("")

    await interaction.response.send_message(
        "\n".join(lines),
        ephemeral=True
    )



@bot.tree.command(name="reportsmurf", description="Report a player for suspected smurfing")
@app_commands.guilds(TEST_GUILD)
@app_commands.describe(member="The player you want to report")
async def reportsmurf(interaction: discord.Interaction, member: discord.Member):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    active_matches = load_json(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    disputed_matches = load_json(DISPUTED_FILE, DEFAULT_DISPUTED)

    reporter_id = str(interaction.user.id)
    reported_id = str(member.id)

    if reporter_id not in players:
        await interaction.response.send_message(
            "You must be signed up before using this command.",
            ephemeral=True
        )
        return

    if reported_id not in players:
        await interaction.response.send_message(
            f"{member.display_name} is not signed up.",
            ephemeral=True
        )
        return

    if reporter_id == reported_id:
        await interaction.response.send_message(
            "You cannot report yourself for smurfing.",
            ephemeral=True
        )
        return

    moved_match_ids = []

    for match_id, match_record in list(active_matches.items()):
        if not player_is_in_match_record(match_record, reporter_id):
            continue

        if not player_is_in_match_record(match_record, reported_id):
            continue

        # Normalize the active match into a disputed match schema
        match_record["status"] = "disputed"
        match_record["dispute"] = {
            "kind": "smurf_report",
            "reason": "smurf reported",
            "created_at": utc_now_iso(),
            "reported_by": reporter_id,
            "resolved": False,
            "resolved_at": None,
            "resolved_by": None,
            "final_outcome": None,
            "notes": None,
            "smurf_report": {
                "reported_player_id": reported_id,
                "reported_player_name": member.display_name,
                "reported_by_id": reporter_id,
                "reported_by_name": interaction.user.display_name,
            }
        }

        disputed_matches[match_id] = match_record
        moved_match_ids.append(match_id)

        mode = match_record["mode"]
        participant_ids = get_match_participant_ids(match_record)

        for participant_id in participant_ids:
            player = players.get(participant_id)
            if not player:
                continue

            mode_data = player.get("modes", {}).get(mode)
            if not mode_data:
                continue

            if mode_data.get("active_match_id") == match_id:
                mode_data["in_match"] = False
                mode_data["active_match_id"] = None

        del active_matches[match_id]

    if not moved_match_ids:
        await interaction.response.send_message(
            f"No shared active match found involving you and {member.display_name}.",
            ephemeral=True
        )
        return

    save_json(PLAYERS_FILE, players)
    save_json(ACTIVE_MATCHES_FILE, active_matches)
    save_json(DISPUTED_FILE, disputed_matches)

    await interaction.response.send_message(
        f"Reported **{member.display_name}** for suspected smurfing.\n"
        f"Moved `{len(moved_match_ids)}` active match(es) to disputed:\n"
        + "\n".join(f"- {match_id}" for match_id in moved_match_ids),
        ephemeral=True
    )