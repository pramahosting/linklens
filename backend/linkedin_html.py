# linkedin_html.py
import time
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse

class LinkedInHTML:
    def __init__(self, page, status_callback=None):
        self.page = page
        self.status_callback = status_callback or (lambda msg: None)
        self.saved_files = []  # Track saved HTML files

    def save_profile_html(self, link: str, folder: Path) -> Path:
        """Save LinkedIn profile page HTML locally, ensuring unique filenames and handling errors."""
        try:
            self.page.goto(link)
            time.sleep(2)
            content = self.page.content()
            if not content or len(content) < 100:
                self.status_callback(f"⚠️ Warning: Content too short or empty for {link}")
        except Exception as e:
            self.status_callback(f"❌ Failed to load {link}: {e}")
            return None

        folder.mkdir(parents=True, exist_ok=True)

        parsed = urlparse(link)
        slug = parsed.path.strip("/").split("/")[-1] or ""
        if not slug:
            title_match = re.search(r"<title>(.*?)</title>", content, re.I | re.S)
            slug = title_match.group(1).strip() if title_match else "linkedin_profile"

        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-") or "linkedin_profile"
        filename = folder / f"{slug}_{int(time.time())}.html"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            self.saved_files.append(filename)
            return filename
        except Exception as e:
            # self.status_callback(f"❌ Failed to save HTML for {link}: {e}")
            return None

    def report_saved_count(self):
        """Send a single status message with total HTML files saved."""
        self.status_callback(f"💾 {len(self.saved_files)} HTML files saved successfully")

    def move_parsed_file(self, file_path: Path, parsed_folder: Path):
        """Move parsed HTML file to a designated folder safely."""
        if not file_path.exists():
            self.status_callback(f"⚠️ File not found: {file_path}")
            return None

        parsed_folder.mkdir(parents=True, exist_ok=True)
        dest_file = parsed_folder / file_path.name
        try:
            shutil.move(str(file_path), str(dest_file))
            self.status_callback(f"Moved parsed file to: {dest_file}")
            return dest_file
        except Exception as e:
            self.status_callback(f"❌ Failed to move {file_path} to {parsed_folder}: {e}")
            return None
