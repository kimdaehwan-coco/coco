"""findJob — 맞춤 채용공고 검색 화면 (Streamlit).

실행:  streamlit run app.py
"""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from core.clock import now_kst, today_kst
from core.codes import (DEFAULT_EXCLUDE_TITLE_KEYWORDS, DEFAULT_JOB_CATEGORIES, DEFAULT_REGIONS,
                        EMPLOYMENT_TYPES, JOB_CATEGORIES, REGIONS, SITES)
from core.export import build_excel
from core.filters import parse_exclude_list
from core.models import SearchCondition
from core.search import run_search

ROOT = Path(__file__).parent
EXCLUDE_FILE = ROOT / "config" / "exclude_companies.txt"
EXCLUDE_TITLE_FILE = ROOT / "config" / "exclude_title_keywords.txt"


def load_list(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def save_list(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parse_exclude_list(text)), encoding="utf-8")


st.set_page_config(page_title="findJob · 채용공고 모아보기", layout="wide")
# 색·글꼴 등 기본 테마는 .streamlit/config.toml, 여기서는 배치와 머리 영역만 다듬는다
st.markdown("""
<style>
/* 좌우 여백을 줄여 결과 표에 쓸 폭을 넓힌다 (가로 스크롤 방지), 위 여백도 줄인다 */
.block-container, [data-testid='stMainBlockContainer'] {
  padding: 1.6rem 1.5rem 3rem 1.5rem; max-width: 100%;
}
[data-testid='stHeader'] { background: transparent; }
/* 머리 영역 */
.fj-hero {
  background: linear-gradient(120deg, #1F3864 0%, #2F5597 100%);
  color: #fff; border-radius: 0.8rem; padding: 1.1rem 1.4rem; margin-bottom: 0.4rem;
}
.fj-hero h1 { color: #fff; font-size: 1.55rem; font-weight: 700; margin: 0; padding: 0; }
.fj-hero p  { color: #D6E0F5; font-size: 0.9rem; margin: 0.3rem 0 0 0; }
.fj-hero .fj-site {
  display: inline-block; background: rgba(255,255,255,0.16); border-radius: 999px;
  padding: 0.05rem 0.6rem; margin-right: 0.3rem; font-size: 0.8rem; color: #fff;
}
/* 구역 제목 */
.fj-section { font-size: 1.02rem; font-weight: 700; color: #1F3864; margin: 0.1rem 0 0.2rem 0; }
.fj-section span { font-size: 0.82rem; font-weight: 400; color: #6B7280; margin-left: 0.5rem; }
/* 검색 조건·결과 상자는 흰 카드처럼 */
.st-key-search_card, .st-key-result_card { background: #FFFFFF; box-shadow: 0 1px 3px rgba(31,56,100,0.06); }
/* 숫자 카드 */
[data-testid='stMetricValue'] { color: #1F3864; font-weight: 700; }
/* 휴대폰 카드 보기의 공고 한 건 */
.fj-card-title { font-weight: 700; font-size: 0.98rem; line-height: 1.35; }
.fj-card-title a { color: #1F3864; text-decoration: none; }
.fj-card-meta { color: #4B5563; font-size: 0.84rem; line-height: 1.5; margin-top: 0.15rem; }
.fj-card-meta b { color: #1F2937; font-weight: 600; }
.fj-badge {
  display: inline-block; background: #EEF2F9; color: #2F5597; border-radius: 999px;
  padding: 0 0.5rem; font-size: 0.75rem; margin-right: 0.25rem;
}
/* 좁은 화면(휴대폰)에서는 여백·머리 글자를 줄인다 */
@media (max-width: 640px) {
  .block-container, [data-testid='stMainBlockContainer'] { padding: 0.8rem 0.6rem 2rem 0.6rem; }
  .fj-hero { padding: 0.8rem 1rem; }
  .fj-hero h1 { font-size: 1.2rem; }
  .fj-hero p { font-size: 0.8rem; }
  .fj-section span { display: block; margin-left: 0; }
  .st-key-pager button { min-width: 2.1rem; padding: 0 0.45rem; }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="fj-hero">
  <h1>findJob · 채용공고 모아보기</h1>
  <p><span class="fj-site">잡코리아</span><span class="fj-site">사람인</span><span class="fj-site">고용24</span>
     에서 조건에 맞는 경력 공고만 한 번에 모아 보여줍니다.</p>
</div>
""", unsafe_allow_html=True)


