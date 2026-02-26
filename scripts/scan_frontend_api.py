import os
import re
import json

def scan_directory(directory, extensions):
    results = []
    # Regex for fetch
    fetch_pattern = re.compile(r'fetch\((.*?)\)')
    # Regex for ApiContract
    api_pattern = re.compile(r'ApiContract\.execute(?:Web)?(?:<.*?>)?\((.*?)\)')
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                path = os.path.join(root, file)
                # handle utf-8 decoding gracefully
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f):
                        line_clean = line.strip()
                        if 'fetch(' in line_clean or 'ApiContract.execute' in line_clean:
                            results.append({
                                'file': path.replace('\\', '/').split('quantsight_cloud_build/')[-1],
                                'line_num': i + 1,
                                'code': line_clean
                            })
    return results

files = scan_directory(r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\src', ['.ts', '.tsx'])
files.extend(scan_directory(r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\electron', ['.js']))

with open(r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\scripts\scan_frontend_api.json', 'w') as f:
    json.dump(files, f, indent=2)
