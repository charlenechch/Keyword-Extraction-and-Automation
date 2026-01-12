# nlp_fallback.py  (Layer 2: Layout-aware inference)
import re
import pytesseract
from PIL import Image
import fitz
import io

# CONSTANTS
DATE_REGEX = r"""
(
    \d{1,2}
    (st|nd|rd|th)?
    \s*(to|–|-)\s*
    \d{1,2}
    (st|nd|rd|th)?
    \s*(Jan|Feb|Mar|April|May|June|July|Aug|Sep|Oct|Nov|Dec)
    [a-z]*\s*\d{4}
)
|
(
    \d{1,2}
    (st|nd|rd|th)?
    \s*(Jan|Feb|Mar|April|May|June|July|Aug|Sep|Oct|Nov|Dec)
    [a-z]*\s*\d{4}
)
"""

VENUE_KEYWORDS = [
    "hall", "hotel", "centre", "center",
    "campus", "auditorium"
]

TITLE_SIGNAL_WORDS = [
    "training", "workshop", "programme", "program",
    "course", "leadership", "management", "digital",
    "advanced", "introduction", "fundamentals",
    "resilience", "sustainability"
]

LABEL_WORDS = ["title", "date", "venue"]

COST_SIGNAL_WORDS = [
    "promo", "promotion", "special", "early bird",
    "fees", "fee", "price", "cost"
]

CURRENCY_REGEX = r"(rm|usd)\s?([\d,]+(?:\.\d{2})?)"

OCR_BLOCKLIST = {
    "CORPORATE LEADERS",
    "WHO SHOULD ATTEND",
    "PROGRAM OVERVIEW",
    "TRAINING OBJECTIVES",
    "ABOUT THE PROGRAM",
    "AGENDA",
    "REGISTRATION"
}

ORGANISER_HINT_WORDS = [
    "organised by",
    "organized by",
    "conducted by",
    "delivered by",
    "hosted by"
]

DOMAIN_ORGANISER_MAP = {
    "sarawakskills.edu.my": "Sarawak Skills",
    "insead.edu": "INSEAD Executive Education",
    "mindzallera.com": "Mindzallera",
}

# HELPER FUNCTIONS
def normalize_blocks(blocks):
    """
    Normalize layout blocks into dict format:
    {
        "bbox": (x0, y0, x1, y1),
        "text": str,
        "size": float
    }

    Supports multiple input block shapes safely.
    """
    normalized = []

    for b in blocks:

        # Case 1: already normalized (dict)
        if isinstance(b, dict):
            if "text" in b and "bbox" in b:
                normalized.append({
                    "text": str(b["text"]),
                    "bbox": tuple(b.get("bbox", (0, 0, 0, 0))),
                    "size": float(b.get("size", 12))
                })
            continue

        # Case 2: list/tuple
        if isinstance(b, (list, tuple)):

            # [x0, y0, x1, y1, text, size]
            if len(b) == 6:
                x0, y0, x1, y1, text, size = b

            # [x0, y0, x1, y1, text]
            elif len(b) == 5:
                x0, y0, x1, y1, text = b
                size = 12

            # [text, size, bbox]
            elif len(b) == 3 and isinstance(b[2], (list, tuple)):
                text, size, bbox = b
                x0, y0, x1, y1 = bbox

            # [text, bbox]
            elif len(b) == 2 and isinstance(b[1], (list, tuple)):
                text, bbox = b
                x0, y0, x1, y1 = bbox
                size = 12

            else:
                # Unknown format → skip safely
                continue

            normalized.append({
                "text": str(text),
                "bbox": (float(x0), float(y0), float(x1), float(y1)),
                "size": float(size)
            })

    return normalized

def has_title_signal(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in TITLE_SIGNAL_WORDS)

def looks_like_brand_header(text: str) -> bool:
    words = text.split()
    return text.isupper() and len(words) <= 4

def is_label(text: str) -> bool:
    return text.lower().strip() in LABEL_WORDS

def is_non_title_line(text: str) -> bool:
    text_upper = text.upper()
    blacklist = [
        "ABOUT", "OVERVIEW", "OBJECTIVES", "WHO SHOULD ATTEND",
        "REGISTRATION", "FORM", "CONTACT", "EMAIL", "PHONE",
        "SDN BHD", "FEES", "PACKAGE", "PARTICIPANT"
    ]
    return any(word in text_upper for word in blacklist)

def looks_incomplete(title: str) -> bool:
    triggers = [":", "FOR", "ON", "AND"]
    return any(title.strip().endswith(t) for t in triggers)

