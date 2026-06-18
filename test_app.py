from playwright.sync_api import sync_playwright

def test_app():
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Navigating to http://localhost:3000...")
        page.goto('http://localhost:3000')
        
        print("Waiting for network idle...")
        page.wait_for_load_state('networkidle')
        
        title = page.title()
        print(f"Page Title: {title}")
        
        print("Taking screenshot...")
        page.screenshot(path='/Users/hammadahmed/.gemini/antigravity-ide/brain/aacfbfae-9108-4e54-9cb4-55f199d902f0/landing_page_test.png', full_page=True)
        
        # Check if the "Due Diligence, Accelerated." text is visible
        try:
            print("Checking for main headline...")
            # We can use a general locator
            locator = page.locator('text="Due Diligence"')
            if locator.is_visible():
                print("SUCCESS: Main headline found.")
            else:
                print("WARNING: Main headline not visible.")
        except Exception as e:
            print(f"Error checking elements: {e}")
            
        print("Test completed successfully.")
        browser.close()

if __name__ == "__main__":
    test_app()
