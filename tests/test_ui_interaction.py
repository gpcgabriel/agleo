import sys
import os
import time


def run_ui_test():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: 'playwright' is not installed. Run 'pip install playwright' first.")
        sys.exit(1)

    # Reading the port from the environment so this follows whatever the app is
    # actually served on; 8502 is what `.claude/launch.json` starts.
    target_url = os.environ.get("LEOSIM_URL", "http://localhost:8502/")
    print(f"Starting UI validation test on {target_url}...")

    with sync_playwright() as p:
        # Launching a headless browser.
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigating to the dashboard.
            page.goto(target_url, wait_until="networkidle", timeout=30000)
            print("Page loaded successfully. Waiting for UI components to stabilize...")

            # Waiting for the main container.
            page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=15000)
            time.sleep(2)  # Give dynamic components a moment to render

            # Clicking Initialize Simulation, which renders the dashboard and the chat.
            page.wait_for_selector("button:has-text('Initialize Simulation')", timeout=10000)
            init_btn = page.locator("button:has-text('Initialize Simulation')")
            init_btn.click()

            # Waiting on the chat input rather than on a fixed delay: building the
            # simulation takes a few seconds, and the first tick of a session is
            # slower than the rest.
            page.wait_for_selector('[data-testid="stChatInput"] textarea', timeout=60000)

            # Letting the accessibility script catch up. It attaches the slash menu
            # to whatever chat input is on the page from a poll that runs once a
            # second, so the field can exist for up to that long before it works.
            time.sleep(3)

            # Waiting for the main container to stabilize again.
            page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=15000)

            # Looking for template tags or raw HTML/JS leaked into the body text.
            body_text = page.locator("body").inner_text()

            # `accessibility.js` interpolates the command list and nothing else, so
            # what a leak looks like today is the script's own source in the body.
            leaks = ["onerror=", "const doc =", "initAccessibility(", "slashMenuRealm"]
            for leak in leaks:
                if leak in body_text:
                    raise AssertionError(f"LEAK DETECTED: Raw script or template token '{leak}' found in UI body text!")

            # Looking for visible style tags, which mean a style block leaked as text.
            if "<style>" in body_text or "</style>" in body_text:
                raise AssertionError("LEAK DETECTED: Raw <style> tags visible as text in UI body!")

            print("✅ No code leaks or raw scripts found on the home page.")

            # Locating the chat input text area.
            chat_input_selector = '[data-testid="stChatInput"] textarea'
            page.wait_for_selector(chat_input_selector, timeout=15000)
            chat_input = page.locator(chat_input_selector)

            # Checking that the slash command menu starts hidden.
            slash_menu = page.locator("#slash-commands-menu")
            if slash_menu.is_visible():
                raise AssertionError("Slash commands menu is visible before typing '/'!")

            # Clicking rather than focusing, and typing through the keyboard: the
            # menu opens from the `input` and `keyup` events the real field emits.
            chat_input.click()
            page.keyboard.type("/")
            time.sleep(1.5)  # Let JS event handlers trigger

            # Checking that the slash command menu is now visible.
            if not slash_menu.is_visible():
                raise AssertionError("Slash commands menu did not appear after typing '/'!")

            # Checking that the menu lists commands.
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
