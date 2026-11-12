from __future__ import annotations

import re
from datetime import date

from .codes import EMPLOYMENT_TYPES, JOB_CATEGORIES, REGIONS
from .models import JobPosting, SearchCondition

_COMPANY_NOISE = re.compile(r"\(주\)|㈜|\(유\)|㈲|주식회사|유한회사|\(재\)|재단법인|\(사\)|사단법인|\s+")


def normalize_company(name: str) -> str:
    return _COMPANY_NOISE.sub("", name or "").lower()


def clean_company_name(name: str) -> str:
    """제외 목록에 넣을 회사 이름: (주)·주식회사·공백 등을 뺀 이름 (대소문자는 그대로)."""
    return _COMPANY_NOISE.sub("", name or "").strip()


def parse_exclude_list(text: str) -> list[str]:
    parts = re.split(r"[,\n]", text or "")
    return [p.strip() for p in parts if p.strip()]


def classify_career(text: str) -> str:
    """경력 조건 문자열을 경력 / 신입 / 신입·경력 / 경력무관 / 알수없음 으로 분류."""
    t = (text or "").replace(" ", "")
    if not t:
        return "알수없음"
    if "무관" in t or "관계없음" in t:
        return "경력무관"
    has_new = "신입" in t
    has_exp = "경력" in t
    if has_new and has_exp:
        return "신입·경력"
    if has_new:
        return "신입"
    if has_exp:
        return "경력"
    return "알수없음"


def _keyword_hit(keyword: str, title: str, full: str) -> bool:
    # 정규식(PL, DA 같은 짧은 약어)은 태그에서 오탐이 많아 제목에서만 찾는다
    if keyword.startswith("re:"):
        return re.search(keyword[3:], title) is not None
    return keyword.lower() in full.lower()


def match_job_categories(posting: JobPosting, categories: list[str]) -> list[str]:
    hits = []
    for name in categories:
        cat = JOB_CATEGORIES[name]
        full = posting.title if cat.get("title_only") else f"{posting.title} {posting.tags}"
        if any(_keyword_hit(k, posting.title, full) for k in cat["keywords"]):
            hits.append(name)
    return hits


def match_region(location: str, regions: list[str]) -> bool:
    return any(alias in location for r in regions for alias in REGIONS[r]["aliases"])


def match_employment(emp_text: str, wanted: list[str]) -> bool:
    if not emp_text:
        return False
    return any(w in emp_text for w in wanted if w in EMPLOYMENT_TYPES)


def is_excluded(company: str, excludes: list[str]) -> bool:
    c = normalize_company(company)
    return any(normalize_company(e) and normalize_company(e) in c for e in excludes)


def has_excluded_word(title: str, words: list[str]) -> bool:
    t = re.sub(r"\s+", "", title or "").lower()
    return any(w and re.sub(r"\s+", "", w).lower() in t for w in words)


def in_period(d: date | None, start: date, end: date) -> bool:
    return d is not None and start <= d <= end


def apply_filters(postings: list[JobPosting], cond: SearchCondition) -> tuple[list[JobPosting], dict[str, int]]:
    """필터를 순서대로 적용하고, 단계별로 빠진 건수를 함께 돌려준다."""
    dropped = {"기간": 0, "직무": 0, "제외직무": 0, "경력": 0, "고용형태": 0, "지역": 0, "제외업체": 0}
    kept: list[JobPosting] = []
    for p in postings:
        if not in_period(p.posted_date, cond.date_from, cond.date_to):
            dropped["기간"] += 1
            continue
        cats = match_job_categories(p, cond.job_categories)
        if not cats:
            dropped["직무"] += 1
            continue
        if has_excluded_word(p.title, cond.exclude_title_keywords):
            dropped["제외직무"] += 1
            continue
        if p.career_kind not in ("경력", "경력무관"):
            dropped["경력"] += 1
            continue
        if not match_employment(p.employment_type, cond.employment_types):
            dropped["고용형태"] += 1
            continue
        if not match_region(p.location, cond.regions):
            dropped["지역"] += 1
            continue
        if is_excluded(p.company, cond.exclude_companies):
            dropped["제외업체"] += 1
            continue
        p.job_category = ", ".join(cats)
        kept.append(p)
    return kept, dropped


def dedupe(postings: list[JobPosting]) -> list[JobPosting]:
    """같은 회사 + 같은 제목은 하나로 합치고 출처를 이어 붙인다."""
    seen: dict[tuple[str, str], JobPosting] = {}
    for p in postings:
        key = (normalize_company(p.company), re.sub(r"\s+", "", p.title).lower())
        if key in seen:
            first = seen[key]
            if p.source not in first.source:
                first.source = f"{first.source}, {p.source}"
        else:
            seen[key] = p
    return list(seen.values())
