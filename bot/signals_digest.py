"""Daily signals digest formatting."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .signals_database import SignalsDatabase

logger = logging.getLogger(__name__)


class SignalsDigestFormatter:
    """Formats daily signals into Slack digest messages."""
    
    def __init__(self, signals_db: SignalsDatabase):
        self.signals_db = signals_db

    def format_daily_digest(self, channel_id: str, hours_back: int = 24) -> str:
        """Format a daily signals digest."""
        signals = self.signals_db.get_recent_signals(hours_back, limit=50)
        
        if not signals:
            return self._format_empty_digest()
        
        # Group signals by type
        hearings = [s for s in signals if 'hearing' in s.get('title', '').lower()]
        bills = [s for s in signals if s.get('bill_id')]
        regulations = [s for s in signals if s.get('rin') or s.get('docket_id')]
        surges = self.signals_db.get_comment_surges(hours_back)
        
        lines = []
        lines.append(f"📰 **Daily Government Signals** — {datetime.now().strftime('%Y-%m-%d')}")
        
        # Hearings section
        if hearings:
            lines.append(f"\n🎤 **Today's Hearings** ({len(hearings)}):")
            for hearing in hearings[:5]:  # Top 5
                time_str = self._format_timestamp(hearing['timestamp'])
                lines.append(f"• {hearing['title']} {time_str}")
                if hearing.get('link'):
                    lines.append(f"  <{hearing['link']}|View Details>")
        
        # Bill movements section
        if bills:
            lines.append(f"\n📜 **Bill Activity** ({len(bills)}):")
            for bill in bills[:5]:  # Top 5
                bill_id = bill.get('bill_id', 'Unknown')
                lines.append(f"• {bill['title']}")
                if bill.get('link'):
                    lines.append(f"  <{bill['link']}|{bill_id}>")
        
        # Regulatory actions section
        if regulations:
            lines.append(f"\n⚖️ **Regulatory Actions** ({len(regulations)}):")
            for reg in regulations[:5]:  # Top 5
                agency = reg.get('agency', 'Unknown Agency')
                lines.append(f"• {agency}: {reg['title']}")
                if reg.get('link'):
                    lines.append(f"  <{reg['link']}|View Rule>")
        
        # Comment surges section
        if surges:
            lines.append(f"\n📈 **Comment Surges** ({len(surges)}):")
            for surge in surges[:3]:  # Top 3
                comment_count = surge.get('metric_json', {}).get('comment_count', 0)
                lines.append(f"• {surge['title']} ({comment_count} comments)")
                if surge.get('link'):
                    lines.append(f"  <{surge['link']}|View Docket>")
        
        # Issue activity summary
        issue_counts = self._count_issues(signals)
        if issue_counts:
            lines.append(f"\n🏷️ **Issue Activity:**")
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                lines.append(f"• {issue}: {count} signals")
        
        # Footer
        lines.append(f"\n_Updated at {datetime.now().strftime('%H:%M')} PT_")
        
        return "\n".join(lines)

    def format_mini_digest(self, channel_id: str, hours_back: int = 4) -> Optional[str]:
        """Format a mini digest if thresholds are met."""
        signals = self.signals_db.get_recent_signals(hours_back, limit=20)
        
        if len(signals) < 5:  # Threshold for mini digest
            return None
        
        # Check for high-priority signals
        high_priority = [s for s in signals if s.get('priority_score', 0) > 5.0]
        
        if not high_priority:
            return None
        
        lines = []
        lines.append(f"⚡ **Mini Signals Alert** — {datetime.now().strftime('%H:%M')} PT")
        lines.append(f"_{len(signals)} signals in last {hours_back}h, {len(high_priority)} high-priority_")
        
        for signal in high_priority[:3]:
            lines.append(f"• {signal['title']}")
            if signal.get('link'):
                lines.append(f"  <{signal['link']}|View>")
        
        return "\n".join(lines)

    def _format_empty_digest(self) -> str:
        """Format digest when no signals are available."""
        return (
            f"📰 **Daily Government Signals** — {datetime.now().strftime('%Y-%m-%d')}\n\n"
            "No significant government activity detected in the last 24 hours.\n\n"
            f"_Updated at {datetime.now().strftime('%H:%M')} PT_"
        )

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            
            diff = now - dt
            if diff.days > 0:
                return f"({diff.days}d ago)"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"({hours}h ago)"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"({minutes}m ago)"
            else:
                return "(just now)"
        except:
            return ""

    def _count_issues(self, signals: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count issue codes across signals."""
        issue_counts = {}
        
        for signal in signals:
            issue_codes = signal.get('issue_codes', [])
            if isinstance(issue_codes, str):
                try:
                    issue_codes = eval(issue_codes)
                except:
                    issue_codes = []
            
            for issue in issue_codes:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        return issue_counts

    def should_send_mini_digest(self, channel_id: str, hours_back: int = 4) -> bool:
        """Check if mini digest should be sent based on thresholds."""
        signals = self.signals_db.get_recent_signals(hours_back, limit=20)
        
        # Check signal count threshold
        if len(signals) < 5:
            return False
        
        # Check for high-priority signals
        high_priority = [s for s in signals if s.get('priority_score', 0) > 5.0]
        if len(high_priority) > 0:
            return True
        
        # Check for comment surges
        surges = self.signals_db.get_comment_surges(hours_back)
        if len(surges) > 0:
            return True
        
        return False
