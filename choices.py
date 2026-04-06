from discord import app_commands

TEAM_MODE_CHOICES = [
    app_commands.Choice(name="2v2", value="2v2"),
    app_commands.Choice(name="3v3", value="3v3"),
]

RANKUP_MODE_CHOICES = [
    app_commands.Choice(name="1v1", value="1v1"),
    app_commands.Choice(name="2v2", value="2v2"),
    app_commands.Choice(name="3v3", value="3v3"),
]

QUEUE_MODE_CHOICES = [
    app_commands.Choice(name="1v1", value="1v1"),
    app_commands.Choice(name="2v2", value="2v2"),
    app_commands.Choice(name="3v3", value="3v3"),
]

REPORT_RESULT_CHOICES = [
    app_commands.Choice(name="win", value="win"),
    app_commands.Choice(name="loss", value="loss"),
]

RESOLVE_OUTCOME_CHOICES = [
    app_commands.Choice(name="team1", value="team1"),
    app_commands.Choice(name="team2", value="team2"),
    app_commands.Choice(name="disregard", value="disregard"),
]