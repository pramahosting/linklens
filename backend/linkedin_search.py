# linkedin_search.py
import time
from typing import List, Optional

class LinkedInSearch:
    def __init__(self, page, status_callback=None):
        self.page = page
        self.status_callback = status_callback or (lambda msg: None)

    def collect_profile_links(self, job_title: str, country: str, max_results: int = 20, city: Optional[str] = "") -> List[str]:
        if not self.page:
            raise RuntimeError("LinkedIn page context required for search")

        search_keywords = f"{job_title} {city} {country}".strip()
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={search_keywords.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER"
        self.status_callback(f"🔍 Searching LinkedIn: {search_keywords}")
        self.page.goto(search_url)
        time.sleep(4)

        profile_links = set()
        scroll_attempts = 0
        max_scroll_attempts = 5

        while len(profile_links) < max_results and scroll_attempts < max_scroll_attempts:
            anchors = self.page.query_selector_all("a[href*='/in/']")
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/search/" not in href:
                    profile_links.add(href.split("?")[0])
                    if len(profile_links) >= max_results:
                        break
            self.page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(2)
            scroll_attempts += 1

        self.status_callback(f"✅ Collected {len(profile_links)} profile links")
        return list(profile_links)[:max_results]
