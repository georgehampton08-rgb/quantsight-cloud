import os
import re
import json

src_dir = r"c:\Users\georg\quantsight_engine\quantsight_cloud_build\src"

fixed_dims = []
overflows = []
modals_popups = []
tabs_found = []

# Regexes
w_px_re = re.compile(r'\bw-\[([0-9]+)px\]')
h_px_re = re.compile(r'\bh-\[([0-9]+)px\]')
style_w_re = re.compile(r'style=\{\{[^\}]*width:\s*[\'"]?([0-9]+)px[\'"]?')
style_h_re = re.compile(r'style=\{\{[^\}]*height:\s*[\'"]?([0-9]+)px[\'"]?')
min_w_px_re = re.compile(r'\bmin-w-\[([0-9]+)px\]')
pos_px_re = re.compile(r'\b(top|left|right|bottom)-\[([0-9]+)px\]')
overflow_re = re.compile(r'\boverflow-(hidden|auto|scroll|visible)\b')

for root, _, files in os.walk(src_dir):
    for f in files:
        if not (f.endswith('.tsx') or f.endswith('.ts')): continue
        path = os.path.join(root, f)
        rel_path = os.path.relpath(path, src_dir).replace('\\', '/')
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
            lines = content.split('\n')
            
            # FIXED DIMS
            for i, line in enumerate(lines):
                # Width
                for m in w_px_re.finditer(line):
                    val = int(m.group(1))
                    fixed_dims.append({"file": rel_path, "line": i+1, "type": "w", "value": val, "safe": "SAFE" if val <= 44 else "BROKEN"})
                for m in style_w_re.finditer(line):
                    val = int(m.group(1))
                    fixed_dims.append({"file": rel_path, "line": i+1, "type": "style-w", "value": val, "safe": "SAFE" if val <= 44 else "BROKEN"})
                
                # Height
                for m in h_px_re.finditer(line):
                    val = int(m.group(1))
                    fixed_dims.append({"file": rel_path, "line": i+1, "type": "h", "value": val, "safe": "SAFE" if val <= 44 else "BROKEN"})
                for m in style_h_re.finditer(line):
                    val = int(m.group(1))
                    fixed_dims.append({"file": rel_path, "line": i+1, "type": "style-h", "value": val, "safe": "SAFE" if val <= 44 else "BROKEN"})
                
                # Min Width
                for m in min_w_px_re.finditer(line):
                    val = int(m.group(1))
                    if val > 320:
                        fixed_dims.append({"file": rel_path, "line": i+1, "type": "min-w", "value": val, "safe": "BROKEN (>320)"})

                # Pos
                for m in pos_px_re.finditer(line):
                    pos_type = m.group(1)
                    val = int(m.group(2))
                    fixed_dims.append({"file": rel_path, "line": i+1, "type": f"{pos_type}", "value": val, "safe": "BROKEN"})
                
                # Overflow
                for m in overflow_re.finditer(line):
                    overflows.append({"file": rel_path, "line": i+1, "type": m.group(1)})
                    
            # TABS
            if "tabs" in content.lower() and "map" in content:
                tabs_found.append(rel_path)
                
            # MODALS
            if any(x in content for x in ["<Modal", "<BottomSheet", "<Dialog", "<Tooltip"]):
                modals_popups.append(rel_path)

out_data = {
    "fixed_dims": fixed_dims,
    "overflows": overflows,
    "tabs": list(set(tabs_found)),
    "modals": list(set(modals_popups))
}

with open("phase0_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2)
