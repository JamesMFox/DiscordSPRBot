import discord
from discord import app_commands

from bot_instance import bot
from config import TEST_GUILD
from utils.permissions_utils import is_mod_or_admin
from commands.spr_group import spr_group


HELP_PAGES = {
    "home": {
        "title": "SPR Help Center",
        "description": (
            "Use the dropdown below to browse command categories.\n"
            "**Quick Start**\n"
            "1. `/spr signup` to create your ladder profile\n"
            "2. `/spr profile` to view your SPR and status\n"
            "3. `/spr queuesolo` for 1v1 or `/spr queueteam` for 2v2/3v3\n"
            "4. `/spr mymatch` to view your active match\n"
            "5. `/spr report1v1`, `/spr report2v2`, or `/spr report3v3` when your set ends\n"
            "6. `/spr rankup` when you reach your class elite tier and want to promote"
        ),
        "fields": [
            (
                "Most Used",
                "`/spr signup` • `/spr profile` • `/spr queuesolo` • `/spr queueteam` • `/spr leavequeue` • `/spr mymatch`",
                False,
            ),
            (
                "Team Rank-Up Rules",
                (
                    "For **2v2** and **3v3** rank-up queue:\n"
                    "• only the **captain** must have an active rank-up attempt\n"
                    "• teammates must explicitly confirm the queue\n"
                    "• teammates with their own active rank-up attempt may join that progress\n"
                    "• teammates without one may still accept the higher-class challenge"
                ),
                False,
            ),
        ],
    },
    "player": {
        "title": "Player Commands",
        "description": "Commands for joining the ladder, viewing your profile, and reporting suspicious players.",
        "fields": [
            (
                "`/spr signup`",
                "Create your player profile and select your current starting rank.",
                False,
            ),
            (
                "`/spr profile`",
                "View your SPR, class, tier, record, queue state, and match state.",
                False,
            ),
            (
                "`/spr reportsmurf @player`",
                "Report a player for suspected smurfing. Any active match involving that player can be moved into dispute review.",
                False,
            ),
        ],
    },
    "queue": {
        "title": "Queue Commands",
        "description": "Commands for joining or leaving matchmaking queues.",
        "fields": [
            (
                "`/spr queuesolo`",
                "Queue yourself for **1v1 ranked matchmaking**.",
                False,
            ),
            (
                "`/spr queueteam`",
                "Queue your premade team for **2v2** or **3v3 ranked matchmaking**.",
                False,
            ),
            (
                "`/spr queuerankup`",
                (
                    "Queue for an active rank-up attempt.\n"
                    "• **1v1:** queues your personal rank-up series\n"
                    "• **2v2 / 3v3:** captain starts the queue, teammates must confirm"
                ),
                False,
            ),
            (
                "`/spr leavequeue`",
                "Leave your current queue if you are queued and not already placed into a match.",
                False,
            ),
        ],
    },
    "matches": {
        "title": "Match Commands",
        "description": "Commands for viewing active matches and reporting results.",
        "fields": [
            (
                "`/spr mymatch`",
                "View your current active match, including teams, mode, and match ID.",
                False,
            ),
            (
                "`/spr report1v1`",
                "Report the result of your active **1v1** match.",
                False,
            ),
            (
                "`/spr report2v2`",
                "Report the result of your active **2v2** match.",
                False,
            ),
            (
                "`/spr report3v3`",
                "Report the result of your active **3v3** match.",
                False,
            ),
            (
                "Reporting Tip",
                "Always use the report command that matches the mode of the active match.",
                False,
            ),
        ],
    },
    "teams": {
        "title": "Team Commands",
        "description": "Commands for creating and managing premade teams.",
        "fields": [
            (
                "`/spr createteam`",
                "Create a premade team for **2v2** or **3v3** play.",
                False,
            ),
            (
                "`/spr teaminfo`",
                "View your current team, captain, mode, and roster.",
                False,
            ),
            (
                "`/spr disbandteam`",
                "Disband your current premade team.",
                False,
            ),
        ],
    },
    "rankup": {
        "title": "Rank-Up Commands",
        "description": "Commands for starting and tracking rank-up series.",
        "fields": [
            (
                "`/spr rankup`",
                "Start a rank-up attempt for **1v1**, **2v2**, or **3v3** when eligible.",
                False,
            ),
            (
                "`/spr rankupstatus`",
                "Check your current rank-up progress, including wins, losses, and target class.",
                False,
            ),
            (
                "`/spr queuerankup`",
                (
                    "Queue an active rank-up attempt.\n"
                    "For **2v2** and **3v3**, only the captain must have the active attempt. "
                    "Teammates must confirm. Teammates with their own active attempt may also join that progress."
                ),
                False,
            ),
        ],
    },
    "mod": {
        "title": "Moderator Commands",
        "description": "Staff-only tools for disputes, repairs, and manual matchmaking control.",
        "fields": [
            (
                "Player Tools",
                "`/spr playerinfo` • `/spr repairplayer` • `/spr repairstate`",
                False,
            ),
            (
                "Dispute Tools",
                "`/spr viewdisputes` • `/spr resolve`",
                False,
            ),
            (
                "Match Tools",
                "`/spr active1v1matches` • `/spr cancelmatch` • `/spr finalize1v1`",
                False,
            ),
            (
                "Matchmaking Tools",
                "`/spr runmatchmaking1v1` • `/spr runmatchmaking2v2` • `/spr runmatchmaking3v3`",
                False,
            ),
            (
                "Testing Tools",
                "`/spr matchtest2v2` • `/spr matchtest3v3`",
                False,
            ),
            (
                "Moderator Help",
                "`/spr modhelp`",
                False,
            ),
        ],
    },
}


def build_help_embed(page_key: str, user: discord.abc.User) -> discord.Embed:
    page = HELP_PAGES[page_key]
    color = discord.Color.blurple() if page_key != "mod" else discord.Color.orange()

    embed = discord.Embed(
        title=page["title"],
        description=page["description"],
        color=color,
    )

    for name, value, inline in page["fields"]:
        embed.add_field(name=name, value=value, inline=inline)

    embed.set_footer(text=f"Requested by {user.display_name}")
    return embed


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, is_mod: bool):
        options = [
            discord.SelectOption(
                label="Home",
                value="home",
                description="Overview and quick start",
                emoji="🏠",
            ),
            discord.SelectOption(
                label="Player",
                value="player",
                description="Signup and profile commands",
                emoji="👤",
            ),
            discord.SelectOption(
                label="Queue",
                value="queue",
                description="Queue and matchmaking commands",
                emoji="🎯",
            ),
            discord.SelectOption(
                label="Matches",
                value="matches",
                description="Active match and reporting commands",
                emoji="⚔️",
            ),
            discord.SelectOption(
                label="Teams",
                value="teams",
                description="Premade team commands",
                emoji="👥",
            ),
            discord.SelectOption(
                label="Rank-Up",
                value="rankup",
                description="Promotion series commands",
                emoji="📈",
            ),
        ]

        if is_mod:
            options.append(
                discord.SelectOption(
                    label="Moderator",
                    value="mod",
                    description="Staff-only commands",
                    emoji="🛠️",
                )
            )

        super().__init__(
            placeholder="Choose a help category...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_page = self.values[0]
        embed = build_help_embed(selected_page, interaction.user)
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, is_mod: bool):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect(is_mod=is_mod))


@spr_group.command(name="help", description="Open the SPR help menu")
async def help_command(interaction: discord.Interaction):
    mod_status = is_mod_or_admin(interaction.user)
    embed = build_help_embed("home", interaction.user)
    view = HelpView(is_mod=mod_status)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)