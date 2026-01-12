import fitz  # PyMuPDF
import pdfplumber
import os

# ======================================================
# OPTIONAL OCR SUPPORT
# ------------------------------------------------------
# OCR requires:
#   - pytesseract (Python package)
#   - tesseract-ocr (system binary)
#   - poppler (for pdf2image)
#
# These are NOT available on Railway by default.
# So we safely detect OCR availability instead of crashing.
# ======================================================

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# ======================================================
# CONFIG
# ======================================================

TEXT_LENGTH_THRESHOLD = 300
OCR_DPI = 300


# ======================================================
# MAIN FUNCTION
# ======================================================

def extract_text_with_fallback(pdf_path):
    """
    Extract text from PDF using:
    1) Native text extraction (PyMuPDF + pdfplumber)
    2) OCR fallback if text is insufficient

    Returns:
        full_text (str)
        method ("TEXT" | "OCR" | "MIXED")
    """

    text_chunks = []

    # --------------------------------------------------
    # 1. PyMuPDF extraction
    # --------------------------------------------------
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_chunks.append(page_text)
    except Exception as e:
        print(f"[ERROR] PyMuPDF failed: {e}")

    text_pymupdf = "\n".join(text_chunks).strip()

    # --------------------------------------------------
    # 2. pdfplumber extraction
    # --------------------------------------------------
    text_plumber = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_plumber.append(page_text)
    except Exception as e:
        print(f"[ERROR] pdfplumber failed: {e}")

    text_plumber = "\n".join(text_plumber).strip()

    # --------------------------------------------------
    # Combine native text
    # --------------------------------------------------
    combined_text = "\n".join([text_pymupdf, text_plumber]).strip()

    # --------------------------------------------------
    # Decide if OCR is needed
    # --------------------------------------------------
    if len(combined_text) >= TEXT_LENGTH_THRESHOLD:
        return combined_text, "TEXT"

    # --------------------------------------------------
    # 3. OCR fallback (ONLY if available)
    # --------------------------------------------------
    if not OCR_AVAILABLE:
        print("[INFO] OCR not available. Skipping OCR fallback.")
        return combined_text, "TEXT"

    print(f"[INFO] Running OCR for: {os.path.basename(pdf_path)}")

    ocr_text = []
    try:
        images = convert_from_path(pdf_path, dpi=OCR_DPI)
        for img in images:
            text = pytesseract.image_to_string(img)
            if text.strip():
                ocr_text.append(text)
    except Exception as e:
        print(f"[ERROR] OCR failed: {e}")

    ocr_text = "\n".join(ocr_text).strip()

    # --------------------------------------------------
    # Final decision
    # --------------------------------------------------
    if combined_text and ocr_text:
        return combined_text + "\n" + ocr_text, "MIXED"
    elif ocr_text:
        return ocr_text, "OCR"
    else:
        return combined_text, "TEXT"


# ======================================================
# LAYOUT-AWARE EXTRACTION (NATIVE PDFs ONLY)
# ======================================================

def extract_layout_blocks_native(pdf_path):
    """
    Extract layout-aware text blocks using PyMuPDF.
    Only valid for native (non-OCR) PDFs.

    Returns:
        pages: list[list[dict]]
    """

    pages = []

    try:
        doc = fitz.open(pdf_path)

        for page in doc:
            page_blocks = []
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] != 0:  # skip images
                    continue

                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text:
                            continue

                        page_blocks.append({
                            "text": text,
                            "size": span["size"],
                            "bbox": span["bbox"]  # (x0, y0, x1, y1)
                        })

            pages.append(page_blocks)

    except Exception as e:
        print(f"[ERROR] Layout extraction failed: {e}")

    return pages
