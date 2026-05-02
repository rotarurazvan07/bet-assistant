"""
generate_slips module for handling the generate-slips mode logic
"""
import os

from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from scrape_kit import SettingsManager, get_logger
from bet_framework.MatchesManager import MatchesManager


logger = get_logger(__name__)


def generate_slips(matches_db_path: str, slips_db_path: str, profile_path: str) -> None:
    """
    Load matches and generate slips for the profile defined in the given YAML file.
    """
    sm = SettingsManager(profile_path)
    # The profile name is the stem of the file
    name = os.path.basename(profile_path).split(".")[0]
    data = sm.get(name)

    if not data:
        logger.error(f"❌ No data found in profile file: {profile_path}")
        raise SystemExit(1)

    raw_df = MatchesManager(matches_db_path).fetch_matches()

    assistant = BetAssistant(slips_db_path)
    assistant.load_matches(raw_df)

    units = float(data.get("units", 1.0))

    cfg = BetSlipConfig(
        target_odds=data.get("target_odds"),
        target_legs=data.get("target_legs"),
        max_legs_overflow=data.get("max_legs_overflow"),
        consensus_floor=data.get("consensus_floor"),
        min_odds=data.get("min_odds"),
        tolerance_factor=data.get("tolerance_factor"),
        stop_threshold=data.get("stop_threshold"),
        min_legs_fill_ratio=data.get("min_legs_fill_ratio"),
        quality_vs_balance=data.get("quality_vs_balance"),
        consensus_vs_sources=data.get("consensus_vs_sources"),
        included_markets=data.get("included_markets"),
        date_from=data.get("date_from"),
        date_to=data.get("date_to"),
        excluded_urls=data.get("excluded_urls"),
    )

    logger.info(f"\n▶ Profile: {name.upper()}")

    legs = assistant.build_slip_auto_exclude(cfg)
    if not legs:
        logger.info("  ℹ️  No suitable matches found.")
    else:
        slip_id = assistant.save_slip(name, legs, units)
        total_odds = 1.0
        for leg in legs:
            logger.info(f"  ⚽ {leg.match_name} ({leg.market.value}) @ {leg.odds:.2f}")
            total_odds *= leg.odds
        logger.info(f"  ✅ Slip #{slip_id} — {len(legs)} legs @ {total_odds:.2f} ({units}u)")

    assistant.close()