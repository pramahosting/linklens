from pathlib import Path
from bs4 import BeautifulSoup
import re
import pandas as pd
import shutil
from datetime import datetime
from difflib import SequenceMatcher

# Folders
HTML_FOLDER = "data/temp"
PARSED_FOLDER = "data/temp/parsed"

BAD_SKILLS = {
    "follow", "message", "subscribe", "connect", "connections",
    "followers", "endorse", "unsw", "ibm", "accenture",
    "·", "2nd", "3rd", "1st"
}

COMMON_WORDS = {'and', 'or', 'the', 'a', 'an', 'in', 'at', 'of', 'for', 'to', 'with'}

# Patterns for junk experience entries
JUNK_EXPERIENCE_PATTERNS = [
    r'^\d+\s+(member|connection|follower)',
    r'^(now you know|you now know)',
    r'^(show all|see all|view)',
    r'^(follow|message|connect|more)',
    r'^\d+\s+(yr|mo|year|month)',
    r'^(full-time|part-time|contract|freelance)$',
    r'^\d+$',
    r'^[·•\-]+$',
]

def normalize_text(t):
    if not t:
        return ""
    t = t.strip().lower()
    t = re.sub(r"[^\w\s\-.#/+]", "", t)
    return t

def is_similar(a, b, threshold=0.82):
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold

def _clean_title_company_for_compare(s):
    if not s:
        return ""
    s = re.sub(r"·.*$", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^A-Za-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_valid_experience_entry(title, company, dates):
    if not title or not company or not dates:
        return False

    title_lower = title.lower().strip()
    company_lower = company.lower().strip()

    for pattern in JUNK_EXPERIENCE_PATTERNS:
        if re.search(pattern, title_lower, re.IGNORECASE):
            return False
        if re.search(pattern, company_lower, re.IGNORECASE):
            return False

    if len(title.strip()) < 3 or len(company.strip()) < 2:
        return False

    ui_junk = {
        'now you know', 'you now know', 'show all', 'see all', 'view more',
        'not found', 'follow', 'message', 'connect',
        'full-time', 'part-time', 'contract', 'freelance', 'remote', 'hybrid'
    }
    if title_lower in ui_junk or company_lower in ui_junk:
        return False

    if re.fullmatch(r'[\d\s\-·•,]+', title.strip()):
        return False
    if re.fullmatch(r'[\d\s\-·•,]+', company.strip()):
        return False

    if not re.search(r'[a-zA-Z]{2,}', title) or not re.search(r'[a-zA-Z]{2,}', company):
        return False

    return True

def find_skills(html):
    soup = BeautifulSoup(html, "html.parser")

    # Locate the "Skills" header
    skills_heading = None
    for h in soup.find_all(["h2", "h3", "span", "div"]):
        if h.get_text(strip=True).lower() == "skills":
            skills_heading = h
            break

    if not skills_heading:
        return []

    # Collect following elements until next section
    skills = []
    for elem in skills_heading.find_all_next(["span", "div", "li"]):
        txt = elem.get_text(strip=True).lower()
        if txt in {"interests", "education", "experience", "volunteering", "recommendations", "licenses & certifications", "test scores", "languages", "honors & awards"}:
            break

        # Skip non-leaf nodes
        if elem.find(True):
            continue
        if not txt:
            continue

        # Skip LinkedIn UI filler
        if any(x in txt for x in [
            "endorse", "logo", "followers", "person",
            "show all", "company", "connections",
        ]):
            continue

        # Skill length sanity
        if 1 <= len(txt.split()) <= 7:
            skills.append(elem.get_text(strip=True))

    # Deduplicate and remove the literal "Skills" word
    seen = set()
    clean_skills = []
    for s in skills:
        s_lower = s.lower()
        if s_lower == "skills":
            continue
        if s_lower not in seen:
            seen.add(s_lower)
            clean_skills.append(s)

    return clean_skills

def load_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]

    cleaned = []
    for ln in lines:
        if ln == "" and (not cleaned or cleaned[-1] == ""):
            continue
        cleaned.append(ln)

    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()

    return cleaned

