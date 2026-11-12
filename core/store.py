"""제외 단어·업체 목록을 오래 보관하는 저장소.

- 클라우드(Streamlit Community Cloud)의 디스크는 앱이 다시 켜질 때마다(잠들었다 깸, Reboot, 새 코드 반영) 지워진다.
  그래서 Streamlit Secrets 에 GITHUB_TOKEN 이 있으면 GitHub 저장소의 `settings` 브랜치에 저장한다.
  (main 이 아닌 별도 브랜치라서 저장해도 앱이 새로 배포되지 않는다.)
- 토큰이 없으면(이 PC 등) `config/user/` 폴더의 파일에 저장한다.

여러 창(세션)이 동시에 고쳐도 서로 덮어쓰지 않도록, 저장은 항상 '최신 내용을 읽고 → 추가/삭제만 반영 → 쓰기'로 한다.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

import requests

from .filters import parse_exclude_list

API = "https://api.github.com"
BRANCH = "settings"
TIMEOUT = 15


def _norm(v: str) -> str:
    return v.strip().lower()


def apply_change(current: list[str], add: list[str] = (), remove: list[str] = ()) -> list[str]:
    """current 에 add 를 더하고 remove 를 뺀다 (대소문자 무시, 순서 유지, 중복 없음)."""
    gone = {_norm(v) for v in remove}
    out = [v for v in current if _norm(v) not in gone]
    have = {_norm(v) for v in out}
    for v in add:
        if v.strip() and _norm(v) not in have:
            out.append(v.strip())
            have.add(_norm(v))
    return out


class LocalStore:
    """config/user/<name>.txt 에 저장 (서버가 다시 켜지면 클라우드에서는 사라짐)."""

    kind = "local"
    label = "이 서버의 임시 파일 (앱이 다시 켜지면 사라짐)"

    def __init__(self, folder: Path):
        self.folder = folder

    def load(self, name: str) -> list[str] | None:
        p = self.folder / f"{name}.txt"
        return parse_exclude_list(p.read_text(encoding="utf-8")) if p.exists() else None

    def update(self, name: str, change: Callable[[list[str]], list[str]], default: list[str]) -> list[str]:
        cur = self.load(name)
        new = change(default if cur is None else cur)
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{name}.txt").write_text("\n".join(new), encoding="utf-8")
        return new


class GitHubStore:
    """GitHub 저장소의 settings 브랜치 `exclude/<name>.txt` 에 저장."""

    kind = "github"
    label = "GitHub settings 브랜치 (앱이 다시 켜져도 남음)"

    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})

    def _url(self, name: str) -> str:
        return f"{API}/repos/{self.repo}/contents/exclude/{name}.txt"

    def _read(self, name: str) -> tuple[list[str] | None, str | None]:
        r = self.s.get(self._url(name), params={"ref": BRANCH}, timeout=TIMEOUT)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        j = r.json()
        return parse_exclude_list(base64.b64decode(j["content"]).decode("utf-8")), j["sha"]

    def _ensure_branch(self) -> None:
        r = self.s.get(f"{API}/repos/{self.repo}/git/ref/heads/{BRANCH}", timeout=TIMEOUT)
        if r.status_code == 200:
            return
        main = self.s.get(f"{API}/repos/{self.repo}/git/ref/heads/main", timeout=TIMEOUT)
        main.raise_for_status()
        c = self.s.post(f"{API}/repos/{self.repo}/git/refs",
                        json={"ref": f"refs/heads/{BRANCH}", "sha": main.json()["object"]["sha"]}, timeout=TIMEOUT)
        if c.status_code not in (201, 422):  # 422: 그 사이 다른 창이 만든 경우
            c.raise_for_status()

    def load(self, name: str) -> list[str] | None:
        try:
            return self._read(name)[0]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:  # 브랜치가 아직 없음
                return None
            raise

    def update(self, name: str, change: Callable[[list[str]], list[str]], default: list[str]) -> list[str]:
        self._ensure_branch()
        for _ in range(4):  # 다른 창이 그 사이 저장했으면(409/422) 최신 내용을 다시 읽어 반영
            cur, sha = self._read(name)
            new = change(default if cur is None else cur)
            body = {"message": f"제외 목록 저장: {name}", "branch": BRANCH,
                    "content": base64.b64encode("\n".join(new).encode("utf-8")).decode("ascii")}
            if sha:
                body["sha"] = sha
            r = self.s.put(self._url(name), json=body, timeout=TIMEOUT)
            if r.status_code in (200, 201):
                return new
            if r.status_code not in (409, 422):
                r.raise_for_status()
        raise RuntimeError("다른 창과 저장이 겹쳐 저장하지 못했습니다. 다시 시도해 주세요.")


def make_store(secrets: dict, local_folder: Path) -> LocalStore | GitHubStore:
    token = (secrets or {}).get("GITHUB_TOKEN")
    if token:
        return GitHubStore(token, (secrets or {}).get("GITHUB_REPO", "kimdaehwan-coco/coco"))
    return LocalStore(local_folder)
