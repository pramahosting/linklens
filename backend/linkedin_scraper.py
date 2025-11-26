import os
import time
import logging
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class LinkedInScraper:
    def __init__(self, headless: bool = False):
        self.driver = None
        self.logged_in = False
        self.wait = None
        self.headless = headless

        try:
            self.initialize_driver(headless=self.headless)
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver in __init__: {e}")

    def initialize_driver(self, headless: bool = False):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

        logger.info("✅ WebDriver initialized")

    def login(self, username: str, password: str):
        try:
            logger.info(f"🔐 Logging in as {username}")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)

            self.driver.find_element(By.ID, "username").send_keys(username)
            self.driver.find_element(By.ID, "password").send_keys(password)
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()

            time.sleep(5)

            current_url = self.driver.current_url.lower()
            if "feed" in current_url or "mynetwork" in current_url or "/in/" in current_url:
                self.logged_in = True
                logger.info("✅ Login successful")
            else:
                logger.warning("⚠️ Login status unclear")
                self.logged_in = True  # Proceed anyway

        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            raise

    def search_candidates(self, job_title: str, country: str, max_results: int = 20, city: Optional[str] = "") -> List[Dict]:
        """
        Search for candidates and extract their profiles.
        Performs strict match filtering on both city and country.
        """
        if not self.logged_in:
            raise RuntimeError("You must login before searching.")

        logger.info(f"🔍 Searching: {job_title} in {city}, {country}")

        #search_url = f"https://www.linkedin.com/search/results/people/?keywords={job_title.replace(' ', '%20')}"

        search_keywords = f"{job_title} {city} {country}".strip()
        search_url = (
            "https://www.linkedin.com/search/results/people/"
            f"?keywords={search_keywords.replace(' ', '%20')}"
            "&origin=GLOBAL_SEARCH_HEADER"
        )
        logger.info(f"🔗 Search URL: {search_url}")

        self.driver.get(search_url)
        time.sleep(4)

        profiles = []
        seen_links = set()
        scroll_attempts = 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        logger.info("📜 Scrolling to collect profiles...")

        while len(profiles) < max_results * 1.5 and scroll_attempts < 8:
            elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/in/')]")

            for el in elements:
                try:
                    link = el.get_attribute("href")
                    if link and "/in/" in link and "/search/" not in link and link not in seen_links:
                        clean_link = link.split('?')[0]
                        seen_links.add(clean_link)
                        profiles.append({"link": clean_link})

                        if len(profiles) >= max_results * 1.5:
                            break
                except:
                    continue

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            last_height = new_height

        logger.info(f"✅ Found {len(profiles)} profile links")

        detailed_profiles = []
        members_skipped = 0

        for idx, p in enumerate(profiles[:max_results * 2], 1):
            if len(detailed_profiles) >= max_results:
                break

            logger.info(f"👤 [{idx}/{len(profiles)}] Processing: {p['link'].split('/in/')[-1][:40]}")

            profile_data = self.extract_profile_details(p["link"])

            if profile_data:
                if profile_data.get("Name", "").lower() == "linkedin member":
                    members_skipped += 1
                    logger.info(f"   🚫 Skipped: LinkedIn Member (private profile)")
                    continue

                # --- STRICT MATCH FILTERING ---  # <-- CHANGE
                profile_city = profile_data.get("City", "").strip().lower()
                profile_country = profile_data.get("Country", "").strip().lower()
                search_city = city.strip().lower() if city else ""
                search_country = country.strip().lower()

                if search_country and profile_country != search_country:
                    logger.info(f"   🚫 Skipped due to country mismatch: {profile_country} != {search_country}")
                    continue
                if search_city and profile_city != search_city:
                    logger.info(f"   🚫 Skipped due to city mismatch: {profile_city} != {search_city}")
                    continue

                detailed_profiles.append(profile_data)
                logger.info(f"   ✅ Extracted: {profile_data.get('Name', 'Unknown')}")
            else:
                logger.warning(f"   ⚠️ No data extracted")

            time.sleep(2)

        logger.info(f"🎉 Extraction complete:")
        logger.info(f"   ✅ Public profiles: {len(detailed_profiles)}")
        logger.info(f"   🚫 Members skipped: {members_skipped}")

        return detailed_profiles

    def extract_profile_details(self, profile_url: str) -> Optional[Dict]:
        try:
            self.driver.get(profile_url)
            time.sleep(3)

            self.driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(1)

            name = ""
            name_selectors = [
                (By.CSS_SELECTOR, "h1.text-heading-xlarge"),
                (By.CSS_SELECTOR, "h1.inline.t-24"),
                (By.XPATH, "//h1[contains(@class, 'text-heading')]"),
                (By.XPATH, "//h1"),
                (By.CSS_SELECTOR, ".pv-text-details__left-panel h1")
            ]

            for by, selector in name_selectors:
                try:
                    element = self.driver.find_element(by, selector)
                    name = element.text.strip()
                    if name and len(name) > 1:
                        break
                except:
                    continue

            if not name:
                logger.warning(f"   ⚠️ Could not extract name from {profile_url}")
                return None

            headline = ""
            headline_selectors = [
                (By.CSS_SELECTOR, "div.text-body-medium.break-words"),
                (By.XPATH, "//div[contains(@class, 'text-body-medium') and contains(@class, 'break-words')]"),
                (By.CSS_SELECTOR, ".pv-text-details__left-panel div.text-body-medium"),
                (By.XPATH, "//div[@class='text-body-medium']")
            ]

            for by, selector in headline_selectors:
                try:
                    element = self.driver.find_element(by, selector)
                    headline = element.text.strip()
                    if headline and len(headline) > 3:
                        break
                except:
                    continue

            location_text = ""
            location_selectors = [
                (By.CSS_SELECTOR, "span.text-body-small.inline.t-black--light.break-words"),
                (By.XPATH, "//span[contains(@class, 'text-body-small') and contains(@class, 'inline')]"),
                (By.CSS_SELECTOR, ".pv-text-details__left-panel span.text-body-small"),
                (By.XPATH, "//span[@class='text-body-small']")
            ]

            for by, selector in location_selectors:
                try:
                    element = self.driver.find_element(by, selector)
                    location_text = element.text.strip()
                    if location_text and len(location_text) > 1:
                        break
                except:
                    continue

            country, city = self.parse_location(location_text)

            # Extract current role
            current_role = headline

            try:
                self.driver.execute_script("window.scrollTo(0, 1200);")
                time.sleep(1)

                experience_selectors = [
                    (By.CSS_SELECTOR, "section#experience ul li:first-child"),
                    (By.XPATH, "//section[contains(@id, 'experience')]//ul//li[1]"),
                    (By.CSS_SELECTOR, "div#experience ul li:first-child"),
                    (By.XPATH, "//div[@id='experience']//ul//li[1]")
                ]

                for by, selector in experience_selectors:
                    try:
                        exp_element = self.driver.find_element(by, selector)
                        exp_text = exp_element.text.strip()
                        if exp_text:
                            lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
                            if lines:
                                current_role = lines[0]
                                break
                    except:
                        continue
            except:
                pass

            qualification = ""
            try:
                self.driver.execute_script("window.scrollTo(0, 1800);")
                time.sleep(1)

                education_selectors = [
                    (By.CSS_SELECTOR, "section#education ul li:first-child"),
                    (By.XPATH, "//section[contains(@id, 'education')]//ul//li[1]"),
                    (By.CSS_SELECTOR, "div#education ul li:first-child"),
                    (By.XPATH, "//div[@id='education']//ul//li[1]//span[@aria-hidden='true']")
                ]

                for by, selector in education_selectors:
                    try:
                        edu_element = self.driver.find_element(by, selector)
                        edu_text = edu_element.text.strip()
                        if edu_text:
                            lines = [l.strip() for l in edu_text.split('\n') if l.strip()]
                            qualification = ' - '.join(lines[:2]) if len(lines) >= 2 else lines[0]
                            break
                    except:
                        continue
            except:
                pass

            skills = []
            try:
                self.driver.execute_script("window.scrollTo(0, 2200);")
                time.sleep(1)

                try:
                    show_all_buttons = self.driver.find_elements(By.XPATH,
                        "//button[contains(text(), 'Show all') and contains(@aria-label, 'skill')]")
                    if show_all_buttons:
                        self.driver.execute_script("arguments[0].click();", show_all_buttons[0])
                        time.sleep(2)
                except:
                    pass

                skill_selectors = [
                    (By.XPATH, "//span[@class='mr1 t-bold']"),
                    (By.CSS_SELECTOR, "span.mr1.t-bold"),
                    (By.XPATH, "//section[contains(@id, 'skill')]//span[contains(@class, 't-bold')]"),
                    (By.CSS_SELECTOR, ".pv-skill-category-entity__name"),
                    (By.XPATH, "//div[@data-section='skill']//span")
                ]

                for by, selector in skill_selectors:
                    try:
                        skill_elements = self.driver.find_elements(by, selector)
                        for elem in skill_elements[:30]:
                            skill_text = elem.text.strip()
                            if skill_text and len(skill_text) < 50 and skill_text not in skills:
                                skills.append(skill_text)
                        if len(skills) > 5:
                            break
                    except:
                        continue
            except:
                pass

            if not skills:
                skills = self.extract_skills_from_page()

            result = {
                "Name": name,
                "Headline": headline,
                "Current Role": current_role,
                "City": city,            # <--- city extracted here
                "Country": country,      # <--- country extracted here
                "Qualification": qualification,
                "Skills": ", ".join(skills) if skills else "",
                "LinkedIn Link": profile_url
            }

            return result

        except Exception as e:
            logger.error(f"   ❌ Error extracting profile: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def extract_skills_from_page(self) -> List[str]:
        common_skills = [
            "Python", "Java", "JavaScript", "TypeScript", "React", "Angular",
            "Vue.js", "Node.js", "Django", "Flask", "Spring Boot", "AWS",
            "Azure", "GCP", "Docker", "Kubernetes", "SQL", "PostgreSQL",
            "MySQL", "MongoDB", "Redis", "Machine Learning", "Data Science",
            "AI", "DevOps", "CI/CD", "Agile", "Scrum", "Git", "REST API",
            "GraphQL", "Microservices", "C++", "C#", ".NET", "Ruby", "PHP",
            "Go", "Rust", "Swift", "Kotlin", "TensorFlow", "PyTorch"
        ]

        found_skills = []

        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            for skill in common_skills:
                if skill.lower() in page_text and skill not in found_skills:
                    found_skills.append(skill)
        except:
            pass

        return found_skills

    def parse_location(self, location_text: str) -> tuple:
        """
        Parses location string from LinkedIn profile.
        Returns (country, city) tuple.
        """
        if not location_text:
            return "", ""

        parts = [p.strip() for p in location_text.split(",")]

        if len(parts) >= 2:
            city = parts[0]
            country = parts[-1]
        elif len(parts) == 1:
            city = parts[0]
            country = ""
        else:
            city = ""
            country = ""

        return country, city

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ Browser closed")
            except:
                pass

    def __del__(self):
        self.close()