def find_name(html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
        name = re.sub(r'·\s*(1st|2nd|3rd)', '', name).split("|")[0].strip()
        if name:
            candidates.append(("h1", name, 10))

    meta = soup.find("meta", {"property": "og:title"})
    if meta and meta.get("content"):
        nm = meta["content"].split("|")[0].strip()
        candidates.append(("og:title", nm, 9))

    title = soup.find("title")
    if title:
        nm = title.get_text(strip=True).split("|")[0].split("-")[0].strip()
        candidates.append(("title", nm, 8))

    if not candidates:
        return "Not found"

    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[0][1]

def find_url(html, fallback=None):
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", {"property": "og:url"})
    return meta.get("content").strip() if meta else fallback

def clean_line(line):
    return line.strip()

def get_visible_text(soup):
    """Return only visible text, ignoring hidden elements and iframes (like reCAPTCHA)."""
    # Remove unwanted tags first
    for tag in soup(["script", "style", "iframe", "noscript", "textarea"]):
        tag.decompose()

    texts = []
    for elem in soup.find_all(text=True):
        parent = elem.parent
        if parent and parent.has_attr("style"):
            style = parent["style"]
            if "display:none" in style or "visibility:hidden" in style:
                continue
        txt = elem.strip()
        if txt:
            texts.append(txt)
    return texts

def extract_experience_lines(html_file):
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    lines = get_visible_text(soup)

    try:
        start_idx = next(i for i, ln in enumerate(lines) if ln.lower() == "experience")
    except StopIteration:
        return []

    block = []
    seen = set()
    for ln in lines[start_idx + 1:]:
        ln_clean = clean_line(ln)

        if ln_clean.lower() in [
            "education", "skills", "languages", "licenses", "about",
            "recommendations", "interests", "volunteering"
        ]:
            break

        if "logo" in ln_clean.lower() or ln_clean.lower().startswith("experience"):
            continue

        if re.search(r'show all|see all', ln_clean, re.I):
            continue

        split_lines = re.split(r'(?<=[a-zA-Z])(?=[A-Z][a-z]+ · )', ln_clean)
        for sl in split_lines:
            sl_clean = sl.strip()
            if sl_clean and sl_clean not in seen:
                block.append(sl_clean)
                seen.add(sl_clean)

    return block

def detect_first_company_structure(block):
    date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present)'
    first_date_idx = None
    for i, ln in enumerate(block[:15]):
        if re.search(date_pattern, ln):
            first_date_idx = i
            break
    if not first_date_idx:
        return 'single'
    duration_summary_pattern = r'^(Full-time|Part-time|Freelance|Contract)\s*·\s*\d+\s*(yr|mo)s?'
    for i in range(first_date_idx):
        if re.match(duration_summary_pattern, block[i], re.I):
            return 'multiple'
    company_with_employment_pattern = r'.+\s*·\s*(Full-time|Part-time|Freelance|Contract)$'
    for i in range(min(3, first_date_idx)):
        if re.search(company_with_employment_pattern, block[i], re.I):
            return 'single'
    return 'single'

def extract_first_company_roles(block, structure):
    date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present)'
    roles = []
    seen_roles = set()
    first_company = None

    if structure == 'multiple':
        i = 0
        while i < len(block):
            line = block[i]

            if not first_company and len(line) > 5:
                if not re.search(date_pattern, line) and not re.search(r'(logo|experience)', line, re.I):
                    first_company = line
                    i += 1
                    if i < len(block) and re.match(r'^(Full-time|Part-time|Freelance|Contract)\s*·\s*\d+', block[i], re.I):
                        i += 1
                    continue

            if first_company and re.search(date_pattern, line):
                entry = {"title": None, "company": first_company, "dates": line, "location": None}

                for j in range(i - 1, max(i - 6, -1), -1):
                    l = block[j]
                    if len(l) < 3:
                        continue
                    if re.search(r'(full-time|part-time|logo)', l, re.I):
                        continue
                    if re.search(date_pattern, l):
                        continue
                    if l.startswith("-"):  # skip description lines
                        continue
                    entry["title"] = l
                    break

                # USE THE HELPER FUNCTION HERE
                entry["location"] = extract_location_from_block(block, i)

                if entry["title"]:
                    role_key = (entry["title"], entry["dates"], entry["location"])
                    if role_key not in seen_roles:
                        roles.append(entry)
                        seen_roles.add(role_key)
            i += 1
    else:
        first_title = None
        first_company = None
        for i, ln in enumerate(block):
            if re.search(date_pattern, ln):
                dates = ln
                # USE THE HELPER FUNCTION HERE TOO
                location = extract_location_from_block(block, i)
                if first_title and first_company:
                    roles.append({"title": first_title, "company": first_company, "dates": dates, "location": location})
                break
            if re.match(r'^(Full-time|Part-time|Freelance|Contract)', ln, re.I):
                continue
            if re.match(r'^(Remote|Hybrid|On-site)$', ln, re.I):
                continue
            if len(ln) < 3:
                continue
            if not first_title:
                first_title = ln
                continue
            if not first_company:
                first_company = re.sub(r'\s*·\s*(Full-time|Part-time|Freelance|Contract).*$', '', ln, flags=re.I).strip()
    return roles

