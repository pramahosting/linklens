import os
import json
import requests
import re
from bs4 import BeautifulSoup

# --------------------------------------------------
# Cookie loader (reusable)
# --------------------------------------------------
def load_cookies(session_dir):
    cookies = {}

    for root, _, files in os.walk(session_dir):
        for file in files:
            if not file.endswith(".json"):
                continue

            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            if isinstance(data, dict) and "cookies" in data:
                cookie_list = data["cookies"]
            elif isinstance(data, list):
                cookie_list = data
            else:
                continue

            for c in cookie_list:
                if "linkedin.com" in c.get("domain", ""):
                    cookies[c["name"]] = c["value"]

    if not cookies.get("li_at"):
        raise Exception("li_at cookie missing")

    return cookies


# --------------------------------------------------
# Public API function (THIS is what app.py will call)
# --------------------------------------------------
def get_contact_info_for_profile(vanity_id, cookies):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
        "Referer": f"https://www.linkedin.com/in/{vanity_id}/",
    }

    overlay_url = f"https://www.linkedin.com/in/{vanity_id}/overlay/contact-info/"
    r = requests.get(overlay_url, headers=headers, cookies=cookies, timeout=30)

    if r.status_code != 200:
        return {"emails": [], "phones": []}

    return _parse_contact_from_html(r.text)


# --------------------------------------------------
# Internal parser
# --------------------------------------------------
def _parse_contact_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    result = {"emails": [], "phones": []}

    # -------- EMAILS --------
    email_regex = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
    emails = set(re.findall(email_regex, text, re.I))

    exclude = ("linkedin.com", "noreply", "donotreply", "example.com")
    valid_emails = [
        e for e in emails
        if not any(x in e.lower() for x in exclude)
    ]

    result["emails"] = sorted(valid_emails)

    # -------- PHONES (10-digit only) --------
    phone_candidates = re.findall(r'[\+\(]?\d[\d\-\s\(\)]{8,}\d', text)

    phones = []
    for p in phone_candidates:
        clean = re.sub(r"\D", "", p)
        if len(clean) == 10 and clean not in phones:
            phones.append(clean)

    result["phones"] = phones

    return result
