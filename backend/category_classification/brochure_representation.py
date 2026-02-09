from typing import Dict
import re


def _clean(s: str) -> str:
    s = (s or "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def build_weighted_brochure_text(meta: Dict, brochure_text: str = "") -> str:
    parts = []

    # Extracting core metadata fields
    title = meta.get("Program Title", "")
    desc = meta.get("Program Description", "") or meta.get("Description", "")
    agenda = meta.get("Agenda", "") or meta.get("Course Outline", "")
    outcomes = meta.get("Learning Outcomes", "") or meta.get("Objectives", "")

    # Boost the "Signal" naturally by repeating the text
    # This ensures the search engine values the Title 3x more than random body text
    if title:
        # CHANGE: Increased boost from 3x to 10x
        boosted_title = " ".join([title] * 10)
        parts.append(f"TITLE: {boosted_title}")
    
    if agenda:
        # The Agenda often contains the 'Functional' keywords like "Pricing" or "Dispute"
        parts.append(f"AGENDA: {agenda} {agenda}")

    if desc:
        parts.append(f"DESC: {desc}")

    # Reduce the "Raw" noise without deleting it
    t = _clean(brochure_text)
    if t:
        # We take a smaller sample (1500 chars) to capture the intro 
        # but avoid the footer/legal text that usually triggers "HSE" keywords
        parts.append("RAW: " + t[:1500]) 

    return _clean(" ".join(parts))