"""Tests for the LDA scheduler orchestration."""

from datetime import datetime

from bot.lda_scheduler import LDAScheduler


def test_run_quarterly_update_succeeds_and_returns_timestamp(
    monkeypatch: object,
) -> None:
    """Successful run should include timestamp and ETL stats."""
    monkeypatch.setenv("ENABLE_LDA_V1", "true")
    monkeypatch.setattr("bot.lda_scheduler.create_database_manager", lambda: "db")

    class DummyETL:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def run_etl(self, mode: str = "update", **_: object) -> dict[str, int]:
            assert mode == "update"
            return {"added": 1, "updated": 0, "errors": 0}

    monkeypatch.setattr("bot.lda_scheduler.LDAETLPipeline", DummyETL)

    scheduler = LDAScheduler()
    result = scheduler.run_quarterly_update()

    assert result["status"] == "success"
    # Validate timestamp string
    datetime.fromisoformat(result["timestamp"])
    assert result["added"] == 1


def test_run_quarterly_update_handles_failures(monkeypatch: object) -> None:
    """Errors from ETL should bubble into the status payload."""
    monkeypatch.setenv("ENABLE_LDA_V1", "true")
    monkeypatch.setattr("bot.lda_scheduler.create_database_manager", lambda: "db")

    class FailingETL:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def run_etl(self, mode: str = "update", **_: object) -> object:  # noqa: ARG002
            raise RuntimeError("boom")

    monkeypatch.setattr("bot.lda_scheduler.LDAETLPipeline", FailingETL)

    scheduler = LDAScheduler()
    result = scheduler.run_quarterly_update()

    assert result["status"] == "error"
    assert "boom" in result["error"]
    datetime.fromisoformat(result["timestamp"])


def test_run_backfill_respects_feature_flag(monkeypatch: object) -> None:
    """Backfill should short-circuit when LDA flag disabled."""
    monkeypatch.setenv("ENABLE_LDA_V1", "false")
    scheduler = LDAScheduler()

    result = scheduler.run_backfill(2020, 2021)

    assert result == {"status": "disabled"}