def section(title: str, note: str = "") -> None:
    st.markdown(f'<div class="fj-section">{title}<span>{note}</span></div>', unsafe_allow_html=True)


# ── 제외 단어·업체: 파일에서 읽어 세션에 목록으로 들고 있고, 바뀔 때마다 바로 파일에 저장한다 ──
if "ex_titles" not in st.session_state:
    st.session_state["ex_titles"] = parse_exclude_list(
        load_list(EXCLUDE_TITLE_FILE, "\n".join(DEFAULT_EXCLUDE_TITLE_KEYWORDS)))
if "ex_companies" not in st.session_state:
    st.session_state["ex_companies"] = parse_exclude_list(load_list(EXCLUDE_FILE))


def _save_excludes(key: str, path: Path) -> None:
    save_list(path, "\n".join(st.session_state[key]))


def _add_bulk(key: str, path: Path) -> None:
    """붙여넣은 여러 개(쉼표·줄바꿈 구분)를 목록에 더한다. 이미 있는 것(대소문자 무시)은 건너뛴다."""
    have = {v.lower() for v in st.session_state[key]}
    new = [v for v in dict.fromkeys(parse_exclude_list(st.session_state[f"{key}_bulk"])) if v.lower() not in have]
    st.session_state[key] = st.session_state[key] + new
    st.session_state[f"{key}_bulk"] = ""
    _save_excludes(key, path)


def _reset(key: str, path: Path, values: list[str]) -> None:
    st.session_state[key] = list(values)
    _save_excludes(key, path)


def exclude_editor(key: str, path: Path, label: str, help_text: str, reset_to: list[str] | None = None) -> None:
    # 태그 입력: 칸에 글자를 치고 Enter 로 하나씩 추가, 태그의 × 로 삭제
    st.multiselect(label, options=st.session_state[key], key=key, accept_new_options=True,
                   placeholder="입력 후 Enter 로 추가", help=help_text, on_change=_save_excludes, args=(key, path))
    st.text_input("여러 개 한 번에 추가", key=f"{key}_bulk", placeholder="쉼표로 구분해 붙여넣고 Enter",
                  on_change=_add_bulk, args=(key, path), label_visibility="collapsed")
    if reset_to is not None:
        st.button("기본값으로 되돌리기", key=f"{key}_reset", on_click=_reset, args=(key, path, reset_to),
                  type="tertiary", icon=":material/restart_alt:")


with st.container(border=True, key="search_card"):
    section("검색 조건", "경력은 '경력' 공고만 찾습니다 (신입·신입/경력·경력무관 제외)")
    today = today_kst()  # 클라우드 서버는 UTC 라서 한국 날짜로 맞춘다
    # 1줄: 기간 · 지역 · 고용형태
    c1, c2, c3, c4 = st.columns([1.3, 1.3, 2, 2])
    date_from = c1.date_input("기간 FROM", value=today, format="YYYY-MM-DD",
                              help="공고 등록일 기준입니다. 사람인은 수정된 공고면 수정일 기준입니다.")
    date_to = c2.date_input("기간 TO", value=today, format="YYYY-MM-DD")
    regions = c3.multiselect("지역", list(REGIONS), default=DEFAULT_REGIONS)
    emps = c4.multiselect("고용형태", EMPLOYMENT_TYPES, default=EMPLOYMENT_TYPES)

    # 2줄: 직무 · 사이트
    j1, j2 = st.columns([3, 2])
    jobs = j1.multiselect("직무",
                          list(JOB_CATEGORIES), default=DEFAULT_JOB_CATEGORIES,
                          help="목록을 펼치면 풀스택·웹퍼블리셔·Java/Spring·PHP·Node.js·웹기획자도 고를 수 있습니다. "
                               "직무를 많이 고를수록 검색이 오래 걸립니다.")
    sites = j2.multiselect("검색 사이트", SITES, default=SITES)

    # 3줄: 제외 설정(팝업) · 페이지 수 · 검색 버튼
    # 제외 단어·업체는 자주 보는 정보가 아니라서 '제외 설정' 버튼 안에 넣고, 태그처럼 하나씩 넣고 빼게 한다.
    e1, e2, e3 = st.columns([2, 2, 1.3], vertical_alignment="bottom")
    n_titles, n_companies = len(st.session_state["ex_titles"]), len(st.session_state["ex_companies"])
    with e1.popover(f"제외 설정 · 단어 {n_titles}개 · 업체 {n_companies}개", icon=":material/block:",
                    width="stretch"):
        exclude_editor("ex_titles", EXCLUDE_TITLE_FILE, "제외할 직무 단어 (공고 제목 기준)",
                       "공고 제목에 이 단어가 있으면 뺍니다. 띄어쓰기·대소문자는 무시합니다. 모두 지우면 이 필터를 쓰지 않습니다.",
                       reset_to=DEFAULT_EXCLUDE_TITLE_KEYWORDS)
        st.divider()
        exclude_editor("ex_companies", EXCLUDE_FILE, "제외할 업체",
                       "(주), ㈜, 주식회사, 띄어쓰기는 무시하고 이름 일부만 맞아도 제외합니다.")
    max_pages = e2.slider("검색어별 최대 페이지 수", 1, 10, 5,
                          help="기간을 길게 잡으면 늘려 주세요. 클수록 오래 걸립니다.")
    run = e3.button("검색", type="primary", width="stretch")
    exclude_titles = list(st.session_state["ex_titles"])
    exclude_companies = list(st.session_state["ex_companies"])

