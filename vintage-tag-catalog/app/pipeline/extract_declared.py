from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DeclaredDateResult:
    source: str | None
    snippet: str | None
    declared_year: int | None
    start_year: int | None
    end_year: int | None
    confidence: float


YEAR_RE = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")
RANGE_RE = re.compile(r"\b(19\d{2}|20[0-2]\d)\s*(?:-|to)\s*(19\d{2}|20[0-2]\d)\b", re.IGNORECASE)
DECADE_RE = re.compile(r"\b(early|mid|late)?\s*('?\d0s|19\d0s|20\d0s)\b", re.IGNORECASE)


def extract_declared_date(title: str | None, description: str | None, specifics: str | None = None) -> DeclaredDateResult:
    fields = [("title", title or ""), ("description", description or ""), ("specifics", specifics or "")]
    for source, text in fields:
        if not text:
            continue
        if m := RANGE_RE.search(text):
            y1, y2 = int(m.group(1)), int(m.group(2))
            return DeclaredDateResult(source, m.group(0), None, min(y1, y2), max(y1, y2), 0.8)
        if m := YEAR_RE.search(text):
            y = int(m.group(1))
            return DeclaredDateResult(source, m.group(0), y, y, y, 0.9)
        if m := DECADE_RE.search(text):
            qualifier, decade_raw = m.group(1), m.group(2).replace("'", "")
            decade = _decode_decade(decade_raw)
            start, end = decade, decade + 9
            if qualifier and qualifier.lower() == "early":
                end = decade + 3
            elif qualifier and qualifier.lower() == "mid":
                start, end = decade + 3, decade + 6
            elif qualifier and qualifier.lower() == "late":
                start = decade + 6
            return DeclaredDateResult(source, m.group(0), None, start, end, 0.55)
    return DeclaredDateResult(None, None, None, None, None, 0.0)


def _decode_decade(token: str) -> int:
    t = token.lower()
    if t.startswith("19") or t.startswith("20"):
        return int(t[:3] + "0")
    return 1900 + int(t[:2])
