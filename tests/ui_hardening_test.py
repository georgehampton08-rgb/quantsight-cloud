from playwright.sync_api import sync_playwright
import sys

def run_tests():
    print("Starting Playwright UI Hardening Tests...")
    
    with sync_playwright() as p:
        # Launch Chromium headless
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print("1. Navigating to Command Center...")
            page.goto("http://localhost:5173")
            page.wait_for_load_state("networkidle")
            
            # Use case-insensitive search or exact DOM case
            page.wait_for_selector('text="Command Center"', timeout=5000)
            print("✔ Command Center Loaded")
            
            page.screenshot(path="tests/screenshots/1_command_center.png", full_page=True)
            
            print("2. Testing Box Score Tab...")
            box_scores_tab = page.locator('button', has_text="BOX SCORES").first
            box_scores_tab.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path="tests/screenshots/2_box_scores_tab.png", full_page=True)
            print("✔ Box Scores Tab active")
            
            print("3. Testing Play-By-Play Tab...")
            pbp_tab = page.locator('button', has_text="PLAY-BY-PLAY").first
            pbp_tab.click()
            page.wait_for_load_state("networkidle")
            page.screenshot(path="tests/screenshots/3_play_by_play_tab.png", full_page=True)
            print("✔ Play-By-Play Tab active")
            
            print("4. Testing Settings Page Routing & Rendering...")
            page.goto("http://localhost:5173/settings")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector('text="System Settings"', timeout=5000)
            page.screenshot(path="tests/screenshots/4_settings_page.png", full_page=True)
            print("✔ Settings Page Loaded")
            
        except Exception as e:
            print(f"❌ Test Failed: {str(e)}")
            page.screenshot(path="tests/screenshots/error_state.png", full_page=True)
            browser.close()
            sys.exit(1)
            
        print("All Hardening Tests Passed successfully.")
        browser.close()

if __name__ == "__main__":
    run_tests()
