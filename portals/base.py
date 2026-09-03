from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Notice:
    portal: str
    pid: str
    title: str
    published_on: str
    deadline: str = ""
    notice_type: str = ""
    contracting_rule: str = ""
    organisation: str = ""
    project_url: str = ""
    city: str = ""
    cpv: str = ""
    excerpt: str = ""
    detail_text: str = ""
    category: str = ""
    match_reason: str = ""
    is_match: bool = False
    nuts: str = ""
    source_platform: str = ""
    area_m2: float | None = None
    capacity_kwp: float | None = None
    completion_on: str = ""
    value_eur: float | None = None
    start_on: str = ""
    is_new_build: bool | None = None
    has_transformer: bool | None = None


@dataclass
class SearchPage:
    page: int
    total_pages: int
    total: int
    notices: list[Notice] = field(default_factory=list)
