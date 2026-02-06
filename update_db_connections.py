"""
Update all database connection calls to use Cloud SQL Connector
"""
import re

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Pattern 1: Full pattern with error check
    pattern1 = r'db_url = get_database_url\(\)\s+if not db_url:\s+raise HTTPException\(status_code=500, detail="DATABASE_URL not configured"\)\s+try:\s+engine = create_engine\(db_url\)'
    replacement1 = 'try:\n        engine = get_database_engine()'
    content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE)
    
    # Pattern 2: Simple pattern
    pattern2 = r'db_url = get_database_url\(\)\s+(if[^\n]+\n\s+[^\n]+\n\s+)?try:\s+engine = create_engine\(db_url\)'
    content = re.sub(pattern2, 'try:\n        engine = get_database_engine()', content, flags=re.MULTILINE)
    
    # Pattern 3: Just the lines
    content = re.sub(r'(\s+)db_url = get_database_url\(\)\n(\s+)if not db_url:\n(\s+)raise HTTPException[^\n]+\n', '', content)
    content = re.sub(r'engine = create_engine\(db_url\)', 'engine = get_database_engine()', content)
    
    # Pattern 4: Standalone get_database_url calls
    content = re.sub(r'(\s+)db_url = get_database_url\(\)\s*\n', '', content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Update all files
files = [
    r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\backend\api\public_routes.py',
    r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\backend\api\admin_routes.py',
    r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\backend\api\matchup_endpoint.py',
]

for file in files:
    try:
        if update_file(file):
            print(f'✅ Updated: {file.split("\\")[-1]}')
        else:
            print(f'⚠️  No changes: {file.split("\\")[-1]}')
    except Exception as e:
        print(f'❌ Error in {file.split("\\")[-1]}: {e}')

print('\n✅ All files updated!')