if run:
    problems = []
    if date_from > date_to:
        problems.append("기간 FROM 이 TO 보다 늦습니다.")
    for label, val in (("직무", jobs), ("지역", regions), ("고용형태", emps), ("검색 사이트", sites)):
        if not val:
            problems.append(f"{label}를 하나 이상 선택하세요.")
    if problems:
        for p in problems:
            st.error(p)
        st.stop()

    cond = SearchCondition(date_from=date_from, date_to=date_to, job_categories=jobs, regions=regions,
                           employment_types=emps, sites=sites, exclude_companies=exclude_companies,
                           exclude_title_keywords=exclude_titles, max_pages=max_pages)
    with st.status("검색 중…", expanded=True) as status:
        lines: list[str] = []
        box = st.empty()

        def log(msg: str) -> None:
            lines.append(msg)  # 스레드에서 불리므로 화면 갱신은 끝난 뒤에 한 번만

        result = run_search(cond, log=log)
        box.code("\n".join(lines) or "(로그 없음)")
        status.update(label=f"검색 완료: {len(result.postings)}건", state="complete", expanded=False)
    st.session_state["result"] = result
    st.session_state["cond"] = cond
    # 새 결과에는 이전 선택·쪽 번호를 남기지 않는다
    for k in [k for k in st.session_state if str(k).startswith(("result_table", "chk_"))]:
        del st.session_state[k]
    st.session_state["page"] = 1
    st.session_state["selected_ids"] = set()

result = st.session_state.get("result")
if result is None:
    st.info("위에서 조건을 고르고 **검색**을 누르세요.")
    st.stop()

for site, err in result.errors.items():
    st.error(f"{site} 수집 실패: {err}")
if "고용24" in st.session_state["cond"].sites and "프리랜서" in st.session_state["cond"].employment_types:
    st.caption("고용24에는 '프리랜서' 고용형태 구분이 없어 정규직·계약직만 조회합니다.")

df = pd.DataFrame([p.to_row() for p in result.postings])
m1, m2, m3 = st.columns(3)
m1.metric("최종 공고 수", f"{len(df)}건", border=True)
m2.metric("수집한 공고 (필터 전)", f"{sum(result.raw_counts.values())}건", border=True)
m3.metric("제외된 공고", f"{sum(result.dropped.values())}건", border=True)
with st.expander("사이트별 수집 / 필터별 제외 건수"):
    x1, x2 = st.columns(2)
    x1.dataframe(pd.DataFrame({"사이트": list(result.raw_counts), "수집 건수": list(result.raw_counts.values())}),
                 hide_index=True, width="stretch")
    x2.dataframe(pd.DataFrame({"필터": list(result.dropped), "제외 건수": list(result.dropped.values())}),
                 hide_index=True, width="stretch")

