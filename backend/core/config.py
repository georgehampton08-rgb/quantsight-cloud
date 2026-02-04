"""
Core Configuration
Central source of truth for application constants.
"""
from datetime import datetime

# --- Global Constants ---
# AUTOMATICALLY CALCULATE SEASON BASED ON DATE
# Logic: If month is >= 10 (Oct), we are in the start of a season (e.g. Oct 2025 -> 2025-26)
# If month is < 10 (Jan-Sep), we are in the end of a season (e.g. Jan 2026 -> 2025-26)

def get_current_season():
    now = datetime.now()
    if now.month >= 10:
        start_year = now.year
        end_year = (now.year + 1) % 100
    else:
        start_year = now.year - 1
        end_year = now.year % 100
    
    return f"{start_year}-{end_year:02d}"

CURRENT_SEASON = get_current_season()
print(f"[CONFIG] Active Season: {CURRENT_SEASON}")

# API Settings
NBA_API_TIMEOUT = 10
NBA_API_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
