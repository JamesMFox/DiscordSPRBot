import discord
from data_manager import (
    load_json, save_json,
    PLAYERS_FILE, DEFAULT_PLAYERS,
    TEAMS_FILE, DEFAULT_TEAMS,
    QUEUE_FILE, DEFAULT_QUEUE,
)
from utils.team_utils import (
    generate_team_id,
    create_team_profile,
    player_is_available_for_team,
    all_players_same_class,
    member_has_active_team_in_mode,
    calculate_team_average_spr,
)
from utils.player_utils import create_new_player_profile
from utils.rank_utils import get_class_from_spr
from utils.rankup_utils import player_can_join_team_rankup_as_participant
from utils.queue_utils import generate_queue_entry_id, set_multiple_players_queue_state
from services.matchmaking_service import (
    run_rankup_2v2_matchmaking_pass,
    run_rankup_3v3_matchmaking_pass,
)

class SignupConfirmView(discord.ui.View):
    def __init__(self, user_id: int, rank_role: str, starting_spr: int):
        super().__init__(timeout=60)
        self.user_id = str(user_id)
        self.rank_role = rank_role
        self.starting_spr = starting_spr
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(
                    content="Signup request expired.",
                    view=self
                )
            except Exception:
                pass

    @discord.ui.button(label="Confirm Signup", style=discord.ButtonStyle.green)
    async def confirm_signup(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "This confirmation is not for you.",
                ephemeral=True
            )
            return

        players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)

        if self.user_id in players:
            await interaction.response.send_message(
                "You are already signed up.",
                ephemeral=True
            )
            return

        profile = create_new_player_profile(
            user_id=interaction.user.id,
            username=interaction.user.name,
            display_name=interaction.user.display_name,
            signup_rank_role=self.rank_role,
            starting_spr=self.starting_spr,
        )

        players[self.user_id] = profile
        save_json(PLAYERS_FILE, players)

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=(
                f"Signup complete.\n"
                f"Detected rank role: {self.rank_role}\n"
                f"Starting SPR: {self.starting_spr}\n"
                f"This SPR was applied to 1v1, 2v2, and 3v3."
            ),
            view=self
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_signup(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "This confirmation is not for you.",
                ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Signup cancelled.",
            view=self
        )


# -----------------------
# Team Confirm View
# -----------------------

