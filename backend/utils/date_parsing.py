import re
from datetime import datetime

def parse_start_date(date_str):
    if not date_str:
        return None

    date_str = date_str.lower()

    # Range: 12–14 March 2025
    match = re.search(r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s*(\w+)\s*(\d{4})", date_str)
    if match:
        day1, _, month, year = match.groups()
        return _to_iso(day1, month, year)

    # Single date: 12 March 2025
    match = re.search(r"(\d{1,2})\s*(\w+)\s*(\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        return _to_iso(day, month, year)

    return None


def parse_end_date(date_str):
    if not date_str:
        return None

    date_str = date_str.lower()

    # Range: 12–14 March 2025
    match = re.search(r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s*(\w+)\s*(\d{4})", date_str)
    if match:
        _, day2, month, year = match.groups()
        return _to_iso(day2, month, year)

    # Single date → same as start
    return parse_start_date(date_str)


def _to_iso(day, month, year):
    try:
        return datetime.strptime(
            f"{int(day)} {month.capitalize()} {year}",
            "%d %B %Y"
        ).date().isoformat()
    except ValueError:
        return None
