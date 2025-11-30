"""Additional coverage for LDAScheduler."""

from bot.lda_scheduler import LDAScheduler


def test_run_backfill_success(monkeypatch: object) -> None:
    """Backfill path should bubble success stats."""
    monkeypatch.setenv("ENABLE_LDA_V1", "true")
    monkeypatch.setattr("bot.lda_scheduler.create_database_manager", lambda: "db")

    class DummyETL:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def run_etl(
            self, mode: str = "backfill", start_year: int = 2020, end_year: int = 2021
        ) -> dict[str, int]:  # noqa: ARG002
            return {
                "added": 2,
                "updated": 0,
                "errors": 0,
                "mode": mode,
                "start_year": start_year,
                "end_year": end_year,
            }

    monkeypatch.setattr("bot.lda_scheduler.LDAETLPipeline", DummyETL)

    scheduler = LDAScheduler()
    result = scheduler.run_backfill(2020, 2021)

    assert result["status"] == "success"
    assert result["start_year"] == 2020
    assert result["end_year"] == 2021