def extract_location_from_block(block, date_index, max_lines=6):
    """
    Extract location for a role from a list of experience lines.
    Searches both before and after the date line.
    """
    # Location pattern - must have comma OR location type keyword
    location_pattern = re.compile(
        r'^(?P<city>[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s,]+)\s*(?:·\s*(Remote|Hybrid|On-site))?|'
        r'^(?P<city2>[A-Z][a-zA-Z\s]+)\s*·\s*(Remote|Hybrid|On-site)', re.I
    )

    # First, check lines BEFORE the date (common in LinkedIn's structure)
    for k in range(max(0, date_index - max_lines), date_index):
        line = block[k].strip()
        if not line or line.startswith("-"):
            continue
        # Skip employment type summary lines
        if re.match(r'^(Full-time|Part-time|Freelance|Contract)\s*·', line, re.I):
            continue
        # Skip if it's just a single word (likely company name)
        if ',' not in line and '·' not in line:
            continue
        match = location_pattern.match(line)
        if match:
            city = match.group("city") or match.group("city2")
            return city.strip() if city else None
    
    # Then check lines AFTER the date
    for k in range(date_index + 1, min(date_index + 1 + max_lines, len(block))):
        line = block[k].strip()
        if not line or line.startswith("-"):
            continue
        if ',' not in line and '·' not in line:
            continue
        match = location_pattern.match(line)
        if match:
            city = match.group("city") or match.group("city2")
            return city.strip() if city else None

    return None

def collapse_consecutive_same_titles(roles):
    collapsed = []
    last_title = None
    for role in roles:
        if role["title"] != last_title:
            collapsed.append(role)
            last_title = role["title"]
    return collapsed

def find_experience(html):
    """Extract structured experience dataset directly from HTML text."""
    soup = BeautifulSoup(html, "html.parser")
    lines = get_visible_text(soup)  # same helper as for skills/text extraction

    # Extract experience lines
    try:
        start_idx = next(i for i, ln in enumerate(lines) if ln.lower() == "experience")
    except StopIteration:
        return {"Company": "No roles found!", "Roles": []}

    block = []
    seen = set()
    for ln in lines[start_idx + 1:]:
        ln_clean = ln.strip()

        if ln_clean.lower() in [
            "education", "skills", "languages", "licenses", "about",
            "recommendations", "interests", "volunteering"
        ]:
            break

        if "logo" in ln_clean.lower() or ln_clean.lower().startswith("experience"):
            continue

        if re.search(r'show all|see all', ln_clean, re.I):
            continue

        # Split combined entries like "Title · Company"
        split_lines = re.split(r'(?<=[a-zA-Z])(?=[A-Z][a-z]+ · )', ln_clean)
        for sl in split_lines:
            sl_clean = sl.strip()
            if sl_clean and sl_clean not in seen:
                block.append(sl_clean)
                seen.add(sl_clean)

    # Detect structure and parse roles
    structure = detect_first_company_structure(block)
    first_company_roles = extract_first_company_roles(block, structure)
    first_company_roles = collapse_consecutive_same_titles(first_company_roles)

    # Format dataset for presentation
    dataset = {}
    if first_company_roles:
        MAX_ROLES = 3
        dataset["Company"] = first_company_roles[0]['company']

        dataset["Roles"] = []
        for role in first_company_roles[:MAX_ROLES]:
            dataset["Roles"].append({
                "Title": role['title'],
                "Dates": role['dates'],
                "Location": role['location']
            })
    else:
        dataset["Company"] = "No roles found!"
        dataset["Roles"] = []

    return dataset

