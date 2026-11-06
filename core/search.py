"""사이트별 수집 → 필터 → 중복 제거 → 정렬을 묶는 진입점."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from scrapers import jobkorea, saramin, work24

from .codes import JOB_CATEGORIES
from .filters import apply_filters, dedupe
from .models import JobPosting, SearchCondition

SCRAPERS = {"잡코리아": jobkorea.search, "사람인": saramin.search, "고용24": work24.search}


@dataclass
class SearchResult:
    postings: list[JobPosting]
    raw_counts: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)


def run_search(cond: SearchCondition, log=print) -> SearchResult:
    queries: list[str] = []
    for c in cond.job_categories:
        for q in JOB_CATEGORIES[c]["queries"]:
            if q not in queries:
                queries.append(q)

    raw: list[JobPosting] = []
    res = SearchResult(postings=[])
    # 사이트끼리는 동시에, 한 사이트 안에서는 간격을 두고 순서대로 요청
    with ThreadPoolExecutor(max_workers=len(cond.sites) or 1) as ex:
        futures = {site: ex.submit(SCRAPERS[site], cond, queries, log) for site in cond.sites}
        for site, fut in futures.items():
            try:
                items = fut.result()
                res.raw_counts[site] = len(items)
                raw.extend(items)
            except Exception as e:  # 한 사이트가 실패해도 나머지는 보여준다
                res.errors[site] = f"{type(e).__name__}: {e}"
                res.raw_counts[site] = 0

    # 같은 사이트에서 검색어만 달리 해 여러 번 나온 공고는 하나만 남긴다
    raw = list({p.url: p for p in raw}.values())
    kept, res.dropped = apply_filters(raw, cond)
    kept = dedupe(kept)
    kept.sort(key=lambda p: (p.posted_date.toordinal() if p.posted_date else 0), reverse=True)
    res.postings = kept
    return res
