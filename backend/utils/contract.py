from utils.date_parsing import parse_start_date, parse_end_date
from layer1_text.hrdc_detection import detect_hrdc_logo

def decide_status(meta):
    if meta.get("Program Date Confidence") == "High":
        return "READY_TO_FILL"
    return "PENDING_REVIEW"

def review_flags(meta):
    flags = []

    if meta.get("Program Date Confidence") != "High":
        flags.append("DATE_UNCERTAIN")

    if meta.get("Venue Confidence") != "High":
        flags.append("VENUE_UNCERTAIN")

    if meta.get("Program Title Confidence") != "High":
        flags.append("TITLE_UNCERTAIN")

    if meta.get("Cost Confidence") != "High":
        flags.append("COST_UNCERTAIN")

    if meta .get("Trainer Confidence") != "High":
        flags.append("TRAINER_UNCERTAIN")

    if meta.get("Organiser Confidence") != "High":
        flags.append("ORGANISER_UNCERTAIN")

    return flags


def to_contract(meta, source_file, pdf_path=None, method=None):
    return {
        "file": source_file,

        "program_title": meta.get("Program Title"),
        "start_date": parse_start_date(meta.get("Program Date")),
        "end_date": parse_end_date(meta.get("Program Date")),
        "venue": meta.get("Venue") or meta.get("Program Venue"),

        
        # COST FIELDS
        "cost_amount": meta.get("Cost Amount", "N/A"),
        "cost_currency": meta.get("Cost Currency", "N/A"),
        "confidence_cost": meta.get("Cost Confidence", "Low"),

        # TRAINER 
        "trainer": meta.get("Trainer"),
        "confidence_trainer": meta.get("Trainer Confidence"),

        # ORGANISER
        "training_organiser": meta.get("Training Organiser"),
        "confidence_organiser": meta.get("Organiser Confidence"),

        # CONFIDENCE
        "confidence_program_title": meta.get("Program Title Confidence"),
        "confidence_date": meta.get("Program Date Confidence"),
        "confidence_venue": meta.get("Venue Confidence"),
        
        "hrdc_certified": (
            "Yes" if pdf_path and detect_hrdc_logo(pdf_path) else "No"
        ),
        "category": meta.get("LMS Category"),
        "confidence_category": meta.get("LMS Category Confidence"),
        "method": method,
        "review_flags": review_flags(meta),
        "status": decide_status(meta)
    }
