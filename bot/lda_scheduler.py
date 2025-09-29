"""LDA Scheduler for regular data updates."""

import logging

# import os  # Unused
from datetime import datetime, timezone
from typing import Any, Dict

from .database_postgres import create_database_manager
from .lda_etl import LDAETLPipeline
from .utils import is_lda_enabled

logger = logging.getLogger(__name__)


class LDAScheduler:
    """Scheduler for LDA data updates."""

    def __init__(self) -> None:
        self.db_manager = create_database_manager()
        self.etl = LDAETLPipeline(self.db_manager)

    def run_quarterly_update(self) -> Dict[str, Any]:
        """Run quarterly LDA data update."""
        if not is_lda_enabled():
            logger.info("LDA features disabled, skipping quarterly update")
            return {"status": "disabled"}

        logger.info("Starting quarterly LDA data update")

        try:
            # Run ETL in update mode (current + previous quarter)
            result = self.etl.run_etl(mode="update")

            logger.info(f"Quarterly update completed: {result}")
            return {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **result,
            }

        except Exception as e:
            logger.error(f"Quarterly update failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def run_backfill(self, start_year: int, end_year: int) -> Dict[str, Any]:
        """Run historical data backfill."""
        if not is_lda_enabled():
            logger.info("LDA features disabled, skipping backfill")
            return {"status": "disabled"}

        logger.info(f"Starting LDA backfill from {start_year} to {end_year}")

        try:
            result = self.etl.run_etl(
                mode="backfill", start_year=start_year, end_year=end_year
            )

            logger.info(f"Backfill completed: {result}")
            return {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "start_year": start_year,
                "end_year": end_year,
                **result,
            }

        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


def run_scheduled_update() -> None:
    """Entry point for scheduled updates (called by cron/GitHub Actions)."""
    scheduler = LDAScheduler()
    result = scheduler.run_quarterly_update()

    if result["status"] == "success":
        print("✅ LDA quarterly update completed successfully")
        print(f"   Added: {result.get('added', 0)} filings")
        print(f"   Updated: {result.get('updated', 0)} filings")
        print(f"   Errors: {result.get('errors', 0)}")
    elif result["status"] == "disabled":
        print("ℹ️  LDA features are disabled (ENABLE_LDA_V1=false)")
    else:
        print(f"❌ LDA quarterly update failed: {result.get('error', 'Unknown error')}")
        exit(1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        # Manual backfill mode
        if len(sys.argv) < 4:
            print("Usage: python -m bot.lda_scheduler backfill <start_year> <end_year>")
            exit(1)

        start_year = int(sys.argv[2])
        end_year = int(sys.argv[3])

        scheduler = LDAScheduler()
        result = scheduler.run_backfill(start_year, end_year)

        if result["status"] == "success":
            print("✅ LDA backfill completed successfully")
            print(f"   Years: {start_year}-{end_year}")
            print(f"   Added: {result.get('added', 0)} filings")
            print(f"   Updated: {result.get('updated', 0)} filings")
            print(f"   Errors: {result.get('errors', 0)}")
        else:
            print(f"❌ LDA backfill failed: {result.get('error', 'Unknown error')}")
            exit(1)
    else:
        # Regular quarterly update
        run_scheduled_update()
