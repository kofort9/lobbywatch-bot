"""Alert system for LobbyLens ETL and operational issues."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alerts for ETL errors and operational issues."""

    def __init__(self, slack_token: Optional[str] = None):
        self.slack_token = slack_token or os.getenv("SLACK_BOT_TOKEN")

        # Support both DM and channel alerts
        self.admin_user_id = os.getenv("LOBBYLENS_ADMIN_USER_ID")  # For DM alerts
        self.alerts_channel = os.getenv(
            "LOBBYLENS_ALERTS_CHANNEL", "#lobbylens-alerts"
        )  # For channel alerts

        # Prefer DM if admin user ID is set, otherwise use channel
        self.alert_target = (
            self.admin_user_id if self.admin_user_id else self.alerts_channel
        )
        self.alert_type = "dm" if self.admin_user_id else "channel"

        self.enabled = os.getenv("ENABLE_ALERTS", "true").lower() == "true"

    def send_etl_error_alert(self, etl_result: Dict[str, Any]) -> bool:
        """Send an alert for ETL errors.

        Args:
            etl_result: ETL result dictionary with counts and errors

        Returns:
            True if alert sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Alerts disabled, skipping ETL error alert")
            return True

        try:
            # Extract key metrics
            added = etl_result.get("added", 0)
            updated = etl_result.get("updated", 0)
            errors = etl_result.get("errors", 0)
            mode = etl_result.get("mode", "unknown")
            timestamp = etl_result.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            )

            # Only send alert if there are errors
            if errors == 0:
                logger.info("No ETL errors, skipping alert")
                return True

            # Get first error message for context
            first_error = "Unknown error"
            if "error_details" in etl_result and etl_result["error_details"]:
                first_error = str(etl_result["error_details"][0])[:200] + "..."
            elif "error" in etl_result:
                first_error = str(etl_result["error"])[:200]

            # Format alert message
            alert_text = self._format_etl_alert(
                mode=mode,
                added=added,
                updated=updated,
                errors=errors,
                first_error=first_error,
                timestamp=timestamp,
            )

            # Send to configured target (DM or channel)
            return self._send_slack_message(self.alert_target, alert_text)

        except Exception as e:
            logger.error(f"Failed to send ETL error alert: {e}")
            return False

    def send_operational_alert(
        self, title: str, message: str, severity: str = "warning"
    ) -> bool:
        """Send a general operational alert.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity (info, warning, error, critical)

        Returns:
            True if alert sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Alerts disabled, skipping operational alert")
            return True

        try:
            # Format alert message
            emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}.get(
                severity, "⚠️"
            )

            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            alert_text = f"{emoji} **{title}**\n\n{message}\n\n_Time: {timestamp}_"

            # Send to configured target (DM or channel)
            return self._send_slack_message(self.alert_target, alert_text)

        except Exception as e:
            logger.error(f"Failed to send operational alert: {e}")
            return False

    def _format_etl_alert(
        self,
        mode: str,
        added: int,
        updated: int,
        errors: int,
        first_error: str,
        timestamp: str,
    ) -> str:
        """Format ETL error alert message.

        Args:
            mode: ETL mode (backfill, update)
            added: Number of filings added
            updated: Number of filings updated
            errors: Number of errors
            first_error: First error message
            timestamp: Timestamp of ETL run

        Returns:
            Formatted alert message
        """
        # Parse timestamp for display
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            time_str = timestamp

        return f"""⚠️ **LDA ETL Error Alert**

**Mode:** {mode.title()}
**Results:** {added} added, {updated} updated, {errors} errors

**First Error:**
```
{first_error}
```

**Time:** {time_str}

Check logs for full error details. Consider investigating data source issues or API rate limits.

_Automated alert from LobbyLens ETL_"""

    def _send_slack_message(self, channel: str, text: str) -> bool:
        """Send a message to Slack channel.

        Args:
            channel: Channel name or ID
            text: Message text

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.slack_token:
            logger.warning("No Slack token available for alerts")
            return False

        try:
            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.slack_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "channel": channel,
                    "text": text,
                    "unfurl_links": False,
                    "unfurl_media": False,
                },
                timeout=10,
            )

            if response.ok:
                data = response.json()
                if data.get("ok"):
                    logger.info(f"Alert sent to {channel}")
                    return True
                else:
                    logger.error(f"Slack API error: {data.get('error')}")
                    return False
            else:
                logger.error(f"HTTP error sending alert: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Exception sending Slack alert: {e}")
            return False

    def test_alerts_system(self) -> bool:
        """Test that alerts can be sent to the configured target (DM or channel).

        Returns:
            True if test message sent successfully, False otherwise
        """
        target_desc = (
            f"DM to user {self.admin_user_id}"
            if self.alert_type == "dm"
            else f"channel {self.alerts_channel}"
        )

        test_message = f"""🧪 **LobbyLens Alert System Test**

This is a test message to verify alerts are configured correctly.

**Alert Type:** {self.alert_type.upper()}
**Target:** {target_desc}
**Time:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

If you see this message, alerts are working! 🎉

_Test message from LobbyLens Alert System_"""

        return self._send_slack_message(self.alert_target, test_message)


# Global instance
_alert_manager = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
