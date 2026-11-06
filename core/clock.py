"""한국 시간(KST) 기준 오늘·지금.

클라우드 서버(Streamlit Community Cloud 등)는 시계가 UTC 라서 date.today() 를 쓰면
한국 아침 9시 전에는 '어제'가 된다. 화면 기본 날짜와 파일 이름은 항상 이 함수로 구한다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def today_kst() -> date:
    return now_kst().date()
