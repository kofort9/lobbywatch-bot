"""Tests for EmailNotifier."""

from typing import Any

import pytest

from bot.notifiers.base import NotificationError
from bot.notifiers.email import EmailNotifier


class TestEmailNotifier:
    """Email notifier tests."""

    def test_send_success(self, mocker: Any) -> None:
        """Ensure email sends with TLS and no auth when not provided."""
        smtp_mock = mocker.patch("smtplib.SMTP")
        conn_mock = smtp_mock.return_value.__enter__.return_value

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
            use_tls=True,
        )

        notifier.send("Hello", subject="Digest")

        conn_mock.starttls.assert_called_once()
        conn_mock.send_message.assert_called_once()

    def test_send_with_auth(self, mocker: Any) -> None:
        """Ensure SMTP auth is used when credentials provided."""
        smtp_mock = mocker.patch("smtplib.SMTP")
        conn_mock = smtp_mock.return_value.__enter__.return_value

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
            username="user",
            password="pass",
            use_tls=True,
        )

        notifier.send("Hello")

        conn_mock.login.assert_called_once_with("user", "pass")
        conn_mock.send_message.assert_called_once()

    def test_send_with_html(self, mocker: Any) -> None:
        """Ensure multipart/alternative is created when HTML is provided."""
        smtp_mock = mocker.patch("smtplib.SMTP")
        conn_mock = smtp_mock.return_value.__enter__.return_value

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
        )

        notifier.send(text="Plain", html="<p>HTML</p>")

        conn_mock.send_message.assert_called_once()
        sent_msg = conn_mock.send_message.call_args.args[0]
        assert sent_msg.is_multipart()
        parts = sent_msg.get_payload()
        assert len(parts) == 2
        assert parts[0].get_content_type() == "text/plain"
        assert parts[1].get_content_type() == "text/html"

    def test_send_no_recipients(self) -> None:
        """Raise when no recipients configured."""
        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_address="from@example.com",
            to_addresses=[],
        )

        with pytest.raises(NotificationError, match="no recipients configured"):
            notifier.send("Hello")
