#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""한국외교사연구회 사이트 빌더.

내용은 data/*.json 에만 있다. 이 스크립트는 그것을 Jinja2 템플릿에 부어
저장소 루트에 HTML 을 쓴다 — <name>.github.io 저장소가 아무 설정 없이
그대로 발행하는 배치다.

    python build.py                      # 산출물 재생성
    python build.py --serve --port 8000  # 빌드 후 http://localhost:8000
    python build.py --serve --no-build   # 다시 빌드하지 않고 미리보기만

산출물이 소스와 같은 폴더에 놓이므로, 빌드는 자기가 만든 파일만 지운다
(generated_paths()). 빌드가 만들지 않는 파일을 산출물 폴더에 두지 말 것.
"""
from __future__ import annotations

import argparse
import http.server
import json
import re
import shutil
import socketserver
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
OUT = ROOT
SESSION_DIR = "sessions"

FONT_HREF = (
    "https://fonts.googleapis.com/css2"
    "?family=Noto+Sans+KR:wght@300;400;500;700"
    "&family=Noto+Serif+KR:wght@400;600;700"
    "&family=Inter:wght@300;400;500;600;700"
    "&family=Spectral:ital,wght@0,400;0,500;0,600;1,400"
    "&display=swap"
)

# (템플릿, 출력파일, nav 키)
PAGES = [
    ("index", "index.html", "home"),
    ("sessions", "sessions.html", "sessions"),
    ("archive", "archive.html", "archive"),
    ("materials", "materials.html", "materials"),
    ("publications", "publications.html", "publications"),
    ("photos", "photos.html", "photos"),
    ("members", "members.html", "members"),
    ("about", "about.html", "about"),
]


def load(name: str):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def env() -> Environment:
    e = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    e.filters["nl2p"] = nl2p
    e.filters["emph"] = emph
    return e


def nl2p(text: str) -> str:
    """빈 줄로 갈린 덩어리를 <p> 로. 세미나 기록 본문에 쓴다."""
    from markupsafe import Markup, escape

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
    return Markup("\n".join(
        "<p>" + str(escape(b)).replace("\n", "<br>") + "</p>" for b in blocks
    ))


def emph(text: str) -> str:
    """서지의 *영문 서명* 을 이탤릭으로. 이스케이프를 먼저 하고 표시만 살린다."""
    from markupsafe import Markup, escape

    s = str(escape(text or ""))
    return Markup(re.sub(r"\*([^*\n]{1,200})\*", r"<em>\1</em>", s))


def generated_paths() -> list[Path]:
    """빌드가 만든 것들 — 청소해도 되는 것만."""
    paths = [OUT / filename for _, filename, _ in PAGES]
    paths.append(OUT / "404.html")
    paths.append(OUT / SESSION_DIR)
    for asset in ASSETS.iterdir():
        paths.append(OUT / asset.name)
    return paths


def clean() -> None:
    """산출물을 지운다.

    폴더는 **속만 비우고 껍데기는 남긴다.** 윈도우에서는 탐색기 창이나 셸이
    폴더 하나를 열어 두기만 해도 rmdir 이 WinError 5 로 막히는데,
    폴더 자체를 지울 이유는 어차피 없다.
    """
    for p in generated_paths():
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file():
                    child.unlink(missing_ok=True)
            for child in sorted(p.rglob("*"), key=lambda c: len(c.parts), reverse=True):
                if child.is_dir():
                    try:
                        child.rmdir()
                    except OSError:
                        pass
        elif p.exists():
            p.unlink()


def copy_assets() -> None:
    for asset in ASSETS.iterdir():
        target = OUT / asset.name
        if asset.is_dir():
            shutil.copytree(asset, target, dirs_exist_ok=True)
        else:
            shutil.copy2(asset, target)


def build() -> None:
    site = load("site")
    sessions = load("sessions")
    materials = load("materials")
    members = load("members")
    publications = load("publications")
    readings_ahead = load("agenda_readings")
    photos = load("photos")

    entries = sorted(sessions["entries"], key=lambda s: s["date"], reverse=True)
    for s in entries:
        s["url"] = f"{SESSION_DIR}/{s['id']}.html"

    by_id = {m["id"]: m for m in materials["entries"]}
    for s in entries:
        s["material_records"] = [by_id[i] for i in s.get("materials", []) if i in by_id]
        # 조립기가 갈라 둔 세 갈래를 실제 레코드로 바꾼다.
        for r in s.get("readings", []):
            if r.get("material") in by_id:
                r["material"] = by_id[r["material"]]
            else:
                r.pop("material", None)
        for p in s.get("presenters", []):
            p["materials"] = [dict(by_id[i], under_presenter=True)
                              for i in p.get("materials", []) if i in by_id]
        s["loose_papers"] = [by_id[i] for i in s.get("loose_papers", []) if i in by_id]
        s["reading_materials"] = [by_id[i] for i in s.get("reading_materials", []) if i in by_id]
        s["other_materials"] = [by_id[i] for i in s.get("other_materials", []) if i in by_id]

    # 2020년 3월을 경계로 「지구사로서 한국외교사」 국면과 그 앞의 지난 기록으로 가른다.
    split = sessions["split"]
    current = [s for s in entries if s["date"] >= split]
    past = [s for s in entries if s["date"] < split]
    # 시기 카드를 누르면 그 시기가 시작되는 자리로 뛴다.
    # 목록은 최신순이므로 각 시기의 '처음 만나는 항목'에 닻을 박는다.
    def mark(rows):
        seen = set()
        for s in rows:
            if s["era"] not in seen:
                seen.add(s["era"])
                s["era_anchor"] = s["era"]
        return seen

    on_current = mark(current)
    on_past = mark(past)
    for e in sessions["eras"]:
        if e["key"] in on_current:
            e["href"] = f"sessions.html#era-{e['key']}"
        elif e["key"] in on_past:
            e["href"] = f"archive.html#era-{e['key']}"

    # 지난 기록 쪽의 시기 카드는 그 쪽에 실린 회차만 센다.
    past_count, past_span = {}, {}
    for s in past:
        past_count[s["era"]] = past_count.get(s["era"], 0) + 1
        lo, hi = past_span.get(s["era"], (s["year"], s["year"]))
        past_span[s["era"]] = (min(lo, s["year"]), max(hi, s["year"]))
    past_eras = [dict(e, href=f"#era-{e['key']}", count=past_count[e["key"]],
                      range=(past_span[e["key"]][0] if past_span[e["key"]][0] == past_span[e["key"]][1]
                             else "–".join(past_span[e["key"]])))
                 for e in sessions["eras"] if past_count.get(e["key"])]

    clean()
    copy_assets()
    e = env()

    common = dict(
        site=site,
        pages=PAGES,
        base_url=site["base_url"],
        font_href=FONT_HREF,
        noindex=False,
    )

    for slug, filename, navkey in PAGES:
        tpl = e.get_template(f"{slug}.html.j2")
        html = tpl.render(
            **common,
            page=navkey,
            page_file=filename,
            prefix="",
            sessions=sessions,
            entries=entries,
            current=current,
            past=past,
            past_eras=past_eras,
            materials=materials,
            members=members,
            publications=publications,
            readings_ahead=readings_ahead,
            photos=photos,
        )
        (OUT / filename).write_text(html, encoding="utf-8")

    (OUT / "404.html").write_text(
        e.get_template("404.html.j2").render(
            **{k: v for k, v in common.items() if k != "noindex"},
            page="", page_file="404.html", prefix="/", noindex=True,
        ),
        encoding="utf-8",
    )

    sdir = OUT / SESSION_DIR
    sdir.mkdir(exist_ok=True)
    tpl = e.get_template("session.html.j2")
    for i, s in enumerate(entries):
        html = tpl.render(
            **common,
            page="sessions",
            page_file=f"{SESSION_DIR}/{s['id']}.html",
            prefix="../",
            session=s,
            newer=entries[i - 1] if i > 0 else None,
            older=entries[i + 1] if i + 1 < len(entries) else None,
        )
        (sdir / f"{s['id']}.html").write_text(html, encoding="utf-8")

    print(f"빌드 완료 — 페이지 {len(PAGES) + 1}, 회차 {len(entries)}, 자료 {len(materials['entries'])}")


def serve(port: int) -> None:
    """미리보기 서버.

    스레드를 쓴다. 한 줄짜리 TCPServer 로 두면 PDF 하나를 받는 동안 다른 요청이
    전부 줄을 서고, 브라우저가 연결을 끊어도 CLOSE_WAIT 이 쌓여 서버가 먹통이 된다.
    한 번 그렇게 멈춰서 바꿨다.
    """
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(OUT), **kw)

        def log_message(self, *a):
            pass

    class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"http://localhost:{port}  (Ctrl+C 로 종료)")
        httpd.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if not args.no_build:
        build()
    if args.serve:
        serve(args.port)
