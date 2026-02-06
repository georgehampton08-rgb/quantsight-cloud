"""
Cleanup Script: Remove Old Nexus Code
Scans backend codebase and removes deprecated Nexus Hub code from server.py
"""
import re
from pathlib import Path

def cleanup_old_nexus():
    """Remove all old Nexus code from server.py"""
    server_file = Path(__file__).parent.parent / "server.py"
    
    if not server_file.exists():
        print("❌ server.py not found")
        return
    
    content = server_file.read_text()
    original_lines = len(content.split('\n'))
    
    # Patterns to remove
    patterns_to_remove = [
        # Old Nexus imports
        (r'from aegis\.nexus_hub import.*\n', ''),
        (r'.*nexus_hub.*\n', ''),
        
        # Old Nexus routes (lines 2831-3005)
        (r'@app\.get\("/nexus/.*?\n.*?(?=@app\.|# =)', '', re.DOTALL),
        (r'@app\.post\("/nexus/.*?\n.*?(?=@app\.|# =)', '', re.DOTALL),
        (r'@app\.delete\("/nexus/.*?\n.*?(?=@app\.|# =)', '', re.DOTALL),
    ]
    
    modified_content = content
    removed_sections = 0
    
    # Remove each pattern
    for pattern, replacement, *flags in patterns_to_remove:
        if flags:
            matches = re.findall(pattern, modified_content, flags[0])
        else:
            matches = re.findall(pattern, modified_content)
        
        if matches:
            removed_sections += len(matches)
            if flags:
                modified_content = re.sub(pattern, replacement, modified_content, flags=flags[0])
            else:
                modified_content = re.sub(pattern, replacement, modified_content)
    
    if modified_content != content:
        # Backup original
        backup_file = server_file.with_suffix('.py.bak')
        server_file.rename(backup_file)
        print(f"✅ Backed up to {backup_file.name}")
        
        # Write cleaned version
        server_file.write_text(modified_content)
        new_lines = len(modified_content.split('\n'))
        
        print(f"✅ Removed {removed_sections} Nexus sections")
        print(f"✅ Reduced from {original_lines} to {new_lines} lines ({original_lines - new_lines} lines removed)")
        print(f"✅ Cleaned server.py saved")
    else:
        print("ℹ️  No old Nexus code found in server.py")

if __name__ == "__main__":
    print("🧹 Cleaning up old Nexus code...")
    cleanup_old_nexus()
    print("✅ Cleanup complete!")
