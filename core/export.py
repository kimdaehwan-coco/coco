"""검색 결과를 보기 좋게 꾸민 엑셀 파일로 만든다."""
from __future__ import annotations

import io
import math
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .clock import now_kst
from .models import SearchCondition

FONT_NAME = "맑은 고딕"
NAVY = "1F3864"
HEADER_FILL = PatternFill("solid", fgColor="2F5597")
STRIPE_FILL = PatternFill("solid", fgColor="F3F6FB")
LABEL_FILL = PatternFill("solid", fgColor="E9EEF7")
LINE = Side(style="thin", color="D0D7E5")
BORDER = Border(left=LINE, right=LINE, top=LINE, bottom=LINE)
SITE_COLORS = {"잡코리아": "1E64C8", "사람인": "4876EF", "고용24": "00A06E"}

# 열 이름 → (너비, 가운데 정렬 여부, 줄바꿈 여부)
COLUMNS = {
    "출처": (12, True, True),
    "회사명": (22, False, True),
    "공고 제목": (48, False, True),
    "직무": (18, False, True),
    "지역": (22, False, True),
    "경력": (12, True, False),
    "고용형태": (13, True, True),
    "급여": (18, False, True),
    "등록일": (12, True, False),
    "날짜구분": (9, True, False),
    "마감일": (13, True, False),
    "링크": (11, True, False),
}
TITLE_ROW, INFO_ROW, HEADER_ROW = 1, 2, 4
LINE_HEIGHT = 15


def _display_width(text: str) -> int:
    """엑셀 열 너비 기준 글자 폭 (한글 등 전각 문자는 2칸)."""
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


def _lines_needed(text: str, width: float) -> int:
    usable = max(width - 1.5, 1)
    return max(1, math.ceil(_display_width(text) / usable))


def _condition_text(cond: SearchCondition | None) -> str:
    if cond is None:
        return ""
    return f"기간 {cond.date_from:%Y-%m-%d} ~ {cond.date_to:%Y-%m-%d}   |   지역 {', '.join(cond.regions)}"


def _write_results(ws, df: pd.DataFrame, cond: SearchCondition | None, created: datetime) -> None:
    cols = list(df.columns)
    last_col = get_column_letter(len(cols))
    ws.sheet_view.showGridLines = False

    # 제목 / 요약
    ws.merge_cells(f"A{TITLE_ROW}:{last_col}{TITLE_ROW}")
    c = ws.cell(TITLE_ROW, 1, "채용공고 목록")
    c.font = Font(name=FONT_NAME, size=16, bold=True, color=NAVY)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[TITLE_ROW].height = 30

    ws.merge_cells(f"A{INFO_ROW}:{last_col}{INFO_ROW}")
    parts = [f"총 {len(df)}건", _condition_text(cond), f"생성 {created:%Y-%m-%d %H:%M}"]
    info = "   |   ".join(p for p in parts if p)
    c = ws.cell(INFO_ROW, 1, info)
    c.font = Font(name=FONT_NAME, size=10, color="595959")
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[INFO_ROW].height = 20

    # 머리글
    for j, name in enumerate(cols, start=1):
        c = ws.cell(HEADER_ROW, j, name)
        c.font = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER
        ws.column_dimensions[get_column_letter(j)].width = COLUMNS.get(name, (14, False, True))[0]
    ws.row_dimensions[HEADER_ROW].height = 24

    # 본문
    for i, row in enumerate(df.itertuples(index=False), start=0):
        r = HEADER_ROW + 1 + i
        lines = 1
        for j, (name, value) in enumerate(zip(cols, row), start=1):
            width, center, wrap = COLUMNS.get(name, (14, False, True))
            text = "" if pd.isna(value) else str(value)
            c = ws.cell(r, j)
            if name == "링크" and text:
                c.value = "공고 보기"
                c.hyperlink = text
                c.font = Font(name=FONT_NAME, size=10, color="0563C1", underline="single")
            else:
                c.value = text
                bold = name in ("회사명",)
                color = SITE_COLORS.get(text.split(",")[0].strip(), "262626") if name == "출처" else "262626"
                c.font = Font(name=FONT_NAME, size=10, bold=bold or name == "출처", color=color)
            c.alignment = Alignment(horizontal="center" if center else "left", vertical="center",
                                    wrap_text=wrap, indent=0 if center else 1)
            c.border = BORDER
            if i % 2 == 1:
                c.fill = STRIPE_FILL
            if wrap and name != "링크":
                lines = max(lines, _lines_needed(text, width))
        ws.row_dimensions[r].height = LINE_HEIGHT * min(lines, 4) + 8

    last_row = HEADER_ROW + len(df)
    ws.auto_filter.ref = f"A{HEADER_ROW}:{last_col}{max(last_row, HEADER_ROW)}"
    ws.freeze_panes = ws.cell(HEADER_ROW + 1, 3)  # 머리글과 출처·회사명 고정

    # 인쇄: 가로, 너비 한 장에 맞춤, 머리글 반복
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"
    ws.page_margins.left = ws.page_margins.right = 0.4


def _write_summary(ws, df: pd.DataFrame, cond: SearchCondition | None, created: datetime) -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 70
    c = ws.cell(1, 1, "검색 조건")
    c.font = Font(name=FONT_NAME, size=14, bold=True, color=NAVY)
    ws.row_dimensions[1].height = 26
    rows = [("생성 일시", f"{created:%Y-%m-%d %H:%M}"), ("결과 건수", f"{len(df)}건")]
    if cond is not None:
        rows += [
            ("기간", f"{cond.date_from:%Y-%m-%d} ~ {cond.date_to:%Y-%m-%d}"),
            ("직무", ", ".join(cond.job_categories)),
            ("지역", ", ".join(cond.regions)),
            ("경력", "경력 공고만 (신입·신입/경력·경력무관 제외)"),
            ("고용형태", ", ".join(cond.employment_types)),
            ("검색 사이트", ", ".join(cond.sites)),
            ("제외 직무 단어", ", ".join(cond.exclude_title_keywords) or "없음"),
            ("제외 업체", ", ".join(cond.exclude_companies) or "없음"),
        ]
    if not df.empty and "출처" in df:
        counts = df["출처"].str.split(", ").explode().value_counts()
        rows.append(("사이트별 건수", "   ".join(f"{k} {v}건" for k, v in counts.items())))
    for i, (k, v) in enumerate(rows, start=3):
        a, b = ws.cell(i, 1, k), ws.cell(i, 2, v)
        a.font = Font(name=FONT_NAME, size=10, bold=True, color=NAVY)
        a.fill = LABEL_FILL
        b.font = Font(name=FONT_NAME, size=10)
        for cell in (a, b):
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        ws.row_dimensions[i].height = LINE_HEIGHT * _lines_needed(v, 70) + 8
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def build_excel(df: pd.DataFrame, cond: SearchCondition | None = None) -> bytes:
    created = now_kst()
    wb = Workbook()
    ws = wb.active
    ws.title = "채용공고"
    _write_results(ws, df, cond, created)
    _write_summary(wb.create_sheet("검색 조건"), df, cond, created)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
