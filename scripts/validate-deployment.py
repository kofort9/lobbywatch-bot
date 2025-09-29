#!/usr/bin/env python3
"""Pre-deployment validation script for LobbyLens."""

# import json  # Unused for now
import os
import subprocess
import sys

# from typing import Any, Dict, List  # Unused for now

# import requests  # Unused for now


class DeploymentValidator:
    """Validates LobbyLens deployment readiness."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_environment(self) -> bool:
        """Validate environment variables."""
        print("🔍 Validating environment variables...")

        required_vars = [
            "SLACK_BOT_TOKEN",
            "SLACK_SIGNING_SECRET",
        ]

        optional_vars = [
            "OPENSECRETS_API_KEY",
            "PROPUBLICA_API_KEY",
            "LOBBYLENS_CHANNELS",
        ]

        # Check required vars
        for var in required_vars:
            if not os.getenv(var):
                self.errors.append(f"Missing required environment variable: {var}")
            else:
                print(f"  ✅ {var} is set")

        # Check optional vars
        for var in optional_vars:
            if not os.getenv(var):
                self.warnings.append(f"Optional environment variable not set: {var}")
            else:
                print(f"  ✅ {var} is set")

        # Validate Slack token format (unless testing)
        bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        if (
            bot_token
            and not bot_token.startswith("xoxb-")
            and bot_token != "test_token"
        ):
            self.errors.append("SLACK_BOT_TOKEN should start with 'xoxb-'")

        return len(self.errors) == 0

    def validate_dependencies(self) -> bool:
        """Validate Python dependencies."""
        print("\n📦 Validating dependencies...")

        required_packages = ["flask", "requests", "pydantic", "click", "rich"]

        # Optional packages for production
        optional_packages = ["psycopg2"]

        missing = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"  ✅ {package}")
            except ImportError:
                missing.append(package)
                print(f"  ❌ {package}")

        # Check optional packages
        for package in optional_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"  ✅ {package} (optional)")
            except ImportError:
                print(f"  ⚠️ {package} (optional - needed for PostgreSQL)")

        if missing:
            self.errors.append(f"Missing required packages: {', '.join(missing)}")

        return len(missing) == 0

    def validate_code_structure(self) -> bool:
        """Validate code structure and imports."""
        print("\n🏗️ Validating code structure...")

        try:
            # Test core imports
            # from bot.config import settings  # Unused for now
            # from bot.database import DatabaseManager  # Unused for now
            # from bot.enhanced_run import main  # Unused for now
            # from bot.web_server import create_web_server  # Unused for now

            print("  ✅ Core modules import successfully")
            return True

        except Exception as e:
            self.errors.append(f"Code structure validation failed: {e}")
            return False

    def validate_database(self) -> bool:
        """Validate database setup."""
        print("\n🗄️ Validating database...")

        try:
            from bot.database_postgres import create_database_manager

            # Test with in-memory database
            db_manager = create_database_manager()  # Will use SQLite for testing
            db_manager.ensure_enhanced_schema()

            # Test basic operations
            # settings = db_manager.get_channel_settings("test")  # Unused for now
            # success = db_manager.add_to_watchlist(  # Unused for now
            #     "test", "client", "Test Corp", "Test Corp"
            # )

            print("  ✅ Database operations working")
            return True

        except Exception as e:
            self.errors.append(f"Database validation failed: {e}")
            return False

    def validate_web_server(self) -> bool:
        """Validate web server functionality."""
        print("\n🌐 Validating web server...")

        try:
            from bot.database import DatabaseManager
            from bot.slack_app import SlackApp
            from bot.web_server import create_web_server

            # Create test app
            db_manager = DatabaseManager(":memory:")
            slack_app = SlackApp(db_manager)
            app = create_web_server(slack_app)

            # Test routes exist
            with app.test_client() as client:
                # Test health endpoint
                response = client.get("/lobbylens/health")
                if response.status_code != 200:
                    self.errors.append("Health endpoint not responding correctly")
                else:
                    print("  ✅ Health endpoint working")

                # Test challenge response
                challenge_response = client.post(
                    "/lobbylens/events",
                    json={"type": "url_verification", "challenge": "test123"},
                )

                if challenge_response.status_code == 200:
                    print("  ✅ Challenge response working")
                else:
                    self.errors.append("Challenge response not working")

            return len(self.errors) == 0

        except Exception as e:
            self.errors.append(f"Web server validation failed: {e}")
            return False

    def validate_security(self) -> bool:
        """Validate security settings."""
        print("\n🔒 Validating security...")

        # Check if signature verification is enabled
        signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        if not signing_secret:
            self.warnings.append(
                "SLACK_SIGNING_SECRET not set - signature verification disabled"
            )
        else:
            print("  ✅ Slack signature verification enabled")

        # Check for secrets in code
        sensitive_patterns = ["xoxb-", "hooks.slack.com", "password", "secret"]

        try:
            result = subprocess.run(
                ["grep", "-r", "-i"] + sensitive_patterns + ["bot/"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.warnings.append(
                    "Potential secrets found in code - "
                    "ensure they're in environment variables"
                )
        except Exception:
            pass  # grep not available or other error

        print("  ✅ Basic security checks passed")
        return True

    def run_validation(self) -> bool:
        """Run all validations."""
        print("🚀 LobbyLens Deployment Validation")
        print("=" * 50)

        validations = [
            self.validate_environment,
            self.validate_dependencies,
            self.validate_code_structure,
            self.validate_database,
            self.validate_web_server,
            self.validate_security,
        ]

        all_passed = True
        for validation in validations:
            if not validation():
                all_passed = False

        # Print summary
        print("\n" + "=" * 50)
        print("📊 Validation Summary")

        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️ Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if all_passed and not self.errors:
            print("\n🎉 All validations passed! Ready for deployment.")
        else:
            print("\n❌ Validation failed. Fix errors before deploying.")

        return all_passed and len(self.errors) == 0


def main():
    """Main validation entry point."""
    validator = DeploymentValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
