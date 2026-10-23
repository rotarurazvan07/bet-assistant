"""
generate_slips module for handling the generate-slips mode logic
"""

from bet_crawler.crawler_logging import get_logger, log_event, reset_event_totals
from bet_framework.BetAssistant import BetAssistant, BetSlipConfig
from bet_framework.MatchesManager import MatchesManager

logger = get_logger(__name__)


def generate_slips(matches_db_path: str, slips_db_path: str, profile_name: str, profile_data: dict) -> None:
    """
    Generate slips for an already loaded profile.
    """
    if not profile_data:
        log_event(
            logger,
            event="stage.failed",
            outcome="error",
            reason_code="profile_data_missing",
            level=40,
            message=f"No data found in profile: {profile_name}",
            stage="generate-slips",
        )
        raise SystemExit(1)

    reset_event_totals(stage="generate-slips")
    try:
        matches_manager = MatchesManager(matches_db_path)
        try:
            raw_df = matches_manager.fetch_matches()
        finally:
            matches_manager.close()

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
            log_event(
                logger,
                event="slip_generation.completed",
                outcome="empty",
                reason_code="no_suitable_matches",
                message="No suitable matches found for the profile",
                stage="generate-slips",
                source_key=profile_name,
                counts={"legs": 0},
            )
        else:
            slip_id = assistant.save_slip(profile_name, legs, units)
            total_odds = 1.0
            for leg in legs:
                logger.info(f"  ⚽ {leg.match_name} ({leg.market.value}) @ {leg.odds:.2f}")
                total_odds *= leg.odds
            logger.info(f"  ✅ Slip #{slip_id} — {len(legs)} legs @ {total_odds:.2f} ({units}u)")
            log_event(
                logger,
                event="slip_generation.completed",
                outcome="success",
                reason_code="slip_saved",
                message=f"Slip #{slip_id} saved for profile {profile_name}",
                stage="generate-slips",
                source_key=profile_name,
                counts={"legs": len(legs)},
            )
    except Exception as exc:
        logger.exception(
            "Slip generation failed for profile %s",
            profile_name,
            extra={
                "event": "stage.failed",
                "outcome": "error",
                "reason_code": "slip_generation_failed",
                "stage": "generate-slips",
                "source_key": profile_name,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise
    finally:
        if "assistant" in locals():
            try:
                assistant.close()
            except Exception as exc:
                logger.exception(
                    "Failed to close slip-generation database %s",
                    slips_db_path,
                    extra={
                        "event": "stage.failed",
                        "outcome": "error",
                        "reason_code": "slip_database_close_failed",
                        "stage": "generate-slips",
                        "source_key": profile_name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                raise
