"""
validate_slips module for handling the validate-slips mode logic
"""

from bet_crawler.crawler_logging import get_logger, log_event, reset_event_totals
from bet_framework.BetAssistant import BetAssistant

logger = get_logger(__name__)


def validate_slips(slips_db_path: str) -> None:
    """
    Delegate entirely to BetAssistant.validate_slips() — no duplicated
    scraping or outcome logic here.
    """
    reset_event_totals(stage="validate-slips")
    assistant = BetAssistant(slips_db_path)
    close_error = None
    result = None
    try:
        result = assistant.validate_slips()
    except Exception as exc:
        logger.exception(
            "Slip validation failed for %s",
            slips_db_path,
            extra={
                "event": "stage.failed",
                "outcome": "error",
                "reason_code": "slip_validation_failed",
                "stage": "validate-slips",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise
    finally:
        try:
            assistant.close()
        except Exception as exc:
            close_error = exc
            logger.exception(
                "Failed to close slip-validation database %s",
                slips_db_path,
                extra={
                    "event": "stage.failed",
                    "outcome": "error",
                    "reason_code": "validation_database_close_failed",
                    "stage": "validate-slips",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
    if result is None:
        return
    if close_error:
        raise close_error

    if result.errors:
        log_event(
            logger,
            event="validation.completed",
            outcome="partial",
            reason_code="validation_errors",
            level=40,
            message=f"Slip validation completed with {result.errors} errors",
            stage="validate-slips",
            counts={
                "checked": result.checked,
                "settled": len(result.settled),
                "live": len(result.live),
                "errors": result.errors,
            },
        )
        raise SystemExit(1)
    else:
        logger.info(
            f"✅ Checked {result.checked} · Settled {len(result.settled)} · Live {len(result.live)} · Errors {result.errors}"
        )
        log_event(
            logger,
            event="validation.completed",
            outcome="success",
            reason_code="validation_succeeded",
            message="Slip validation completed",
            stage="validate-slips",
            counts={
                "checked": result.checked,
                "settled": len(result.settled),
                "live": len(result.live),
                "errors": 0,
            },
        )

    for item in result.live:
        logger.info(f"  🟡 {item.match_name} ({item.market})  {item.score}  {item.minute}")

    for item in result.settled:
        icon = "✅" if item.outcome == "Won" else "❌"
        logger.info(f"  {icon} {item.match_name} ({item.market})  {item.score}  → {item.outcome}")
