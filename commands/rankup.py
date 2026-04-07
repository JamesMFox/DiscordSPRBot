import discord
from discord import app_commands

from bot_instance import bot
from config import TEST_GUILD
from choices import RANKUP_MODE_CHOICES
from data_manager import load_json, save_json, PLAYERS_FILE, DEFAULT_PLAYERS
from utils.rankup_utils import (
    is_rankup_eligible,
    get_rankup_target_class,
    start_rankup_for_mode,
)
from commands.spr_group import spr_group


@spr_group.command(name="rankup", description="Start a rank-up attempt for 1v1, 2v2, or 3v3")
@app_commands.choices(mode=RANKUP_MODE_CHOICES)
async def rankup(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message(
            "You are not signed up.",
            ephemeral=True
        )
        return

    player = players[user_id]
    selected_mode = mode.value

    if selected_mode not in player.get("modes", {}):
        await interaction.response.send_message(
            f"Mode `{selected_mode}` was not found on your profile.",
            ephemeral=True,
        )
        return

    mode_data = player["modes"][selected_mode]
    spr = mode_data.get("spr")

    if spr is None:
        await interaction.response.send_message(
            f"Your {selected_mode} SPR is missing.",
            ephemeral=True,
        )
        return

    if mode_data.get("rankup_active", False):
        await interaction.response.send_message(
            (
                f"You already have an active {selected_mode} rank-up attempt.\n"
                f"Target Class: {mode_data.get('rankup_target_class', 'Unknown')}\n"
                f"Record: {mode_data.get('rankup_wins', 0)}-{mode_data.get('rankup_losses', 0)}"
            ),
            ephemeral=True,
        )
        return

    if mode_data.get("in_match", False):
        await interaction.response.send_message(
            f"You cannot start a {selected_mode} rank-up while in a match.",
            ephemeral=True,
        )
        return

    if mode_data.get("in_queue", False):
        await interaction.response.send_message(
            f"You cannot start a {selected_mode} rank-up while queued.",
            ephemeral=True,
        )
        return

    if not is_rankup_eligible(mode_data, spr):
        await interaction.response.send_message(
            (
                f"You are not eligible to start a {selected_mode} rank-up.\n"
                "You must be in an Elite tier and not already have an active rank-up."
            ),
            ephemeral=True,
        )
        return

    target_class = get_rankup_target_class(spr)

    if target_class is None:
        await interaction.response.send_message(
            "You do not have a valid next class for rank-up.",
            ephemeral=True
        )
        return

    start_rankup_for_mode(mode_data, target_class)
    save_json(PLAYERS_FILE, players)

    await interaction.response.send_message(
        (
            f"{selected_mode} rank-up started.\n"
            f"Target Class: {target_class}\n"
            "Series: Best of 5\n"
            f"Next: Use `/queuerankup mode:{selected_mode}` to look for a rank-up match."
        ),
        ephemeral=True,
    )


@spr_group.command(name="rankupstatus", description="Check your active rank-up for 1v1, 2v2, or 3v3")
@app_commands.choices(mode=RANKUP_MODE_CHOICES)
async def rankupstatus(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
):
    players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
    user_id = str(interaction.user.id)

    if user_id not in players:
        await interaction.response.send_message(
            "You are not signed up.",
            ephemeral=True
        )
        return

    player = players[user_id]
    selected_mode = mode.value

    if selected_mode not in player.get("modes", {}):
        await interaction.response.send_message(
            f"Mode `{selected_mode}` was not found on your profile.",
            ephemeral=True,
        )
        return

    mode_data = player["modes"][selected_mode]

    if not mode_data.get("rankup_active", False):
        await interaction.response.send_message(
            f"You do not have an active rank-up in {selected_mode}.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        (
            f"Rank-up Status — {selected_mode}\n"
            f"SPR: {mode_data.get('spr', 'Unknown')}\n"
            f"Target Class: {mode_data.get('rankup_target_class', 'Unknown')}\n"
            f"Started At: {mode_data.get('rankup_started_at', 'Unknown')}\n"
            f"Series Record: Wins: {mode_data.get('rankup_wins', 0)}- Losses:{mode_data.get('rankup_losses', 0)}\n"
            f"History Count: {len(mode_data.get('rankup_history', []))}"
        ),
        ephemeral=True
    )
