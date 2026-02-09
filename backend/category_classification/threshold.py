from typing import List, Dict


def compute_confidence(cands: List[Dict]) -> str:
    """
    Heuristic confidence based on top1 score and margin vs top2.
    cands: list of dicts with 'score'
    """
    if not cands:
        return "Low"

    s1 = float(cands[0].get("score", 0.0))
    s2 = float(cands[1].get("score", 0.0)) if len(cands) > 1 else 0.0
    gap = s1 - s2

    # Tune these thresholds if needed
    if s1 >= 0.55 and gap >= 0.08:
        return "High"
    if s1 >= 0.42 and gap >= 0.04:
        return "Medium"
    return "Low"
