#!/usr/bin/env python3
"""Script to fix unused imports in test files."""

import os
import re


def fix_unused_imports():
    """Fix unused imports in test files."""
    test_files = [
        "tests/conftest.py",
        "tests/test_config.py",
        "tests/test_daily_signals_v2.py",
        "tests/test_digest.py",
        "tests/test_digest_v2.py",
        "tests/test_notifiers.py",
        "tests/test_run.py",
        "tests/test_run_v2.py",
        "tests/test_signals_database_v2.py",
        "tests/test_signals_v2.py",
        "tests/test_test_fixtures_v2.py",
        "tests/test_web_server_v2.py",
    ]

    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"Fixing {file_path}...")
            with open(file_path, "r") as f:
                content = f.read()

            # Remove unused imports
            unused_imports = [
                "import json",
                "from typing import Any, Dict, List, Optional",
                "from typing import Dict, List, Optional",
                "from typing import Any, Dict, List",
                "from typing import Any, Dict",
                "from typing import Any",
                "from typing import Dict",
                "from typing import List",
                "from typing import Optional",
                "from unittest.mock import Mock",
                "from unittest.mock import MagicMock",
                "import os",
                "import argparse",
                "from bot.signals_v2 import SignalType, Urgency",
            ]

            for unused_import in unused_imports:
                # Remove the import line
                content = re.sub(
                    f"^{re.escape(unused_import)}$", "", content, flags=re.MULTILINE
                )
                # Remove empty lines that might be left behind
                content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)

            with open(file_path, "w") as f:
                f.write(content)


if __name__ == "__main__":
    fix_unused_imports()
    print("Fixed unused imports in test files")
