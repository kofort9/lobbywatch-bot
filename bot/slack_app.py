"""Slack app integration for interactive LobbyLens features."""

import hashlib
import hmac

# import json  # Unused for now
import logging
import os
import time

# import urllib.parse  # Unused for now
from typing import Any, Dict, List, Optional

import requests

from .config import settings
from .database import DatabaseManager
from .enhanced_digest import EnhancedDigestComputer
from .matching import MatchingService

logger = logging.getLogger(__name__)


class SlackApp:
    """Handles Slack app interactions including slash commands and events."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.matching_service = MatchingService(db_manager)
        self.digest_computer = EnhancedDigestComputer(db_manager)

        # Slack app credentials (need to be set in environment)
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET")

        # Track pending confirmations
        self.pending_confirmations: Dict[str, Any] = {}

    def verify_slack_request(self, headers: Dict[str, str], body: str) -> bool:
        """Verify that request came from Slack with proper signature validation."""
        if not self.signing_secret:
            # In production, this should be an error
            if settings.is_production():
                logger.error("SLACK_SIGNING_SECRET not set in production!")
                return False
            else:
                logger.warning(
                    "SLACK_SIGNING_SECRET not set, skipping verification (dev mode)"
                )
                return True

        timestamp = headers.get("X-Slack-Request-Timestamp", "")
        signature = headers.get("X-Slack-Signature", "")

        if not timestamp or not signature:
            logger.warning("Missing Slack signature headers")
            return False

        try:
            # Check timestamp is recent (within 5 minutes)
            request_timestamp = int(timestamp)
            if abs(time.time() - request_timestamp) > 300:
                logger.warning("Slack request timestamp too old")
                return False
        except ValueError:
            logger.warning("Invalid Slack request timestamp")
            return False

        # Create signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_signature = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Invalid Slack request signature")

        return is_valid

    def post_message(
        self, channel: str, text: str, thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Post message to Slack channel."""
        if not self.bot_token:
            logger.error("SLACK_BOT_TOKEN not set")
            return {"ok": False, "error": "no_token"}

        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "channel": channel,
            "text": text,
            "unfurl_links": True,
            "unfurl_media": True,
        }

        if thread_ts:
            payload["thread_ts"] = thread_ts

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            result = response.json()
            return (
                result
                if isinstance(result, dict)
                else {"ok": False, "error": "invalid_response"}
            )
        except Exception as e:
            logger.error(f"Failed to post Slack message: {e}")
            return {"ok": False, "error": str(e)}

    def handle_slash_command(self, command_data: Dict[str, Any]) -> Dict[str, str]:
        """Handle slash command from Slack."""
        command = command_data.get("command", "")
        text = command_data.get("text", "").strip()
        channel_id = command_data.get("channel_id", "")
        user_id = command_data.get("user_id", "")

        logger.info(
            f"Slash command: {command} {text} in channel {channel_id} by user {user_id}"
        )

        if command == "/watchlist":
            return self._handle_watchlist_command(text, channel_id, user_id)
        elif command == "/threshold":
            return self._handle_threshold_command(text, channel_id, user_id)
        elif command == "/summary":
            return self._handle_summary_command(text, channel_id, user_id)
        elif command == "/lobbylens":
            return self._handle_lobbylens_command(text, channel_id, user_id)
        elif command == "/lobbypulse":
            return self._handle_lobbypulse_command(text, channel_id, user_id)
        else:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: {command}",
            }

    def _handle_watchlist_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /watchlist command."""
        if not text:
            return {
                "response_type": "ephemeral",
                "text": (
                    "Usage: `/watchlist add [name]`, `/watchlist remove [name]`, "
                    "or `/watchlist list`"
                ),
            }

        parts = text.split(" ", 1)
        action = parts[0].lower()

        if action == "list":
            return self._handle_watchlist_list(channel_id)
        elif action == "add" and len(parts) > 1:
            return self._handle_watchlist_add(parts[1], channel_id, user_id)
        elif action == "remove" and len(parts) > 1:
            return self._handle_watchlist_remove(parts[1], channel_id)
        else:
            return {
                "response_type": "ephemeral",
                "text": (
                    "Usage: `/watchlist add [name]`, `/watchlist remove [name]`, "
                    "or `/watchlist list`"
                ),
            }

    def _handle_watchlist_list(self, channel_id: str) -> Dict[str, str]:
        """Handle watchlist list command."""
        watchlist = self.db_manager.get_channel_watchlist(channel_id)

        if not watchlist:
            return {
                "response_type": "ephemeral",
                "text": (
                    "📝 Watchlist is empty. Use `/watchlist add [name]` to add entities."
                ),
            }

        lines = ["📝 **Current Watchlist:**"]

        # Group by type
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for item in watchlist:
            item_type = item["entity_type"]
            if item_type not in by_type:
                by_type[item_type] = []
            by_type[item_type].append(item)

        for entity_type, items in by_type.items():
            type_name = entity_type.title() + "s"
            lines.append(f"\n*{type_name}:*")
            for item in items:
                score_text = (
                    f" ({item['fuzzy_score']:.0f}% match)"
                    if item["fuzzy_score"] < 100
                    else ""
                )
                lines.append(f"• {item['display_name']}{score_text}")

        return {"response_type": "ephemeral", "text": "\n".join(lines)}

    def _handle_watchlist_add(
        self, search_term: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle watchlist add command."""
        result = self.matching_service.process_watchlist_add(channel_id, search_term)

        if result["status"] == "success":
            return {"response_type": "in_channel", "text": result["message"]}
        elif result["status"] == "no_match":
            return {"response_type": "ephemeral", "text": result["message"]}
        elif result["status"] == "confirmation_needed":
            # Store pending confirmation
            confirmation_key = f"{channel_id}:{user_id}:{int(time.time())}"
            self.pending_confirmations[confirmation_key] = {
                "search_term": result["search_term"],
                "candidates": result["candidates"],
                "channel_id": channel_id,
                "user_id": user_id,
                "timestamp": time.time(),
            }

            # Post message asking for confirmation
            message = result["message"] + f"\n\n_Confirmation key: {confirmation_key}_"

            return {"response_type": "ephemeral", "text": message}
        else:
            return {"response_type": "ephemeral", "text": result["message"]}

    def _handle_watchlist_remove(
        self, search_term: str, channel_id: str
    ) -> Dict[str, str]:
        """Handle watchlist remove command."""
        success = self.db_manager.remove_from_watchlist(channel_id, search_term)

        if success:
            return {
                "response_type": "in_channel",
                "text": f"✅ Removed **{search_term}** from watchlist.",
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": f"❌ **{search_term}** not found in watchlist.",
            }

    def _is_admin_user(self, user_id: str) -> bool:
        """Check if user is admin."""
        admin_users = settings.get_admin_users()
        return (
            not admin_users or user_id in admin_users
        )  # If no admins configured, everyone is admin

    def _handle_threshold_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /threshold command."""
        # Admin check for threshold changes
        if text and not self._is_admin_user(user_id):
            return {
                "response_type": "ephemeral",
                "text": (
                    "❌ Only admins can modify thresholds. "
                    "Contact your channel admin."
                ),
            }

        if not text:
            settings = self.db_manager.get_channel_settings(channel_id)
            return {
                "response_type": "ephemeral",
                "text": (
                    f"Current thresholds:\n• Filings: {settings['threshold_filings']}\n"
                    f"• Amount: ${settings['threshold_amount']:,}\n\n"
                    f"Usage: `/threshold set filings [number]` or "
                    f"`/threshold set amount [number]`"
                ),
            }

        parts = text.split()
        if len(parts) != 3 or parts[0] != "set":
            return {
                "response_type": "ephemeral",
                "text": (
                    "Usage: `/threshold set filings [number]` or "
                    "`/threshold set amount [number]`"
                ),
            }

        threshold_type = parts[1].lower()
        try:
            value = int(parts[2])
        except ValueError:
            return {
                "response_type": "ephemeral",
                "text": "Threshold value must be a number.",
            }

        if threshold_type == "filings":
            self.db_manager.update_channel_setting(
                channel_id, "threshold_filings", value
            )
            return {
                "response_type": "in_channel",
                "text": f"✅ Mini-digest filing threshold set to **{value}**.",
            }
        elif threshold_type == "amount":
            self.db_manager.update_channel_setting(
                channel_id, "threshold_amount", value
            )
            return {
                "response_type": "in_channel",
                "text": f"✅ Alert amount threshold set to **${value:,}**.",
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": "Threshold type must be 'filings' or 'amount'.",
            }

    def _handle_summary_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /summary command."""
        # Admin check for summary setting changes
        if text and not self._is_admin_user(user_id):
            return {
                "response_type": "ephemeral",
                "text": (
                    "❌ Only admins can modify summary settings. "
                    "Contact your channel admin."
                ),
            }

        if not text or text.lower() not in ["on", "off"]:
            settings = self.db_manager.get_channel_settings(channel_id)
            status = "ON" if settings["show_descriptions"] else "OFF"
            return {
                "response_type": "ephemeral",
                "text": (
                    f"Filing descriptions are currently **{status}**.\n\n"
                    f"Usage: `/summary on` or `/summary off`"
                ),
            }

        show_descriptions = text.lower() == "on"
        self.db_manager.update_channel_setting(
            channel_id, "show_descriptions", show_descriptions
        )

        status = "ON" if show_descriptions else "OFF"
        return {
            "response_type": "in_channel",
            "text": f"✅ Filing descriptions turned **{status}**.",
        }

    def _handle_lobbylens_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /lobbylens command for manual digest generation and LDA commands."""
        if not text:
            return self._lobbylens_help()

        parts = text.strip().split()
        command = parts[0].lower()

        if command == "digest":
            # Generate manual digest (V2 signals)
            try:
                digest = self.digest_computer.compute_enhanced_digest(
                    channel_id, "daily"
                )

                # Post digest to channel
                result = self.post_message(channel_id, digest)

                if result.get("ok"):
                    return {
                        "response_type": "ephemeral",
                        "text": "✅ Manual digest generated and posted to channel.",
                    }
                else:
                    return {
                        "response_type": "ephemeral",
                        "text": (
                            f"❌ Failed to post digest: "
                            f"{result.get('error', 'Unknown error')}"
                        ),
                    }
            except Exception as e:
                logger.error(f"Manual digest generation failed: {e}")
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Failed to generate digest: {e}",
                }

        elif command == "lda":
            # Handle LDA subcommands
            return self._handle_lda_subcommands(parts[1:], channel_id, user_id)

        else:
            return self._lobbylens_help()

    def _handle_lda_subcommands(
        self, args: List[str], channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle LDA subcommands."""
        from .lda_front_page_digest import LDAFrontPageDigest
        from .permissions import get_permission_manager
        from .utils import is_lda_enabled

        if not is_lda_enabled():
            return {
                "response_type": "ephemeral",
                "text": (
                    "💵 LDA features are currently disabled. "
                    "Set ENABLE_LDA_V1=true to enable."
                ),
            }

        permission_manager = get_permission_manager()

        if not args:
            return self._lda_help()

        subcommand = args[0].lower()

        try:
            lda_digest = LDAFrontPageDigest(self.db_manager)

            if subcommand == "digest":
                # Check permissions - only channel admins can post digests
                if not permission_manager.can_post_digest(channel_id, user_id):
                    return {
                        "response_type": "ephemeral",
                        "text": permission_manager.get_permission_error_message(
                            "/lobbylens lda digest"
                        ),
                    }

                # Generate LDA digest
                quarter = None
                if len(args) > 1 and args[1].startswith("q="):
                    quarter = args[1][2:]  # Extract quarter from q=2025Q3

                digest = lda_digest.generate_digest(channel_id, quarter)

                # Post digest to channel
                result = self.post_message(channel_id, digest)

                if result.get("ok"):
                    # Record digest run
                    self.db_manager.record_digest_run(channel_id, "lda_digest")
                    return {
                        "response_type": "ephemeral",
                        "text": "✅ LDA digest generated and posted to channel.",
                    }
                else:
                    return {
                        "response_type": "ephemeral",
                        "text": (
                            f"❌ Failed to post LDA digest: "
                            f"{result.get('error', 'Unknown error')}"
                        ),
                    }

            elif subcommand == "top":
                if len(args) < 2:
                    return {
                        "response_type": "ephemeral",
                        "text": (
                            "Usage: `/lobbylens lda top registrants [q=2025Q3] [n=10]` "
                            "or "
                            "`/lobbylens lda top clients [q=2025Q3] [n=10]`"
                        ),
                    }

                entity_type = args[1].lower()
                quarter = None
                limit = 10

                # Parse optional parameters
                for arg in args[2:]:
                    if arg.startswith("q="):
                        quarter = arg[2:]
                    elif arg.startswith("n="):
                        try:
                            limit = int(arg[2:])
                        except ValueError:
                            pass

                if entity_type == "registrants":
                    results = lda_digest.get_top_registrants(quarter, limit)
                    title = f"Top Registrants ({quarter or 'Current Quarter'})"
                elif entity_type == "clients":
                    results = lda_digest.get_top_clients(quarter, limit)
                    title = f"Top Clients ({quarter or 'Current Quarter'})"
                else:
                    return {
                        "response_type": "ephemeral",
                        "text": (
                            "Usage: `/lobbylens lda top registrants` or "
                            "`/lobbylens lda top clients`"
                        ),
                    }

                if not results:
                    return {
                        "response_type": "ephemeral",
                        "text": f"No {entity_type} found for the specified quarter.",
                    }

                # Format results
                from .utils import format_amount

                lines = [f"💵 {title}", ""]
                for i, result in enumerate(results, 1):
                    name = result["name"]
                    amount = format_amount(result["total_amount"])
                    count = result["filing_count"]
                    lines.append(f"{i}. {name} — {amount} ({count} filings)")

                return {"response_type": "ephemeral", "text": "\n".join(lines)}

            elif subcommand == "issues":
                quarter = None
                if len(args) > 1 and args[1].startswith("q="):
                    quarter = args[1][2:]

                results = lda_digest.get_issues_summary(quarter)

                if not results:
                    return {
                        "response_type": "ephemeral",
                        "text": "No issues found for the specified quarter.",
                    }

                # Format results
                from .utils import format_amount

                lines = [
                    f"💵 Issue Summary ({quarter or 'Current Quarter'})",
                    "",
                ]
                for result in results:
                    code = result["code"]
                    count = result["filing_count"]
                    total = format_amount(result["total_amount"])
                    lines.append(f"• {code}: {count} filings ({total})")

                return {"response_type": "ephemeral", "text": "\n".join(lines)}

            elif subcommand == "entity":
                if len(args) < 2:
                    return {
                        "response_type": "ephemeral",
                        "text": "Usage: `/lobbylens lda entity <name>`",
                    }

                entity_name = " ".join(args[1:])
                quarter = None

                # Check if last arg is a quarter
                if args[-1].startswith("q="):
                    quarter = args[-1][2:]
                    entity_name = " ".join(args[1:-1])

                result = lda_digest.search_entity(entity_name, quarter)

                if "error" in result:
                    return {
                        "response_type": "ephemeral",
                        "text": result["error"],
                    }

                # Format entity results
                from .utils import format_amount

                entity = result["entity"]
                total_amount = format_amount(result["total_amount"])
                filing_count = result["filing_count"]
                quarter_str = result["quarter"]

                lines = [
                    f"💵 {entity['name']} ({entity['type'].title()})",
                    f"Quarter: {quarter_str}",
                    f"Total: {total_amount} ({filing_count} filings)",
                    "",
                ]

                # Show recent filings
                if result["filings"]:
                    lines.append("Recent filings:")
                    for filing in result["filings"][:5]:
                        amount = format_amount(filing.get("amount", 0))
                        if entity["type"] == "client":
                            other_party = filing.get("registrant_name", "Unknown")
                            lines.append(f"• → {other_party} ({amount})")
                        else:
                            other_party = filing.get("client_name", "Unknown")
                            lines.append(f"• {other_party} → ({amount})")

                return {"response_type": "ephemeral", "text": "\n".join(lines)}

            elif subcommand == "watchlist":
                if len(args) < 2:
                    return {
                        "response_type": "ephemeral",
                        "text": (
                            "Usage: `/lobbylens lda watchlist add/remove/list <term>`"
                        ),
                    }

                action = args[1].lower()

                if action == "list":
                    watchlist = self.db_manager.get_channel_watchlist(channel_id)
                    if not watchlist:
                        return {
                            "response_type": "ephemeral",
                            "text": "No watchlist items configured for this channel.",
                        }

                    lines = ["💵 LDA Watchlist:", ""]
                    for item in watchlist:
                        entity_type = item["entity_type"].title()
                        name = item["display_name"] or item["watch_name"]
                        lines.append(f"• {name} ({entity_type})")

                    return {
                        "response_type": "ephemeral",
                        "text": "\n".join(lines),
                    }

                elif action in ["add", "remove"]:
                    if len(args) < 3:
                        return {
                            "response_type": "ephemeral",
                            "text": (
                                f"Usage: `/lobbylens lda watchlist {action} "
                                f"<entity_name>`"
                            ),
                        }

                    entity_name = " ".join(args[2:])

                    if action == "add":
                        # Default to client type for LDA watchlist
                        success = self.db_manager.add_to_watchlist(
                            channel_id, "client", entity_name
                        )
                        if success:
                            return {
                                "response_type": "ephemeral",
                                "text": f"✅ Added '{entity_name}' to LDA watchlist.",
                            }
                        else:
                            return {
                                "response_type": "ephemeral",
                                "text": (
                                    f"❌ Failed to add '{entity_name}' to watchlist."
                                ),
                            }

                    else:  # remove
                        success = self.db_manager.remove_from_watchlist(
                            channel_id, entity_name
                        )
                        if success:
                            return {
                                "response_type": "ephemeral",
                                "text": f"✅ Removed '{entity_name}' from watchlist.",
                            }
                        else:
                            return {
                                "response_type": "ephemeral",
                                "text": f"❌ '{entity_name}' not found in watchlist.",
                            }

                else:
                    return {
                        "response_type": "ephemeral",
                        "text": (
                            "Usage: `/lobbylens lda watchlist add/remove/list <term>`"
                        ),
                    }

            elif subcommand == "help":
                return self._lda_help()

            else:
                return self._lda_help()

        except Exception as e:
            logger.error(f"LDA command failed: {e}")
            return {
                "response_type": "ephemeral",
                "text": f"❌ LDA command failed: {str(e)}",
            }

    def _lobbylens_help(self) -> Dict[str, str]:
        """Return LobbyLens help message."""
        return {
            "response_type": "ephemeral",
            "text": "🔍 **LobbyLens Commands:**\n"
            "• `/lobbypulse` - Generate fresh government activity digest\n"
            "• `/watchlist` - Manage watchlist entities\n"
            "• `/threshold` - Set alert thresholds\n"
            "• `/summary` - Toggle filing descriptions\n"
            "• `/lobbylens digest` - Generate manual V2 digest\n"
            "• `/lobbylens lda` - LDA (lobbying money) commands\n\n"
            "_Use `/lobbylens lda help` for LDA commands._",
        }

    def _lda_help(self) -> Dict[str, str]:
        """Return LDA help message."""
        return {
            "response_type": "ephemeral",
            "text": "💵 **LDA Commands:**\n\n"
            "**Data Queries** (available to all members):\n"
            "• `/lobbylens lda top registrants [q=2025Q3] [n=10]` - "
            "Top lobbying firms\n"
            "• `/lobbylens lda top clients [q=2025Q3] [n=10]` - "
            "Top clients by spending\n"
            "• `/lobbylens lda issues [q=2025Q3]` - Issue code summary\n"
            "• `/lobbylens lda entity <name>` - Search for specific entity\n"
            "• `/lobbylens lda watchlist add/remove/list <term>` - Manage watchlist\n\n"
            "**Digest Posting** (channel admins only):\n"
            "• `/lobbylens lda digest [q=2025Q3]` - "
            "Post LDA money digest to channel\n\n"
            "**Understanding LDA Data:**\n"
            "• **Amount Semantics**: `—` = not reported, `$0` = explicitly zero "
            "(may indicate ≤$5K)\n"
            "• **Issue Codes**: HCR = Health, DEF = Defense, BUD = Budget, "
            "EDU = Education, etc.\n"
            "• **Data Cadence**: Quarterly filings, updated monthly on 15th\n"
            '• **Amendments**: Labeled "(amended)" in digests\n\n'
            "**Common Issue Codes:**\n"
            "HCR (Health) • DEF (Defense) • BUD (Budget) • EDU (Education)\n"
            "TAX (Taxation) • ENV (Environmental) • FIN (Financial) • TEC (Telecom)\n\n"
            "_Quarter format: 2025Q1, 2025Q2, etc. Data from U.S. Senate LDA filings._",
        }

    def handle_message_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Handle message events (for confirmation responses)."""
        if event_data.get("type") != "message" or event_data.get("bot_id"):
            return None  # Skip non-messages and bot messages

        text = event_data.get("text", "").strip()
        channel_id = event_data.get("channel", "")
        user_id = event_data.get("user", "")

        # Look for confirmation key in message
        confirmation_key = None
        for key in self.pending_confirmations:
            if key in text:
                confirmation_key = key
                break

        if not confirmation_key:
            return None  # Not a confirmation response

        confirmation = self.pending_confirmations.get(confirmation_key)
        if (
            not confirmation
            or confirmation["channel_id"] != channel_id
            or confirmation["user_id"] != user_id
        ):
            return None

        # Check if confirmation is still valid (within 10 minutes)
        if time.time() - confirmation["timestamp"] > 600:
            del self.pending_confirmations[confirmation_key]
            return None

        # Extract response from message (remove confirmation key)
        response = text.replace(confirmation_key, "").strip()

        # Process confirmation response
        result = self.matching_service.process_confirmation_response(
            channel_id=confirmation["channel_id"],
            search_term=confirmation["search_term"],
            candidates=confirmation["candidates"],
            response=response,
        )

        # Clean up confirmation
        del self.pending_confirmations[confirmation_key]

        # Post result to channel
        self.post_message(channel_id, result["message"])

        return result

    def _handle_lobbypulse_command(
        self, text: str, channel_id: str, user_id: str
    ) -> Dict[str, str]:
        """Handle /lobbypulse command for manual digest generation."""
        # Parse digest type from text
        digest_type = "daily"  # Default
        if text:
            text_lower = text.lower().strip()
            if text_lower in ["daily", "mini"]:
                digest_type = text_lower
            elif text_lower in ["help", "?"]:
                return {
                    "response_type": "ephemeral",
                    "text": "💓 **LobbyPulse Commands:**\n"
                    "• `/lobbypulse` - Generate daily digest\n"
                    "• `/lobbypulse daily` - Generate daily digest\n"
                    "• `/lobbypulse mini` - Generate mini digest\n"
                    "• `/lobbypulse help` - Show this help\n\n"
                    "_This won't affect your scheduled morning/afternoon digests._",
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Unknown option: `{text}`\n"
                    "Use `/lobbypulse help` for available options.",
                }

        # Generate and send digest
        try:
            logger.info(
                f"Manual {digest_type} digest requested by {user_id} in {channel_id}"
            )

            # Generate digest
            digest = self.digest_computer.compute_enhanced_digest(
                channel_id, digest_type
            )

            # Post to channel
            result = self.post_message(channel_id, digest)

            if result.get("ok", False):
                return {
                    "response_type": "in_channel",
                    "text": (
                        f"💓 **LobbyPulse {digest_type.title()} Digest** "
                        f"generated successfully!"
                    ),
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": (
                        f"❌ Failed to generate {digest_type} digest. "
                        f"Please try again."
                    ),
                }

        except Exception as e:
            logger.error(f"Error generating manual {digest_type} digest: {e}")
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error generating {digest_type} digest: {str(e)}",
            }

    def send_digest(self, channel_id: str, digest_type: str = "daily") -> bool:
        """Send digest to a channel."""
        try:
            digest = self.digest_computer.compute_enhanced_digest(
                channel_id, digest_type
            )
            result = self.post_message(channel_id, digest)
            return bool(result.get("ok", False))
        except Exception as e:
            logger.error(f"Failed to send {digest_type} digest to {channel_id}: {e}")
            return False

    def send_alert(self, channel_id: str, message: str) -> bool:
        """Send alert message to a channel."""
        try:
            alert_text = f"🚨 **LobbyLens Alert**\n\n{message}"
            result = self.post_message(channel_id, alert_text)
            return bool(result.get("ok", False))
        except Exception as e:
            logger.error(f"Failed to send alert to {channel_id}: {e}")
            return False


def create_slack_app(db_manager: DatabaseManager) -> SlackApp:
    """Factory function to create Slack app instance."""
    return SlackApp(db_manager)
