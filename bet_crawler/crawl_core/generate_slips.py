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

    # Pass only the keys actually present in the profile: omitted keys fall back
    # to BetSlipConfig dataclass defaults (explicit None would crash the
    # __post_init__ clamps on partial/hand-edited profiles).
    _cfg_keys = (
        "target_odds",
        "target_legs",
        "max_legs_overflow",
        "consensus_floor",
        "min_odds",
        "tolerance_factor",
        "stop_threshold",
        "min_legs_fill_ratio",
        "quality_vs_balance",
        "consensus_vs_sources",
        "included_markets",
        "date_from",
        "date_to",
        "excluded_urls",
        "odds_movement_weight",
        "odds_movement_strength_min",
    )
    cfg_kwargs = {k: profile_data[k] for k in _cfg_keys if k in profile_data}
    cfg = BetSlipConfig(**cfg_kwargs)

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
