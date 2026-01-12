import os
import json
import re
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# ORGANISER NORMALISATION
def normalize_organiser(name: str) -> str:
    if not name:
        return name

    text = name.strip()

    separators = [
        " and ",
        " & ",
        " with ",
        " in partnership with ",
        " in collaboration with ",
        " x ",
        "/"
    ]

    lowered = text.lower()
    for sep in separators:
        if sep in lowered:
            parts = text.split(sep, 1)
            return parts[0].strip()

    return text

def gemini_fallback(meta, text):
    """
    Layer 3: Semantic inference using Gemini.
    Runs ONLY when confidence < High.
    """

    # ---- HARD GUARD ----
    if all(meta.get(k) == "High" for k in [
        "Program Title Confidence",
        "Program Date Confidence",
        "Venue Confidence",
        "Cost Confidence", 
        "Trainer Confidence",
        "Organiser Confidence"
    ]):
        return meta

    prompt = f"""
    You are a professional data entry clerk. Your goal is to extract EXACT metadata from a training brochure.
    
    CRITICAL RULES:
    - Do NOT guess.
    - Do NOT summarise.
    - Extract ONLY if explicitly stated.
    - Preserve original wording, currency, and numbers.

    
    CRITICAL INSTRUCTIONS:
    1. PROGRAM TITLE: This is usually the largest text on the first page. 
       - Capture the FULL title, including any colon-separated subtitles or theme names.
       - Do NOT shorten or summarise.
       - Example: If it says "PROJECT MANAGEMENT: THE AGILE WAY", do NOT just return "Project Management".

    2. PROGRAM DATE: Look for the specific days of the event. 
       - If a range is provided (e.g., 21-22 July), you MUST return the full range.S
       - Do not return just a single day or a registration deadline.
       - If the programme has multiple sessions in different locations, return ALL sessions in a single string, separated by semicolons.
       - Example: "Malaysia: 3–7 June 2025; Singapore: 10–14 June 2025"

    3. PROGRAM VENUE: Extract the full venue name as stated.
        - Might be hotel names, conference centers, or online platforms.
        - If more than one venue is listed, extract the primary one. 

    4. COST: Extract the exact cost amount and currency as stated.
        - If any of the fields are NOT found, return "Not detected" for that field
        - If multiple costs are listed, extract the main program cost.
        - If there is a discounted price and a normal price, extract the discounted price.
        - If there is with and without accommodation prices, extract the without accommodation price.
        - If there are member and non-member prices, extract the non-member price.

    5. TRAINER: Extract the main trainer / speaker name(s) as stated.
        - If multiple trainers are listed, extract all names in a single string, separated by semicolons.
        - If no trainer names are found, return "Not detected".
        
    6. ORGANISER: Extract the full organiser name as stated.
        - If no organiser is found, return "Not detected".
        - If multiple organisers are listed, extract the primary one.
        - Usually the organiser is found at the logo or footer section.

    7. EXACTNESS: Do not summarize. Do not add words like "Conference" if they aren't part of the main title block.
    
    Return ONLY valid JSON:
    {{
        "Program Title": "...",
        "Program Date": "...",
        "Venue": "...",
        "Cost": "...",
        "Trainer": "...",
        "Organiser": "..."
     }}
    Document text:
    {text[:4000]}
    """

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0
            )
        )

        data = json.loads(response.text)

        # --- Apply Gemini results conservatively ---
        # --- Title ---
        if meta.get("Program Title Confidence") != "High":
            v = data.get("Program Title")
            if v and v != "Not detected":
                meta["Program Title"] = v
                meta["Program Title Confidence"] = "Medium"
                meta["Flags"] += ";GEMINI_TITLE"

        # ---- DATE ----
        if meta.get("Program Date Confidence") != "High":
            v = data.get("Program Date")
            if v and v != "Not detected":
                meta["Program Date"] = v
                meta["Program Date Confidence"] = "Medium"
                meta["Flags"] += ";GEMINI_DATE"

        # ---- VENUE ----
        if meta.get("Venue Confidence") != "High":
            v = data.get("Venue")
            if v and v != "Not detected":
                meta["Venue"] = v
                meta["Venue Confidence"] = "Medium"
                meta["Flags"] += ";GEMINI_VENUE"

        # ---- COST (VERY GUARDED) ----
        if meta.get("Cost Confidence") != "High":
            v = data.get("Cost")
            if v and v != "Not detected":
                m = re.search(r"(rm|usd)\s?\d+(?:,\d{3})*(?:\.\d{2})?", v, re.I)
                if m:
                    meta["Cost Amount"] = re.search(r"\d+(?:,\d{3})*(?:\.\d{2})?", v).group(0).replace(",", "")
                    meta["Cost Currency"] = m.group(1).upper()
                    meta["Cost Confidence"] = "Medium"
                    meta["Flags"] += ";GEMINI_COST"

        # ---- TRAINER ----
        if meta.get("Trainer Confidence") != "High":
            v = data.get("Trainer")
            if v and v != "Not detected":
                meta["Trainer"] = v
                meta["Trainer Confidence"] = "Medium"
                meta["Flags"] += ";GEMINI_TRAINER"

        # ---- ORGANISER ----
        if meta.get("Organiser Confidence") != "High":
            v = data.get("Organiser")
            if v and v != "Not detected":
                meta["Training Organiser"] = normalize_organiser(v)
                meta["Organiser Confidence"] = "Medium"
                meta["Flags"] += ";GEMINI_ORG"

    except Exception as e:
        print("[Gemini Error]", e)

    return meta
