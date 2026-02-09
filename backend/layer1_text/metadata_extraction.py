# EXTRACT METADATA FROM TRAINING PROGRAM BROCHURES
import re

meta = {
    "Program Title": None,
    "Program Title Confidence": "Low",
    "Program Date": None,
    "Program Date Confidence": "Low",
    "Program Venue": None,
    "Program Venue Confidence": "Low",
    "Organizer": None,
    "HRDC": None,
    "Flags": ""
}

MONTHS = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec"
)

TITLE_BLOCKLIST = [
    "limited to", "average rating", "hrd", "claimable",
    "programme", "program", "course overview",
    "learning outcomes", "upcoming", "event"
]

VENUE_BLOCKLIST = [
    "cancellation", "registration", "invoice",
    "method of payment", "delegate details"
]

HRDC_BLOCK = [
    "hrdc", "hrdf", "hrd corp", "human resource development corp",
    "claimable", "claim", "levy", "100% hrd", "100% hrd corp"
]

JOB_TITLE_BLOCK = [
    "executive", "manager", "director", "officer", "assistant",
    "coordinator", "specialist", "consultant", "administrator"
]

GENERIC_CORP_BLOCK = [
    "corp", "corporate", "company", "enterprise"
]

AUDIENCE_LABELS = {
    "corporate leaders",
    "who should attend",
    "target participants",
    "target audience",
    "entrepreneurs",
    "business owners",
    "public sector",
    "change agents",
    "executives",
    "managers"
}

def clean_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip()]

def looks_like_person(name: str) -> bool:
    name = name.strip()
    words = name.split()

    # length / word count guard
    if not (2 <= len(words) <= 4) or not (5 <= len(name) <= 35):
        return False

    # reject digits / symbols (kills "100%", "HRD Corp", etc.)
    if re.search(r"[\d%$@#/]", name):
        return False

    lower = name.lower()

    # reject common non-name words that appear in headings/topics
    TOPIC_BLOCK = {
        "risk","management","allocation","negotiation","strategy","planning",
        "chatgpt","ai","office","productivity","contract","leadership",
        "development","programme","program","course","session","module",
        "overview","outcomes","objectives","agenda","introduction"
    }
    if any(w in TOPIC_BLOCK for w in re.findall(r"[a-z]+", lower)):
        return False

    # reject role/label words
    ROLE_BLOCK = {"trainer","speaker","facilitator","profile","expert","management"}
    if any(w in lower for w in ROLE_BLOCK):
        return False

    # must look like proper-cased words (Name Surname), allow connectors like bin/binti
    allowed_connectors = {"bin","binti","a/l","a/p","van","von","de","da","di"}
    caps_ok = 0
    for w in words:
        wl = w.lower().strip(".,()")
        if wl in allowed_connectors:
            continue
        if not re.match(r"^[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\.?$", w.strip(",.")):
            return False
        caps_ok += 1

    return caps_ok >= 2

def looks_like_heading(s: str) -> bool:
    s = s.strip()

    # 1️⃣ Long uppercase or title-style headings
    if len(s.split()) >= 4:
        return True

    # 2️⃣ Label-style headings (e.g., "Trainer:")
    if ":" in s and len(s.split(":")[0].split()) >= 2:
        return True

    # 3️⃣ REGION / QUALIFIER + TRAINER (critical fix)
    # Examples:
    #   SINGAPORE TRAINER
    #   REGIONAL TRAINER
    #   LEAD TRAINER
    if re.match(r"^[A-Z]{2,}\s+TRAINER$", s):
        return True

    return False

