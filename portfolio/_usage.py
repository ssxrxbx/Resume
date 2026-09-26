#!/usr/bin/env python3
"""답안 아카이브 사용 이력 집계 — 개별 ID + 계열, 두 단위로.

사용:  python3 portfolio/_usage.py <회사명>
예:    python3 portfolio/_usage.py 회사명

`/answer` 「2. 후보 스캔」의 선행 단계. `--exp prj-08`: 모든 회사 답안에서 그 경험을 쓴 문장만(프레이밍 일관성 확인). 인라인 스크립트를 쓰지 않는 이유:
아카이브 포맷이 회사마다 조금씩 달라(`### 사용 경험 ID` 헤딩 / `**사용 경험 ID**:` 볼드,
`[car-01](링크)` / `**car-01**` 표기) 정규식 하나로는 조용히 0건을 리턴한다.
편중 경보가 "미사용"으로 오작동하면 편중을 못 잡으므로, 포맷 관용적으로 파싱한다.
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ID = r"(?:car|act|prj)-\d+"
META = {}   # id → type·tags·정량·재료·한 줄 요약 (로스터 출력용)


def load_roster():
    """경험 파일 frontmatter에서 전체 로스터와 계열(container+하위)을 만든다."""
    roster, projects_of, parent_of = {}, {}, {}
    META.clear()
    for f in sorted(ROOT.rglob("*.md")):
        if "_templates" in f.parts:      # 템플릿(car-00 등)은 로스터가 아니다
            continue
        head = f.read_text(encoding="utf-8").split("---")[1] if "---" in f.read_text(encoding="utf-8") else ""
        m = re.search(r"^id:\s*(\S+)", head, re.M)
        if not m:
            continue
        eid = m.group(1)
        t = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M)
        roster[eid] = (t.group(1) if t else f.stem)[:44]
        g = lambda k: (re.search(rf"^{k}:\s*(.*?)(?:\s+#.*)?$", head, re.M) or [None, ""])[1]
        body = f.read_text(encoding="utf-8").split("---", 2)[-1]
        s = re.search(r"^## 한 줄 요약\n+(?!#)(.+)$", body, re.M)
        META[eid] = dict(type=g("type")[:1] or "?", tags=re.sub(r"[\[\]\s]", "", g("tags")),
                         quant="✅" if g("quant").startswith("true") else "△",
                         ready="✅" if g("material_ready").startswith("true") else "✗",
                         summary=re.sub(r"\*\*|`", "", s.group(1)).strip()[:60] if s else "")
        p = re.search(r"^projects:\s*\[(.*?)\]", head, re.M)
        if p:
            kids = re.findall(ID, p.group(1))
            projects_of[eid] = kids
            for k in kids:
                parent_of[k] = eid
        for key in ("career", "activity"):
            a = re.search(rf"^{key}:\s*\"?({ID})", head, re.M)
            if a:
                parent_of.setdefault(eid, a.group(1))
    return roster, projects_of, parent_of


def parse_blocks(text):
    """문항 블록으로 자른다 — `## Q.`가 있으면 그걸로, 없으면 모든 `## ` 헤딩으로."""
    parts = re.split(r"\n## Q\.", text)
    if len(parts) > 1:
        return [("## Q." + p).split("\n")[0][:60] and ("## Q." + p) for p in parts[1:]]
    parts = re.split(r"\n## (?!Q\.)", text)
    return ["## " + p for p in parts[1:]]


def qtype_of(block):
    """문항 유형(A/B/C/D)을 읽는다. D형(항목 기입 = 이력 필드)은 편중 판정 대상이 아니다.

    경력사항·수상경력·프로젝트 같은 이력 필드는 '그 경험을 쓸 수밖에 없는 칸'이라,
    편중 분모에 넣으면 car-01 계열 경보가 상시 울려 진짜 편중과 구별되지 않는다.
    유형이 안 적힌 옛 아카이브는 보수적으로 서술형으로 세고 그 사실을 경고한다."""
    m = re.search(r"\*\*문항\s*유형\*\*\s*:?\s*\**\s*([ABCD])", block)
    return m.group(1) if m else None


def ids_in_block(block):
    """그 문항이 '사용'했다고 밝힌 경험 ID만 뽑는다(개정 이력·전략 카드 언급은 제외)."""
    secs = re.findall(
        r"(?:^#{2,4}\s*(?:✅\s*)?사용(?:한)?\s*(?:핵심\s*)?경험\s*(?:ID|근거)[^\n]*\n(.*?)(?=\n#{2,4}\s|\Z)"
        r"|\*\*사용(?:한)?\s*(?:핵심\s*)?경험\s*(?:ID|근거)[^*]*\*\*\s*:?(.*?)(?=\n\*\*|\n#{2,4}\s|\n\n|\Z))",
        block, re.S | re.M)
    body = "\n".join(a or b for a, b in secs)
    if not body:
        return set(), False
    return set(re.findall(ID, body)), True


def total_usage():
    """전 회사 답안에서 경험별 사용 횟수(로스터 표시용)."""
    c = Counter()
    for f in (REPO / "applications").glob("*/answers.md"):
        for b in parse_blocks(f.read_text(encoding="utf-8")):
            c.update(ids_in_block(b)[0])
    return c


def print_roster(roster, per_id, parent_of):
    """후보 스캔용 전체 로스터 — INDEX.md 전체를 읽지 않아도 되게 한 줄씩(frontmatter 기준이라 항상 최신).
    ⭐ 보강 1순위 = 전체 5회↑ 쓰였는데 정량 △ / 💤 미활용 강한 재료 = 정량 ✅인데 전체 1회 이하."""
    tot = total_usage()
    print(f"\n[로스터] {len(roster)}건 — ID 유형(e/c) 재료/정량 · 이 회사 사용 · 제목 — 한 줄 요약 · 태그  (⭐ 정량 보강 1순위 · 💤 미활용 강한 재료)")
    for i in sorted(roster, key=lambda x: (x[:3] != "car", x[:3] != "act", x)):
        m = META.get(i, {})
        up = f" ↑{parent_of[i]}" if i in parent_of else ""
        used = f"{per_id[i]}회" if per_id.get(i) else "·"
        flag = "⭐" if tot[i] >= 5 and m.get("quant") == "△" else "💤" if m.get("quant") == "✅" and tot[i] <= 1 else "  "
        print(f"  {flag}{i} {m.get('type','?')} {m.get('ready','?')}/{m.get('quant','?')} {used:>3}{up}  {roster[i]} — {m.get('summary','')} · {m.get('tags','')}")


def main(company):
    path = REPO / "applications" / company / "answers.md"
    roster, projects_of, parent_of = load_roster()
    if not path.exists():
        print(f"■ {company} — 저장된 답안 없음(첫 문항). 편중 집계는 건너뛴다.")
        print_roster(roster, {}, parent_of)
        return 0
    text = path.read_text(encoding="utf-8")

    blocks = parse_blocks(text)
    per_id, per_line, missing = Counter(), Counter(), []
    narr_line, n_narr, n_field, n_untyped = Counter(), 0, 0, 0
    for b in blocks:
        title = b.split("\n")[0].lstrip("# ").strip()[:52]
        ids, found = ids_in_block(b)
        if not found:
            missing.append(title)
        per_id.update(ids)
        lines = {parent_of.get(i, i) for i in ids}
        per_line.update(lines)
        t = qtype_of(b)
        if t == "D":
            n_field += 1
        else:                        # A·B·C + 유형 미기재(보수적으로 서술형 취급)
            n_narr += 1
            n_untyped += (t is None)
            narr_line.update(lines)

    print(f"■ {company} — 문항 {len(blocks)}건 (서술형 {n_narr} · 이력 필드(D) {n_field})")
    if n_untyped:
        print(f"⚠️  문항 유형 미기재 {n_untyped}건 — 서술형으로 세었다. "
              f"`**문항 유형**: A~D`를 블록에 넣으면 편중 판정이 정확해진다")
    if missing:
        print("⚠️  '사용 경험 ID' 섹션을 못 찾은 문항 (아카이브 포맷 확인 필요):")
        for m in missing:
            print(f"     - {m}")

    print(f"\n[개별 ID] {per_id.most_common()}")
    print(f"[계열]    {per_line.most_common()}   ← container+하위를 한 계열로 묶음")

    hot_id = [f"{k}({v}회)" for k, v in per_id.most_common() if v > 1]
    hot_line = [f"{k}({v}문항)" for k, v in per_line.most_common() if v > 1]
    print(f"\n2회 이상 (개별): {hot_id or '없음'}")
    print(f"2문항 이상 (계열): {hot_line or '없음'}  ← 계열 편중이 진짜 경보")
    if narr_line:
        top, n = narr_line.most_common(1)[0]
        print(f"[서술형만] {narr_line.most_common()}   ← 편중 판정은 이 줄로 한다")
        if n_narr >= 3 and n / n_narr >= 0.5:
            print(f"🚨 계열 편중: 서술형 {n_narr}문항 중 {n}문항이 '{top}' 계열 "
                  f"— 정당한 편중(그 경험이 유일·압도적 적합)인지 관성인지 판정할 것")
    if n_field:
        print(f"(이력 필드 {n_field}건은 편중 분모에서 제외 — 경력·수상·프로젝트 칸은 "
              f"쓸 경험이 정해져 있어 편중 판정 대상이 아니다)")

    unused = [i for i in roster if i not in per_id]
    print_roster(roster, per_id, parent_of)
    for i in []:
        print(f"   {i}  {roster[i]}")
    if len(unused) > len(roster) / 2:
        print(f"⚠️  로스터의 절반 이상({len(unused)}/{len(roster)})이 미사용 — 게이트에 보고할 것")
    return 0


def by_experience(eid):
    """모든 회사 answers.md에서 eid를 근거로 쓴 줄(「사용 경험 ID」)만 모은다 — 답안 전문을 읽지 않고 프레이밍을 대조."""
    n = 0
    for f in sorted((REPO / "applications").glob("*/answers.md")):
        for b in parse_blocks(f.read_text(encoding="utf-8")):
            ids, _ = ids_in_block(b)
            if eid not in ids:
                continue
            title = b.split("\n")[0].lstrip("# ").strip()[:40]
            lines = [l.strip() for l in b.split("\n") if eid in l and l.strip().startswith(("-", "|", "*"))][:2]
            print(f"■ {f.parent.name} · {title}")
            for l in lines:
                print(f"    {l[:180]}")
            n += 1
    print(f"→ {eid}: {n}문항에서 사용")
    return 0


if __name__ == "__main__":
    if "--exp" in sys.argv:
        sys.exit(by_experience(sys.argv[sys.argv.index("--exp") + 1]))
    if len(sys.argv) < 2:
        print(__doc__)
        cs = sorted(p.name for p in (REPO / "applications").iterdir() if p.is_dir())
        print("회사:", ", ".join(cs))
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
