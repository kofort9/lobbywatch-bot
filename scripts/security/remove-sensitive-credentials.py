#!/usr/bin/env python3
"""
Security script to check for and remove sensitive credentials from the codebase.

This script scans for common patterns of sensitive data:
- API keys
- Database connection strings with passwords
- Slack tokens and webhooks
- Other secrets

Usage:
    python scripts/security/remove-sensitive-credentials.py --check
    python scripts/security/remove-sensitive-credentials.py --scan
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Patterns to detect sensitive data
SENSITIVE_PATTERNS = [
    # API Keys
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([A-Za-z0-9]{20,})["\']?', "API Key"),
    # Database URLs with passwords
    (
        r"postgresql://[^:]+:([^@]+)@",
        "Database password in connection string",
    ),
    (
        r"mysql://[^:]+:([^@]+)@",
        "MySQL password in connection string",
    ),
    # Slack tokens
    (r"xoxb-[A-Za-z0-9-]{20,}", "Slack bot token"),
    (r"xoxa-[A-Za-z0-9-]{20,}", "Slack app token"),
    (r"xoxp-[A-Za-z0-9-]{20,}", "Slack user token"),
    (r"hooks\.slack\.com/services/[A-Za-z0-9/]+", "Slack webhook URL"),
    # Signing secrets (hex strings)
    (
        r'(?i)(signing[_-]?secret|secret)\s*[=:]\s*["\']?([a-f0-9]{32,})["\']?',
        "Signing secret",
    ),
    # Generic secrets (long alphanumeric strings)
    (
        r'(?i)(password|passwd|pwd|secret|token)\s*[=:]\s*["\']?([A-Za-z0-9]{16,})["\']?',
        "Generic secret",
    ),
]

# Files/directories to exclude from scanning
EXCLUDE_PATTERNS = [
    ".git",
    "__pycache__",
    "*.pyc",
    ".env",  # This should be in .gitignore, but check anyway
    "node_modules",
    ".venv",
    "venv",
    "htmlcov",
    "build",
    "dist",
    "*.egg-info",
    ".pytest_cache",
]


def should_exclude_file(file_path: Path) -> bool:
    """Check if a file should be excluded from scanning."""
    path_str = str(file_path)
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str:
            return True
    return False


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a file for sensitive patterns."""
    findings = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                for pattern, description in SENSITIVE_PATTERNS:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        # Mask the sensitive part
                        matched_text = match.group(0)
                        if len(matched_text) > 50:
                            masked = matched_text[:20] + "..." + matched_text[-10:]
                        else:
                            masked = matched_text[:10] + "..."
                        findings.append((line_num, description, masked))
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
    return findings


def scan_directory(root_dir: Path) -> dict:
    """Scan a directory for sensitive data."""
    findings = {}
    root_str = str(root_dir)

    # Scan Python files
    for py_file in root_dir.rglob("*.py"):
        if should_exclude_file(py_file):
            continue
        file_findings = scan_file(py_file)
        if file_findings:
            rel_path = str(py_file.relative_to(root_dir))
            findings[rel_path] = file_findings

    # Scan Markdown files
    for md_file in root_dir.rglob("*.md"):
        if should_exclude_file(md_file):
            continue
        file_findings = scan_file(md_file)
        if file_findings:
            rel_path = str(md_file.relative_to(root_dir))
            findings[rel_path] = file_findings

    # Scan shell scripts
    for sh_file in root_dir.rglob("*.sh"):
        if should_exclude_file(sh_file):
            continue
        file_findings = scan_file(sh_file)
        if file_findings:
            rel_path = str(sh_file.relative_to(root_dir))
            findings[rel_path] = file_findings

    # Scan YAML files (for GitHub Actions, docker-compose, etc.)
    for yaml_file in root_dir.rglob("*.yml"):
        if should_exclude_file(yaml_file):
            continue
        file_findings = scan_file(yaml_file)
        if file_findings:
            rel_path = str(yaml_file.relative_to(root_dir))
            findings[rel_path] = file_findings

    for yaml_file in root_dir.rglob("*.yaml"):
        if should_exclude_file(yaml_file):
            continue
        file_findings = scan_file(yaml_file)
        if file_findings:
            rel_path = str(yaml_file.relative_to(root_dir))
            findings[rel_path] = file_findings

    return findings


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for sensitive credentials in the codebase"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for sensitive data and exit with error if found",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan for sensitive data and report findings",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Path to scan (default: current directory)",
    )

    args = parser.parse_args()

    if not args.check and not args.scan:
        parser.print_help()
        sys.exit(1)

    root_dir = Path(args.path).resolve()
    if not root_dir.exists():
        print(f"Error: Path {root_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Scanning {root_dir} for sensitive credentials...")
    print("=" * 70)

    findings = scan_directory(root_dir)

    if not findings:
        print("✅ No sensitive credentials found in tracked files!")
        print("\nNote: Make sure .env is in .gitignore and not committed.")
        sys.exit(0)

    print(
        f"\n⚠️  Found {sum(len(v) for v in findings.values())} potential security issues:\n"
    )

    for file_path, file_findings in sorted(findings.items()):
        print(f"📄 {file_path}:")
        for line_num, description, masked_text in file_findings:
            print(f"   Line {line_num}: {description}")
            print(f"      Found: {masked_text}")
        print()

    if args.check:
        print(
            "\n❌ Security check failed! Please remove sensitive data before committing."
        )
        sys.exit(1)
    else:
        print("\n⚠️  Review the findings above and remove any sensitive data.")
        sys.exit(0)


if __name__ == "__main__":
    main()
