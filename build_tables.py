import json
from collections import Counter

with open('audit_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Design System Violations (Colors)
print("### Design System Violations")
print("| File | Value Found | Should Be |")
print("|---|---|---|")
for color_item in data['hardcoded_colors']:
    if 'index.css' in color_item['file']: continue
    val = color_item['match']
    print(f"| {color_item['file']} | `{val}` | Tailwind token or CSS Var |")

print("\n### Spacing Inconsistency Map")
print("| Component Class | Occurrences |")
print("|---|---|")
spacing = data['spacing_classes']
sorted_spacing = sorted(spacing.items(), key=lambda x: x[1], reverse=True)
for sp_class, count in sorted_spacing:
    print(f"| `{sp_class}` | {count} |")

print("\n### TODOs and Hacks")
for item in data['todos_hacks']:
    print(f"- **{item['file']}:{item['line']}**: `{item['match']}`")

print("\n### Inline Styles")
for item in data['style_overrides']:
    print(f"- **{item['file']}:{item['line']}**: `{item['match']}`")

print("\n### !important usage")
for item in data['important_css']:
    print(f"- **{item['file']}:{item['line']}**: `{item['match']}`")

print("\n### Console Logs")
for item in data['console_logs']:
    print(f"- **{item['file']}:{item['line']}**: `{item['match']}`")
