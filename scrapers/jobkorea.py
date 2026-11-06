"""잡코리아 검색 결과 크롤러.

검색 페이지(Next.js)가 서버에서 내려주는 RSC 데이터 안의 JOB_LIST 쿼리 결과(JSON)를 읽는다.
지역 필터는 URL 파라미터가 아니라 `searchBarLocal` 쿠키로 전달해야 적용된다.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from core.codes import JOBKOREA_CAREER, JOBKOREA_EMP, JOBKOREA_EMP_NAME, REGIONS
from core.models import JobPosting, SearchCondition

from .base import PoliteSession

NAME = "잡코리아"
SEARCH_URL = "https://www.jobkorea.co.kr/Search/"
VIEW_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/{}"

_NEXT_F = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
_ROW_PREFIX = re.compile(r"^[0-9a-zA-Z]+:")

# 지역 코드(앞 글자) → 지역명.  세종은 '1000' 계열
_REGION_BY_PREFIX = {v["jobkorea"][0]: k for k, v in REGIONS.items() if v["jobkorea"] != "1000"}


def _region_name(code: str) -> str:
    if code.startswith("1"):
        return "세종"
    if code.startswith("Q"):
        return "전국"
    return _REGION_BY_PREFIX.get(code[:1], "")


def _find_job_list(obj):
    """중첩 구조에서 queryKey[0] == 'JOB_LIST' 인 쿼리의 data 를 찾는다."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            qk = cur.get("queryKey")
            if isinstance(qk, list) and qk and qk[0] == "JOB_LIST":
                return cur.get("state", {}).get("data")
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _extract_job_list(html: str) -> dict | None:
    text = "".join(json.loads(f'"{c}"') for c in _NEXT_F.findall(html))
    for line in text.split("\n"):
        if '"JOB_LIST"' not in line:
            continue
        payload = _ROW_PREFIX.sub("", line, count=1)
        try:
            data = _find_job_list(json.loads(payload))
        except json.JSONDecodeError:
            continue
        if data is not None:
            return data
    return None


def _to_posting(j: dict) -> JobPosting:
    p = JobPosting(source=NAME, company=j.get("companyName") or j.get("postingCompanyName") or "",
                   title=j.get("title", ""), url=VIEW_URL.format(j.get("id")))
    regions = []
    for c in j.get("areaCodeList") or []:
        n = _region_name(c)
        if n and n not in regions:
            regions.append(n)
    p.location = ", ".join(regions)
    kind = JOBKOREA_CAREER.get(str(j.get("careerType")), "알수없음")
    p.career_kind = kind
    years = j.get("careerRange") or 0
    p.career = f"경력{years}년↑" if kind == "경력" and 0 < years < 100 else kind
    emps = []
    for code in j.get("employmentTypeCodeList") or []:
        name = JOBKOREA_EMP_NAME.get(code.split("/")[0], "")
        if name and name not in emps:
            emps.append(name)
    p.employment_type = "·".join(emps)
    pay = j.get("payRange") or {}
    start, end = str(pay.get("start") or "0"), str(pay.get("end") or "0")
    if start != "0" or end != "0":
        p.salary = f"{int(start):,}~{int(end):,}만원" if end != "0" else f"{int(start):,}만원~"
    created = j.get("createdAt")
    if created:
        p.posted_date = datetime.fromisoformat(created).date()
    end_dt = (j.get("applicationPeriod") or {}).get("end")
    if end_dt:
        d = datetime.fromisoformat(end_dt).date()
        p.deadline = "상시채용" if d.year >= 2060 else d.isoformat()
    p.tags = j.get("jobClassificationOrIndustry") or ""
    return p


def search(cond: SearchCondition, queries: list[str], log=print) -> list[JobPosting]:
    sess = PoliteSession()
    local = ",".join(f"{REGIONS[r]['jobkorea']}_" for r in cond.regions)
    sess.s.cookies.set("searchBarLocal", local, domain=".jobkorea.co.kr")
    emp = ",".join(JOBKOREA_EMP[e] for e in cond.employment_types if e in JOBKOREA_EMP)
    results: list[JobPosting] = []
    for q in queries:
        page = 1
        while page <= cond.max_pages:
            params = {"stext": q, "tabType": "recruit", "careerType": "2", "Page_No": str(page)}
            if emp:
                params["jobtype"] = emp
            r = sess.get(SEARCH_URL, params=params)
            data = _extract_job_list(r.text)
            if data is None:
                raise RuntimeError("잡코리아 검색 결과 데이터를 찾지 못했습니다 (페이지 구조 변경 가능성)")
            items = [_to_posting(j) for j in data.get("content") or []]
            log(f"[잡코리아] '{q}' {page}/{data.get('totalPages', '?')}페이지: {len(items)}건")
            results.extend(items)
            if page >= int(data.get("totalPages") or 0):
                break
            page += 1
    return results
