#!/usr/bin/env python3
"""Verify LobbyLens setup and configuration."""

import os
import sys
from pathlib import Path

def check_environment():
    """Check environment variables and configuration."""
    print("🔍 Checking environment configuration...")
    
    required_for_testing = ["SLACK_WEBHOOK_URL"]
    optional = ["OPENSECRETS_API_KEY", "PROPUBLICA_API_KEY"]
    
    missing_required = []
    missing_optional = []
    
    for var in required_for_testing:
        if not os.getenv(var):
            missing_required.append(var)
        else:
            print(f"  ✅ {var} is set")
    
    for var in optional:
        if not os.getenv(var):
            missing_optional.append(var)
        else:
            print(f"  ✅ {var} is set")
    
    if missing_required:
        print(f"  ❌ Missing required: {', '.join(missing_required)}")
        return False
    
    if missing_optional:
        print(f"  ⚠️  Missing optional: {', '.join(missing_optional)}")
        print("     (Bot will work but may have limited data)")
    
    return True

def check_dependencies():
    """Check that required packages are installed."""
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        "requests",
        "python-dotenv", 
        "pandas",
        "python-dateutil",
        "click",
        "rich",
        "pydantic",
        "pydantic-settings"
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"  ✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package}")
    
    if missing:
        print(f"\n  Install missing packages: pip install {' '.join(missing)}")
        return False
    
    return True

def check_bot_modules():
    """Check that bot modules can be imported."""
    print("\n🤖 Checking bot modules...")
    
    modules = [
        "bot.config",
        "bot.digest", 
        "bot.run",
        "bot.notifiers.slack"
    ]
    
    missing = []
    
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            missing.append(module)
            print(f"  ❌ {module}: {e}")
    
    if missing:
        print("\n  Some bot modules failed to import. Check dependencies.")
        return False
    
    return True

def test_cli_command():
    """Test that the CLI command is available."""
    print("\n💻 Testing CLI command...")
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["lobbylens", "--help"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            print("  ✅ CLI command works")
            return True
        else:
            print(f"  ❌ CLI command failed: {result.stderr}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  ❌ CLI command not available: {e}")
        return False

def test_dry_run():
    """Test a dry run of the bot."""
    print("\n🧪 Testing dry run...")
    
    if not os.getenv("SLACK_WEBHOOK_URL"):
        print("  ⚠️  Skipping dry run test (no SLACK_WEBHOOK_URL)")
        return True
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["lobbylens", "--dry-run", "--skip-fetch"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("  ✅ Dry run successful")
            if "DRY RUN" in result.stdout:
                print("  ✅ Dry run output detected")
                return True
            else:
                print("  ⚠️  Dry run completed but no expected output")
                return True
        else:
            print(f"  ❌ Dry run failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Dry run timed out")
        return False

def main():
    """Run all verification checks."""
    print("🔍 LobbyLens Setup Verification\n" + "="*40)
    
    checks = [
        ("Environment Configuration", check_environment),
        ("Dependencies", check_dependencies), 
        ("Bot Modules", check_bot_modules),
        ("CLI Command", test_cli_command),
        ("Dry Run Test", test_dry_run)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        print(f"\n{'='*40}")
        if check_func():
            passed += 1
        
    print(f"\n{'='*40}")
    print(f"📊 Summary: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All checks passed! LobbyLens is ready to use.")
        
        print("\n💡 Next steps:")
        print("  1. Set up GitHub repository secrets")
        print("  2. Enable GitHub Actions workflows") 
        print("  3. Test manual workflow dispatch")
        print("  4. Wait for your first daily digest!")
        
        return True
    else:
        print(f"❌ {total - passed} checks failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
