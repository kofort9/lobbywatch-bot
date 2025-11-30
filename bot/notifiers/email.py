"""Email notifier implementation using SMTP."""

import smtplib
from email.message import EmailMessage
from typing import List, Optional

from .base import NotificationError


class EmailNotifier:
    """Sends notifications via SMTP email."""

    def __init__(
        self,
        host: str,
        port: int,
        from_address: str,
        to_addresses: List[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        subject_prefix: str = "LobbyLens",
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.use_tls = use_tls
        self.subject_prefix = subject_prefix or "LobbyLens"

    def send(
        self, text: str, subject: Optional[str] = None, html: Optional[str] = None
    ) -> None:
        """Send a plain-text email notification (with optional HTML alternative).

        Args:
            text: Message body to send (plain text).
            subject: Optional subject override (prefix is applied automatically).
            html: Optional HTML body for multipart/alternative delivery.

        Raises:
            NotificationError: If sending fails.
        """
        if not self.to_addresses:
            raise NotificationError(
                "Email notification failed: no recipients configured"
            )

        message = EmailMessage()
        final_subject = subject or "Digest"
        message["Subject"] = f"{self.subject_prefix} | {final_subject}"
        message["From"] = self.from_address
        message["To"] = ", ".join(self.to_addresses)
        message.set_content(text or "")

        if html:
            message.add_alternative(html, subtype="html")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()

                if self.username and self.password:
                    server.login(self.username, self.password)

                server.send_message(message)

        except (
            Exception
        ) as exc:  # pragma: no cover - covered via unit tests mocking SMTP
            raise NotificationError(f"Email notification failed: {exc}") from exc
