import sys
import os
import time

def run_ui_test():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: 'playwright' is not installed. Run 'pip install playwright' first.")
        sys.exit(1)

    target_url = "http://localhost:8501/"
    print(f"Starting UI validation test on {target_url}...")

    with sync_playwright() as p:
        # Launch headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the dashboard
            page.goto(target_url, wait_until="networkidle", timeout=30000)
            print("Page loaded successfully. Waiting for UI components to stabilize...")
            
            # Wait for main container
            page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=15000)
            time.sleep(2) # Give dynamic components a moment to render

            # Click Initialize Simulation button to start the simulation and render main dashboard/chat
            page.wait_for_selector("button:has-text('Initialize Simulation')", timeout=10000)
            init_btn = page.locator("button:has-text('Initialize Simulation')")
            init_btn.click()
            time.sleep(3) # Give simulation a moment to initialize and reload

            # Wait for main container to stabilize again
            page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=15000)

            # Check for leaked template tags or raw HTML/JS code strings in body text
            body_text = page.locator("body").inner_text()
            
            leaks = ["{{IS_DARK}}", "{{COMMANDS_JSON}}", "onerror=", "const doc =", "window.fixA11yInterval"]
            for leak in leaks:
                if leak in body_text:
                    raise AssertionError(f"LEAK DETECTED: Raw script or template token '{leak}' found in UI body text!")
            
            # Check for visible style tags (indicating style blocks leaked as text)
            if "<style>" in body_text or "</style>" in body_text:
                raise AssertionError("LEAK DETECTED: Raw <style> tags visible as text in UI body!")

            print("✅ No code leaks or raw scripts found on the home page.")

            # Locate chat input text area
            chat_input_selector = '[data-testid="stChatInput"] textarea'
            page.wait_for_selector(chat_input_selector, timeout=15000)
            chat_input = page.locator(chat_input_selector)

            # Check that the slash command menu is hidden initially
            slash_menu = page.locator("#slash-commands-menu")
            if slash_menu.is_visible():
                raise AssertionError("Slash commands menu is visible before typing '/'!")

            # Focus and type '/' into the chat input
            chat_input.focus()
            chat_input.type("/")
            time.sleep(1) # Let JS event handlers trigger

            # Check that slash commands menu is now visible
            if not slash_menu.is_visible():
                raise AssertionError("Slash commands menu did not appear after typing '/'!")
            
            # Verify menu content has commands
            menu_text = slash_menu.inner_text()
            expected_commands = ["/help", "/step", "/restart", "/review"]
            for cmd in expected_commands:
                if cmd not in menu_text:
                    raise AssertionError(f"Expected command '{cmd}' not found in the slash commands autocomplete menu!")

            print("✅ Autocomplete slash commands menu is working as expected.")
            print("\n🎉 ALL UI VALIDATION TESTS PASSED SUCCESSFULLY!")

        except Exception as e:
            print(f"\n❌ UI Test Failed: {e}")
            browser.close()
            sys.exit(1)

        browser.close()

if __name__ == "__main__":
    run_ui_test()
