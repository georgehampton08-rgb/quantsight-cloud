import os
import glob
import re

def main():
    base_dir = r"c:\Users\georg\quantsight_engine\quantsight_cloud_build\src"
    tsx_files = glob.glob(os.path.join(base_dir, "**", "*.tsx"), recursive=True)
    
    replacements = {
        # Colors
        "cyber-bg": "pro-bg",
        "cyber-surface": "pro-surface",
        "cyber-border": "pro-border",
        "cyber-text": "pro-text",
        "cyber-muted": "pro-muted",
        "cyber-green": "emerald-500",
        "cyber-blue": "blue-500",
        "cyber-gold": "amber-500",
        "cyber-red": "red-500",
        "cyber-purple": "purple-500",
        
        # Border logic / Brutalism removals
        "rounded-none": "rounded-xl",
        "shadow-none": "shadow-sm",
        "font-display": "font-medium",
        
        # Clean up tracking and text limits that made it look childish
        "tracking-[0.2em]": "tracking-wide",
        "tracking-[0.08em]": "tracking-normal",
        "tracking-[0.1em]": "tracking-wide",
        "tracking-[0.15em]": "tracking-wide",
        "text-[10px]": "text-xs",
        "text-[9px]": "text-xs",
        
        # We don't want uppercase spanning paragraphs
        # "uppercase": "" # careful with global replace, let's keep it for headers and labels, but we will remove it where redundant
        
        # Removing specific brutalist inline styles and patterns
        "style={{ border: '1px solid #1a2332' }}": "",
        "style={{ border: '1px solid rgba(245, 158, 11, 0.3)' }}": "",
    }
    
    # Regexes for multi-line block removals
    corner_bracket_re = re.compile(r"<\s*CornerBrackets.*?\s*/>")
    corner_bracket_import_re = re.compile(r"import\s+CornerBrackets.*?['\"].*?['\"];?.*?\n")
    
    # Background scanline gradient removal
    scanline_re = re.compile(r"<div\s+className=[\"']absolute inset-0 pointer-events-none opacity-\[0\.03\].*?</div>", flags=re.DOTALL)
    scanline_style_re = re.compile(r"style=\{\{\s*backgroundImage:\s*'linear-gradient\(.*?\)',\s*backgroundSize:\s*'32px 32px',\s*\}\}\s*/>", flags=re.DOTALL)

    for fp in tsx_files:
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
            
        original_content = content
        
        # 1. Direct string replacements
        for old, new in replacements.items():
            content = content.replace(old, new)
            
        # 2. Regex removals
        content = corner_bracket_re.sub("", content)
        content = corner_bracket_import_re.sub("", content)
        
        # Sometimes the scanline div spans multiple lines, so let's hit it with a broader regex
        content = re.sub(r'<div className="absolute inset-0 pointer-events-none opacity-\[0\.03\] z-0"\s*style=\{\{\s*backgroundImage:\s*\'linear-gradient.*?backgroundSize:\s*\'32px 32px\',\s*\}\}\s*/>', '', content, flags=re.DOTALL)
        
        if content != original_content:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Refactored styling in: {os.path.basename(fp)}")

if __name__ == "__main__":
    main()
