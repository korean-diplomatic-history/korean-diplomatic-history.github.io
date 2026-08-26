#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_harvest/ 의 원자료를 data/*.json 으로 조립한다.

세 소스를 회차 날짜(YYYY-MM-DD)로 합친다.

  _harvest/hayoungsun/meetings.json   하영선 홈페이지 meet1.asp — 2006~2021, 모임 기록 본문 + 첨부
  _harvest/hayoungsun/files_probe.json  첨부 149건의 쪽수·본문 앞머리
  _harvest/gmail/extract.json         지메일 스레드 151건 구조화 추출
  _harvest/drive/files.json           구글드라이브 '하샘 외교사모임' 47건
  _harvest/classify.json              자료별 저작권 판정 (별도 단계에서 생성)

data/ 는 이 스크립트가 덮어쓴다. 손으로 고칠 것이 있으면 _harvest/overrides.json 에.

    python _build/assemble.py
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "_harvest"
DATA = ROOT / "data"

SAFE = re.compile(r'[\/:*?"<>|]')


def safe_name(x: str) -> str:
    """지메일 첨부를 디스크에 쓸 때 쓴 이름. 한글은 NFC 로 맞춘다."""
    return unicodedata.normalize("NFC", SAFE.sub("_", x or "")).strip()

WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]

# 2020년 3월 모임부터를 「지구사로서 한국외교사」 국면으로 본다. 그 앞은 지난 기록.
SPLIT = "2020-03-01"
# 최근 참여자와 지나간 참여자를 가르는 기준.
ACTIVE = "2024-01-01"

ERAS = [
    ("jiseongsa", "18세기 지성사 독회", "2006–2009",
     "『연행록 선집』과 18세기 지성사 연구서", "2006-01-01", "2010-12-31"),
    ("yeonhaeng", "연행록연구회", "2011–2012",
     "조천록·연행록과 그 연구", "2011-01-01", "2012-08-31"),
    ("hanoesa", "한국외교사연구회", "2012–",
     "『역주 중국정사 조선전』·『사조선록 역주』에서 근대 개념사까지", "2012-09-01", "2099-12-31"),
]


def read(p: Path, default=None):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def era_of(date: str) -> str:
    for key, _l, _r, _n, lo, hi in ERAS:
        if lo <= date <= hi:
            return key
    return "hanoesa"


def display_date(iso: str) -> str:
    import datetime
    try:
        d = datetime.date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAY[d.weekday()]})"


ANGLE = re.compile(r"<([^<>\n]{1,80})>")


DISTRIB = re.compile(r"^발제\s*\d+\s*[:：]\s*")


def topic_of(t: str) -> str:
    """발제 배분 표기('발제 1: …')에서 앞머리를 떼고 대상만 남긴다."""
    return DISTRIB.sub("", titles(t or "")).strip()


def titles(text: str) -> str:
    """원 기록은 서명을 <…> 로 쓴다. 한국어 표기 관행대로 『…』 로 바꾼다."""
    return ANGLE.sub(lambda m: "『" + m.group(1) + "』", (text or "").replace("﻿", ""))


FILEEXT = re.compile(r"\.(pdf|hwp|hwpx|docx?|pptx?|xlsx?|zip|ics|jpe?g|png)\s*$", re.I)
FOLD = re.compile(r"[\s,.·:;()\[\]{}<>“”\"'‘’「」『』〈〉《》/\-–—_*＊]+")


def fold(s: str) -> str:
    """서지 두 표기가 같은 문헌인지 보려고 눌러 쓴 꼴."""
    return FOLD.sub("", s or "").lower()


def sig(raw: str) -> str:
    """중복 판정용 지문. 서명(『…』)이 있으면 그것만 본다 —
    같은 책의 서지 표기가 소스마다 조금씩 달라도 서명은 같기 때문이다.
    『사조선록 역주 3』 과 『사조선록 역주 4』 처럼 권차가 다르면 지문도 달라 합쳐지지 않는다."""
    m = re.search(r"『([^』]+)』", raw)
    return fold(m.group(1) if m else raw)


