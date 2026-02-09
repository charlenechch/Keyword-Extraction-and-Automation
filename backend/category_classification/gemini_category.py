import os
import json
import re
from typing import List, Dict, Optional

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def build_prompt(brochure_summary: str, candidates: List[Dict]) -> str:
    cand_lines = []
    for i, c in enumerate(candidates, 1):
        cand_lines.append(
            f"{i}) [{c['domain']}] {c['category']}\n"
            f"   Details: {c.get('blob','')}\n"
        )

    return f"""
You are categorising a training brochure into EXACTLY ONE category from the candidate list.

BROCHURE SUMMARY:
{brochure_summary}

CANDIDATE CATEGORIES (choose one only):
{''.join(cand_lines)}

Rules:
- Choose EXACTLY ONE category from the candidates above.
- Output must match the category text exactly (case and spelling).
- Base decision on the actual topics/tools taught, agenda, and skills focus.
- Return STRICT JSON only. No markdown.

Output JSON schema:
{{
  "category": "<one of the candidate category names>",
  "confidence": "High" | "Medium" | "Low",
  "reason": "one short sentence"
}}
""".strip()


def choose_category_with_gemini(brochure_summary: str, candidates: List[Dict]) -> Dict:
    allowed = {c["category"] for c in candidates}
    prompt = build_prompt(brochure_summary, candidates)

    model = genai.GenerativeModel(MODEL_NAME)
    resp = model.generate_content(
        prompt,
        generation_config={"temperature": 0, "top_p": 0.1}
    )

    text = getattr(resp, "text", "") or ""
    data = _extract_json(text)

    if not isinstance(data, dict):
        return {
            "category": candidates[0]["category"],
            "confidence": "Medium",
            "reason": "Gemini returned invalid JSON; fallback to top candidate."
        }

    cat = data.get("category")
    conf = data.get("confidence", "Medium")
    reason = data.get("reason", "")

    if cat not in allowed:
        return {
            "category": candidates[0]["category"],
            "confidence": "Medium",
            "reason": "Gemini chose a category outside candidates; fallback to top candidate."
        }

    if conf not in ("High", "Medium", "Low"):
        conf = "Medium"

    return {"category": cat, "confidence": conf, "reason": reason}
