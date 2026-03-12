import os
import glob
import re

def main():
    base_dir = r"c:\Users\georg\quantsight_engine\quantsight_cloud_build\src"
    tsx_files = glob.glob(os.path.join(base_dir, "**", "*.tsx"), recursive=True)
    
    replacements = {
        # Fix font weights
        "font-600": "font-semibold",
        "font-700": "font-bold",
        "font-500": "font-medium",
        
        # Remove wide tracking
        "tracking-widest": "tracking-wide",
        "tracking-[0.12em]": "tracking-normal",
        "tracking-[0.05em]": "tracking-normal",
        
        # Mute glowing text artifacts
        "text-emerald-400": "text-emerald-500",
        "text-blue-400": "text-blue-500",
        
        # Fix terms to be more professional
        "CONTROL ROOM": "System Settings",
        "VANGUARD SOVEREIGN HEALTH": "System Health & Diagnostics",
        "SEARCH PROTOCOL INITIATED": "Ready for Search",
        "AWAITING CONTENDERS": "Select Matchup",
        "SELECT A PLAYER FROM THE COMMAND CENTER OR TEAM CENTRAL TO INITIALIZE ANALYSIS.": "Search for a player to view detailed head-to-head analysis.",
        "CLOUD TWIN V4.1.2": "Version 4.1.2",
    }
    
    # Outer glow / global shadows removal
    # the cyber-root class or global shadow styling
    
    for fp in tsx_files:
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
            
        original_content = content
        
        # 1. Direct string replacements
        for old, new in replacements.items():
            content = content.replace(old, new)
            
        if content != original_content:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Refactored typography & copy in: {os.path.basename(fp)}")

if __name__ == "__main__":
    main()
