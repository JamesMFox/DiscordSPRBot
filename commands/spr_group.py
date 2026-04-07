from discord import app_commands

spr_group = app_commands.Group(
    name="spr",
    description="SPR ranked system commands"
)

mod_group = app_commands.Group(
    name="mod",
    description="Moderator-only commands",
    parent=spr_group
)

admin_group = app_commands.Group(
    name="admin",
    description="Admin-only commands",
    parent=spr_group
)