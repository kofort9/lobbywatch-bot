"""Slack notifier implementation."""

import logging
from typing import Any, Dict

import requests

from .base import NotificationError

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Sends notifications to Slack via webhook URL."""

    def __init__(self, webhook_url: str):
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack incoming webhook URL
        """
        self.webhook_url = webhook_url

    def send(self, text: str) -> None:
        """Send message to Slack.

        Args:
            text: Message text to send

        Raises:
            NotificationError: If the message fails to send
        """
        payload: Dict[str, Any] = {
            "text": text,
            "username": "LobbyLens",
            "icon_emoji": ":magnifying_glass_tilted_left:",
            "unfurl_links": True,
            "unfurl_media": True,
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            if response.text.strip() != "ok":
                raise NotificationError(f"Slack webhook returned: {response.text}")

            logger.info("Successfully sent Slack notification")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
            raise NotificationError(f"Slack notification failed: {e}") from e
