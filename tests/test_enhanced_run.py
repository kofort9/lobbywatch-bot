"""Smoke tests for bot.enhanced_run helpers."""

from bot import enhanced_run


def test_get_configured_channels_reads_env(monkeypatch: object) -> None:
    """Ensure env parsing trims blanks."""
    monkeypatch.setenv("LOBBYLENS_CHANNELS", "ch-1, ch-2,, ch-3 ")

    channels = enhanced_run.get_configured_channels()

    assert channels == ["ch-1", "ch-2", "ch-3"]


def test_run_scheduled_digests_skips_mini_when_threshold_not_met(
    monkeypatch: object,
) -> None:
    """Mini digest should skip sending when threshold guard fails."""
    monkeypatch.setenv("LOBBYLENS_CHANNELS", "C123")

    class DummyDigestComputer:
        def __init__(self, db_manager: object) -> None:
            self.db_manager = db_manager

        def should_send_mini_digest(self, channel_id: str) -> bool:  # noqa: ARG002
            return False

    class DummySlackApp:
        def __init__(self) -> None:
            self.sent: list[tuple[str, str]] = []

        def send_digest(self, channel_id: str, digest_type: str = "daily") -> bool:
            self.sent.append((channel_id, digest_type))
            return True

    monkeypatch.setattr(enhanced_run, "EnhancedDigestComputer", DummyDigestComputer)
    slack = DummySlackApp()

    result = enhanced_run.run_scheduled_digests(
        db_manager=object(), slack_app=slack, digest_type="mini"
    )

    assert result == {"C123": True}
    assert slack.sent == []


def test_run_scheduled_digests_sends_each_channel(monkeypatch: object) -> None:
    """Daily digest path should invoke Slack send for every configured channel."""
    monkeypatch.setenv("LOBBYLENS_CHANNELS", "A,B")

    send_log: list[tuple[str, str]] = []

    class DummySlackApp:
        def send_digest(self, channel_id: str, digest_type: str = "daily") -> bool:
            send_log.append((channel_id, digest_type))
            return channel_id == "A"

    result = enhanced_run.run_scheduled_digests(
        db_manager=object(), slack_app=DummySlackApp(), digest_type="daily"
    )

    assert result == {"A": True, "B": False}
    assert ("A", "daily") in send_log and ("B", "daily") in send_log