def add_reading(s: dict, raw: str, **rest) -> None:
    """읽은 글 한 줄 추가. 파일명은 자료지 읽은 글이 아니고, 같은 문헌은 온전한 쪽만 남긴다."""
    raw = titles((raw or "").strip())
    if not raw or FILEEXT.search(raw):
        return
    # "발제 3: 괴령, 『동사기사시략』" 은 그날 읽은 글이 아니라 발제 배분이다 —
    # 같은 내용이 presenters 에 이미 들어 있으므로 읽은 글 목록에서는 뺀다.
    if re.match(r"발제\s*\d+\s*[:：]", raw):
        return
    key = sig(raw)
    if not key:
        return
    for i, ex in enumerate(s["readings"]):
        k = sig(ex["raw"])
        same = k == key or (min(len(k), len(key)) >= 6 and (k in key or key in k))
        if same:
            if len(raw) > len(ex["raw"]):        # 더 온전한 표기로 갈아끼운다
                s["readings"][i] = {"raw": raw, **rest}
            return
    s["readings"].append({"raw": raw, **rest})


def _edge_margins(im, thr=14.0, gap=14, limit=0.16):
    import statistics as st
    px = im.load()
    W, H = im.size

    def std(i, horiz):
        if horiz:
            step = max(1, W // 160)
            v = [sum(px[x, i]) / 3 for x in range(0, W, step)]
        else:
            step = max(1, H // 160)
            v = [sum(px[i, y]) / 3 for y in range(0, H, step)]
        return st.pstdev(v)

    def scan(n, horiz, forward):
        last, lim = -1, int(n * limit)
        for k in range(lim):
            i = k if forward else n - 1 - k
            if std(i, horiz) < thr:
                last = k
            elif k - last > gap:
                break
        return last + 1

    return [scan(W, False, True), scan(H, True, True), scan(W, False, False), scan(H, True, False)]


def autotrim(im, rounds=4):
    """사진에 박혀 있는 액자를 걷어낸다.

    액자는 네 변이 같은 폭이므로 **네 변의 중앙값**만큼 잘라 내기를 되풀이한다.
    한 변이 하늘처럼 밋밋해 잘못 잡혀도 중앙값이 그것을 눌러 준다 —
    변마다 따로 자르면 흐린 하늘을 액자로 오인해 사진 위쪽을 크게 베어 먹는다.
    """
    import statistics as st
    for _ in range(rounds):
        c = int(st.median(_edge_margins(im)))
        if c < 3:
            break
        W, H = im.size
        if c * 2 >= min(W, H) // 2:
            break
        im = im.crop((c, c, W - c, H - c))
    return im


def norm_label(title: str, iso: str) -> str:
    """'한국외교사연구회 2018년 10월 정례모임' → 그대로. 연도 없는 옛 제목엔 연도를 넣는다."""
    t = (title or "").strip()
    if not t:
        return f"{iso[:4]}년 {int(iso[5:7])}월 모임"
    if re.search(r"\d{4}\s*년", t):
        return t
    return re.sub(r"(\d+월)", rf"{iso[:4]}년 \1", t, count=1)


def main() -> None:
    meetings = read(H / "hayoungsun" / "meetings.json", [])
    probe = {r["file"]: r for r in read(H / "hayoungsun" / "files_probe.json", [])}
    gmail = read(H / "gmail" / "extract.json", {"threads": []})["threads"]
    # 기록 본문에서 뽑은 실제 개최일·발제자·읽은 글. 파일명이 "<게시일>_<idx>.txt".
    recs = {}
    for r in read(H / "records_extract.json", {"records": []})["records"]:
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d+)\.txt", r.get("file", ""))
        if m:
            recs[int(m.group(2))] = r
    drive = read(H / "drive" / "files.json", [])
    classify = {c["key"]: c for c in read(H / "classify.json", [])}
    # 주제 체계와 배정. 없으면 자료 페이지가 한 덩어리로 나온다.
    th = read(H / "themes.json", {"themes": [], "sessions": [], "orphans": []})
    theme_defs = th["themes"]
    theme_of_session = {r["id"]: r["theme"] for r in th["sessions"]}
    topic_of_session = {r["id"]: r["topic"] for r in th["sessions"] if r.get("topic")}
    theme_of_orphan = {r["key"]: r["theme"] for r in th["orphans"]}
    overrides = read(H / "overrides.json", {})
    # 자료마다 사람에게 보일 제목과, 그것이 누구의 발제자료인지.
    titles_of = {t["key"]: t for t in read(H / "material_titles.json", {"items": []})["items"]}

    sessions: dict[str, dict] = {}
    materials: list[dict] = []
    seen_material: dict[str, str] = {}
    mid = [0]

    # 모임에서 다뤄지지 않은 자료는 아예 싣지 않는다.
    dropped_keys = set(overrides.get("exclude_materials", []))
    dropped_keys |= {u["key"] for u in read(H / "usage_audit.json", {"items": []})["items"]
                     if not u.get("used") and u["key"] not in overrides.get("keep_materials", [])}

    def add_material(**kw) -> str:
        key = kw["key"]
        if key in dropped_keys:
            return ""
        if key in seen_material:
            return seen_material[key]
        mid[0] += 1
        rid = f"m{mid[0]:04d}"
        c = classify.get(key, {})
        rec = {
            "id": rid,
            "name": kw["name"],
            "kind": c.get("kind") or kw.get("kind", "기타"),
            "author": c.get("author") or kw.get("author", ""),
            "session": kw.get("session", ""),
            "origin": kw["origin"],
            "access": c.get("access", "restricted"),
            "rights_note": c.get("rights_note", "저작권 판정 전 — 기본 비공개"),
            "key": key,
        }
        for f in ("file", "pages", "bytes", "citation"):
            v = kw.get(f) or c.get(f)
            if v:
                rec[f] = v
        # url 은 판정이 확인한 '공개 원문' 이 우선이다. 드라이브 viewUrl 은 열람 권한이
        # 있어야 열리므로 공개 링크가 될 수 없다 — 판정이 준 것이 없을 때만 쓴다.
        v = c.get("url") or kw.get("url")
        if v:
            rec["url"] = v
        t = titles_of.get(key, {})
        rec["title"] = t.get("title") or rec["name"]
        rec["group"] = t.get("group") or ("발제자료" if rec["kind"] in ("발제문", "발표자료", "토론기록") else "기타자료")
        rec["presenter"] = t.get("presenter", "")
        if t.get("author") and not rec["author"]:
            rec["author"] = t["author"]
        materials.append(rec)
        seen_material[key] = rid
        return rid

    def session(iso: str) -> dict:
        if iso not in sessions:
            sessions[iso] = {
                "id": iso, "date": iso, "year": iso[:4],
                "date_display": display_date(iso), "era": era_of(iso),
                "session_label": "", "kind": "정례모임", "topic": "",
                "venue": "", "meeting_time": "", "format": "", "status": "개최",
                "presenters": [], "readings": [], "materials": [],
                "record": "", "record_source": None, "notes": [], "links": [], "sources": [],
            }
        return sessions[iso]

    # --- 1. 하영선 홈페이지 -------------------------------------------------
    for m in meetings:
        r = recs.get(m["idx"], {})
        # 게시일이 아니라 기록 본문의 "일시:"가 실제 개최일이다.
        iso = r.get("meeting_date") or m["date"]
        s = session(iso)
        s["session_label"] = norm_label(m["title"], m["date"])
        s["record"] = titles(m["body_text"])
        s["record_source"] = {"label": "하영선 홈페이지", "url": m["source_url"]}
        s["sources"].append("hayoungsun")
        if r.get("kind") and r["kind"] != "불명":
            s["kind"] = r["kind"]
        if r.get("topic_summary"):
            s["topic"] = titles(r["topic_summary"])
        for field in ("venue", "meeting_time"):
            if r.get(field) and not s.get(field):
                s[field] = r[field]
        for p in r.get("presenters", []):
            if p.get("name") and not any(x["name"] == p["name"] for x in s["presenters"]):
                s["presenters"].append({"name": p["name"], "topic": topic_of(p.get("topic", "")),
                                        "role": p.get("role", "발제")})
        for rd in r.get("readings", []):
            add_reading(s, rd.get("raw"), kind=rd.get("kind", ""),
                        authors=rd.get("authors", ""), title=titles(rd.get("title", "")),
                        container="", year="")
        for f in m["files"]:
            base = f["local"].split("/")[-1]
            p = probe.get(base, {})
            rid = add_material(
                key=f"hys:{base}", name=f["name"], origin="hayoungsun",
                session=iso, file=f"files/{base}",
                pages=p.get("pages"), bytes=p.get("bytes"),
            )
            if rid and rid not in s["materials"]:
                s["materials"].append(rid)

    # --- 2. 지메일 ---------------------------------------------------------
    for t in gmail:
        if t.get("category") == "무관":
            continue
        iso = (t.get("meeting_date") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
            continue
        s = session(iso)
        if not s["session_label"]:
            s["session_label"] = t.get("session_label") or f"{iso[:4]}년 {int(iso[5:7])}월 모임"
        for field in ("venue", "format", "meeting_time"):
            if not s.get(field) and t.get(field) and t[field] != "불명":
                s[field] = t[field]
        if t.get("group") == "방법론워크샵":
            s["kind"] = "워크샵"
        if t.get("status") and t["status"] not in ("불명", "예정"):
            s["status"] = t["status"]
        for p in t.get("presenters", []):
            if p.get("name") and not any(x["name"] == p["name"] for x in s["presenters"]):
                s["presenters"].append({
                    "name": p["name"], "topic": topic_of(p.get("topic", "")), "role": p.get("role", "발제")})
        for r in t.get("readings", []):
            add_reading(s, r.get("raw"), kind=r.get("kind", ""),
                        authors=r.get("authors", ""), title=titles(r.get("title", "")),
                        container=r.get("container", ""), year=r.get("year", ""))
        for a in t.get("attachments", []):
            fn = a.get("filename")
            if not fn:
                continue
            rid = add_material(key=f"gmail:{fn}", name=fn, origin="gmail", session=iso)
            if rid and rid not in s["materials"]:
                s["materials"].append(rid)
        ex = (t.get("excerpt_text") or "").strip()
        if len(ex) > 40 and all(fold(ex) != fold(n["text"]) for n in s["notes"]):
            s["notes"].append({"text": titles(ex), "source": "회람 메일"})
        for u in t.get("links", []):
            if u.startswith("http") and "zoom" not in u.lower() and u not in s["links"]:
                s["links"].append(u)
        if "gmail" not in s["sources"]:
            s["sources"].append("gmail")

    # --- 2b. 지메일 원문에서 꺼낸 첨부 -------------------------------------
    # 스레드 추출이 놓친 첨부가 있다. 파일을 실제로 확보했으니 자료로 올린다.
    msg_date = {}
    for t in gmail:
        d0 = (t.get("meeting_date") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d0):
            continue
        for a_ in t.get("attachments", []):
            if a_.get("message_id"):
                msg_date[a_["message_id"]] = d0
    gdir = H / "gmail" / "files"
    known = {safe_name(k[6:]) for k in seen_material if k.startswith("gmail:")}
    for rec in read(H / "gmail" / "attachments_saved.json", {"saved": []})["saved"]:
        fn = safe_name(rec.get("filename", ""))
        if not fn or fn in known or not (gdir / fn).exists():
            continue
        known.add(fn)
        iso = msg_date.get(rec.get("message_id", ""), "")
        rid = add_material(key=f"gmail:{fn}", name=rec["filename"], origin="gmail", session=iso)
        if rid and iso and iso in sessions and rid not in sessions[iso]["materials"]:
            sessions[iso]["materials"].append(rid)

    # --- 3. 구글 드라이브 ---------------------------------------------------
    for f in drive:
        add_material(key=f"drive:{f['id']}", name=f["title"], origin="drive",
                     url=f.get("viewUrl", ""), bytes=f.get("fileSize"))

    # --- 4. 사람 -----------------------------------------------------------
    counts: dict[str, int] = defaultdict(int)
    talks: dict[str, int] = defaultdict(int)
    first: dict[str, str] = {}
    last: dict[str, str] = {}
    seen: dict[str, str] = {}     # 발제가 아니어도 그 자리에 있었던 마지막 날
    for n in overrides.get("add_members", []):
        counts.setdefault(n, 0)
        talks.setdefault(n, 0)
        first.setdefault(n, "")
        last.setdefault(n, "")
        seen.setdefault(n, "9999-12-31")     # 손으로 넣은 분은 현재 참여자로 본다
    for s in sorted(sessions.values(), key=lambda x: x["date"]):
        for p in s["presenters"]:
            n = p["name"]
            counts[n] += 1
            if p.get("role", "발제") in ("발제", "발표"):
                talks[n] += 1
            first.setdefault(n, s["date"])
            last[n] = s["date"]
            seen[n] = max(seen.get(n, ""), s["date"])

    alias = overrides.get("alias", {})
    for t in gmail:
        d = (t.get("meeting_date") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        for n in t.get("participants", []):
            n = alias.get(n, n)
            if n in counts:
                seen[n] = max(seen.get(n, ""), d)

    # 세미나가 아닌 자리(송년회 등)는 아카이브에 싣지 않는다.
    for iso in [k for k, v in sessions.items()
                if "송년회" in v["session_label"] and not v["readings"] and not v["presenters"]]:
        del sessions[iso]

    entries = sorted(sessions.values(), key=lambda s: s["date"])

    # 표제 정리. 시기(18세기 지성사·연행록연구회·한국외교사연구회)는 배지가 표시하므로
    # 표제에서는 떼고 "YYYY년 M월 정례모임" 으로 통일한다. 한 달에 두 번 모인 달은 1차·2차.
    monthly = defaultdict(list)
    for s in entries:
        label = s["session_label"]
        if "송년회" in label or "학술행사" in label or "희수" in label:
            s["kind"] = "행사"
        elif "워크샵" in label or "워크숍" in label:
            s["kind"] = "워크샵"
        if s["kind"] == "정례모임":
            monthly[s["date"][:7]].append(s)
    for ym, group in monthly.items():
        y, mo = int(ym[:4]), int(ym[5:7])
        for i, s in enumerate(group, 1):
            nth = f" {i}차" if len(group) > 1 else ""
            s["session_label"] = f"{y}년 {mo}월{nth} 정례모임"

    # 읽은 글 목록 다듬기. 회원 발제문은 자료지 읽은 글이 아니고, 장(章) 분담은
    # 이미 발제자 항목에 있으므로 두 번 보일 이유가 없다.
    CHAP = re.compile(r"^\s*(?:제?\s*\d+\s*[장.)]|ch(?:ap(?:ter)?)?\.?\s*\d+)\s*[:.]?\s*", re.I)
    for s in entries:
        ptopics = [fold(p.get("topic", "")) for p in s["presenters"] if p.get("topic")]
        keep = []
        for rd in s["readings"]:
            if rd.get("kind") == "발제문" or "발제문" in rd["raw"]:
                continue
            # 장(章) 분담 표기만 걷어낸다. "1. International Law and…" 처럼 장 번호로
            # 시작하는 줄이 발제자 항목과 겹칠 때만 뺀다 — 그날의 主 텍스트까지
            # 발제자 항목과 겹친다고 지우면 독회 문헌이 비어 버린다.
            if CHAP.match(rd["raw"]):
                body = fold(CHAP.sub("", rd["raw"]))
                if len(body) >= 8 and any(body in pt or pt in body for pt in ptopics if len(pt) >= 8):
                    continue
            keep.append(rd)
        s["readings"] = keep

    # 손질한 서지로 갈아끼운다. rid 는 "<회차>#<그 회차 안에서의 순번>" 이라,
    # 원본 raw 가 그대로인지 대조해 확인한 것만 반영한다(순서가 밀리면 조용히 건너뛴다).
    clean = {r["rid"]: r for r in read(H / "readings_clean.json", {"readings": []})["readings"]}
    expect = {r["rid"]: r["raw"] for r in read(H / "readings_input.json", [])}
    swapped = dropped = skipped_r = 0
    for s in entries:
        keep = []
        for i, rd in enumerate(s["readings"]):
            c = clean.get(f"{s['id']}#{i}")
            if not c or fold(expect.get(f"{s['id']}#{i}", "")) != fold(rd["raw"]):
                if c:
                    skipped_r += 1
                keep.append(rd)
                continue
            if c.get("drop"):
                dropped += 1
                continue
            if c.get("cite"):
                rd["raw"] = titles(c["cite"])
                swapped += 1
            if c.get("kind"):
                rd["kind"] = c["kind"]
            if c.get("url"):
                rd["url"] = c["url"]
            keep.append(rd)
        s["readings"] = keep
    if clean:
        print(f"  읽은 글 정돈: 교체 {swapped} · 제외 {dropped} · 대조실패 {skipped_r}")

    # 주제 배정과, 손본 주제문.
    for s in entries:
        s["theme"] = theme_of_session.get(s["id"], "")
        if topic_of_session.get(s["id"]):
            s["topic"] = titles(topic_of_session[s["id"]])
        elif not s["topic"] and s["readings"]:
            r = s["readings"][0]
            s["topic"] = r.get("title") or r["raw"][:60]

    # 회차 연결이 끊겼던 자료를 제 회차에 붙인다(나중에 원문에서 꺼낸 첨부들).
    reattach = {r["key"]: r for r in read(H / "reattach.json", {"items": []})["items"]}
    for m in materials:
        r = reattach.get(m["key"])
        if not r:
            continue
        if r.get("theme"):
            m["theme_hint"] = r["theme"]
        iso = r.get("session")
        if iso and iso in sessions:
            m["session"] = iso
            if m["id"] not in sessions[iso]["materials"]:
                sessions[iso]["materials"].append(m["id"])

    # 손으로 지정한 자료 이동·제외를 먼저 처리한다.
    # 한 자료가 여러 스레드에서 언급되면 엉뚱한 회차에도 붙는다 — 그것을 사람이 바로잡는 자리.
    id_of = {m["key"]: m["id"] for m in materials}
    for key, patch in overrides.get("materials", {}).items():
        dest = patch.get("move_to")
        if not dest or key not in id_of:
            continue
        rid = id_of[key]
        for s in sessions.values():
            if rid in s["materials"]:
                s["materials"].remove(rid)
        if dest in sessions and rid not in sessions[dest]["materials"]:
            sessions[dest]["materials"].append(rid)
        for m in materials:
            if m["key"] == key:
                m["session"] = dest
    for iso, patch in overrides.get("sessions", {}).items():
        for key in patch.get("drop_materials", []):
            rid = id_of.get(key)
            if rid and iso in sessions and rid in sessions[iso]["materials"]:
                sessions[iso]["materials"].remove(rid)

    # 회차마다 자료를 세 갈래로 가른다 — 독회 문헌 · 발제자 및 발제자료 · 기타 자료.
    by_id = {m["id"]: m for m in materials}
    for s in entries:
        mats = [by_id[i] for i in s["materials"] if i in by_id]
        used = set()

        # (1) 독회문헌으로 분류된 자료는 그날 읽은 글 옆에 붙인다.
        for m in [x for x in mats if x["group"] == "독회문헌"]:
            k = sig(m["title"])
            if not k:
                continue
            for r in s["readings"]:
                if r.get("material"):
                    continue
                rk = sig(r["raw"])
                if rk and (rk == k or (min(len(rk), len(k)) >= 6 and (rk in k or k in rk))):
                    r["material"] = m["id"]
                    used.add(m["id"])
                    break

        # (2) 발제자료는 발제자에게 붙인다.
        for p in s["presenters"]:
            p["materials"] = []
        for m in [x for x in mats if x["group"] == "발제자료"]:
            for p in s["presenters"]:
                if m["presenter"] and m["presenter"] == p["name"]:
                    p["materials"].append(m["id"])
                    used.add(m["id"])
                    break
        s["loose_papers"] = [m["id"] for m in mats
                             if m["group"] == "발제자료" and m["id"] not in used]
        used.update(s["loose_papers"])

        # 서지와 짝이 안 맞은 독회문헌도 그날 읽은 텍스트다 — 독회 문헌 절에 남긴다.
        s["reading_materials"] = [m["id"] for m in mats
                                  if m["group"] == "독회문헌" and m["id"] not in used]
        used.update(s["reading_materials"])

        # (3) 남은 것이 기타 자료다.
        s["other_materials"] = [m["id"] for m in mats if m["id"] not in used]

    # 손으로 고친 것을 마지막에 얹는다. 워크플로 판정이 틀린 자리를 사람이 바로잡는 층이다.
    mo = overrides.get("materials", {})
    for m in materials:
        for f, v in mo.get(m["key"], {}).items():
            m[f] = v
    so = overrides.get("sessions", {})
    for s in entries:
        for f, v in so.get(s["id"], {}).items():
            if f == "readings":            # 읽은 글은 순번으로 짚어 고친다
                for i, patch in v.items():
                    if int(i) < len(s["readings"]):
                        s["readings"][int(i)].update(patch)
            elif f == "presenters":
                for nm, patch in v.items():
                    for pp in s["presenters"]:
                        if pp["name"] == nm:
                            pp.update(patch)
            else:
                s[f] = v

    for s in entries:
        s.pop("sources", None)

    era_counts = defaultdict(int)
    for s in entries:
        era_counts[s["era"]] += 1

    # 공개로 판정된 파일만 저장소의 files/ 로 옮긴다. 나머지는 _harvest 에만 둔다.
    pub = ROOT / "files"
    pub.mkdir(exist_ok=True)
    wanted = set()
    copied = skipped = 0
    for m in materials:
        if m["access"] == "public" and "file" not in m and m["origin"] == "gmail":
            m["file"] = f"files/{safe_name(m['name'])}"
        if m["access"] == "external" and m.get("url"):
            m.pop("file", None)
            continue
        if m["access"] != "public":
            m.pop("file", None)
            continue
        base = (m.get("file") or "").split("/")[-1]
        src = H / "hayoungsun" / "files" / base if base else None
        if (src is None or not src.exists()) and m["origin"] == "gmail":
            # 지메일 첨부는 원문(RAW)에서 꺼내 _harvest/gmail/files/ 에 모아 둔다.
            cand = H / "gmail" / "files" / safe_name(m["name"])
            if cand.exists():
                src = cand
                base = cand.name
                m["file"] = f"files/{base}"
        if src is None or not src.exists():
            # 공개해도 될 글이지만 원본이 우리 손에 없다. 지메일 첨부는 내려받을 방법이
            # 없고, 드라이브 파일은 링크를 걸어도 열람 권한이 필요하다 — 목록에만 남긴다.
            m["access"] = "restricted"
            m["rights_note"] = (
                "공개 가능한 글이나 원본 파일 미확보 — "
                + ("지메일 첨부" if m["origin"] == "gmail" else "구글드라이브 파일")
                + " (요청 시 게재 가능)")
            m.pop("file", None)
            skipped += 1
            continue
        wanted.add(base)
        dst = pub / base
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
            copied += 1
    for f in pub.iterdir():
        if f.is_file() and f.name not in wanted:
            f.unlink()
    print(f"  files/ 동기화: {len(wanted)}개 (새로 복사 {copied}, 원본없어 제외 {skipped})")

    DATA.mkdir(exist_ok=True)
    (DATA / "sessions.json").write_text(json.dumps({
        "title": "모임 기록",
        "subtitle": "지구 문명사적 관점에서 본 한국외교사",
        "kicker": f"{SPLIT[:4]}– · {sum(1 for x in entries if x['date'] >= SPLIT)}회",
        "lede": "",
        "meta_description": "한국외교사연구회의 회차별 모임 기록.",
        "note": "",
        "split": SPLIT,
        "past": {
            "title": "지난 기록",
            "kicker": f"{entries[0]['date'][:4]}–{SPLIT[:4]} · {sum(1 for x in entries if x['date'] < SPLIT)}회",
            "meta_description": "18세기 지성사 독회·연행록연구회와 한국외교사연구회 초기의 모임 기록.",
        },
        "era_labels": {k: l for k, l, *_ in ERAS},
        "eras": [{"key": k, "label": l, "range": r, "note": n, "count": era_counts[k]}
                 for k, l, r, n, *_ in ERAS],
        "entries": entries,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    sess_theme = {s["id"]: s["theme"] for s in entries}
    for m in materials:
        m["theme"] = (sess_theme.get(m.get("session") or "")
                      or theme_of_orphan.get(m["key"], "")
                      or m.pop("theme_hint", ""))
        m.pop("theme_hint", None)
    by_theme = defaultdict(list)
    for m in materials:
        by_theme[m["theme"]].append(m)
    order = {t["key"]: i for i, t in enumerate(theme_defs)}
    grouped = [{"key": t["key"], "label": t["label"], "note": t.get("note", ""),
                "entries": sorted(by_theme.get(t["key"], []),
                                  key=lambda m: (m.get("session") or "9999", m["name"]))}
               for t in theme_defs]
    leftover = [m for m in materials if m["theme"] not in order]
    if leftover:
        grouped.append({"key": "etc", "label": "그 밖의 자료", "note": "",
                        "entries": sorted(leftover, key=lambda m: (m.get("session") or "9999", m["name"]))})
    grouped = [g for g in grouped if g["entries"]]

    (DATA / "materials.json").write_text(json.dumps({
        "title": "자료",
        "kicker": f"{len(materials)}건",
        "lede": "",
        "meta_description": "한국외교사연구회 모임 자료 목록.",
        "policy_note": (
            "저작권이 살아 있는 단행본과 학술논문은 서지사항만 적고, "
            "원문이 공개된 것은 그 링크로 연결합니다."),
        "note": "",
        "themes": grouped,
        "entries": materials,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (DATA / "members.json").write_text(json.dumps({
        "title": "참여 연구자",
        "kicker": "",
        "lede": "",
        "meta_description": "한국외교사연구회 참여 연구자.",
        "note": "",
        "active_label": "참여 연구자",
        "alumni_label": "함께했던 분들",
        # exclude 에 적힌 사람(초청 발표자 등)은 명단에서 아예 뺀다.
        "entries": [{"name": n, "affil": overrides.get("affil", {}).get(n, ""),
                     "note": "", "sessions": talks[n], "appearances": c,
                     "last": seen[n], "active": (
                         n in overrides.get("active", [])
                         or (n not in overrides.get("alumni", [])
                             and seen[n] >= ACTIVE)),
                     "span": ("" if not first[n] else
                              first[n][:4] if first[n][:4] == last[n][:4]
                              else f"{first[n][:4]}–{last[n][:4]}")}
                    for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                    if n not in overrides.get("exclude", [])],
    }, ensure_ascii=False, indent=1), encoding="utf-8")


    # --- 사진 ---------------------------------------------------------------
    # 「사진」 폴더에 파일을 떨어뜨리면 그대로 photos/ 로 옮겨 붙는다. 설명은 붙이지 않는다.
    SRC = ROOT / "사진"
    OUTP = ROOT / "photos"
    EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    photos = []
    if SRC.exists():
        OUTP.mkdir(exist_ok=True)
        want = set()
        for f in sorted(SRC.iterdir()):
            if f.suffix.lower() not in EXT or not f.is_file():
                continue
            want.add(f.name)
            dst = OUTP / f.name
            rec = {"file": f"photos/{f.name}", "name": f.stem}
            try:
                from PIL import Image
                with Image.open(f) as im:
                    im = im.convert("RGB")
                    box = overrides.get("photo_crop", {}).get(f.name)
                    if box:
                        im = im.crop(tuple(box))
                    elif f.name not in overrides.get("photo_notrim", []):
                        im = autotrim(im)
                    if im.width > 1600:
                        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
                    rec["w"], rec["h"] = im.size
                    im.save(dst, quality=86, optimize=True, progressive=True)
            except Exception as e:
                print(f"  사진 {f.name}: 손질 실패({e}) — 원본 그대로")
                shutil.copy2(f, dst)
            photos.append(rec)
        for f in OUTP.iterdir():
            if f.is_file() and f.name not in want:
                f.unlink()
    # 파일 이름이 대개 올린 날짜(YYYYMMDD…)라, 그 순서면 시간순이 된다.
    photos.sort(key=lambda x: x["name"], reverse=True)
    (DATA / "photos.json").write_text(json.dumps({
        "title": "사진",
        "meta_description": "한국외교사연구회의 사진 기록.",
        "entries": photos,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  사진 {len(photos)}장")

    # --- 출판물 -------------------------------------------------------------
    pub = read(H / "publications.json", {"publications": [], "book": None})
    roster = {m["name"] for m in json.loads((DATA / "members.json").read_text(encoding="utf-8"))["entries"]}
    BOOKISH = ("저서", "편저", "역서")
    drop_m = set(overrides.get("exclude_pub_members", []))
    drop_p = set(overrides.get("exclude_pub_papers", []))
    drop_t = overrides.get("exclude_publications", [])

    def keep(x):
        if not x.get("verified") or x.get("member") not in roster:
            return False
        if (x.get("year") or "") < "2020":
            return False
        if x["member"] in drop_m:
            return False
        if x["member"] in drop_p and not any(x.get("kind", "").startswith(b) for b in BOOKISH):
            return False
        return not any(t and t in x.get("title", "") for t in drop_t)

    rows = [x for x in pub["publications"] if keep(x)]
    rows.sort(key=lambda x: (x.get("year", ""), x.get("member", "")), reverse=True)
    groups = []
    for label, pick in [
        ("저서 · 편저 · 역서", lambda k: any(k.startswith(b) for b in BOOKISH)),
        ("학술논문", lambda k: not any(k.startswith(b) for b in BOOKISH)),
    ]:
        e = [x for x in rows if pick(x.get("kind", ""))]
        if e:
            groups.append({"label": label, "note": "", "entries": e})
    book = pub.get("book") or None
    if book:
        # 목차의 부(部) 표제는 필자가 없다 — 장만 남긴다.
        book["contents"] = [c for c in (book.get("contents") or []) if c.get("author")]
        book["note"] = ("2011~2012년 연행록연구회가 조천록·연행록을 통독하고 "
                        "2012년 2월 워크샵에서 발표한 원고들이 이 책이 되었습니다.")
    (DATA / "publications.json").write_text(json.dumps({
        "title": "출판물",
        "kicker": f"참여 연구자의 2020년 이후 저작 {len(rows)}건",
        "meta_description": "한국외교사연구회 참여 연구자의 저서와 논문.",
        "note": "",
        "book": book,
        "groups": groups,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  출판물 {len(rows)}건 · 필자 {len(set(x['member'] for x in rows))}명")

    print(f"회차 {len(entries)}  자료 {len(materials)}  발제자 {len(counts)}")
    print("  기록 있는 회차:", sum(1 for s in entries if s["record"]))
    print("  읽은 글 있는 회차:", sum(1 for s in entries if s["readings"]))
    print("  시기별:", dict(era_counts))


if __name__ == "__main__":
    main()
