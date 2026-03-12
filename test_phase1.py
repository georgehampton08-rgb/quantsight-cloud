import os
import subprocess

def test_hygiene():
    # Check if tracked by git
    result_secrets = subprocess.run(["git", "ls-files", ".db_url_secret.txt"], capture_output=True, text=True)
    assert not result_secrets.stdout.strip(), "Secret file still tracked by git"
    
    result_modules = subprocess.run(["git", "ls-files", "node_modules"], capture_output=True, text=True)
    assert not result_modules.stdout.strip(), "node_modules still tracked by git"
    print("Phase 1 Tests Passed.")

if __name__ == "__main__":
    test_hygiene()
