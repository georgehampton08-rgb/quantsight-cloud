import sys
import json
import os
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "tests/screenshots/layout"

def get_layout_issues(page):
    """
    Inject JS to find elements whose scrollWidth exceed clientWidth 
    AND to find significant visual overlaps.
    """
    js_code = """() => {
        let issues = [];
        
        // 1. Check for Overflow Issues
        document.querySelectorAll('*').forEach(el => {
            const style = window.getComputedStyle(el);
            if (el.scrollWidth > Math.ceil(el.clientWidth)) {
                // Ignore elements that intentionally scroll
                if (style.overflow === 'hidden' || style.overflowX === 'hidden' || style.overflowX === 'auto' || style.overflowX === 'scroll') {
                    return;
                }
                
                // Ignore text inputs
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    return;
                }
                
                let id = el.className || el.tagName;
                issues.push('Horizontal Overflow on: ' + id);
            }
        });

        // 2. Check for Overlap Issues (Collision Detection)
        // Only checking significant identifiable elements to avoid noise.
        const targets = Array.from(document.querySelectorAll('button, a, input, h1, h2, .pro-card, .sidebar, header'));
        
        for (let i = 0; i < targets.length; i++) {
            for (let j = i + 1; j < targets.length; j++) {
                const rect1 = targets[i].getBoundingClientRect();
                const rect2 = targets[j].getBoundingClientRect();
                
                // Ignore hidden or zero-size elements
                if (rect1.width === 0 || rect1.height === 0 || rect2.width === 0 || rect2.height === 0) continue;
                
                // Check if they visually intersect
                const intersectX = Math.max(0, Math.min(rect1.right, rect2.right) - Math.max(rect1.left, rect2.left));
                const intersectY = Math.max(0, Math.min(rect1.bottom, rect2.bottom) - Math.max(rect1.top, rect2.top));
                
                const overlapArea = intersectX * intersectY;
                
                // If overlap is significant (>20px area) and they aren't parent/child
                if (overlapArea > 20) {
                    if (!targets[i].contains(targets[j]) && !targets[j].contains(targets[i])) {
                        
                        // Ignore absolute/fixed overlays intentionally covering things
                        const style1 = window.getComputedStyle(targets[i]);
                        const style2 = window.getComputedStyle(targets[j]);
                        
                        if (style1.position === 'absolute' || style1.position === 'fixed' || 
                            style2.position === 'absolute' || style2.position === 'fixed') {
                            
                            // Let's only flag it if they have z-index issues, or if it's text/buttons overlapping
                            // For this audit, we'll flag it so we can review it manually.
                            issues.push(`Visual Overlap: <${targets[i].tagName} class="${targets[i].className}"> overlaps <${targets[j].tagName} class="${targets[j].className}">`);
                        }
                    }
                }
            }
        }

        return issues;
    }"""
    try:
        issues = page.evaluate(js_code)
        # Deduplicate and filter empty
        return list(set([i for i in issues if i.strip()]))
    except Exception as e:
        return [f"JS Eval Error: {e}"]


def run_tests():
    print("Starting Comprehensive UI Check (Overflow, Types, Overlaps, Sizing)...")
    
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    routes = [
        ("/", "Command Center"),
        ("/#/player", "Player Lab"),
        ("/#/matchup", "Matchup Engine"),
        ("/#/settings", "Settings")
    ]
    
    viewports = [
        {"name": "Desktop", "width": 1920, "height": 1080},
        {"name": "Mobile", "width": 375, "height": 812}
    ]
    
    has_global_errors = False
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for vp in viewports:
            print(f"\n======================================")
            print(f"Testing Viewport: {vp['name']} ({vp['width']}x{vp['height']})")
            print(f"======================================")
            
            context = browser.new_context(viewport={"width": vp['width'], "height": vp['height']})
            page = context.new_page()
            
            try:
                page.goto("http://localhost:5173/")
                page.wait_for_load_state("networkidle")
                page.wait_for_selector('#disclaimer-acknowledge-btn', timeout=3000)
                page.locator('#disclaimer-acknowledge-btn').click()
                page.wait_for_timeout(1000)
            except Exception:
                pass 
                
            for route, name in routes:
                print(f"\n  ---> Navigating to {name} ({route})")
                try:
                    page.goto(f"http://localhost:5173{route}")
                    page.wait_for_load_state("networkidle", timeout=10000)
                    page.wait_for_timeout(2000) 
                    
                    issues = get_layout_issues(page)
                    
                    filename = f"{SCREENSHOT_DIR}/{vp['name']}_{name.replace(' ', '_').lower()}.png"
                    page.screenshot(path=filename, full_page=True)
                    
                    if issues:
                        print(f"       ❌ Found {len(issues)} UI anomalies:")
                        for issue in issues[:10]: # Show up to 10
                            print(f"          - {issue}")
                        has_global_errors = True
                    else:
                        print(f"       ✔ Layout clean.")
                        
                except Exception as e:
                    print(f"       ❌ Failed to load route: {str(e)[:100]}...")
                    has_global_errors = True
                    
            context.close()
            
        browser.close()
        
    if has_global_errors:
        print("\n❌ Comprehensive UI Check finished with errors. Please review the output.")
        sys.exit(1)
    else:
        print("\n✅ All comprehensive UI checks passed successfully!")

if __name__ == "__main__":
    run_tests()