def is_training_program(title: str) -> bool:
    if not title:
        return False
    t = title.lower()

    # conference indicators → NOT training
    if any(w in t for w in [
        "conference", "summit", "forum",
        "congress", "symposium", "expo"
    ]):
        return False

    # training indicators
    return any(w in t for w in [
        "training", "workshop", "course",
        "programme", "program", "masterclass"
    ])

def has_trainer_section(blocks):
    for b in blocks:
        t = b["text"].upper()
        if "TRAINER PROFILE" in t or "FACULTY PROFILE" in t:
            return True
    return False

def clean_org_name(text):
    text = text.strip()
    text = re.sub(r"©.*", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text

# OCR 
def get_page_image(pdf_path, page_number=0, dpi=200):
    doc = fitz.open(pdf_path)
    page = doc[page_number]

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)

    img_bytes = pix.tobytes("png")
    doc.close()

    img = Image.open(io.BytesIO(img_bytes))
    return img.convert("RGBA")

def ocr_image_region(image):
    return pytesseract.image_to_string(image, config="--psm 6")

def ocr_header_footer(page_image):
    w, h = page_image.size

    header = page_image.crop((0, 0, w, int(h * 0.25)))
    footer = page_image.crop((0, int(h * 0.8), w, h))

    texts = []
    texts.append(ocr_image_region(header))
    texts.append(ocr_image_region(footer))

    return "\n".join(texts)

def ocr_text_to_blocks(text):
    blocks = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        blocks.append({
            "text": line,
            "size": 12,        # fake but consistent
            "bbox": (0, 0, 0, 0)
        })
    return blocks

def ocr_full_page(page_image):
    return pytesseract.image_to_string(page_image, config="--psm 6")

# LABEL → VALUE INFERENCE
def find_value_near_label(blocks, label_block):
    lx0, ly0, lx1, ly1 = label_block["bbox"]

    candidates = []

    for b in blocks:
        bx0, by0, bx1, by1 = b["bbox"]

        # RIGHT of label
        if bx0 > lx1 and abs(by0 - ly0) < 40:
            candidates.append((bx0 - lx1, b["text"]))

        # BELOW label
        elif by0 > ly1 and abs(bx0 - lx0) < 40:
            candidates.append((by0 - ly1, b["text"]))

    return min(candidates)[1] if candidates else None

# TITLE INFERENCE (POSTER STYLE)
def infer_program_title(blocks):
    if not blocks:
        return None

    valid_blocks = [b for b in blocks if len(b["text"].strip()) > 5]
    if not valid_blocks:
        return None

    max_font = max(b["size"] for b in valid_blocks)

    best_score = -1
    best_title = None

    for i, b in enumerate(blocks):
        text = b["text"].strip()

        if b["size"] < (max_font * 0.8):
            continue
        if is_non_title_line(text):
            continue

        y0 = b["bbox"][1]
        position_weight = 1.0 if y0 < 350 else 0.2

        merged_lines = [text]
        curr_y = b["bbox"][3]

        for j in range(i + 1, len(blocks)):
            nxt = blocks[j]
            if abs(nxt["bbox"][1] - curr_y) > 15:
                break
            if abs(nxt["size"] - b["size"]) > 1.0:
                break
            if is_non_title_line(nxt["text"]):
                break
            merged_lines.append(nxt["text"].strip())
            curr_y = nxt["bbox"][3]

        merged_text = " ".join(merged_lines)

        length_score = len(merged_text) * 2
        font_score = b["size"] * 1.5
        position_score = 1000 / (y0 + 1)

        uppercase_penalty = 200 if looks_like_brand_header(text) else 0
        no_signal_penalty = 150 if not has_title_signal(merged_text) else 0

        score = (
            length_score
            + font_score
            + position_weight * position_score
            - uppercase_penalty
            - no_signal_penalty
        )

        if score > best_score:
            best_score = score
            best_title = merged_text

    return best_title

# DATE INFERENCE
def infer_program_date(blocks):
    candidates = []

    for i, b in enumerate(blocks):
        if re.search(DATE_REGEX, b["text"], re.I):
            date_text = b["text"].strip()

            if i + 1 < len(blocks):
                nxt = blocks[i + 1]
                if abs(nxt["bbox"][1] - b["bbox"][3]) < 20:
                    if re.search(r"(\d{4}|to|-)", nxt["text"]):
                        date_text += " " + nxt["text"].strip()

            score = 1000 - b["bbox"][1]
            candidates.append((score, date_text))

    return max(candidates)[1] if candidates else None

# VENUE INFERENCE
def infer_program_venue(blocks):
    candidates = []

    for b in blocks:
        text = b["text"].lower()
        if any(k in text for k in VENUE_KEYWORDS):
            score = 1000 - b["bbox"][1]
            candidates.append((score, b["text"]))

    return max(candidates)[1] if candidates else None

