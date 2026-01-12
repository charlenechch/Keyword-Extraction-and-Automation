import os
import pandas as pd

from utils.text_extraction import (
    extract_text_with_fallback,
    extract_layout_blocks_native
)

from layer1_text.metadata_extraction import extract_metadata
from layer1_text.hrdc_detection import detect_hrdc_logo
from layer2_layout.layout_inference import layout_fallback
from layer3_llm.gemini_fallback import gemini_fallback
from utils.contract import to_contract

def is_high(conf):
    return conf == "High"

# CONFIG (Batch mode only)
BROCHURE_FOLDER = "brochures"
OUTPUT_EXCEL = "brochure_metadata.xlsx"


# SINGLE PDF PROCESSOR (API MODE)
def process_single_pdf(pdf_path: str) -> dict:
    """
    Progressive 3-layer extraction:
    Layer 1 → Text-only
    Layer 2 → Layout-aware
    Layer 3 → LLM (Gemini)
    """

    # LAYER 1 — TEXT ONLY
    print("[Layer 1] Text extraction")
    text, method = extract_text_with_fallback(pdf_path)
    meta = extract_metadata(text)
    text_hrdc = meta["HRDC Certified"] == "Yes"

    try:
        logo_hrdc = detect_hrdc_logo(pdf_path)
    except Exception:
        logo_hrdc = False
        meta["Flags"] += "; HRDC_LOGO_ERROR"

    if logo_hrdc or text_hrdc:
        meta["HRDC Certified"] = "Yes"
        meta["HRDC Confidence"] = "High" if logo_hrdc else "Medium"
        if logo_hrdc:
            meta["Flags"] += "; HRDC_LOGO_DETECTED"
    else:
        meta["HRDC Certified"] = "No"
        meta["HRDC Confidence"] = "Low"


    # LAYER 2 — LAYOUT AWARE
    if any(meta.get(k) != "High" for k in [
        "Program Title Confidence",
        "Program Date Confidence",
        "Venue Confidence", 
        "Cost Confidence",
        "Trainer Confidence",
        "Organiser Confidence"
    ]):
        print("[Layer 2] Layout fallback triggered")
        layout_pages = extract_layout_blocks_native(pdf_path)
        meta = layout_fallback(meta, layout_pages, pdf_path)
    else:
        print("[Layer 2] Skipped (confidence already high)")

    # LAYER 3 — LLM FALLBACK
    if any(meta.get(k) != "High" for k in [
        "Program Title Confidence",
        "Program Date Confidence",
        "Venue Confidence", 
        "Cost Confidence",
        "Trainer Confidence",
        "Organiser Confidence"
    ]):
        print("[Layer 3] LLM (Gemini) fallback triggered")
        meta = gemini_fallback(meta, text)
    else:
        print("[Layer 3] Skipped (confidence already high)")

    # STANDARDISATION 
    payload = to_contract(
        meta,
        source_file=os.path.basename(pdf_path),
        pdf_path=pdf_path,
        method=method
    )

    # FORCE JSON-SAFE OUTPUT
    safe_payload = {}
    for k, v in payload.items():
        if v is None:
            safe_payload[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            safe_payload[k] = v
        else:
            safe_payload[k] = str(v)

    return safe_payload

# BATCH PROCESSOR (OFFLINE MODE)
def run_batch_pipeline():
    """
    Process ALL PDFs in brochures/ and write Excel output.
    """

    rows = []

    for file in os.listdir(BROCHURE_FOLDER):
        if not file.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(BROCHURE_FOLDER, file)
        print(f"\n[Batch] Processing {file}")

        payload = process_single_pdf(pdf_path)
        rows.append(payload)

    if not rows:
        print("No brochures found.")
        return

    df = pd.DataFrame(rows)

    ready = df[df["status"] == "READY_TO_FILL"]
    review = df[df["status"] == "PENDING_REVIEW"]

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        ready.to_excel(writer, sheet_name="READY_TO_FILL", index=False)
        review.to_excel(writer, sheet_name="PENDING_REVIEW", index=False)

    print(f"\nBatch completed → {OUTPUT_EXCEL}")


# ENTRY POINT
if __name__ == "__main__":
    run_batch_pipeline()
