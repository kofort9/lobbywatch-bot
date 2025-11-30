"""Tests for notifier selection and JSON logging setup in bot.run."""

import json
import logging
from unittest.mock import Mock, patch

import pytest

from bot.config import Settings
from bot.run import create_notifier, setup_logging


def test_create_notifier_email() -> None:
    settings = Settings(
        smtp_host="localhost",
        smtp_port=1025,
        email_from_address="from@example.com",
        email_to="to@example.com",
        notifier_preference="email",
    )
    with patch("bot.run.settings", settings):
        notifier = create_notifier()
        assert hasattr(notifier, "send")


def test_create_notifier_slack() -> None:
    settings = Settings(slack_webhook_url="https://hooks.slack.com/test")
    with patch("bot.run.settings", settings):
        notifier = create_notifier()
        assert hasattr(notifier, "send")


def test_setup_logging_json(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(log_json=True)
    with patch("bot.run.settings", settings):
        setup_logging("INFO")
        logger = logging.getLogger("test_logger")
        logger.info("hello")
    out = capsys.readouterr().out
    if out.strip():
        assert json.loads(out)["message"] == "hello"