def format_experience_bullets(experience):
    if not isinstance(experience, dict) or not experience.get("Roles"):
        return "• No experience found"

    bullets = []
    company = experience.get("Company", "Unknown Company")

    bullets.append(f"• {company}")

    for role in experience["Roles"]:
        title = role.get("Title", "Unknown Title")
        dates = role.get("Dates", "Dates not found")
        location = role.get("Location")

        line = f"  ◦ {title} ({dates})"
        if location:
            line += f" — {location}"

        bullets.append(line)

    return "\n".join(bullets)

def get_company_from_experience(experience):
    if not isinstance(experience, dict):
        return "Not found"
    return experience.get("Company", "Not found")

def get_title_from_experience(experience):
    if not isinstance(experience, dict):
        return "Not found"

    roles = experience.get("Roles", [])
    if not roles:
        return "Not found"

    return roles[0].get("Title", "Not found")

def get_first_role_title(experience):
    roles = experience.get("Roles", [])
    if not roles:
        return None
    return roles[0].get("Title")

def get_location_from_experience(experience):
    if not isinstance(experience, dict):
        return "Not found"

    roles = experience.get("Roles", [])
    for role in roles:
        loc = role.get("Location")
        if loc:
            return loc

    return "Not found"

def extract_location_from_headline(html):
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "span.pv-text-details__left-panel div.inline-flex span",
        "span.text-body-small.inline.t-black--light.break-words",
        "span.text-body-small",
        "div.pv-top-card--list-bullet > li",
        "li.t-black.t-normal.inline-block",
    ]
    candidate_texts = []
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            if text:
                candidate_texts.append(text)

    if not candidate_texts:
        top = soup.find("div", {"class": "pv-top-card"})
        candidate_texts = list(top.stripped_strings) if top else list(soup.stripped_strings)

    clean = []
    for t in candidate_texts:
        if re.search(r'\b(follower|connection|connect|contact|email|1st|2nd|3rd)\b', t, re.I):
            continue
        if re.search(r'\b(Engineer|Developer|Manager|Founder|Consultant|CEO|CTO)\b', t):
            continue
        if " at " in t.lower():
            continue
        if re.fullmatch(r"[0-9,]+", t):
            continue
        if len(t) <= 2:
            continue
        clean.append(t)

    location_regex = re.compile(r"^[A-Z][A-Za-z\.\s'-]+(,\s*[A-Z][A-Za-z\.\s'-]+)+$")
    for t in clean:
        if location_regex.match(t):
            return t.strip()

    for t in clean:
        m = re.search(r"\bGreater\s+[A-Z][A-Za-z\s]+Area\b", t)
        if m:
            return m.group(0)

    for t in clean:
        if re.fullmatch(r"[A-Z][A-Za-z\s]+", t) and len(t.split()) <= 3:
            if not re.search(r"(Manager|Engineer|Developer|Officer|Consultant)", t):
                return t

    for t in clean:
        if re.search(r"\b(Remote|Hybrid)\b", t, re.I):
            return t.strip()

    return None

# List of patterns that indicate a recruitment / staffing profile
recruitment_agencies = [
    r'\brecruit', r'\bstaffing\b', r'\btalent acquisition\b',
    r'\bhuman resources\b', r'\bexec level hiring\b'
]

# Keywords that indicate a technical/engineering role
tech_keywords = ['engineer', 'developer', 'architect', 'analyst', 'data', 'software', 'ai', 'ml']

def is_recruiter_profile(title, company):
    """
    Returns True if the profile is likely a recruiter, False otherwise.
    Only checks title and company.
    """
    # Combine title and company for pattern matching
    combined = f"{title} {company}"

    for pattern in recruitment_agencies:
        if re.search(pattern, combined, re.I):
            # If the title contains clear technical keywords, allow it through
            if any(kw in title.lower() for kw in tech_keywords):
                return False
            # Otherwise, treat as recruiter
            return True
    return False


def normalize_role_word(word):
    """
    Normalize common job-title morphology:
    scientist <-> science
    engineer <-> engineering
    analyst <-> analytics
    manager <-> management
    """
    w = word.lower()

    rules = [
        (r'(ists?|ism)$', ''),        # scientist → scient
        (r'(ing)$', ''),              # engineering → engineer
        (r'(ics)$', 'ic'),             # analytics → analytic
        (r'(ers?)$', ''),              # engineers → engineer
        (r'(ors?)$', ''),              # advisors → advisor
        (r'(ments?)$', ''),            # management → manage
        (r'(ives?)$', 'ive'),          # executive → executive
        (r'(ians?)$', 'ian'),          # statistician
    ]

    for pattern, repl in rules:
        w = re.sub(pattern, repl, w)

    return w