def is_person_like(s):
    return bool(re.match(r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}$", s))

def is_label(s):
    return s.lower() in {
        "about", "venue", "date", "agenda", "registration",
        "invoice", "contact", "payment", "trainer", "speaker"
    }

def looks_like_org_generic(s):
    s = s.strip()

    if len(s) < 4 or len(s) > 80:
        return False

    if looks_like_sentence(s):
        return False

    if looks_like_copyright(s):
        return False

    if "@" in s or any(ch.isdigit() for ch in s):
        return False

    if is_person_like(s):
        return False

    return True

def looks_like_sentence(s):
    return (
        s.endswith(".")
        or s.count(" ") >= 6
        or re.search(r"\b(is|are|will|can|to|for|with|that)\b", s.lower())
    )

def looks_like_copyright(s):
    return bool(re.search(r"(©|copyright|all rights reserved)", s.lower()))

def looks_like_audience_label(s):
    return s.lower() in AUDIENCE_LABELS

# PROGRAM TITLE
def extract_program_title(text):
    lines = clean_lines(text)

    # High confidence: explicit label
    for i, line in enumerate(lines):
        if re.search(r"(course title|program title)", line, re.I):
            parts = re.split(r"[:\-]", line, 1)
            if len(parts) == 2 and len(parts[1].strip()) > 5:
                return parts[1].strip(), "High"
            for j in range(i + 1, i + 4):
                if j < len(lines) and len(lines[j]) > 5:
                    return lines[j], "High"

    # Medium confidence: poster-style stacked title
    for i in range(len(lines) - 1):
        if (
            re.match(r"^[A-Z][A-Za-z ]+$", lines[i])
            and re.match(r"^and [A-Za-z ]+$", lines[i + 1], re.I)
        ):
            return f"{lines[i]} {lines[i + 1]}", "Medium"

    return "Not detected", "Low"

# PROGRAM DATE
# PROGRAM DATE
def extract_program_date(text):
    normalized = re.sub(r"\s+", " ", text)
    lines = clean_lines(text)

    # Agenda-style date headers (e.g. Monday, 21ST July 2025)
    agenda_dates = re.findall(
        rf"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s*"
        rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}",
        normalized,
        re.I
    )

    if agenda_dates:
        # Normalize ordinals: 21ST → 21
        cleaned = [
            re.sub(r"(\d{{1,2}})(st|nd|rd|th)", r"\1", d, flags=re.I)
            for d in agenda_dates
        ]

        # Deduplicate while preserving order
        unique = list(dict.fromkeys(cleaned))

        if len(unique) == 1:
            return unique[0], "High"

        days = [
            re.search(r"(\d{1,2})", d).group(1)
            for d in unique
        ]

        m_my = re.search(
            rf"(?:{MONTHS})\s+\d{{4}}",
            unique[0],
            re.I
        )
        if not m_my:
            return unique[0], "High"

        month_year = m_my.group(0)
        return f"{days[0]}–{days[-1]} {month_year}", "High"

    # Full date range with year
    m = re.search(
        rf"\d{{1,2}}\s*[-–—-]\s*\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}",
        normalized,
        re.I
    )
    if m:
        return m.group(0), "High"

    # Single date with year
    m2 = re.search(
        rf"\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}",
        normalized,
        re.I
    )
    if m2:
        return m2.group(0), "Medium"

    return "Not detected", "Low"

# VENUE
def clean_venue_text(text):
    return re.sub(r"^venue\s*[:\-]\s*", "", text, flags=re.I).strip()

def extract_venue(text):
    lines = clean_lines(text)

    # High confidence: hotel / known venue
    for line in lines:
        if re.search(r"(ritz[- ]carlton|marriott|hotel)", line, re.I):
            return clean_venue_text(line), "High"

    # High confidence: explicit venue label
    for i, line in enumerate(lines):
        if line.lower() == "venue":
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j] != ":":
                    return clean_venue_text(lines[j]), "High"

    # Medium confidence: INSEAD fallback
    if "insead" in text.lower():
        return "INSEAD campus, Singapore / Malaysia", "Medium"

    return "Not detected", "Low"

# HRDC (TEXT ONLY)
def detect_hrdc(text):
    t = text.lower()
    patterns = [
        "hrdc",
        "hrdf",
        "hrd claimable",
        "hrdc claimable",
        "claimable under hrdc",
        "claimable under hrdf"
    ]
    return any(p in t for p in patterns)

# COST 
def extract_cost(text):
    """
    Layer 1 COST RULES (enterprise-safe)
    Priority:
    1) Explicit PROMO / EARLY BIRD fee
    2) Explicit NON-MEMBER fee
    3) Without accommodation fee
    4) Base per pax
    5) Lowest visible price (fallback)
    """

    t = re.sub(r"\s+", " ", text.lower())

    # PROMO / EARLY BIRD 
    promo = re.search(
        r"(promo fee|promotional fee|promo price|early bird).{0,60}"
        r"(rm|usd)\s?([\d,]+(?:\.\d{2})?)",
        t,
        re.I
    )
    if promo:
        return promo.group(3).replace(",", ""), promo.group(2).upper(), "High"

    # NON-MEMBER PRICE 
    non_member = re.search(
        r"(non[- ]member).{0,60}"
        r"(rm|usd)\s?([\d,]+(?:\.\d{2})?)",
        t,
        re.I
    )
    if non_member:
        return non_member.group(3).replace(",", ""), non_member.group(2).upper(), "High"

    # WITHOUT ACCOMMODATION
    wa = re.search(
        r"(rm|usd)\s?([\d,]+(?:\.\d{2})?).{0,60}"
        r"without (hotel )?accommodation",
        t,
        re.I
    )
    if wa:
        return wa.group(2).replace(",", ""), wa.group(1).upper(), "High"

    # PER PAX
    pax = re.search(
        r"(rm|usd)\s?([\d,]+(?:\.\d{2})?)\s*(per pax|per person)",
        t,
        re.I
    )
    if pax:
        return pax.group(2).replace(",", ""), pax.group(1).upper(), "Medium"

    # FALLBACK — LOWEST VISIBLE PRICE
    prices = re.findall(
        r"(rm|usd)\s?([\d,]+(?:\.\d{2})?)",
        t,
        re.I
    )

    parsed = []
    for cur, amt in prices:
        try:
            parsed.append((cur.upper(), float(amt.replace(",", ""))))
        except ValueError:
            pass

    if parsed:
        currency, amount = sorted(parsed, key=lambda x: x[1])[0]
        return str(amount), currency, "Low"

    return "N/A", "N/A", "Low"

