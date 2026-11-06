from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class SearchCondition:
    date_from: date
    date_to: date
    job_categories: list[str]
    regions: list[str]
    employment_types: list[str]
    sites: list[str]
    exclude_companies: list[str] = field(default_factory=list)
    exclude_title_keywords: list[str] = field(default_factory=list)  # 제목에 있으면 제외 (장비·인프라 등)
    max_pages: int = 5  # 사이트·검색어당 최대 페이지 수


@dataclass
class JobPosting:
    source: str
    company: str
    title: str
    url: str
    location: str = ""
    career: str = ""            # 화면 표시용 (예: 경력3년↑)
    career_kind: str = ""       # 경력 / 신입 / 신입·경력 / 경력무관 / 알수없음
    employment_type: str = ""   # 예: 정규직·계약직
    salary: str = ""
    posted_date: date | None = None
    date_label: str = "등록일"  # 등록일 / 수정일
    deadline: str = ""
    tags: str = ""              # 사이트가 붙인 직무 태그 (직무 매칭용)
    job_category: str = ""      # 매칭된 직무 (필터 단계에서 채움)

    def to_row(self) -> dict:
        return {
            "출처": self.source,
            "회사명": self.company,
            "공고 제목": self.title,
            "직무": self.job_category,
            "지역": self.location,
            "경력": self.career,
            "고용형태": self.employment_type,
            "급여": self.salary,
            "등록일": self.posted_date.isoformat() if self.posted_date else "",
            "날짜구분": self.date_label,
            "마감일": self.deadline,
            "링크": self.url,
        }
