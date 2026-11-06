"""고용24 채용정보 상세검색 크롤러."""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from core.codes import REGIONS, WORK24_EMP
from core.filters import classify_career
from core.models import JobPosting, SearchCondition

from .base import PoliteSession

NAME = "고용24"
BASE = "https://www.work24.go.kr"
SEARCH_URL = BASE + "/wk/a/b/1200/retriveDtlEmpSrchList.do"
PAGE_SIZE = 50

_REG_RE = re.compile(r"등록일\s*:\s*(\d{4})-(\d{2})-(\d{2})")
_CLOSE_RE = re.compile(r"마감일\s*:\s*([^\s]+)")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _parse_row(row, emp_label: str) -> JobPosting | None:
    link = row.select_one("a[data-emp-detail]")
    corp = row.select_one(".cp_name")
    if not link or not corp:
        return None
    title = _clean(link.get_text(" ", strip=True))
    chk = row.select_one("input[id^=chkboxWantedAuthNo]")
    if chk and chk.get("value"):
        parts = chk["value"].split("|")
        if len(parts) >= 4 and parts[3].strip():
            title = parts[3].strip()  # 목록에서는 제목이 잘려 있어 원문 사용
    p = JobPosting(source=NAME, company=_clean(corp.get_text()), title=title,
                   url=BASE + link["href"], employment_type=emp_label)
    member = row.select("li.member span.item")
    if member:
        p.career = _clean(member[0].get_text())
    p.career_kind = classify_career(p.career)
    pay = row.select_one("li.dollar")
    if pay:
        p.salary = _clean(" ".join(s.get_text(" ", strip=True) for s in pay.select("span.item")))
    site = row.select_one("li.site")
    if site:
        p.location = _clean(site.get_text())
    text = _clean(row.get_text(" ", strip=True))
    m = _REG_RE.search(text)
    if m:
        p.posted_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _CLOSE_RE.search(text)
    if m:
        p.deadline = m.group(1)
    return p


def search(cond: SearchCondition, queries: list[str], log=print) -> list[JobPosting]:
    """검색 조건은 GET 파라미터로는 일부만 적용되어 화면과 같은 POST 폼으로 보낸다.
    검색어는 'keyword'가 아니라 'srcKeyword' 필드여야 적용된다."""
    sess = PoliteSession()
    region = ",".join(REGIONS[r]["work24"] for r in cond.regions)
    results: list[JobPosting] = []
    # 고용24 목록에는 고용형태가 표시되지 않으므로 고용형태별로 따로 조회해 표시한다
    for emp in cond.employment_types:
        if emp not in WORK24_EMP:
            log(f"[고용24] '{emp}' 구분은 고용24에 없어 건너뜀")
            continue
        for q in queries:
            for page in range(1, cond.max_pages + 1):
                form = {
                    "srcKeyword": q, "region": region, "careerTypes": "E", "employGbn": WORK24_EMP[emp],
                    "resultCnt": str(PAGE_SIZE), "sortField": "DATE", "sortOrderBy": "DESC",
                    "currentPageNo": str(page), "pageIndex": str(page), "siteClcd": "all", "empTpGbcd": "1",
                }
                r = sess.post(SEARCH_URL, data=form)
                soup = BeautifulSoup(r.text, "lxml")
                items = [p for p in (_parse_row(row, emp) for row in soup.select("tr[id^=list]")) if p]
                log(f"[고용24] {emp} '{q}' {page}페이지: {len(items)}건")
                results.extend(items)
                if len(items) < PAGE_SIZE:
                    break
                # 등록일 내림차순 정렬 → 페이지 전체가 시작일 이전이면 더 볼 필요 없음
                if all(p.posted_date and p.posted_date < cond.date_from for p in items):
                    break
    return results