if df.empty:
    st.warning("조건에 맞는 공고가 없습니다. 기간을 늘리거나 지역·직무를 넓혀 보세요.")
    st.stop()

# ── 쪽 나누기: 한 화면에 PAGE_SIZE 건씩 ──
PAGE_SIZE = 10
total_pages = max(1, -(-len(df) // PAGE_SIZE))
page = min(max(1, st.session_state.get("page", 1)), total_pages)
st.session_state["page"] = page
start = (page - 1) * PAGE_SIZE


def go_page(n: int) -> None:
    st.session_state["page"] = n


# 행을 선택하면 그 줄의 배경색을 바꿔 눈에 띄게 한다 (왼쪽 체크칸으로 여러 줄 선택 가능)
# Streamlit은 화면에서 사라진 표(다른 쪽)의 선택을 지우므로, 선택한 공고 번호(전체 기준)를 따로 기억해 두고
# 그 쪽으로 돌아오면 selection_default 로 체크칸을 다시 채운다.
TABLE_KEY = f"result_table_{page}"
SELECTED_STYLE = "background-color: #FFE9A8; color: #1F2937; font-weight: 600"
store: set[int] = st.session_state.setdefault("selected_ids", set())


def on_table_select() -> None:
    rows = st.session_state[TABLE_KEY]["selection"]["rows"]
    store.difference_update(range(start, start + PAGE_SIZE))  # 이 쪽 선택을 표의 체크 상태로 바꿔 넣는다
    store.update(start + i for i in rows)


selected_rows = {i for i in store if start <= i < start + PAGE_SIZE}
selected_total = len(store)
# 화면 표는 가로 스크롤이 생기지 않게 열 너비를 작게 정해 둔다.
# 화면이 더 넓으면 Streamlit이 남는 폭만큼 열을 늘려 채운다. 칸보다 긴 글자는 … 으로 줄이고, 칸을 누르면 전체가 보인다.
# '날짜구분' 열은 등록일 옆에 (수정)으로 합쳐 열 수를 줄인다. 엑셀·CSV는 원래 열 그대로 내려준다.
view = df.copy()
view["등록일"] = view["등록일"] + view["날짜구분"].map(lambda v: " (수정)" if v == "수정일" else "")
view = view.drop(columns=["날짜구분"])
# 합계(체크칸 포함 약 900px)를 창 너비 1024px 화면에서도 들어가게 맞춘 값 (결과 카드 안쪽 여백 포함)
COLUMN_WIDTHS = {"출처": 55, "회사명": 100, "공고 제목": 170, "직무": 85, "지역": 75, "경력": 65,
                 "고용형태": 65, "급여": 60, "등록일": 80, "마감일": 65}
column_config = {name: st.column_config.TextColumn(name, width=w) for name, w in COLUMN_WIDTHS.items()}
column_config["링크"] = st.column_config.LinkColumn("링크", display_text="공고 보기", width=60)

page_view = view.iloc[start:start + PAGE_SIZE]  # 인덱스는 전체 기준 번호 그대로
stamp = now_kst().strftime("%Y%m%d_%H%M")
cond_for_file = st.session_state["cond"]

# 휴대폰으로 열면 표 대신 카드 목록으로 보여준다 (표는 열이 많아 휴대폰 폭에 들어가지 않음)
_ua = (st.context.headers.get("User-Agent") or "").lower()
IS_MOBILE = any(k in _ua for k in ("iphone", "ipad", "android", "mobile"))


def toggle_card(i: int) -> None:
    if st.session_state[f"chk_{i}"]:
        store.add(i)
    else:
        store.discard(i)


def card_html(row: pd.Series) -> str:
    e = lambda v: html.escape(str(v or ""))  # noqa: E731  공고 제목에 <, & 같은 글자가 있어도 깨지지 않게
    title = f'<a href="{e(row["링크"])}" target="_blank">{e(row["공고 제목"])}</a>' if row["링크"] else e(row["공고 제목"])
    badges = "".join(f'<span class="fj-badge">{e(v)}</span>' for v in (row["출처"], row["직무"]) if v)
    return (f'<div class="fj-card-title">{title}</div>'
            f'<div class="fj-card-meta">{badges}</div>'
            f'<div class="fj-card-meta"><b>{e(row["회사명"])}</b> · {e(row["지역"])}</div>'
            f'<div class="fj-card-meta">{e(row["경력"])} · {e(row["고용형태"])} · 급여 {e(row["급여"]) or "-"}</div>'
            f'<div class="fj-card-meta">등록 {e(row["등록일"])} · 마감 {e(row["마감일"]) or "-"}</div>')


with st.container(border=True, key="result_card"):
    # 구역 제목 + 보기 방식 + 오른쪽에 다운로드 버튼 (휴대폰에서는 위아래로 쌓인다)
    h1, h0, h2, h3 = st.columns([5, 1.6, 1.3, 1.3], vertical_alignment="center")
    mode = h0.segmented_control("보기", ["표", "카드"], default="카드" if IS_MOBILE else "표",
                                key="view_mode", label_visibility="collapsed", required=True)
    with h1:
        hint = ("왼쪽 체크칸으로 줄 선택 · 잘린 글자는 칸을 누르면 전체가 보입니다" if mode == "표"
                else "제목을 누르면 공고가 열립니다 · '선택'으로 표시해 둘 수 있습니다")
        section(f"검색 결과 {len(df)}건", ("%d건 선택됨 · " % selected_total if selected_total else "") + hint)
    # 파일은 미리 만들거나 저장하지 않고, 다운로드 버튼을 누를 때 만들어서 바로 내려준다
    h2.download_button("엑셀 다운로드", lambda: build_excel(df, cond_for_file), file_name=f"jobs_{stamp}.xlsx",
                       type="primary", icon=":material/download:", width="stretch",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    h3.download_button("CSV 다운로드", lambda: df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"jobs_{stamp}.csv", mime="text/csv", width="stretch")

    if mode == "표":
        styled = page_view.style.apply(lambda r: [SELECTED_STYLE if r.name in selected_rows else ""] * len(r), axis=1)
        st.dataframe(
            styled, width="stretch", hide_index=True, key=TABLE_KEY, row_height=35,
            height=(len(page_view) + 1) * 35 + 3,  # 줄 수에 맞춘 높이 (세로 스크롤 없음)
            on_select=on_table_select, selection_mode="multi-row", column_config=column_config,
            selection_default={"selection": {"rows": sorted(i - start for i in selected_rows)}},
        )
    else:
        # 선택한 카드는 표의 선택 줄과 같은 노란색 배경
        if selected_rows:
            css = ", ".join(f".st-key-card_{i}" for i in selected_rows)
            st.markdown(f"<style>{css} {{ background: #FFE9A8; }}</style>", unsafe_allow_html=True)
        for idx, row in page_view.iterrows():
            with st.container(border=True, key=f"card_{idx}"):
                st.markdown(card_html(row), unsafe_allow_html=True)
                st.checkbox("선택", value=idx in store, key=f"chk_{idx}", on_change=toggle_card, args=(idx,))

    # 쪽 이동: « ‹ 1 2 3 … › »  (쪽 번호는 현재 쪽 주변 최대 10개, 휴대폰은 5개)
    # 가로 컨테이너라 휴대폰에서도 세로로 쌓이지 않고, 자리가 모자라면 다음 줄로 넘어간다
    if total_pages > 1:
        span = 5 if IS_MOBILE else 10
        first = max(1, min(page - span // 2, total_pages - span + 1))
        numbers = list(range(first, min(total_pages, first + span - 1) + 1))
        nav = [("‹", page - 1, page == 1)] + [(str(n), n, False) for n in numbers] + [("›", page + 1, page == total_pages)]
        if not IS_MOBILE:  # 휴대폰은 한 줄에 들어가도록 처음·마지막 쪽 버튼을 뺀다
            nav = [("«", 1, page == 1)] + nav + [("»", total_pages, page == total_pages)]
        with st.container(horizontal=True, horizontal_alignment="center", gap="small", key="pager"):
            for label, target, disabled in nav:
                st.button(label, key=f"pg_{label}_{target}", on_click=go_page, args=(target,), disabled=disabled,
                          type="primary" if label == str(page) else "secondary")
        st.markdown(f"<div style='text-align:center;color:#6B7280;font-size:0.82rem'>"
                    f"{page} / {total_pages}쪽 · {start + 1}–{start + len(page_view)}번째 공고</div>",
                    unsafe_allow_html=True)
