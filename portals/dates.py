from __future__ import annotations

import re

DATE_RE = re.compile(r"(\d{2})[./](\d{2})[./](\d{2,4})")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def parse_de_date(value: str) -> str:
    """Return ISO date YYYY-MM-DD from DD.MM.YYYY or DD.MM.YY, or empty."""
    if not value:
        return ""
    match = DATE_RE.search(value)
    if not match:
        return ""
    day, month, year = match.group(1), match.group(2), match.group(3)
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month}-{day}"
