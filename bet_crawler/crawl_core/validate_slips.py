"""
validate_slips module for handling the validate-slips mode logic
"""

from scrape_kit import get_logger

from bet_framework.BetAssistant import BetAssistant

logger = get_logger(__name__)


def validate_slips(slips_db_path: str) -> None:
    """
    Delegate entirely to BetAssistant.validate_slips() — no duplicated
    scraping or outcome logic here.
    """
    assistant = BetAssistant(slips_db_path)
    result = assistant.validate_slips()
    assistant.close()

    logger.info(
        f"✅ Checked {result['checked']} · Settled {len(result['settled'])} · Live {len(result['live'])} · Errors {result['errors']}"
    )

    for item in result["live"]:
        logger.info(f"  🟡 {item['match_name']} ({item['market']})  {item['score']}  {item['minute']}")

    for item in result["settled"]:
        icon = "✅" if item["outcome"] == "Won" else "❌"
        logger.info(f"  {icon} {item['match_name']} ({item['market']})  {item['score']}  → {item['outcome']}")
