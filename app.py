"""findJob — 맞춤 채용공고 검색 화면 (Streamlit).

실행:  streamlit run app.py
"""
from __future__ import annotations

import html
import importlib
import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st


def _reload_changed_modules() -> None:
    """서버가 켜진 뒤 바뀐 core/·scrapers/ 파일을 다시 읽는다.

    Streamlit 클라우드는 GitHub에서 새 코드를 받으면 app.py만 다시 실행하고, 이미 불러 둔 core/ 모듈은
    예전 것을 그대로 쓴다. 그러면 app.py가 새로 만든 함수를 못 찾아 ImportError가 난다(2026-11-10).
    서버 시작 후 고쳐진 파일만, 고쳐질 때마다 한 번씩 다시 읽는다. 의존 순서대로 읽어야 해서 순서를 정해 둔다.
    """
    import core  # noqa: F401  (패키지에 서버 시작 시각을 기록해 두는 용도)
    # 서버(파이썬 프로세스)가 켜진 시각. 리눅스(클라우드)는 /proc 에서 실제 시작 시각을 읽고,
    # 없으면(Windows) 이 코드가 처음 돈 시각을 쓴다.
    proc = Path(f"/proc/{os.getpid()}")
    started = core.__dict__.setdefault("_fj_proc_started", proc.stat().st_ctime if proc.exists() else time.time())
    order = ["core.clock", "core.codes", "core.models", "core.filters", "core.store", "core.export",
             "scrapers.base", "scrapers.saramin", "scrapers.jobkorea", "scrapers.work24", "core.search"]
    for name in order:
        mod = sys.modules.get(name)
        path = getattr(mod, "__file__", None)
        if not path:
            continue
        mtime = Path(path).stat().st_mtime
        if mtime > started and getattr(mod, "_fj_mtime", None) != mtime:
            mod = importlib.reload(mod)
            mod._fj_mtime = mtime


_reload_changed_modules()

from core.clock import now_kst, today_kst  # noqa: E402  (위에서 바뀐 모듈을 다시 읽은 뒤 가져온다)
from core.codes import (DEFAULT_EXCLUDE_TITLE_KEYWORDS, DEFAULT_JOB_CATEGORIES, DEFAULT_REGIONS,
                        EMPLOYMENT_TYPES, JOB_CATEGORIES, REGIONS, SITES)
from core.export import build_excel
from core.filters import clean_company_name, is_excluded, normalize_company, parse_exclude_list
from core.models import SearchCondition
from core.search import run_search  # noqa: E402
from core.store import apply_change, make_store  # noqa: E402

ROOT = Path(__file__).parent
# 기본 목록: GitHub에 올라가는 원본. 앱이 실행 중에 이 파일을 고치지 않는다 (읽기만).
EXCLUDE_FILE = ROOT / "config" / "exclude_companies.txt"
EXCLUDE_TITLE_FILE = ROOT / "config" / "exclude_title_keywords.txt"
# 화면에서 고친 목록은 core/store.py 저장소에 따로 둔다 (토큰이 없으면 config/user/, GitHub에 올리지 않음).
USER_DIR = ROOT / "config" / "user"


