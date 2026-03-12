import os
import sys
# Add parent directory to path so app.core can be found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import config

def test_config():
    os.environ["APP_ENV"] = "development"
    os.environ["TEST_SECRET"] = "super_secret"
    val = config.get_secret("TEST_SECRET")
    assert val == "super_secret", "Config failed to read env var in dev mode"
    print("Phase 2 Tests Passed.")

if __name__ == "__main__":
    test_config()