# COST INFERENCE (LAYOUT)
def infer_cost_from_layout(blocks):
    candidates = []

    for b in blocks:
        text = b["text"].lower()

        if not re.search(CURRENCY_REGEX, text, re.I):
            continue

        # Extract currency + amount
        m = re.search(CURRENCY_REGEX, text, re.I)
        if not m:
            continue

        currency = m.group(1).upper()
        amount = m.group(2).replace(",", "")

        # ---------- SCORING ----------
        score = 0

        # Visual importance
        score += b["size"] * 2
        score += max(0, 1000 - b["bbox"][1])  # higher = better

        # Promo / emphasis
        if any(w in text for w in COST_SIGNAL_WORDS):
            score += 800

        # Penalise "normal price" / crossed-out prices
        if "normal" in text or "was" in text:
            score -= 400

        candidates.append((score, amount, currency))

    if not candidates:
        return None

    # Best visual candidate
    best = max(candidates, key=lambda x: x[0])
    return {
        "amount": best[1],
        "currency": best[2],
        "confidence": "Medium"
    }

# TRAINER INFERENCE
def extract_trainers_from_profile(blocks):
    trainers = []

    for b in blocks:
        text = b["text"].strip()

        # Likely name: Title Case, short, no digits
        if (
            len(text.split()) <= 4
            and text.istitle()
            and not re.search(r"\d", text)
        ):
            trainers.append(text)

    if not trainers:
        return None

    # De-duplicate
    return list(dict.fromkeys(trainers))

# ORGANISER INFERENCE
def infer_organiser_from_ocr(blocks):
    candidates = []

    for idx, b in enumerate(blocks):
        text = b["text"].strip()

        if (
            text.isupper()
            and len(text.split()) <= 5
            and text not in OCR_BLOCKLIST
            and "@" not in text
            and not re.search(r"\d", text)
        ):
            # earlier lines = header = more likely organiser
            score = 1000 - idx * 10
            candidates.append((score, text))

    if not candidates:
        return None

    return max(candidates, key=lambda x: x[0])[1]

def infer_organiser_from_domain(text):
    for domain, org in DOMAIN_ORGANISER_MAP.items():
        if domain in text.lower():
            return org
    return None

