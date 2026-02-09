from dataclasses import dataclass
from typing import List, Optional
from docx import Document
import re


@dataclass
class Category:
    domain: str
    name: str
    definition: str = ""
    remarks: str = ""
    ref_keywords: str = ""

    @property
    def blob(self) -> str:
        parts = [self.domain, self.name, self.definition, self.remarks, self.ref_keywords]
        return " | ".join(p.strip() for p in parts if p and p.strip())


def _clean(s: str) -> str:
    s = (s or "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_categories_from_docx(docx_path: str) -> List[Category]:
    doc = Document(docx_path)
    cats: List[Category] = []

    domain_by_table_index = {0: "Technical", 1: "Functional"}

    def col_idx(header_cells: List[str], *candidates: str) -> Optional[int]:
        for cand in candidates:
            cand_l = cand.lower()
            for i, h in enumerate(header_cells):
                if cand_l in h:
                    return i
        return None

    for ti, table in enumerate(doc.tables):
        domain = domain_by_table_index.get(ti, "Unknown")
        header = [_clean(c.text).lower() for c in table.rows[0].cells]

        idx_name = col_idx(header, "category", "categories")
        idx_def = col_idx(header, "definition", "description", "defination")
        idx_rem = col_idx(header, "remarks", "remark", "note", "notes")
        idx_kw = col_idx(header, "reference keyword", "reference keywords", "keywords", "keyword")

        # Fallback layout: No | Category | Definition | Remarks | (Keywords optional)
        if idx_name is None:
            idx_name = 1 if len(header) > 1 else 0
        if idx_def is None:
            idx_def = 2 if len(header) > 2 else idx_name
        if idx_rem is None:
            idx_rem = 3 if len(header) > 3 else idx_def

        # If no keyword header detected but 5 cols exist, assume last col is keywords
        if idx_kw is None and len(header) >= 5:
            idx_kw = 4

        for r in range(1, len(table.rows)):
            cells = table.rows[r].cells
            if idx_name >= len(cells):
                continue

            name = _clean(cells[idx_name].text)
            if not name:
                continue

            definition = _clean(cells[idx_def].text) if idx_def < len(cells) else ""
            remarks = _clean(cells[idx_rem].text) if idx_rem < len(cells) else ""
            ref_keywords = _clean(cells[idx_kw].text) if (idx_kw is not None and idx_kw < len(cells)) else ""

            cats.append(Category(domain=domain, name=name, definition=definition, remarks=remarks, ref_keywords=ref_keywords))

    # De-dup by (domain, name)
    seen = set()
    unique: List[Category] = []
    for c in cats:
        key = (c.domain.strip().lower(), c.name.strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique
