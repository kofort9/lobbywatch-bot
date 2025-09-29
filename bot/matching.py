"""Fuzzy matching system for entity and issue matching."""

import logging
import re
import sqlite3
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """Handles fuzzy matching for entities, issues, and aliases."""

    def __init__(self, db_connection: sqlite3.Connection):
        self.conn = db_connection

    def normalize_string(self, text: str) -> str:
        """Normalize string for matching."""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove common suffixes and prefixes
        suffixes = [
            " inc",
            " inc.",
            " corp",
            " corp.",
            " llc",
            " ltd",
            " ltd.",
            " company",
            " co",
            " co.",
            " corporation",
            " incorporated",
            " limited",
            " llp",
            " lp",
            " pllc",
        ]

        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break

        # Remove punctuation except spaces and alphanumeric
        text = re.sub(r"[^\w\s]", " ", text)

        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def token_set_ratio(self, str1: str, str2: str) -> float:
        """Calculate token set ratio (similar to fuzzywuzzy)."""
        tokens1 = set(str1.split())
        tokens2 = set(str2.split())

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        if not union:
            return 0.0

        return len(intersection) / len(union) * 100

    def similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings."""
        norm1 = self.normalize_string(str1)
        norm2 = self.normalize_string(str2)

        # Exact match after normalization
        if norm1 == norm2:
            return 100.0

        # Token set ratio (handles word order differences)
        token_score = self.token_set_ratio(norm1, norm2)

        # Sequence matcher (handles typos and partial matches)
        sequence_score = SequenceMatcher(None, norm1, norm2).ratio() * 100

        # Return the higher of the two scores
        return max(token_score, sequence_score)

    def find_entity_matches(
        self,
        search_term: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find entity matches with scores."""
        matches = []

        # First check aliases
        alias_query = "SELECT * FROM entity_aliases WHERE alias_name = ?"
        params = [self.normalize_string(search_term)]

        if entity_type:
            alias_query += " AND entity_type = ?"
            params.append(entity_type)

        cursor = self.conn.execute(alias_query, params)
        alias_result = cursor.fetchone()

        if alias_result:
            matches.append(
                {
                    "type": "entity",
                    "id": alias_result["entity_id"],
                    "name": alias_result["canonical_name"],
                    "entity_type": alias_result["entity_type"],
                    "score": 100.0,  # Perfect alias match
                    "source": "alias",
                }
            )
            return matches

        # Search entities
        entity_query = """
        SELECT id, name, type FROM entity
        WHERE 1=1
        """
        params = []

        if entity_type and entity_type in ["client", "registrant"]:
            entity_query += " AND type = ?"
            params.append(entity_type)

        cursor = self.conn.execute(entity_query, params)
        entities = cursor.fetchall()

        for entity in entities:
            score = self.similarity_score(search_term, entity["name"])
            if score >= 50:  # Minimum threshold
                matches.append(
                    {
                        "type": "entity",
                        "id": entity["id"],
                        "name": entity["name"],
                        "entity_type": entity["type"],
                        "score": score,
                        "source": "database",
                    }
                )

        # Search issues if relevant
        if not entity_type or entity_type == "issue":
            issue_query = "SELECT id, code, description FROM issue"
            cursor = self.conn.execute(issue_query)
            issues = cursor.fetchall()

            for issue in issues:
                # Check both code and description
                code_score = self.similarity_score(search_term, issue["code"])
                desc_score = self.similarity_score(
                    search_term, issue["description"] or ""
                )
                score = max(code_score, desc_score)

                if score >= 50:
                    matches.append(
                        {
                            "type": "issue",
                            "id": issue["id"],
                            "name": f"{issue['code']} "
                            f"({issue['description'] or issue['code']})",
                            "entity_type": "issue",
                            "code": issue["code"],
                            "description": issue["description"],
                            "score": score,
                            "source": "database",
                        }
                    )

        # Sort by score descending and limit results
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    def categorize_matches(
        self, matches: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize matches by confidence level."""
        exact = []
        high_confidence = []
        medium_confidence = []
        low_confidence = []

        for match in matches:
            score = match["score"]
            if score >= 95:
                exact.append(match)
            elif score >= 91:
                high_confidence.append(match)
            elif score >= 85:
                medium_confidence.append(match)
            else:
                low_confidence.append(match)

        return {
            "exact": exact,
            "high_confidence": high_confidence,
            "medium_confidence": medium_confidence,
            "low_confidence": low_confidence,
        }

    def create_confirmation_message(
        self,
        search_term: str,
        categorized_matches: Dict[str, List[Dict[str, Any]]],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Create confirmation message and return candidates for selection."""
        exact = categorized_matches["exact"]
        high_confidence = categorized_matches["high_confidence"]
        medium_confidence = categorized_matches["medium_confidence"]
        low_confidence = categorized_matches["low_confidence"]

        # Auto-accept exact matches
        if exact:
            if len(exact) == 1:
                return "auto_accept", exact
            else:
                # Multiple exact matches - user should choose
                candidates = exact
                message = f"Multiple exact matches for '{search_term}':\n"
                for i, match in enumerate(candidates, 1):
                    message += f"{i}) {match['name']}\n"
                message += "\nReply with number (1-{}), 'all', or 'q' to cancel.".format(
                    len(candidates))
                return message, candidates

        # High confidence - auto-accept single, prompt for multiple
        if high_confidence:
            if len(high_confidence) == 1:
                return "auto_accept", high_confidence
            else:
                candidates = high_confidence
                message = f"High confidence matches for '{search_term}':\n"
                for i, match in enumerate(candidates, 1):
                    message += f"{i}) {match['name']}\n"
                message += "\nReply with number (1-{}), 'all', or 'q' to cancel.".format(
                    len(candidates))
                return message, candidates

        # Medium confidence - always prompt
        if medium_confidence:
            candidates = medium_confidence[:3]  # Limit to top 3
            message = f"Possible matches for '{search_term}':\n"
            for i, match in enumerate(candidates, 1):
                message += (
                    f"{i}) {match['name']} ({match['score']:.0f}% match)\n"
                )
            message += (
                "\nReply with number (1-{}), 'all', or 'q' to cancel.".format(
                    len(candidates)
                )
            )
            return message, candidates

        # Low confidence or no matches
        if low_confidence:
            candidates = low_confidence[:3]
            message = f"Weak matches for '{search_term}' (try a more complete name):\n"
            for i, match in enumerate(candidates, 1):
                message += (
                    f"{i}) {match['name']} ({match['score']:.0f}% match)\n"
                )
            message += "\nReply with number (1-{}) or 'q' to cancel.".format(
                len(candidates)
            )
            return message, candidates

        # No matches at all
        return (
            f"No matches found for '{search_term}'. "
            f"Try a more complete name (e.g., 'Alphabet Inc.' instead of 'Google').",
            [],
        )


class MatchingService:
    """Service for handling entity matching workflows."""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager

    def process_watchlist_add(
        self, channel_id: str, search_term: str
    ) -> Dict[str, Any]:
        """Process a watchlist add request with fuzzy matching."""
        with self.db_manager.get_connection() as conn:
            matcher = FuzzyMatcher(conn)

            # Find matches
            matches = matcher.find_entity_matches(search_term)
            categorized = matcher.categorize_matches(matches)

            # Create confirmation message
            message, candidates = matcher.create_confirmation_message(
                search_term, categorized
            )

            if message == "auto_accept":
                # Auto-accept the match
                match = candidates[0]
                success = self.db_manager.add_to_watchlist(
                    channel_id=channel_id,
                    entity_type=match["entity_type"],
                    watch_name=search_term,
                    display_name=match["name"],
                    entity_id=match["id"],
                    fuzzy_score=match["score"],
                )

                if success:
                    # Add alias for future fast matching
                    self.db_manager.add_entity_alias(
                        alias_name=search_term,
                        canonical_name=match["name"],
                        entity_type=match["entity_type"],
                        entity_id=match["id"],
                        confidence_score=match["score"] / 100.0,
                    )

                    return {
                        "status": "success",
                        "message": f"✅ Now watching **{match['name']}**.",
                        "added": [match],
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Failed to add to watchlist. Please try again.",
                        "added": [],
                    }

            elif not candidates:
                # No matches found
                return {
                    "status": "no_match",
                    "message": message,
                    "candidates": [],
                }

            else:
                # Need user confirmation
                return {
                    "status": "confirmation_needed",
                    "message": message,
                    "candidates": candidates,
                    "search_term": search_term,
                }

    def process_confirmation_response(
        self,
        channel_id: str,
        search_term: str,
        candidates: List[Dict[str, Any]],
        response: str,
    ) -> Dict[str, Any]:
        """Process user's confirmation response."""
        response = response.strip().lower()

        if response == "q":
            return {
                "status": "cancelled",
                "message": "❌ Cancelled adding to watchlist.",
                "added": [],
            }

        added = []

        if response == "all":
            # Add all candidates
            for candidate in candidates:
                success = self.db_manager.add_to_watchlist(
                    channel_id=channel_id,
                    entity_type=candidate["entity_type"],
                    watch_name=search_term,
                    display_name=candidate["name"],
                    entity_id=candidate["id"],
                    fuzzy_score=candidate["score"],
                )

                if success:
                    added.append(candidate)
                    # Add alias
                    self.db_manager.add_entity_alias(
                        alias_name=search_term,
                        canonical_name=candidate["name"],
                        entity_type=candidate["entity_type"],
                        entity_id=candidate["id"],
                        confidence_score=candidate["score"] / 100.0,
                    )

        else:
            # Try to parse as number
            try:
                choice_num = int(response)
                if 1 <= choice_num <= len(candidates):
                    candidate = candidates[choice_num - 1]
                    success = self.db_manager.add_to_watchlist(
                        channel_id=channel_id,
                        entity_type=candidate["entity_type"],
                        watch_name=search_term,
                        display_name=candidate["name"],
                        entity_id=candidate["id"],
                        fuzzy_score=candidate["score"],
                    )

                    if success:
                        added.append(candidate)
                        # Add alias
                        self.db_manager.add_entity_alias(
                            alias_name=search_term,
                            canonical_name=candidate["name"],
                            entity_type=candidate["entity_type"],
                            entity_id=candidate["id"],
                            confidence_score=candidate["score"] / 100.0,
                        )
                else:
                    return {
                        "status": "error",
                        "message": (
                            f"Invalid choice. Please reply 1-{len(candidates)}, "
                            f"'all', or 'q'."
                        ),
                        "added": [],
                    }
            except ValueError:
                return {
                    "status": "error",
                    "message": (
                        f"Invalid response. Please reply 1-{len(candidates)}, "
                        f"'all', or 'q'."
                    ),
                    "added": [],
                }

        if added:
            if len(added) == 1:
                message = f"✅ Now watching **{added[0]['name']}**."
            else:
                names = [item["name"] for item in added]
                message = f"✅ Now watching {len(added)} entities: {', '.join(names)}."

            return {"status": "success", "message": message, "added": added}
        else:
            return {
                "status": "error",
                "message": "Failed to add any entities to watchlist.",
                "added": [],
            }