# MAIN ENTRY — LAYER 2
def layout_fallback(meta, layout_pages, pdf_path):
    """
    Layer 2: Layout + OCR fallback
    layout_pages: List[List[raw_block]]
    raw_block format: [x0, y0, x1, y1, text, size]
    """

    if not layout_pages:
        return meta

    if not isinstance(meta.get("Flags"), str):
        meta["Flags"] = ""

    # ==============================
    # NORMALIZE ALL PAGES FIRST
    # ==============================
    normalized_pages = [
        normalize_blocks(page) for page in layout_pages
    ]

    # Use first page for label-based inference
    page0 = normalized_pages[0]

    # ==============================
    # LABEL → VALUE (TABLE STYLE)
    # ==============================
    for b in page0:
        label = b["text"].strip().lower()

        if label == "title" and meta.get("Program Title Confidence") != "High":
            value = find_value_near_label(page0, b)
            if value:
                meta["Program Title"] = value.strip()
                meta["Program Title Confidence"] = "Medium"
                meta["Flags"] += ";LAYOUT_TITLE_LABEL"

        elif label == "date" and meta.get("Program Date Confidence") != "High":
            value = find_value_near_label(page0, b)
            if value:
                meta["Program Date"] = value.strip()
                meta["Program Date Confidence"] = "Medium"
                meta["Flags"] += ";LAYOUT_DATE_LABEL"

        elif label == "venue" and meta.get("Venue Confidence") != "High":
            value = find_value_near_label(page0, b)
            if value:
                meta["Venue"] = value.strip()
                meta["Venue Confidence"] = "Medium"
                meta["Flags"] += ";LAYOUT_VENUE_LABEL"

        elif label in {"cost", "fee", "fees", "price"} and meta.get("Cost Confidence") != "High":
            value = find_value_near_label(page0, b)
            if value:
                m = re.search(r"(rm|usd)\s?([\d,]+(?:\.\d{2})?)", value, re.I)
                if m:
                    meta["Cost Amount"] = m.group(2).replace(",", "")
                    meta["Cost Currency"] = m.group(1).upper()
                    meta["Cost Confidence"] = "Medium"
                    meta["Flags"] += ";LAYOUT_COST_LABEL"

    # ==============================
    # POSTER-STYLE FALLBACKS
    # ==============================
    if meta.get("Program Title Confidence") == "Low":
        title = infer_program_title(page0)
        if title:
            meta["Program Title"] = title.strip()
            meta["Program Title Confidence"] = "Medium"
            meta["Flags"] += ";LAYOUT_TITLE"

    if meta.get("Program Date Confidence") == "Low":
        date = infer_program_date(page0)
        if date:
            meta["Program Date"] = date.strip()
            meta["Program Date Confidence"] = "Medium"
            meta["Flags"] += ";LAYOUT_DATE"

    if meta.get("Venue Confidence") == "Low":
        venue = infer_program_venue(page0)
        if venue:
            meta["Venue"] = venue.strip()
            meta["Venue Confidence"] = "Medium"
            meta["Flags"] += ";LAYOUT_VENUE"

    if meta.get("Cost Confidence") == "Low":
        cost = infer_cost_from_layout(page0)
        if cost:
            meta["Cost Amount"] = cost["amount"]
            meta["Cost Currency"] = cost["currency"]
            meta["Cost Confidence"] = cost["confidence"]
            meta["Flags"] += ";LAYOUT_COST"

    # ==============================
    # TRAINER (STRICT, SAFE)
    # ==============================
    if meta.get("Trainer Confidence") == "Low":
        title = meta.get("Program Title", "")

        if is_training_program(title):
            detected_trainers = []

            for page_idx, page_blocks in enumerate(normalized_pages):

                # 1️⃣ Layout-based profile detection
                if has_trainer_section(page_blocks):
                    trainers = extract_trainers_from_profile(page_blocks)
                    if trainers:
                        detected_trainers.extend(trainers)
                        break

                # 2️⃣ OCR-based profile detection (INSEAD)
                page_image = get_page_image(pdf_path, page_number=page_idx)
                ocr_text = ocr_full_page(page_image)

                if (
                    "TRAINER PROFILE" in ocr_text.upper()
                    or "FACULTY PROFILE" in ocr_text.upper()
                ):
                    ocr_blocks = ocr_text_to_blocks(ocr_text)
                    trainers = extract_trainers_from_profile(ocr_blocks)
                    if trainers:
                        detected_trainers.extend(trainers)
                        break

            if detected_trainers:
                meta["Trainer"] = ", ".join(dict.fromkeys(detected_trainers))
                meta["Trainer Confidence"] = "Medium"
                meta["Flags"] += ";LAYOUT_OCR_TRAINER_PROFILE"

    # ==============================
    # ORGANISER (L2 FIX-UP)
    # ==============================
    org_conf = meta.get("Organiser Confidence", "Low")
    current_org = (meta.get("Training Organiser") or "").strip()

    def is_junk_organiser(s: str) -> bool:
        u = s.upper().strip()
        l = s.lower().strip()

        if not s or s == "Not detected":
            return True

        # URL / domain-like
        if any(tok in l for tok in ["www.", "http://", "https://", ".com", ".org", ".edu", ".edu.my", ".my"]):
            return True

        # Known bad headers / audience labels
        if u in OCR_BLOCKLIST:
            return True

        return False

    # Run L2 organiser if:
    # - not already High AND
    # - organiser is junk (URL / header / missing)
    if org_conf != "High" and is_junk_organiser(current_org):

        organiser = None

        # ---- 0️⃣ Domain mapping from existing value (NO OCR needed) ----
        organiser = infer_organiser_from_domain(current_org)

        # ---- 1️⃣ Text blocks explicit "organised by ..." ----
        if not organiser:
            for page_blocks in normalized_pages:
                for b in page_blocks:
                    t = b["text"].lower()
                    for hint in ORGANISER_HINT_WORDS:
                        if hint in t:
                            candidate = b["text"].split(hint, 1)[-1]
                            organiser = clean_org_name(candidate)
                            break
                    if organiser:
                        break
                if organiser:
                    break

        # ---- 2️⃣ OCR header/footer of page 1 ----
        if not organiser:
            page_image0 = get_page_image(pdf_path, page_number=0)
            ocr_text = ocr_header_footer(page_image0)

            organiser = infer_organiser_from_domain(ocr_text)

            if not organiser:
                ocr_blocks = ocr_text_to_blocks(ocr_text)
                organiser = infer_organiser_from_ocr(ocr_blocks)

        # ---- 3️⃣ Venue-based fallback (still Medium) ----
        if not organiser:
            venue = (meta.get("Venue") or "").lower()
            if "insead" in venue:
                organiser = "INSEAD Executive Education"
            elif "sarawak skills" in venue:
                organiser = "Sarawak Skills"

        if organiser:
            meta["Training Organiser"] = organiser
            meta["Organiser Confidence"] = "Medium"
            meta["Flags"] += ";L2_ORGANISER_FIXUP"



    return meta
