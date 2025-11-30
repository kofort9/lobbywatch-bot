"""Extra coverage for enhanced_run helpers."""

from datetime import datetime, timezone

from bot import enhanced_run


class _FixedDateTime(datetime):
    """datetime subclass with overridable now()."""

    fixed_now: datetime = datetime.now(timezone.utc)

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls.fixed_now


def test_is_time_for_digest_daily_false_outside_window(monkeypatch: object) -> None:
    """Daily digest should only trigger in early-hour window."""
    _FixedDateTime.fixed_now = datetime(2024, 1, 1, 3, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(enhanced_run, "datetime", _FixedDateTime)

    assert enhanced_run.is_time_for_digest("daily") is False


def test_is_time_for_digest_mini_true(monkeypatch: object) -> None:
    """Mini digest window check."""
    _FixedDateTime.fixed_now = datetime(2024, 1, 1, 16, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(enhanced_run, "datetime", _FixedDateTime)

    assert enhanced_run.is_time_for_digest("mini") is True