def extract_normalized_role_words(text):
    words = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
    words -= COMMON_WORDS
    return {normalize_role_word(w) for w in words}

def fuzzy_match(query, target, threshold=0.6):
    """
    Generic fuzzy match based on normalized word overlap.
    """
    if not query or not target:
        return False

    # Extract normalized words
    query_words = extract_normalized_role_words(query)
    target_words = extract_normalized_role_words(target)

    if not query_words or not target_words:
        return False

    # Compute overlap ratio
    overlap = len(query_words & target_words)
    ratio = overlap / len(query_words)

    return ratio >= threshold

def parse_html(html, file_name):
    lines = load_text_from_html(html)
    Experience = find_experience(html)
    Name = find_name(html)
    Company = get_company_from_experience(Experience)
    Title = get_title_from_experience(Experience)
    Location = get_location_from_experience(Experience)

    # --- Skills ---
    Skills = find_skills(html)

    stem = Path(file_name).stem.strip()
    stem = re.sub(r'_\d{10}$', '', stem)
    constructed_url = f"https://www.linkedin.com/in/{stem}/"
    url = find_url(html, constructed_url)

    return {
        "Name": Name,
        "Title": Title,
        "Company": Company,
        "Location": Location,
        "Skills": "\n".join(f"• {s}" for s in Skills) if Skills else "Not found",
        "Experience": format_experience_bullets(Experience),
        "Source_URL": url
    }


def parse_all_html(move_files=True, role="", loc=""):
    results = []
    html_files = list(Path(HTML_FOLDER).glob("*.html"))

    parsed_path = Path(PARSED_FOLDER)
    if move_files:
        parsed_path.mkdir(parents=True, exist_ok=True)

    for file in html_files:
        try:
            html = file.read_text(encoding="utf-8")
            parsed = parse_html(html, file)

            # Skip recruiters
            if is_recruiter_profile(parsed["Title"], parsed["Company"]):
                continue

            # Title match
            first_role_title = get_first_role_title(find_experience(html))
            title_match = fuzzy_match(role, first_role_title) if role else True

            # Location match with fallback to headline if experience location fails
            loc_match = False
            if loc:
                experience_loc = parsed["Location"]
                if fuzzy_match(loc, experience_loc):
                    loc_match = True
                else:
                    headline_loc = extract_location_from_headline(html)
                    if headline_loc and fuzzy_match(loc, headline_loc):
                        loc_match = True
                        parsed["Location"] = headline_loc  # optionally overwrite with headline

            # Ensure profile has skills and experience
            has_skills = parsed["Skills"] != "Not found"
            has_experience = parsed["Experience"] != "Not found"

            parsed['Accepted'] = bool(title_match and loc_match and has_skills and has_experience)

            if not parsed['Accepted']:
                reasons = []
                if not title_match:
                    reasons.append(f"Title mismatch: expected '{role}', got '{parsed['Title']}'")
                if not loc_match:
                    reasons.append(f"Location mismatch: expected '{loc}', got '{parsed['Location']}'")
                if not has_skills:
                    reasons.append("Missing skills")
                if not has_experience:
                    reasons.append("Missing experience")
                print(f"⚠️ Rejected: {parsed['Name']} - {', '.join(reasons)}")
                continue

            results.append(parsed)

            if move_files:
                dest_file = parsed_path / file.name
                shutil.move(str(file), str(dest_file))
                #print(f"Moved parsed file to: {dest_file}")

        except Exception as e:
            print(f"❌ Error parsing {file.name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if not results:
        print("❌ No accepted profiles found")
        return pd.DataFrame()

    desired_order = ["Name", "Title", "Company", "Location", "Skills", "Experience", "Source_URL"]

    df = pd.DataFrame(results)
    df = df.reindex(columns=desired_order)
    df.insert(0, "#", range(1, len(df) + 1))

    print(f"✅ Parsed {len(html_files)} profiles, {len(results)} accepted")
    return df

