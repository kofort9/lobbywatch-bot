#!/usr/bin/env python3
"""Script to fix remaining line length issues in test files."""

import os
import re


def fix_line_length_final() -> None:
    """Fix remaining line length issues in test files."""
    test_files = [
        "tests/test_daily_signals_v2.py",
        "tests/test_digest_v2.py",
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

            lines = content.split("\n")
            fixed_lines = []

            for line in lines:
                if len(line) > 88:
                    # Fix long method signatures
                    if "def test_" in line and "(" in line and ")" in line:
                        # Break method signatures at parameters
                        if "self, " in line:
                            parts = line.split("self, ")
                            if len(parts) == 2:
                                method_part = parts[0] + "self,"
                                params_part = parts[1]
                                if len(method_part) + len(params_part) > 88:
                                    # Break at the first parameter
                                    params = params_part.split(", ")
                                    if len(params) > 1:
                                        first_param = params[0]
                                        remaining_params = ", ".join(params[1:])
                                        fixed_line = f"{method_part}\n        {first_param},\n        {remaining_params}"
                                        fixed_lines.append(fixed_line)
                                    else:
                                        fixed_lines.append(line)
                                else:
                                    fixed_lines.append(line)
                            else:
                                fixed_lines.append(line)
                        else:
                            fixed_lines.append(line)
                    elif "assert " in line and len(line) > 88:
                        # Break assert statements
                        if " in " in line:
                            parts = line.split(" in ")
                            if len(parts) == 2:
                                left_part = parts[0]
                                right_part = parts[1]
                                if len(left_part) + len(right_part) + 4 > 88:
                                    fixed_line = f"        {left_part} in {right_part}"
                                    fixed_lines.append(fixed_line)
                                else:
                                    fixed_lines.append(line)
                            else:
                                fixed_lines.append(line)
                        else:
                            fixed_lines.append(line)
                    else:
                        # Generic long line - try to break at spaces
                        if " " in line:
                            words = line.split(" ")
                            if len(words) > 1:
                                # Try to break at 80 characters
                                current_line = ""
                                for word in words:
                                    if len(current_line + word) > 80:
                                        if current_line:
                                            fixed_lines.append(current_line.rstrip())
                                        current_line = "        " + word + " "
                                    else:
                                        current_line += word + " "
                                if current_line:
                                    fixed_lines.append(current_line.rstrip())
                            else:
                                fixed_lines.append(line)
                        else:
                            fixed_lines.append(line)
                else:
                    fixed_lines.append(line)

            with open(file_path, "w") as f:
                f.write("\n".join(fixed_lines))


if __name__ == "__main__":
    fix_line_length_final()
    print("Fixed line length issues in test files")
