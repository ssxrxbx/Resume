#!/usr/bin/env python3
"""회귀 테스트 — 답안 규칙을 바꾼 뒤, 승인된 과거 답안을 현재 규칙으로 다시 써 보고 비교한다.

    python3 portfolio/_regress.py                 # 후보 목록 (★ = 개정이 많았던 문항 — 과거 결함 재발을 보기 좋다)
    python3 portfolio/_regress.py <회사> <번호>    # 그 문항의 작성자·채점자 지시문 + 비교 재료를 portfolio/.regress/에 만든다

`/retro` 딥 회고에서 답안 규칙을 크게 고쳤을 때 쓴다. 작성자는 하위 에이전트로 **승인 답안을 보지 않고** 쓴다.
작성자 초안은 사용자와 여러 번 주고받기 전의 첫 초안이라 승인본보다 낮은 게 정상이다 —
비교의 초점은 ①승인본의 「개정 이력」에 적힌 과거 결함이 재발하는가 ②루브릭 A 항목별로 어디가 모자라는가다.
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
import _lint


def candidates():
    out = []
    for f in sorted((REPO / "applications").glob("*/answers.md")):
        text = f.read_text(encoding="utf-8")
        secs = {s.split("\n")[0].strip(): s for s in re.split(r"^## ", text, flags=re.M)[1:]}
        for b in _lint.answer_blocks(f.parent.name):
            sec = secs.get(b["head"], "")
            hist = re.search(r"^### 개정 이력[^\n]*\n(.*?)(?=^#{2,3} |\Z)", sec, re.S | re.M)
            n_rev = len(re.findall(r"^\s*(?:-|\d+\.)\s", hist.group(1), re.M)) if hist else 0
            out.append(dict(company=f.parent.name, head=b["head"], body=b["body"], qtype=b["qtype"],
                            limit=b["limit"], hist=hist.group(1).strip() if hist else "", n_rev=n_rev))
    return out


def main(argv):
    cs = candidates()
    if len(argv) < 3:
        for n, c in enumerate(cs, 1):
            star = "★" if c["n_rev"] >= 3 else " "
            print(f"{n:>3} {star} {c['company']:<8} {c['qtype'] or '?'}형 {c['limit'] or '-':>5}자  개정 {c['n_rev']:>2}  {c['head'][:50]}")
        print("\n고르는 기준: 유형이 겹치지 않게 2~3개(서술형 1~2 + 항목 기입형 1), ★ 우선. 다음: _regress.py <회사> <번호>")
        return 0
    company, num = argv[1], int(argv[2])
    c = cs[num - 1]
    if c["company"] != company:
        sys.exit(f"❌ {num}번은 {c['company']} 문항이다")
    d = ROOT / ".regress" / f"{date.today()}-{company}-{num}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "approved.md").write_text(f"# 승인본 — {c['head']}\n\n{_lint.clean(c['body'])}\n", encoding="utf-8")
    (d / "defects.md").write_text(f"# 승인까지의 개정 이력 (과거 결함)\n\n{c['hist'] or '(기록 없음)'}\n", encoding="utf-8")
    rel = d.relative_to(REPO)
    writer = f"""[작성자 지시문 — 하위 에이전트에 그대로 넘긴다]
저장소 {REPO} 에서 `/answer`를 수행한다. 회사: {company} / 문항: {c['head']}
- 먼저 `.claude/CLAUDE.md`와 `.claude/skills/answer/SKILL.md`를 읽고 그 절차를 따른다(스킬 안의 스크립트도 그대로 쓴다).
- 회사 입력: `companies/{company}/`(분석 요약이 있으면 `applications/{company}/session.md` 「분석 요약」만). 경험: `portfolio/`.
- **블라인드**: `applications/*/answers.md`를 직접 열지 않는다(다른 회사 답안 포함 — 승인본이 옮겨져 있을 수 있다). 다른 답안의 프레이밍은 `_usage.py --exp`의 한 줄 출력으로만 본다. `{rel}/`도 열지 않는다.
- 사용자가 없다. 스킬이 사용자에게 묻거나 승인을 받으라는 자리에서는 기본값을 고르고 무엇을 골랐는지 적는다. 사실은 원본에 있는 것만 쓴다.
- 결과: `{rel}/new.md`에 전략 카드 → 답안 → 사용 경험 ID 순으로 저장하고, `python3 portfolio/_lint.py {company} --file <답안만 담은 임시 파일>` 결과 요약 한 줄을 붙인다. 채팅 보고는 파일 경로와 lint 요약만."""
    judge = f"""[채점자 지시문 — 작성자와 다른 하위 에이전트에 넘긴다]
`{rel}/approved.md`(사용자 승인본)와 `{rel}/new.md`(현재 규칙의 첫 초안)를 비교한다. `{rel}/defects.md`는 승인까지 고친 과거 결함이다.
1. `.claude/skills/retro/SKILL.md` 루브릭 A 0~10번을 두 답안 각각 ✅/⚠️/❌로 채점한다(근거 한 줄씩).
2. 과거 결함마다 new.md에서 **재발 / 방지됨 / 해당 없음**을 판정한다 — 이것이 규칙 효과의 1차 지표다.
3. new.md가 승인본보다 나은 점이 있으면 적는다(첫 초안이 더 나으면 규칙이 품질을 올렸다는 증거다).
4. 결론: 규칙 개선 / 중립 / 퇴보 중 하나 + 원인이 된 규칙(스킬의 어느 줄)을 짚는다. `{rel}/verdict.md`에 저장하고, 채팅엔 결론과 재발 결함 수만."""
    (d / "brief.md").write_text(writer + "\n\n" + judge + "\n", encoding="utf-8")
    print(f"■ {rel}/ — approved.md · defects.md(개정 {c['n_rev']}건) · brief.md\n")
    print(writer + "\n\n" + judge)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