# TRAINER 
def extract_trainer(text):
    lines = clean_lines(text)

    ROLE_LABELS = [
        r"lead trainer", r"course leader", r"courseleader", r"facilitator", 
        r"speaker", r"conducted by", r"presented by", r"trainer profile", r"\btrainer\b"
    ]

    # TRAINER PROFILE SECTION (strong signal)
    for i, line in enumerate(lines):
        if re.fullmatch(r"(trainer profile|trainer profiles)", line, re.I):
            candidates = []
            for j in range(i + 1, i + 8):
                if j >= len(lines):
                    break

                candidate = lines[j].strip()

                if looks_like_heading(candidate):
                    continue

                # Stop when bio text starts
                if re.search(r"\b(is|has|was)\b", candidate.lower()):
                    break

                if looks_like_person(candidate):
                    candidates.append(candidate)

                if len(candidates) == 2:
                    break

            if candidates:
                return "; ".join(candidates), "High"

    # ROLE-BASED FALLBACK
    for i, line in enumerate(lines):
        for role in ROLE_LABELS:
            if re.search(rf"\b{role}\b", line, re.I):

                # 🚫 Generic trainer must look like heading
                if role == r"\btrainer\b" and not looks_like_heading(line):
                    continue

                # Same-line case
                parts = re.split(r"[:\-–—]", line, 1)
                if len(parts) == 2 and looks_like_person(parts[1]):
                    return parts[1].strip(), "High"

                # Look-ahead case
                for offset in [1, 2]:
                    if i + offset < len(lines):
                        candidate = lines[i + offset].strip()
                        if looks_like_heading(candidate):
                            continue
                        if looks_like_person(candidate):
                            return candidate, "High"

    return "Not detected", "Low"

# ORGANISER 
def extract_organiser(text):
    lines = clean_lines(text)

    # Get program title to block false positives
    title, _ = extract_program_title(text)
    title_lower = title.lower() if title != "Not detected" else None

    # ABOUT section ownership
    for i, line in enumerate(lines):
        if line.lower().startswith("about"):
            for j in range(i + 1, i + 4):
                if j < len(lines):
                    candidate = lines[j].strip()
                    if title_lower and title_lower in candidate.lower():
                        continue

                    # ABOUT sections often have: "<ORG>, with the support of ..."
                    org_part = candidate.split(",", 1)[0].strip()

                    if title_lower and title_lower in org_part.lower():
                        continue

                    if looks_like_org_generic(org_part):
                        return org_part, "High"

    # Explicit ownership phrases
    for line in lines:
        if re.search(r"(organised by|organized by|hosted by|payable to)", line, re.I):
            candidate = line.split("by", 1)[-1].strip()
            if title_lower and title_lower in candidate.lower():
                continue

            if looks_like_org_generic(candidate):
                return candidate, "High"

    # Address ownership block
    for i, line in enumerate(lines):
        if re.search(r"(address|jalan|road|street|level|floor)", line.lower()):
            for k in range(i - 1, max(i - 4, -1), -1):
                candidate = lines[k]
                if title_lower and title_lower in candidate.lower():
                    continue

                if looks_like_org_generic(candidate) and not is_label(candidate):
                    return candidate, "Medium"

    # Repetition dominance
    freq = {}
    for line in lines:
        if title_lower and title_lower in line.lower():
            continue

        if looks_like_org_generic(line) and len(line.split()) <= 4:
            freq[line] = freq.get(line, 0) + 1

    if freq:
        top, count = max(freq.items(), key=lambda x: x[1])
        if count >= 3:
            return top, "Medium"

    # Safe failure
    return "Not detected", "Low"

# MASTER
def extract_metadata(text):
    title, title_conf = extract_program_title(text)
    date, date_conf = extract_program_date(text)
    venue, venue_conf = extract_venue(text)

    cost_amount, cost_currency, cost_conf = extract_cost(text)
    trainer, trainer_conf = extract_trainer(text)
    organiser, organiser_conf = extract_organiser(text)


    flags = []

    if title_conf == "Low":
        flags.append("TITLE_MISSING")
    if date_conf == "Low":
        flags.append("DATE_MISSING")
    if venue_conf == "Low":
        flags.append("VENUE_MISSING")
    if cost_conf == "Low":
        flags.append("COST_MISSING")
    if trainer_conf == "Low":
        flags.append("TRAINER_MISSING")
    if organiser_conf == "Low":
        flags.append("ORGANISER_MISSING")


    return {
        # CORE FIELDS
        "Program Title": title,
        "Program Title Confidence": title_conf,

        "Program Date": date,
        "Program Date Confidence": date_conf,

        "Venue": venue,
        "Venue Confidence": venue_conf,

        "Cost Amount": cost_amount,
        "Cost Currency": cost_currency,
        "Cost Confidence": cost_conf,

        "Trainer": trainer,
        "Trainer Confidence": trainer_conf,

        "Training Organiser": organiser,
        "Organiser Confidence": organiser_conf,

        "HRDC Certified": "Yes" if detect_hrdc(text) else "No",
        "Flags": "; ".join(flags) if flags else "OK"
    }