def load_list(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def default_titles() -> list[str]:
    return parse_exclude_list(load_list(EXCLUDE_TITLE_FILE, "\n".join(DEFAULT_EXCLUDE_TITLE_KEYWORDS)))


def default_companies() -> list[str]:
    return parse_exclude_list(load_list(EXCLUDE_FILE))


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


# ── 제외 단어·업체 ──
# 저장소(core/store.py): Secrets 에 GITHUB_TOKEN 이 있으면 GitHub settings 브랜치, 없으면 config/user/ 파일.
#   클라우드 디스크는 앱이 다시 켜질 때마다 지워져서, 오래 보관하려면 GitHub 쪽을 써야 한다.
# 저장소가 '진짜' 목록이다. 매 실행마다 저장소(20초 캐시)에서 읽어 세션에 맞춘다 → 다른 창에서 고친 것도 보인다.
# 고칠 때는 목록 전체를 덮어쓰지 않고 '추가/삭제한 것'만 최신 내용에 반영한다 → 여러 창이 서로 지우지 않는다.
# 태그 입력칸은 별도 키("…_w")를 쓴다. 입력칸 상태가 어떤 이유로 비어도 목록은 남아 있게 하기 위해서다.
def _secrets() -> tuple[dict, str]:
    """Secrets 에서 GITHUB_TOKEN/GITHUB_REPO 를 읽는다. 두 번째 값은 화면에 보여줄 상태(값은 절대 넣지 않음)."""
    try:
        names = list(st.secrets.keys())
    except FileNotFoundError:
        return {}, "Secrets 없음"
    except Exception as e:  # TOML 형식이 틀렸을 때 등
        return {}, f"Secrets를 읽지 못함 ({type(e).__name__}: 형식 확인 필요)"
    found: dict = {}
    for k in ("GITHUB_TOKEN", "GITHUB_REPO"):
        v = st.secrets.get(k)
        if v is None:  # [github] 같은 묶음 안에 넣은 경우도 찾아본다
            for n in names:
                sec = st.secrets.get(n)
                if hasattr(sec, "get") and sec.get(k) is not None:
                    v = sec.get(k)
                    break
        if isinstance(v, str) and v.strip():
            found[k] = v.strip()
    if "GITHUB_TOKEN" in found:
        return found, "Secrets의 GITHUB_TOKEN 사용"
    return found, ("Secrets에 GITHUB_TOKEN 이 없음" + (f" (있는 이름: {', '.join(names)})" if names else " (비어 있음)"))


_SECRETS, SECRETS_STATUS = _secrets()
STORE = make_store(_SECRETS, USER_DIR)
STORE_NAMES = {"ex_titles": "exclude_title_keywords", "ex_companies": "exclude_companies"}
DEFAULTS = {"ex_titles": default_titles, "ex_companies": default_companies}


@st.cache_data(ttl=20, show_spinner=False)
def _load_saved(name: str, kind: str) -> list[str] | None:  # kind: 저장소가 바뀌면 캐시도 따로
    return STORE.load(name)


for _key, _name in STORE_NAMES.items():
    try:
        _saved = _load_saved(_name, STORE.kind)
    except Exception as _e:  # GitHub 이 잠깐 안 될 때: 지금 화면 값을 그대로 쓴다
        _saved = st.session_state.get(_key)
        st.session_state["store_error"] = f"저장된 목록을 불러오지 못했어요 ({type(_e).__name__}). 잠시 뒤 다시 열어 주세요."
    _latest = list(_saved) if _saved is not None else DEFAULTS[_key]()
    if st.session_state.get(_key) != _latest:
        st.session_state[_key] = _latest
        st.session_state[f"{_key}_w"] = list(_latest)


def _change(key: str, add: list[str] = (), remove: list[str] = (), replace: list[str] | None = None) -> None:
    """저장소의 최신 목록에 추가/삭제(또는 통째 교체)를 반영하고 화면 값도 맞춘다."""
    def fn(cur: list[str]) -> list[str]:
        return list(replace) if replace is not None else apply_change(cur, add, remove)
    try:
        new = STORE.update(STORE_NAMES[key], fn, DEFAULTS[key]())
    except Exception as e:
        st.session_state["store_error"] = f"저장하지 못했어요 ({type(e).__name__}). 잠시 뒤 다시 해 주세요."
        new = fn(st.session_state[key])
    _load_saved.clear()
    st.session_state[key] = new
    st.session_state[f"{key}_w"] = list(new)


def _on_tags(key: str) -> None:
    old, new = st.session_state[key], st.session_state[f"{key}_w"]
    old_n, new_n = {v.lower() for v in old}, {v.lower() for v in new}
    _change(key, add=[v for v in new if v.lower() not in old_n], remove=[v for v in old if v.lower() not in new_n])


def _add_bulk(key: str) -> None:
    """붙여넣은 여러 개(쉼표·줄바꿈 구분)를 목록에 더한다. 이미 있는 것(대소문자 무시)은 건너뛴다."""
    items = parse_exclude_list(st.session_state[f"{key}_bulk"])
    st.session_state[f"{key}_bulk"] = ""
    _change(key, add=items)


def _reset(key: str) -> None:
    _change(key, replace=DEFAULTS[key]())


def exclude_editor(key: str, label: str, help_text: str) -> None:
    # 태그 입력: 칸에 글자를 치고 Enter 로 하나씩 추가, 태그의 × 로 삭제
    wkey = f"{key}_w"
    if wkey not in st.session_state:
        st.session_state[wkey] = list(st.session_state[key])
    options = list(dict.fromkeys(st.session_state[key] + st.session_state[wkey]))
    st.multiselect(label, options=options, key=wkey, accept_new_options=True,
                   placeholder="입력 후 Enter 로 추가", help=help_text, on_change=_on_tags, args=(key,))
    st.text_input("여러 개 한 번에 추가", key=f"{key}_bulk", placeholder="쉼표로 구분해 붙여넣고 Enter",
                  on_change=_add_bulk, args=(key,), label_visibility="collapsed")
    st.button("기본값으로 되돌리기", key=f"{key}_reset", on_click=_reset, args=(key,),
              type="tertiary", icon=":material/restart_alt:", help="GitHub에 올라가 있는 기본 목록으로 돌아갑니다.")
    if key == "ex_companies":
        st.caption(f"저장 위치: {STORE.label} · {SECRETS_STATUS}")


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
                          help="목록을 펼치면 웹퍼블리셔·PHP·Node.js·웹기획자도 고를 수 있습니다. "
                               "직무를 많이 고를수록 검색이 오래 걸립니다.")
    sites = j2.multiselect("검색 사이트", SITES, default=SITES)

    # 3줄: 제외 설정(팝업) · 페이지 수 · 검색 버튼
    # 제외 단어·업체는 자주 보는 정보가 아니라서 '제외 설정' 버튼 안에 넣고, 태그처럼 하나씩 넣고 빼게 한다.
    e1, e2, e3 = st.columns([2, 2, 1.3], vertical_alignment="bottom")
    n_titles, n_companies = len(st.session_state["ex_titles"]), len(st.session_state["ex_companies"])
    with e1.popover(f"제외 설정 · 단어 {n_titles}개 · 업체 {n_companies}개", icon=":material/block:",
                    width="stretch"):
        exclude_editor("ex_titles", "제외할 직무 단어 (공고 제목 기준)",
                       "공고 제목에 이 단어가 있으면 뺍니다. 띄어쓰기·대소문자는 무시합니다. 모두 지우면 이 필터를 쓰지 않습니다.")
        st.divider()
        exclude_editor("ex_companies", "제외할 업체",
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

if _msg := st.session_state.pop("exclude_msg", None):
    st.toast(_msg, icon=":material/block:")
if _err := st.session_state.pop("store_error", None):
    st.warning(_err, icon=":material/cloud_off:")

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
# table_ver: 결과에서 공고를 빼면 올려서 표를 새로 만든다 (브라우저에 남은 체크 표시까지 지우려고)
TABLE_KEY = f"result_table_{st.session_state.get('table_ver', 0)}_{page}"
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


def exclude_from_results(companies: list[str]) -> None:
    """회사들을 제외 업체 목록에 넣고, 지금 결과에서도 바로 뺀다."""
    names = [n for n in dict.fromkeys(clean_company_name(c) for c in companies) if n]
    if not names:
        return
    have = {normalize_company(v) for v in st.session_state["ex_companies"]}
    added = [n for n in names if normalize_company(n) not in have]
    _change("ex_companies", add=added)

    res = st.session_state["result"]
    before = len(res.postings)
    res.postings = [p for p in res.postings if not is_excluded(p.company, names)]
    removed = before - len(res.postings)
    res.dropped["제외업체"] = res.dropped.get("제외업체", 0) + removed
    st.session_state["cond"].exclude_companies = list(st.session_state["ex_companies"])  # 엑셀 '검색 조건' 시트용
    # 결과 줄 번호가 바뀌므로 선택·체크 상태는 비운다 (쪽 번호는 남는 줄 수에 맞게 위에서 다시 조정됨)
    for k in [k for k in st.session_state if str(k).startswith(("result_table", "chk_"))]:
        del st.session_state[k]
    st.session_state["selected_ids"] = set()
    st.session_state["table_ver"] = st.session_state.get("table_ver", 0) + 1
    st.session_state["exclude_msg"] = (f"제외 업체에 추가: {', '.join(added)}" if added else "이미 제외 목록에 있는 업체예요") \
        + f" · 결과에서 {removed}건 뺐어요"


VER = st.session_state.get("table_ver", 0)


def toggle_card(i: int) -> None:
    if st.session_state[f"chk_{VER}_{i}"]:
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

    # 선택한 공고(표의 체크칸·카드의 '선택', 모든 쪽 합계)의 회사를 한 번에 제외 업체로
    sel_companies = sorted({df.at[i, "회사명"] for i in store if i < len(df)})
    st.button(f"선택한 공고의 업체 {len(sel_companies)}곳을 제외 업체에 포함" if sel_companies
              else "제외 업체에 포함 (먼저 공고를 선택하세요)",
              key="exc_selected", icon=":material/block:", disabled=not sel_companies,
              on_click=exclude_from_results, args=(sel_companies,),
              help="선택한 공고의 회사를 제외 업체 목록에 넣고, 지금 결과에서도 그 회사 공고를 모두 뺍니다.")

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
                with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
                    st.checkbox("선택", value=idx in store, key=f"chk_{VER}_{idx}", on_change=toggle_card, args=(idx,))
                    st.button("제외 업체에 포함", key=f"exc_{VER}_{idx}", type="tertiary", icon=":material/block:",
                              on_click=exclude_from_results, args=([row["회사명"]],),
                              help=f"'{row['회사명']}'을(를) 제외 업체에 넣고 결과에서 뺍니다.")

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
