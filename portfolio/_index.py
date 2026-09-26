#!/usr/bin/env python3
"""INDEX.md 재생성 — 경험 파일 frontmatter가 단일 진실원이다.

    python3 portfolio/_index.py          # INDEX.md를 다시 쓴다
    python3 portfolio/_index.py --diff   # 쓰지 않고 달라지는 줄만 보여 준다

표·연결 맵·태그별 인덱스는 frontmatter에서 뽑는다(손으로 고치지 않는다).
그 밖의 섹션(커버리지 공백·보강 필요 TODO·사실 확인 대기 등)은 사람이 관리하는 곳이라 그대로 보존한다.
_check.py가 같은 함수로 드리프트를 검사한다.
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "INDEX.md"
CATS = [("career", "경력 (career)"), ("activities", "대외활동 (activities)"), ("projects", "프로젝트 (projects)")]
GENERATED = {c[1] for c in CATS} | {"카테고리 구조", "연결 맵 (활동 → 프로젝트)", "태그별 인덱스 (질문 매칭용)"}
HEADER = """# 경험 인덱스

> 모든 경험을 검색·매칭하기 위한 색인. 태그 어휘는 `portfolio/TAGS.md`(표준 용어집)를 따른다.
> **이 파일의 표·연결 맵·태그별 인덱스는 `python3 portfolio/_index.py`가 frontmatter에서 생성한다 — 손으로 고치지 않는다.** 아래쪽 「커버리지 공백」·「보강 필요」 등은 사람이 관리한다(재생성 때 보존).
> **경험 유형**: `episode`(단일 STAR로 말할 수 있는 사건) / `container`(하위 프로젝트를 거느린 기간·소속 — STAR 없는 게 정상, 개요·전체 성과·증거 조각이 재료).
> 범례: 정량·재료 ✅ 충족 · △ 보강 권장

## 카테고리 구조
```
career/      car-*   경력
activities/  act-*   대외활동
projects/    prj-*   프로젝트 (구체 산출물)
연결: 하위 프로젝트 `activity:`·`career:` ↔ 상위 `projects:[]`, 그 외 `related:[]`
```
"""


def frontmatter():
    out = []
    for d, _ in CATS:
        for f in sorted((ROOT / d).glob("*.md"), key=lambda p: int(re.search(r"-(\d+)", p.stem).group(1))):
            fm = f.read_text(encoding="utf-8").split("---")[1]
            g = lambda k: (re.search(rf"^{k}:\s*(.*?)(?:\s+#.*)?$", fm, re.M) or [None, ""])[1].strip().strip('"')
            ids = lambda k: re.findall(r"(?:car|act|prj)-\d+", g(k))
            out.append(dict(cat=d, id=g("id"), type=g("type"), title=g("title"),
                            period=re.sub(r"\s*~\s*", "~", g("period")),
                            tags=[t.strip() for t in re.sub(r"[\[\]]", "", g("tags")).split(",") if t.strip()],
                            quant=g("quant").startswith("true"), ready=g("material_ready").startswith("true"),
                            parent=(ids("activity") + ids("career") + [""])[0],
                            projects=ids("projects"), related=ids("related")))
    return out


def short(title):
    return re.split(r" — | \(", title)[0].strip()


def tag_order():
    t = (ROOT / "TAGS.md").read_text(encoding="utf-8")
    return [m for m in re.findall(r"^\| ([가-힣A-Za-z]+) \|", t, re.M) if m != "태그"]


def generate():
    ex = frontmatter()
    by = {e["id"]: e for e in ex}
    ok = lambda b: "✅" if b else "△"
    lines = [HEADER]
    for d, head in CATS:
        rows = [e for e in ex if e["cat"] == d]
        mid = {"career": "", "activities": " 하위 프로젝트 |", "projects": " 상위 |"}[d]
        lines += [f"## {head}", f"| ID | 유형 | 제목 | 기간 |{mid} 역량 태그 | 정량 | 재료 |",
                  "|----|:----:|------|------|" + ("------|" if mid else "") + "-----------|:----:|:----:|"]
        for e in rows:
            extra = {"career": "", "activities": f" {', '.join(e['projects']) or '—'} |",
                     "projects": f" {e['parent'] or '독립'} |"}[d]
            lines.append(f"| {e['id']} | {e['type']} | {e['title']} | {e['period']} |{extra} "
                         f"{'·'.join(e['tags'])} | {ok(e['quant'])} | {ok(e['ready'])} |")
        lines.append("")
    lines += ["## 연결 맵 (활동 → 프로젝트)"]
    for e in ex:
        if e["projects"]:
            kids = ", ".join(f"{p} {short(by[p]['title'])}" for p in e["projects"] if p in by)
            lines.append(f"- **{e['id']} {short(e['title'])}** → {kids}")
    pairs = sorted({tuple(sorted((e["id"], r))) for e in ex for r in e["related"] if r in by
                    and not (by[r]["parent"] == e["id"] or e["parent"] == r)})
    if pairs:
        lines.append("- **그 외 연결(related)**: " + " · ".join(f"{a} ↔ {b}" for a, b in pairs))
    solo = [e["id"] for e in ex if not e["projects"] and not e["parent"] and not any(e["id"] in p for p in pairs)]
    if solo:
        lines.append("- **독립 경험**: " + ", ".join(solo))
    lines += ["", "## 태그별 인덱스 (질문 매칭용)",
              "<!-- 한 줄에 태그 하나: - **태그**: car-01, prj-03  (_check.py가 이 형식으로 읽는다) -->"]
    order = tag_order()
    used = sorted({t for e in ex for t in e["tags"]}, key=lambda t: (order.index(t) if t in order else 999, t))
    for t in used:
        lines.append(f"- **{t}**: " + ", ".join(e["id"] for e in ex if t in e["tags"]))
    return "\n".join(lines).rstrip() + "\n"


def manual_sections(text):
    """생성 대상이 아닌 `## ` 섹션 — 원문 그대로."""
    parts = re.split(r"^(?=## )", text, flags=re.M)[1:]
    return [p.rstrip() + "\n" for p in parts if p.split("\n")[0][3:].strip() not in GENERATED]


def build():
    old = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    manual = manual_sections(old)
    return generate() + ("\n" + "\n".join(manual) if manual else "")


def drift():
    """INDEX.md의 생성 영역이 frontmatter와 다른 줄 수 (0이면 일치). _check.py가 쓴다."""
    old = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    gen = set(generate().split("\n"))
    cur = set(l for p in re.split(r"^(?=## )", old, flags=re.M)
              if not p.startswith("## ") or p.split("\n")[0][3:].strip() in GENERATED for l in p.split("\n"))
    return len((gen ^ cur) - {""})


if __name__ == "__main__":
    new = build()
    if "--diff" in sys.argv:
        old = INDEX.read_text(encoding="utf-8").split("\n") if INDEX.exists() else []
        o, n = set(old), set(new.split("\n"))
        for l in old:
            if l not in n and l.strip():
                print("- " + l[:150])
        for l in new.split("\n"):
            if l not in o and l.strip():
                print("+ " + l[:150])
    else:
        INDEX.write_text(new, encoding="utf-8")
        print(f"INDEX.md 재생성 ({date.today()}) — 표·연결 맵·태그 인덱스 생성, 손 관리 섹션 {len(manual_sections(new))}개 보존")
