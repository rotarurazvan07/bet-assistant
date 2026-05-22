"""
generate_slips module for handling the generate-slips mode logic
"""

from scrape_kit import get_logger

from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.MatchesManager import MatchesManager

logger = get_logger(__name__)


def generate_slips(matches_db_path: str, slips_db_path: str, profile_name: str, profile_data: dict) -> None:
    """
    Generate slips for an already loaded profile.
    """
    if not profile_data:
        logger.error(f"❌ No data found in profile: {profile_name}")
        raise SystemExit(1)

    raw_df = MatchesManager(matches_db_path).fetch_matches()

    assistant = BetAssistant(slips_db_path)
    assistant.load_matches(raw_df)

    units = float(profile_data.get("units", 1.0))

    cfg = BetSlipConfig(
        target_odds=profile_data.get("target_odds"),
        target_legs=profile_data.get("target_legs"),
        max_legs_overflow=profile_data.get("max_legs_overflow"),
        consensus_floor=profile_data.get("consensus_floor"),
        min_odds=profile_data.get("min_odds"),
        tolerance_factor=profile_data.get("tolerance_factor"),
        stop_threshold=profile_data.get("stop_threshold"),
        min_legs_fill_ratio=profile_data.get("min_legs_fill_ratio"),
        quality_vs_balance=profile_data.get("quality_vs_balance"),
        consensus_vs_sources=profile_data.get("consensus_vs_sources"),
        included_markets=profile_data.get("included_markets"),
        date_from=profile_data.get("date_from"),
        date_to=profile_data.get("date_to"),
        excluded_urls=profile_data.get("excluded_urls"),
        odds_movement_weight=profile_data.get("odds_movement_weight"),
        odds_movement_strength_min=profile_data.get("odds_movement_strength_min"),
    )

    logger.info(f"\n▶ Profile: {profile_name.upper()}")

    legs = assistant.build_slip_auto_exclude(cfg)
    if not legs:
        logger.info("  ℹ️  No suitable matches found.")
    else:
        slip_id = assistant.save_slip(profile_name, legs, units)
        total_odds = 1.0
        for leg in legs:
            logger.info(f"  ⚽ {leg.match_name} ({leg.market.value}) @ {leg.odds:.2f}")
            total_odds *= leg.odds
        logger.info(f"  ✅ Slip #{slip_id} — {len(legs)} legs @ {total_odds:.2f} ({units}u)")

    assistant.close()
