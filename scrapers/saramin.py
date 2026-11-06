"""사람인 검색 결과 페이지 크롤러."""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from core.codes import REGIONS, SARAMIN_EMP
from core.filters import classify_career
from core.models import JobPosting, SearchCondition

from .base import PoliteSession

NAME = "사람인"
SEARCH_URL = "https://www.saramin.co.kr/zf_user/search/recruit"
VIEW_URL = "https://www.saramin.co.kr/zf_user/jobs/relay/view?view_type=search&rec_idx={}"
PAGE_SIZE = 40

_EMP_WORDS = ("정규직", "계약직", "프리랜서", "인턴", "아르바이트", "파견", "위촉", "병역특례", "교육생", "전임", "파트", "해외취업")
_DATE_RE = re.compile(r"(등록일|수정일)\s*(\d{2})/(\d{2})/(\d{2})")


def _parse_item(it) -> JobPosting | None:
    tit = it.select_one(".job_tit a")
    corp = it.select_one(".corp_name")
    rec_idx = it.get("value")
    if not tit or not corp or not rec_idx:
        return None
    p = JobPosting(source=NAME, company=corp.get_text(strip=True),
                   title=tit.get("title") or tit.get_text(" ", strip=True),
                   url=VIEW_URL.format(rec_idx))
    spans = [s.get_text(" ", strip=True) for s in it.select(".job_condition > span")]
    if spans:
        p.location = re.sub(r"\s*,\s*", ", ", spans[0])
    for s in spans[1:]:
        if "경력" in s or "신입" in s:
            p.career = s
        elif any(w in s for w in _EMP_WORDS):
            p.employment_type = s
        elif "만원" in s or "내규" in s or "면접" in s:
            p.salary = s
    p.career_kind = classify_career(p.career)
    sector = it.select_one(".job_sector")
    if sector:
        p.tags = sector.get_text(" ", strip=True)
    day = it.select_one(".job_day")
    if day:
        m = _DATE_RE.search(day.get_text(" ", strip=True))
        if m:
            p.date_label = m.group(1)
            p.posted_date = date(2000 + int(m.group(2)), int(m.group(3)), int(m.group(4)))
    dl = it.select_one(".job_date .date")
    if dl:
        p.deadline = dl.get_text(strip=True)
    return p


def search(cond: SearchCondition, queries: list[str], log=print) -> list[JobPosting]:
    sess = PoliteSession()
    params_base = {
        "loc_mcd": ",".join(REGIONS[r]["saramin"] for r in cond.regions),
        "exp_cd": "2",  # 경력
        "job_type": ",".join(SARAMIN_EMP[e] for e in cond.employment_types if e in SARAMIN_EMP),
        "sort": "reg_dt",
        "recruitPageCount": str(PAGE_SIZE),
    }
    results: list[JobPosting] = []
    for q in queries:
        for page in range(1, cond.max_pages + 1):
            r = sess.get(SEARCH_URL, params={**params_base, "searchword": q, "recruitPage": str(page)})
            soup = BeautifulSoup(r.text, "lxml")
            items = [p for p in (_parse_item(it) for it in soup.select("div.item_recruit")) if p]
            log(f"[사람인] '{q}' {page}페이지: {len(items)}건")
            results.extend(items)
            # sort=reg_dt 여도 수정일 공고가 섞여 날짜순이 엄격하지 않으므로 날짜로 조기 종료하지 않음
            if len(items) < PAGE_SIZE:
                break
    return results
