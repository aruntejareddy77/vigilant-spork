"""
src/sovereign/tools/builtin/parsing.py
Structured document, table, and text extraction tools per TOOL-03.
"""
import csv
import io
import re
from typing import Any, Dict, List


def parse_table(content: str, delimiter: str = ",") -> Dict[str, Any]:
    """
    Parse a tabular string (CSV/TSV) into structured column headers and row dictionaries.
    Returns metadata including column names, row count, and parsed rows.
    """
    if not content or not content.strip():
        return {
            "columns": [],
            "row_count": 0,
            "rows": [],
            "sample": [],
        }

    # Detect delimiter if auto
    reader = csv.reader(io.StringIO(content.strip()), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        return {"columns": [], "row_count": 0, "rows": [], "sample": []}

    # Clean header columns
    columns = [col.strip() for col in header]
    rows: List[Dict[str, Any]] = []

    for row_idx, row_values in enumerate(reader):
        row_dict: Dict[str, Any] = {}
        for col_idx, col_name in enumerate(columns):
            val = row_values[col_idx].strip() if col_idx < len(row_values) else ""
            # Attempt numeric conversion
            if val.isdigit():
                row_dict[col_name] = int(val)
            else:
                try:
                    row_dict[col_name] = float(val)
                except ValueError:
                    row_dict[col_name] = val
        rows.append(row_dict)

    return {
        "columns": columns,
        "row_count": len(rows),
        "rows": rows,
        "sample": rows[:5],
    }


def extract_text(content: str) -> str:
    """
    Clean and normalize raw text extracted from documents.
    Strips XML/HTML tags, normalizes whitespace, and unifies line breaks.
    """
    if not content:
        return ""

    # Remove basic HTML/XML tags
    cleaned = re.sub(r"<[^>]+>", " ", content)

    # Normalize carriage returns and multiple newlines
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Collapse multiple horizontal whitespace
    lines = []
    for line in cleaned.split("\n"):
        stripped = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(stripped)

    return "\n".join(lines).strip()
