# ------------------------
# Imports
# ------------------------

import discord
import os
from discord.ext import commands
from discord import app_commands

from utils.rank_utils import (
    get_class_info_from_spr,
    get_rank_data_from_discord_roles,
    get_next_class,
    is_elite_tier,
    same_class,
    get_lowest_tier_of_class,
    get_class_from_spr,
    get_tier_from_spr,
)
from utils.player_utils import (
    create_new_player_profile,
    get_display_name,
    get_display_names,
    format_player_names,
    utc_now_iso
)
from utils.team_utils import (
    generate_team_id,
    create_team_profile,
    get_required_team_size,
    player_is_available_for_team,
    all_players_same_class,
    find_team_by_captain_and_mode,
    member_has_active_team_in_mode,
    find_team_by_member_and_mode
)
from utils.queue_utils import (
    generate_queue_entry_id,
    create_solo_queue_entry,
    create_premade_queue_entry,
    get_player_spr_for_mode,
    get_player_queue_class_for_mode,
    calculate_average_spr,
    find_solo_queue_entry,
    find_premade_queue_entry_by_captain,
    find_any_queue_entry_for_member,
    find_any_queue_entry_for_member_any_mode,
    remove_queue_entry_by_id,
    player_can_queue,
    set_player_queue_state,
    get_queue_block_reason,
    get_team_queue_block_reason,
    set_multiple_players_queue_state,
    find_solo_queue_entry_any_mode,
    find_premade_queue_entry_by_captain_any_mode,
    find_any_queue_entry_for_member_any_mode_with_mode
)
from utils.rankup_utils import (
    is_rankup_eligible,
    get_rankup_target_class,
    start_rankup_for_mode,
    clear_rankup_for_mode,
    record_rankup_history_entry,
    should_fail_rankup_for_spr,
    get_class_from_spr,
    get_tier_from_spr,
    is_valid_rankup_opponent,
    find_best_rankup_opponent_from_queue
)
from utils.matchmaking_utils import (
    generate_match_id,
    create_match_team_object,
    create_active_match_record,
    group_queue_entries_by_class,
    find_best_1v1_match,
    set_players_in_match,
    clear_players_from_queue,
    remove_queue_entries_by_ids,
    build_match_summary_line,
    create_matchmaking_result,
    MatchMakingResult
)
from utils.reporting_utils import (
    find_player_team_key,
    get_opposite_team_key,
    build_team_report,
    reports_are_complete_for_1v1,
    reports_agree_for_1v1,
)
from utils.finalization_utils import (
    utc_now_iso,
    get_winner_and_loser_team_keys_from_reports,
    apply_win_to_player_mode,
    apply_loss_to_player_mode,
    clear_players_from_match,
    create_completed_match_record,
    increment_incorrect_reports_for_resolved_match,
    clear_players_from_disputed_match,
    finalize_agreed_1v1_match,
    fail_rankup_if_needed,
    apply_rankup_progress_if_needed
)
