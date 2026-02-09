# category_classification/__init__.py
from typing import Dict, Tuple

from .category_loader import load_categories_from_docx
from .brochure_representation import build_weighted_brochure_text
from .category_index import CategoryIndex
from .threshold import compute_confidence

def classify_brochure_category(
    meta: Dict,
    brochure_text: str,
    docx_path: str,
    top_k: int = 5,
    use_gemini: bool = False,
    gemini_callable=None,  # function(brochure_summary, candidates) -> dict
) -> Tuple[str, str]:
    """
    Classifies a brochure. 
    1. Uses local Hybrid Search (BM25 + Embeddings).
    2. Computes a confidence score.
    3. If confidence is Low/Medium and use_gemini is True, falls back to Gemini for reranking.
    """
    # 1. Load data and build index
    categories = load_categories_from_docx(docx_path)
    index = CategoryIndex(categories)

    # 2. Pre-process text (Applying the 3x title boost and 2x agenda boost)
    weighted_text = build_weighted_brochure_text(meta, brochure_text)

    # 3. Retrieve candidates using Hybrid Search
    cands = index.retrieve_topk(weighted_text, k=top_k)

    if not cands:
        return ("Uncategorized", "Low")

    # 4. Determine initial confidence
    conf = compute_confidence(cands)
    final_category = cands[0]["category"]

    print(f"\n=== DEBUG: Local Top Match: {final_category} (Conf: {conf}) ===")

    # 5. FALLBACK LOGIC: Only use Gemini if confidence isn't High
    # Or if the top two scores are nearly identical (a "close call")
    is_close_call = False
    if len(cands) > 1:
        # If the difference between top 1 and top 2 is less than 0.03
        is_close_call = (cands[0]["score"] - cands[1]["score"]) < 0.03

    should_fallback = use_gemini and gemini_callable and (conf == "Low" or is_close_call)

    if should_fallback:
        print("--- Low confidence or close call detected. Triggering Gemini Fallback... ---")
        
        # We pass only the top 3-5 candidates to Gemini to keep it focused
        top_candidates = cands[:3] 
        # Truncate summary to save tokens
        summary_for_gemini = weighted_text[:2000] 
        
        decided = gemini_callable(summary_for_gemini, top_candidates)

        # If Gemini returns a valid result, override the local decision
        if isinstance(decided, dict) and decided.get("category"):
            final_category = decided["category"]
            # We bump the confidence to Medium because a second "expert" verified it
            conf = "Medium" 
            print(f"--- Gemini Overrode to: {final_category} ---")

    return (final_category, conf)