class TeamConfirmView(discord.ui.View):
    def __init__(self, mode: str, captain: discord.Member, member_objects: list[discord.Member], team_name: str | None):
        super().__init__(timeout=120)

        self.mode = mode
        self.captain = captain
        self.member_objects = member_objects
        self.team_name = team_name
        self.member_ids = [str(member.id) for member in member_objects]
        self.pending_confirm_ids = {
            str(member.id) for member in member_objects if member.id != captain.id
        }
        self.confirmed_ids = set()
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(
                    content="Team creation request expired.",
                    view=self
                )
            except Exception:
                pass

    def _build_status_message(self) -> str:
        lines = [
            f"Team creation pending",
            f"Mode: {self.mode}",
            f"Captain: {self.captain.display_name}",
            f"Members: {', '.join(member.display_name for member in self.member_objects)}",
            f"Team Name: {self.team_name if self.team_name else 'None'}",
            ""
        ]

        if self.pending_confirm_ids:
            pending_names = [
                member.display_name
                for member in self.member_objects
                if str(member.id) in self.pending_confirm_ids
            ]
            lines.append(f"Waiting for: {', '.join(pending_names)}")
        else:
            lines.append("All teammates confirmed.")

        return "\n".join(lines)

    @discord.ui.button(label="Accept Team", style=discord.ButtonStyle.green)
    async def accept_team(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        clicking_user_id = str(interaction.user.id)

        if clicking_user_id == str(self.captain.id):
            await interaction.response.send_message(
                "You are already the captain. Waiting on teammates to confirm.",
                ephemeral=True
            )
            return

        if clicking_user_id not in self.member_ids:
            await interaction.response.send_message(
                "You are not part of this team request.",
                ephemeral=True
            )
            return

        if clicking_user_id not in self.pending_confirm_ids:
            await interaction.response.send_message(
                "You have already confirmed.",
                ephemeral=True
            )
            return

        # Re-load data at confirmation time to prevent stale team creation.
        players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
        teams = load_json(TEAMS_FILE, DEFAULT_TEAMS)

        # Final safety validation before accepting.
        for member in self.member_objects:
            member_id = str(member.id)

            if member_id not in players:
                await interaction.response.send_message(
                    f"{member.display_name} is no longer signed up.",
                    ephemeral=True
                )
                return

            if not player_is_available_for_team(players[member_id], self.mode):
                await interaction.response.send_message(
                    f"{member.display_name} is no longer available for a {self.mode} team.",
                    ephemeral=True
                )
                return

            if member_has_active_team_in_mode(teams, member_id, self.mode):
                await interaction.response.send_message(
                    f"{member.display_name} is already on another active {self.mode} team.",
                    ephemeral=True
                )
                return

        if not all_players_same_class(players, self.member_ids, self.mode):
            await interaction.response.send_message(
                "Team creation failed. All members must still be in the same class.",
                ephemeral=True
            )
            return

        self.pending_confirm_ids.remove(clicking_user_id)
        self.confirmed_ids.add(clicking_user_id)

        if self.pending_confirm_ids:
            await interaction.response.edit_message(
                content=self._build_status_message(),
                view=self
            )
            return

        # Final create step after all teammates confirm.
        team_id = generate_team_id(teams)
        team_profile = create_team_profile(
            team_id=team_id,
            mode=self.mode,
            captain_id=self.captain.id,
            member_ids=[member.id for member in self.member_objects],
            name=self.team_name
        )

        teams[team_id] = team_profile
        save_json(TEAMS_FILE, teams)

        self._disable_buttons()

        await interaction.response.edit_message(
            content=(
                f"Team created.\n"
                f"Team ID: {team_id}\n"
                f"Mode: {self.mode}\n"
                f"Captain: {self.captain.display_name}\n"
                f"Members: {', '.join(member.display_name for member in self.member_objects)}\n"
                f"Team Name: {self.team_name if self.team_name else 'None'}"
            ),
            view=self
        )

    @discord.ui.button(label="Decline Team", style=discord.ButtonStyle.red)
    async def decline_team(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        clicking_user_id = str(interaction.user.id)

        if clicking_user_id not in self.member_ids:
            await interaction.response.send_message(
                "You are not part of this team request.",
                ephemeral=True
            )
            return

        self._disable_buttons()

        await interaction.response.edit_message(
            content=f"Team creation cancelled by {interaction.user.display_name}.",
            view=self
        )


# -----------------------
# Team Rankup Confrim View
# -----------------------

class TeamRankupConfirmView(discord.ui.View):
    def __init__(
        self,
        mode: str,
        captain,
        team_record: dict,
        rankup_target_class: str,
    ):
        super().__init__(timeout=120)
        self.mode = mode
        self.captain = captain
        self.team_record = team_record
        self.rankup_target_class = rankup_target_class

        self.captain_id = str(captain.id)
        self.member_ids = [str(x) for x in team_record.get("member_ids", [])]

        self.accepted_ids = {self.captain_id}
        self.rankup_participants = {self.captain_id}
        self.declined = False
        self.message = None

    def _disable_buttons(self):
        for item in self.children:
            item.disabled = True

    def _all_non_captains_accepted(self) -> bool:
        for member_id in self.member_ids:
            if member_id == self.captain_id:
                continue
            if member_id not in self.accepted_ids:
                return False
        return True

    def _build_status_message(self) -> str:
        accepted_mentions = [f"<@{x}>" for x in sorted(self.accepted_ids)]
        participant_mentions = [f"<@{x}>" for x in sorted(self.rankup_participants)]

        return (
            f"**{self.mode} Rank-Up Confirmation**\n"
            f"Captain: <@{self.captain_id}>\n"
            f"Target class: `{self.rankup_target_class}`\n\n"
            f"Accepted: {', '.join(accepted_mentions) if accepted_mentions else 'None'}\n"
            f"Rank-up participants: {', '.join(participant_mentions) if participant_mentions else 'None'}\n\n"
            f"Teammates: choose whether to join the rank-up or just accept the harder match."
        )

    async def _finalize_and_queue(self, interaction: discord.Interaction):
        players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
        queue_data = load_json(QUEUE_FILE, DEFAULT_QUEUE)

        queue_data.setdefault("rankup", {})
        queue_data["rankup"].setdefault(self.mode, [])

        member_ids = [str(x) for x in self.team_record.get("member_ids", [])]

        captain_profile = players.get(self.captain_id)
        if not captain_profile:
            await interaction.response.send_message(
                "Captain profile could not be found.",
                ephemeral=True,
            )
            return

        queue_class = get_class_from_spr(captain_profile["modes"][self.mode]["spr"])
        if queue_class is None:
            await interaction.response.send_message(
                "Could not determine queue class for this team.",
                ephemeral=True,
            )
            return

        average_spr = calculate_team_average_spr(players, member_ids, self.mode)
        entry_id = generate_queue_entry_id(queue_data)

        queue_entry = {
            "entry_id": entry_id,
            "entry_type": "premade",
            "captain_id": self.captain_id,
            "member_ids": member_ids,
            "team_id": self.team_record["team_id"],
            "average_spr": average_spr,
            "queue_class": queue_class,
            "rankup_owner_id": self.captain_id,
            "rankup_target_class": self.rankup_target_class,
            "rankup_participants": sorted(self.rankup_participants),
        }

        queue_data["rankup"][self.mode].append(queue_entry)
        set_multiple_players_queue_state(players, member_ids, self.mode, True)

        save_json(QUEUE_FILE, queue_data)
        save_json(PLAYERS_FILE, players)

        matchmaking_result = None
        if self.mode == "2v2":
            matchmaking_result = run_rankup_2v2_matchmaking_pass()
        elif self.mode == "3v3":
            matchmaking_result = run_rankup_3v3_matchmaking_pass()

        self._disable_buttons()

        if matchmaking_result and matchmaking_result["created_count"] > 0:
            await interaction.response.edit_message(
                content=(
                    f"{self._build_status_message()}\n\n"
                    f"Queued successfully into **{self.mode} rank-up**.\n\n"
                    f"Matchmaking found:\n" + "\n".join(matchmaking_result["created_summaries"])
                ),
                view=self,
            )
            return

        await interaction.response.edit_message(
            content=(
                f"{self._build_status_message()}\n\n"
                f"Queued successfully into **{self.mode} rank-up**."
            ),
            view=self,
        )

    @discord.ui.button(label="Accept + Join Rank-Up", style=discord.ButtonStyle.success)
    async def accept_and_join_rankup(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        clicking_user_id = str(interaction.user.id)

        if clicking_user_id == self.captain_id:
            await interaction.response.send_message(
                "You are already the captain and rank-up owner for this queue.",
                ephemeral=True,
            )
            return

        if clicking_user_id not in self.member_ids:
            await interaction.response.send_message(
                "You are not on this team.",
                ephemeral=True,
            )
            return

        players = load_json(PLAYERS_FILE, DEFAULT_PLAYERS)
        can_join, reason = player_can_join_team_rankup_as_participant(
            players=players,
            player_id=clicking_user_id,
            mode=self.mode,
            target_class=self.rankup_target_class,
        )

        if not can_join:
            await interaction.response.send_message(reason, ephemeral=True)
            return

        self.accepted_ids.add(clicking_user_id)
        self.rankup_participants.add(clicking_user_id)

        if self._all_non_captains_accepted():
            await self._finalize_and_queue(interaction)
            return

        await interaction.response.edit_message(
            content=self._build_status_message(),
            view=self,
        )

    @discord.ui.button(label="Accept Match Only", style=discord.ButtonStyle.primary)
    async def accept_match_only(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        clicking_user_id = str(interaction.user.id)

        if clicking_user_id == self.captain_id:
            await interaction.response.send_message(
                "You are already the captain and rank-up owner for this queue.",
                ephemeral=True,
            )
            return

        if clicking_user_id not in self.member_ids:
            await interaction.response.send_message(
                "You are not on this team.",
                ephemeral=True,
            )
            return

        self.accepted_ids.add(clicking_user_id)

        if self._all_non_captains_accepted():
            await self._finalize_and_queue(interaction)
            return

        await interaction.response.edit_message(
            content=self._build_status_message(),
            view=self,
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_rankup(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        clicking_user_id = str(interaction.user.id)

        if clicking_user_id not in self.member_ids:
            await interaction.response.send_message(
                "You are not on this team.",
                ephemeral=True,
            )
            return

        self.declined = True
        self._disable_buttons()

        await interaction.response.edit_message(
            content=(
                f"{self._build_status_message()}\n\n"
                f"Rank-up queue cancelled because <@{clicking_user_id}> declined."
            ),
            view=self,
        )

    async def on_timeout(self):
        self._disable_buttons()

        if self.message:
            try:
                await self.message.edit(
                    content="Team rank-up confirmation expired.",
                    view=self,
                )
            except Exception:
                pass