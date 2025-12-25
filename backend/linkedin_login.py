# linkedin_login.py
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

class LinkedInLogin:
    def __init__(self, headless: bool = True, status_callback=None):
        self.headless = headless
        self.status_callback = status_callback or (lambda msg: None)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = None
        self.page = None
        self.logged_in = False
        self.cookies = None  # <-- Add cookies attribute

    # Initialize context and page for a user
    def _init_context(self, username: str):
        storage_path = Path("data/linkedin") / username
        storage_path.mkdir(parents=True, exist_ok=True)
        state_file = storage_path / "state.json"
        time.sleep(1)

        if state_file.exists():
            time.sleep(1)
            self.status_callback(f"🔄 Loading existing LinkedIn session for {username}")
            self.context = self.browser.new_context(storage_state=str(state_file))
            self.page = self.context.new_page()
            self.page.goto("https://www.linkedin.com/feed/")
            time.sleep(3)
            if "feed" in self.page.url or "/in/" in self.page.url:
                self.logged_in = True
                self.cookies = self.context.cookies()  # <-- Populate cookies
                self.status_callback("✅ Reused saved login session")
                return
            else:
                self.status_callback("⚠️ Saved session invalid, logging in fresh...")

        # If no valid session, create fresh context and page
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    # Perform login
    def login(self, username: str, password: str):
        self._init_context(username)
        if self.logged_in:
            return

        self.status_callback(f"🔐 Logging in as {username}")
        self.page.goto("https://www.linkedin.com/login")
        self.page.fill("input#username", username)
        self.page.fill("input#password", password)
        self.page.click("button[type=submit]")
        time.sleep(5)

        current_url = self.page.url
        if "feed" in current_url or "/in/" in current_url:
            self.logged_in = True
            self.cookies = self.context.cookies()  # <-- Populate cookies after login
            self.status_callback("✅ Logged in successfully!")

            # Save session for reuse
            storage_path = Path("data/linkedin") / username
            storage_path.mkdir(parents=True, exist_ok=True)
            state_file = storage_path / "state.json"
            self.context.storage_state(path=str(state_file))
            self.status_callback("💾 Saved LinkedIn session for future reuse")
        else:
            self.logged_in = False
            self.status_callback(f"❌ Login failed. URL: {current_url}")

    def goto(self, url: str):
        if self.page:
            self.page.goto(url)
        else:
            raise RuntimeError("Browser page not initialized. Call login() first.")

    # Close browser and context
    def close(self):
        try:
            if self.context:
                self.context.close()
            self.browser.close()
            self.playwright.stop()
            self.status_callback("✅ Playwright browser closed")
        except Exception as e:
            self.status_callback(f"⚠️ Error closing browser: {e}")
