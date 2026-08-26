#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""data/*.json 을 사람이 읽고 고칠 수 있는 마크다운 두 장으로 뽑는다.

    아카이브_정리.md   회차별 연표 — 주제·발제자·읽은 글·자료
    아카이브_점검.md   손이 필요한 곳만 모은 점검표

    python _build/digest.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ACCESS = {"public": "공개", "external": "링크", "restricted": "비공개"}


def load(n):
    return json.loads((DATA / f"{n}.json").read_text(encoding="utf-8"))


def main() -> None:
    S = load("sessions")
    M = load("materials")
    mats = {m["id"]: m for m in M["entries"]}
    entries = sorted(S["entries"], key=lambda s: s["date"])
    eras = {e["key"]: e["label"] for e in S["eras"]}

    out = ["# 한국외교사연구회 아카이브 — 회차 정리", "",
           f"회차 {len(entries)}건 · {entries[0]['date'][:4]}–{entries[-1]['date'][:4]} · "
           f"자료 {len(M['entries'])}건", "",
           "출처: 하영선 홈페이지(meet1.asp) · 지메일 회람 · 구글드라이브 「하샘 외교사모임」", ""]

    split = S.get("split", "2020-03-01")
    era = None
    phase = None
    for s in entries:
        ph = "지구 문명사적 관점에서 본 한국외교사" if s["date"] >= split else "지난 기록"
        if ph != phase:
            phase = ph
            out += ["", f"# {phase}", ""]
            era = None
        if s["era"] != era:
            era = s["era"]
            out += ["", f"## {eras[era]}", ""]
        out.append(f"### {s['date']} · {s['session_label']}")
        meta = [x for x in (s["kind"] if s["kind"] != "정례모임" else "",
                            s["venue"], s["meeting_time"], s["format"],
                            s["status"] if s["status"] != "개최" else "") if x]
        if meta:
            out.append("  " + " · ".join(meta))
        if s["topic"]:
            out.append(f"  **주제** {s['topic']}")
        def line(mid, indent="  "):
            m = mats.get(mid)
            if not m:
                return None
            loc = m.get("file") or m.get("url") or ""
            return (f"{indent}- [{ACCESS[m['access']]}] {m['title']}"
                    + (f" ({m['author']})" if m.get("author") else "")
                    + (f" — {loc}" if loc else ""))
        if s["readings"]:
            out.append("  **독회 문헌**")
            for r in s["readings"]:
                k = f" `{r['kind']}`" if r.get("kind") else ""
                out.append(f"  - {r['raw']}{k}")
                if r.get("material"):
                    x = line(r["material"], "    ")
                    if x:
                        out.append(x)
        if s["presenters"]:
            out.append("  **발제자 및 발제자료**")
            for p in s["presenters"]:
                role = "" if p.get("role", "발제") == "발제" else f"({p['role']}) "
                out.append(f"  - {role}{p['name']}" + (f" — {p['topic']}" if p.get("topic") else ""))
                for mid in p.get("materials", []):
                    x = line(mid, "    ")
                    if x:
                        out.append(x)
            for mid in s.get("loose_papers", []):
                x = line(mid)
                if x:
                    out.append(x)
        if s.get("other_materials"):
            out.append("  **기타 자료**")
            for mid in s["other_materials"]:
                x = line(mid)
                if x:
                    out.append(x)
        if s["record"]:
            out.append(f"  **모임 기록** {len(s['record']):,}자 — {s['record_source']['url']}")
        if s["notes"]:
            out.append(f"  **회람 메일 기록** {len(s['notes'])}건")
        out.append("")

    if M.get("themes"):
        out += ["", "# 주제별 자료", ""]
        for t in M["themes"]:
            out += ["", f"## {t['label']} ({len(t['entries'])})", ""]
            if t.get("note"):
                out += [t["note"], ""]
            for m in t["entries"]:
                loc = m.get("file") or m.get("url") or ""
                out.append(f"- [{ACCESS[m['access']]}] {m['title']}" + (f" — {loc}" if loc else ""))
                if m.get("citation"):
                    out.append(f"  {m['citation']}")

    (ROOT / "아카이브_정리.md").write_text("\n".join(out), encoding="utf-8")

    # --- 점검표 ---------------------------------------------------------
    chk = ["# 아카이브 점검표", "",
           "게재 전에 사람 눈이 한 번 닿아야 하는 것만 모았다.", ""]

    flags = [m for m in M["entries"]
             if any(k in m.get("rights_note", "") for k in ("학번", "마스킹", "주의", "권고", "확인"))]
    chk += ["## 게재 전 확인이 필요한 자료", ""]
    for m in flags:
        chk.append(f"- **{m['title']}** ({ACCESS[m['access']]}) — {m['rights_note']}")
    chk.append("")

    noinfo = [s for s in entries if not s["record"] and not s["notes"]]
    chk += ["", f"## 기록이 남지 않은 회차 ({len(noinfo)})", "",
            "공지 메일만 남아 토론 내용이 없는 회차다. 기억나는 것이 있으면 채워 넣을 수 있다.", ""]
    for s in noinfo:
        chk.append(f"- {s['date']} {s['session_label']} — 읽은 글 {len(s['readings'])}, 발제자 {len(s['presenters'])}")

    nofile = [m for m in M["entries"] if "원본 파일 미확보" in m.get("rights_note", "")]
    chk += ["", f"## 공개해도 되지만 원본이 없는 자료 ({len(nofile)})", "",
            "지메일 첨부는 내려받을 방법이 없고 드라이브 파일은 열람 권한이 필요하다. "
            "원본을 `_harvest/hayoungsun/files/` 에 같은 이름으로 넣고 다시 조립하면 게재된다.", ""]
    for m in nofile:
        chk.append(f"- {m['title']} ({m['session'] or '회차 미상'})")

    noaffil = [m for m in load("members")["entries"] if not m["affil"]]
    chk += ["", f"## 소속이 비어 있는 참여자 ({len(noaffil)})", "",
            "`_harvest/overrides.json` 의 `affil` 에 넣으면 반영된다.", "",
            "```json", '{"affil": {'] + \
           [f'  "{m["name"]}": "",' for m in noaffil] + ["}}", "```"]

    (ROOT / "아카이브_점검.md").write_text("\n".join(chk), encoding="utf-8")

    print(f"아카이브_정리.md  {len(out)}줄")
    print(f"아카이브_점검.md  확인필요 {len(flags)} · 기록없음 {len(noinfo)} · 원본없음 {len(nofile)}")
    print("자료 상태:", dict(Counter(m["access"] for m in M["entries"])))


if __name__ == "__main__":
    main()
