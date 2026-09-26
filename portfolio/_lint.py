#!/usr/bin/env python3
"""답안 검사 — `/answer` 문체·형식 규칙을 한 번에 기계 검사한다.

    python3 portfolio/_lint.py <회사명>                    # session.md 「현재 초안」
    python3 portfolio/_lint.py <회사명> --file x.txt [--limit 800] [--type A]
    python3 portfolio/_lint.py <회사명> --all              # answers.md 저장본 전체 (회고·보정용)
    python3 portfolio/_lint.py <회사명> --coverage         # JD 키워드가 지원서 전체의 어느 문항에 있나
    옵션: --kw "키워드1,키워드2"   JD 키워드 포함 여부 (--coverage는 없으면 session.md 「분석 요약」에서 읽는다)

즉석 검사 스크립트를 짜거나 초안을 명령에 다시 타이핑하지 않기 위한 도구다.
판정: ❌ 규칙 위반(사용자에게 보이기 전에 고친다) / ⚠️ 판단 필요(에이전트가 확인).
포지셔닝·인과의 진위·톤은 검사하지 않는다 — 그건 루브릭(`/retro` A)이 본다.
규칙 원문은 `/answer` SKILL.md 「문체」·「기계 검사」. 규칙을 바꾸면 여기 목록도 함께 고친다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

# ── 규칙 목록 (SKILL.md와 동기화) ─────────────────────────────
BRIDGES = ["이를 통해", "이렇게 쌓은", "또한", "나아가"]           # 도식적 브릿지 (⚠️ — 승인 답안에도 드물게 있음)
ORDER_LABELS = ["첫째", "둘째", "셋째"]                            # 순서 라벨
COLLOQUIAL = ["돌아가는지", "들여다봤", "들여다보", "다뤄보고 싶어",  # 구어·회화체
              "눈을 키웠", "짚어", "쪼개"]
ABSTRACT = ["원리", "구조", "역량"]                                # 땜빵 추상명사 (4회↑)
LEN = {  # 유형별 문장 길이: (목표 상한, 규칙 상한, 무조건 분할) — None이면 ⚠️만
    "narr": (60, 80, 100),
    "D": (90, 110, None),
}
MIN_SHARE_LONG = 0.15   # 서술형: 60자↑ 문장이 이 비율 미만이면 "전부 단문" 경고 (승인 기준 약 1/3)
COPY_MIN = 25           # 같은 회사 다른 문항과 이 길이 이상 연속 일치하면 중복 경고
COPY_MIN_SRC = 30       # 포트폴리오 원본과는 이 길이 이상 (서비스명·설명구 수준의 짧은 일치는 정상)
FILL = 0.95             # 글자 수 목표: 제한의 95% 이상
# 수치 근거: "숫자+단위"가 경험 파일·회사 분석에 없으면 ⚠️ (합산·외부 출처면 근거를 남기고 유지)
NUM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(%|퍼센트|배|건|명|개사|개|종|곳|팀|위|회|주|개월|년|시간|초|분|만|억|천)")


def clean(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"```[a-z]*\n?", "", t)
    t = re.sub(r"^\s*>.*$", "", t, flags=re.M)          # 인용 = 작성 메모, 답안 아님
    return t.replace("**", "").replace("`", "").strip()


def split_title(body):
    lines = [l for l in body.split("\n") if l.strip()]
    if lines and re.match(r"^\s*\[.+\]\s*$", lines[0]):
        return lines[0].strip()[1:-1].strip(), "\n".join(lines[1:])
    return None, "\n".join(lines)


def sentences(text):
    out = []
    for para in text.split("\n"):
        para = para.strip()
        if not para or re.match(r"^\s*\[.+\]\s*$", para):
            continue
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=\S)", para) if len(s.strip()) > 1]
    return out


def shingles(text, n=COPY_MIN):
    t = re.sub(r"\s+", " ", text)
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def overlaps(text, pool, n=COPY_MIN):
    """text 안에서 pool(각 원천의 n자 shingle 집합)과 n자 이상 연속 일치하는 구간."""
    t = re.sub(r"\s+", " ", text)
    hits = []
    for name, sh in pool:
        i = 0
        while i <= len(t) - n:
            if t[i:i + n] in sh:
                j = i + n
                while j < len(t) and t[j - n + 1:j + 1] in sh:
                    j += 1
                hits.append((j - i, name, t[i:j]))
                i = j
            else:
                i += 1
    return sorted(hits, reverse=True)


def portfolio_pool():
    pool = []
    for f in sorted(ROOT.glob("*/*.md")):
        if "_templates" in f.parts:
            continue
        m = re.search(r"^id:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
        body = clean(f.read_text(encoding="utf-8").split("---", 2)[-1])
        pool.append((m.group(1) if m else f.stem, shingles(body, COPY_MIN_SRC)))
    return pool


def source_corpus(company):
    """수치 근거를 찾을 원천: 경험 파일·프로필·기술 + 그 회사 분석(이름이 겹치는 폴더 포함). _history는 제외."""
    fs = [f for f in ROOT.glob("**/*.md") if "_templates" not in f.parts and f.name != "_history.md"
          and f.name not in ("INDEX.md", "TAGS.md")]
    cdir = REPO / "companies"
    if cdir.exists():
        for d in cdir.iterdir():
            if d.is_dir() and (company.startswith(d.name) or d.name.startswith(company)):
                fs += list(d.glob("**/*.md"))
    return clean("\n".join(f.read_text(encoding="utf-8") for f in fs)).replace(",", "")


def short(s, n=34):
    return s if len(s) <= n else s[:n] + "…"


def parse_limit(s):
    """'(800자 제한' · '1,000자' · '최대 1,500자' · '500~1000자' → 상한 정수. 공백 제외 표기도 읽는다."""
    s2 = s.replace(",", "")
    nums = [int(x) for x in re.findall(r"(\d{2,5})\s*자", s2)]
    return (max(nums) if nums else None), bool(re.search(r"공백\s*제외", s))


def parse_type(s):
    m = re.search(r"\b([ABCD])(?:\+[ABCD])?\s*(?:형|\(|$|\s|—)", s) or re.search(r"([ABCD])형", s)
    return m.group(1) if m else ("D" if "항목 기입" in s else None)


def lint(body, limit=None, no_space=False, qtype=None, locked=(), others=(), kw=(), pool=None, label="", per_item=False, corpus=None, jd_terms=()):
    body = clean(body)
    title, text = split_title(body)
    sents = sentences(body)
    kind = "D" if qtype == "D" else "narr"
    goal, cap, hard = LEN[kind]
    full = re.sub(r"\n\s*\n+", "\n", body).strip()
    n_sp, n_ns, n_nl = len(full.replace("\n", "")), len(re.sub(r"\s", "", full)), len(full)
    E, W, OK = [], [], []

    # 1. 글자 수
    n = n_ns if no_space else n_sp
    if per_item:
        OK.append("항목별 제한 — 글자 수는 항목마다 따로 확인")
    elif limit:
        pct = n / limit
        msg = f"글자 수 {n}/{limit} ({pct:.0%}{', 공백 제외' if no_space else ''})"
        if n > limit:
            E.append(msg + f" — {n - limit}자 초과")
        elif not no_space and n_nl > limit:
            W.append(msg + f" — 줄바꿈까지 세는 사이트면 {n_nl}자로 초과. 입력란 기준 확인")
        else:
            (W if pct < FILL else OK).append(msg + (f" — 95%까지 {int(limit * FILL) - n}자 부족" if pct < FILL else ""))
    # 2. 소제목
    if not title:
        (OK.append("소제목 없음(D형 허용)") if kind == "D" else E.append("소제목 없음 — 첫 줄에 [소제목] 1개"))
    elif kind == "narr" and re.search(r"(다|니다|겠습니다|싶습니다)$", title):
        E.append(f"소제목이 문장형 — 서술형은 명사형: [{short(title)}]")
    elif kind == "D" and not title.endswith("다"):
        W.append(f"D형 소제목은 `~하다` 문장형 권장: [{short(title)}]")
    elif kind == "D" and not 30 <= len(title) <= 50:
        W.append(f"D형 소제목 {len(title)}자 (권장 30~50자)")
    else:
        OK.append(f"소제목 [{short(title, 24)}]")
    # 3. 문장 길이
    lk = [s for s in locked if s]
    judged = [(i, s) for i, s in enumerate(sents, 1) if not any(s in l or l in s for l in lk)]
    over = [(i, s) for i, s in judged if len(s) > cap]
    if sents:
        L = [len(s) for s in sents]
        dist = f"{len(L)}문장 평균 {sum(L) // len(L)}자, {min(L)}~{max(L)}자, 60자↑ {sum(x >= 60 for x in L) / len(L):.0%}"
        if over:
            det = ", ".join(f"#{i}({len(s)}자) \"{short(s, 22)}\"" for i, s in over[:4])
            hard_over = hard and any(len(s) > hard for _, s in over)
            (E if hard_over else W).append(
                f"{cap}자 초과 {len(over)}문장{f' ({hard}자↑는 분할 필수)' if hard_over else ''} — {det}  [{dist}]")
        else:
            OK.append(f"문장 길이 [{dist}]")
        if kind == "narr" and len(L) >= 6 and sum(x >= 60 for x in L) / len(L) < MIN_SHARE_LONG:
            W.append("전부 단문에 가까움 — 인과·역접을 종속절로 흡수해 60~80자를 1/3쯤 섞는다")
    # 4. 금지 표현
    mid = body
    for k in jd_terms:                      # JD 표기 그대로 쓴 용어의 가운뎃점은 허용
        mid = mid.replace(k, "")
    bad = ([f"가운뎃점 {mid.count('·')}개(쉼표로, JD 표기 용어는 예외)"] if "·" in mid else []) + \
          [f"\"{w}\" {text.count(w)}회" for w in ORDER_LABELS + COLLOQUIAL if w in text]
    (E if bad else OK).append("금지 표현: " + ", ".join(bad) if bad else "금지 표현 없음")
    br = [f"\"{w}\"" for w in BRIDGES if w in text]
    if br:
        W.append(f"도식적 브릿지 {', '.join(br)} — 내용으로 잇는 편이 낫다(승인 문장이면 유지)")
    # 5. 확인 필요
    for i, s in enumerate(sents):
        if "그 결과" in s:
            prev = sents[i - 1] if i else ""
            W.append(f"\"그 결과\" 인과 확인: \"{short(prev, 26)}\" → \"{short(s, 26)}\"")
    for w in ABSTRACT:
        if text.count(w) >= 4:
            W.append(f"추상명사 \"{w}\" {text.count(w)}회 — 다른 표현으로")
    # 6. 🔒 승인 문장 보존
    if lk:
        miss = [l for l in lk if l not in body]
        (E if miss else OK).append(
            f"🔒 승인 문장 {len(lk) - len(miss)}/{len(lk)} 보존" + (" — 변형·누락: " + "; ".join(f"\"{short(m)}\"" for m in miss) if miss else ""))
    # 7·8. 원본 복붙 / 다른 문항 중복
    for pool_, what, k_ in ((pool, "원본 문장 일치", COPY_MIN_SRC), (others, "같은 회사 다른 문항과 일치", COPY_MIN)):
        if not pool_:
            continue
        h = overlaps(text, pool_, k_)
        if h:
            W.append(f"{what} {len(h)}곳 — " + "; ".join(f"{k}자 {nm} \"{short(s, 28)}\"" for k, nm, s in h[:3]))
        else:
            OK.append(f"{what} 없음")
    # 9. JD 키워드
    if kw:
        miss = [k for k in kw if k not in text]
        (W if miss else OK).append(f"JD 키워드 {len(kw) - len(miss)}/{len(kw)}" + (f" — 없음: {', '.join(miss)}" if miss else ""))

    # 10. 수치 근거 (🔒 문장 제외)
    if corpus is not None:
        judged_text = " ".join(s for s in sents if not any(s in l or l in s for l in lk))
        miss = sorted({m.group(0) for m in NUM.finditer(judged_text)
                       if not re.search(rf"(?<![\d.]){re.escape(m.group(1).replace(',', ''))}\s*{re.escape(m.group(2))}", corpus)})
        (W if miss else OK).append("수치 근거 확인" if not miss else
            f"원본에 없는 수치 {len(miss)}개 — {', '.join(miss[:6])} (합산·외부 출처면 근거를 사용 경험 ID에 남기고, 아니면 원본 수치로 고친다)")

    typ = qtype or "?"
    print(f"■ {label} ({limit or '제한 없음'}{'자' if limit else ''}, {typ}형) — 공백 포함 {n_sp} / 제외 {n_ns}")
    print("✅ " + " · ".join(OK))
    for e in E:
        print("❌ " + e)
    for w in W:
        print("⚠️  " + w)
    print(f"→ ❌ {len(E)} · ⚠️ {len(W)}\n")
    return len(E)


# ── 입력 파싱 ────────────────────────────────────────────────
def sections(text, level="###"):
    parts = re.split(rf"^{level} ", text, flags=re.M)
    return {p.split("\n")[0].strip(): p.split("\n", 1)[1] if "\n" in p else "" for p in parts[1:]}


def answer_blocks(company):
    p = REPO / "applications" / company / "answers.md"
    if not p.exists():
        return []
    out = []
    for blk in re.split(r"^## ", p.read_text(encoding="utf-8"), flags=re.M)[1:]:
        head = blk.split("\n")[0]
        m = re.search(r"^### 답안[^\n]*\n(.*?)(?=^#{2,3} |\Z)", blk, re.S | re.M)
        if not m or not clean(m.group(1)):
            continue
        tm = re.search(r"\*\*문항\s*유형\*\*\s*:?\s*([^\n]*)", blk)
        limit, ns = parse_limit(head)
        per_item = bool(re.search(r"(각|별|항목당)\s*(?:상세설명\s*)?(?:최대\s*)?\d[\d,]*\s*자", head))
        out.append(dict(head=head.strip(), body=m.group(1), limit=limit, no_space=ns, per_item=per_item,
                        qtype=parse_type(tm.group(1)) if tm else parse_type(head)))
    return out


def from_session(company):
    p = REPO / "applications" / company / "session.md"
    if not p.exists():
        sys.exit(f"❌ 없음: {p} — `--file`로 텍스트를 넘기거나 session.md를 만든다")
    t = p.read_text(encoding="utf-8")
    prog = t.split("\n## 진행 중", 1)[-1] if "\n## 진행 중" in t else ""
    sec = sections(prog)
    draft = next((v for k, v in sec.items() if k.startswith("현재 초안")), "")
    lock = next((v for k, v in sec.items() if "승인 문장" in k), "")
    locked = [clean(re.sub(r"^\s*-\s*", "", l)).strip('"“”') for l in lock.split("\n")
              if re.match(r"^\s*-\s*\S", l)]
    q = re.search(r"^-\s*\**문항\**\s*:\s*(.*)$", prog, re.M)
    qline = q.group(1) if q else ""
    if not re.search(r"\d+\s*자", qline):   # 문항 상태표의 ◐ 행에서 보충
        row = next((l for l in t.split("\n") if l.startswith("|") and "◐" in l), "")
        qline += " " + row
    limit, ns = parse_limit(qline)
    return dict(head=f"{company} 진행 중 {qline.split('|')[0].strip()[:30]}", body=clean(draft),
                limit=limit, no_space=ns, qtype=parse_type(qline), locked=locked)


def coverage(company, blocks, kw):
    """JD 키워드가 지원서 전체(저장 답안 + 현재 초안)의 어느 문항에 들어 있는지. 빈 축을 찾는다."""
    sp = REPO / "applications" / company / "session.md"
    draft = ""
    if sp.exists():
        st = sp.read_text(encoding="utf-8")
        if not kw:
            m = re.search(r"^-\s*JD 키워드[^:]*:\s*(.+)$", st, re.M)
            kw = [k.strip(" `*") for k in re.split(r"[,，、]", m.group(1)) if k.strip(" `*")] if m else []
        try:
            draft = from_session(company)["body"]
        except SystemExit:
            pass
    if not kw:
        print("❌ 키워드 없음 — --kw \"A,B\" 로 주거나 session.md 「분석 요약」의 'JD 키워드' 줄을 채운다")
        return 1
    docs = [(b["head"].split("]")[0].lstrip("Q. [")[:14] or b["head"][:14], clean(b["body"])) for b in blocks]
    if draft:
        docs.append(("현재 초안", clean(draft)))
    print(f"■ {company} JD 키워드 커버리지 — 문항 {len(docs)}개")
    empty = []
    for k in kw:
        where = [n for n, d in docs if k in d]
        empty += [] if where else [k]
        print(f"  {'✅' if where else '⚠️ '} {k:16s} {', '.join(where) if where else '어느 문항에도 없음'}")
    print(f"→ 빈 축 {len(empty)}/{len(kw)}" + (f": {', '.join(empty)} — 남은 문항에 배정하거나 이유를 남긴다" if empty else ""))
    return 0


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        print(__doc__)
        return 1
    company, args = argv[1], argv[2:]
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    kw = [k.strip() for k in (opt("--kw") or "").split(",") if k.strip()]
    pool = portfolio_pool()
    corpus = source_corpus(company)
    blocks = answer_blocks(company)
    jd_terms = [k for k in kw if "·" in k]
    sp = REPO / "applications" / company / "session.md"
    if sp.exists():
        m = re.search(r"^-\s*JD 키워드[^:]*:\s*(.+)$", sp.read_text(encoding="utf-8"), re.M)
        if m:
            jd_terms += [k.strip(" `*") for k in re.split(r"[,，、]", m.group(1)) if "·" in k]
    if "--coverage" in args:
        return coverage(company, blocks, kw)
    others_of = lambda body: [(b["head"][:20], shingles(clean(b["body"]))) for b in blocks
                              if clean(b["body"]) != clean(body)]
    errs = 0
    if "--all" in args:
        if not blocks:
            print(f"⚠️  `### 답안` 블록 없음: applications/{company}/answers.md (구 포맷이면 검사 대상 아님)")
            return 0
        for b in blocks:
            errs += lint(b["body"], b["limit"], b["no_space"], b["qtype"], others=others_of(b["body"]),
                         kw=kw, pool=pool, label=b["head"][:48], per_item=b["per_item"], corpus=corpus, jd_terms=jd_terms)
        print(f"■ {company} {len(blocks)}문항 — ❌ 합계 {errs}")
    elif opt("--file"):
        body = Path(opt("--file")).read_text(encoding="utf-8")
        errs = lint(body, int(opt("--limit")) if opt("--limit") else None, "--no-space" in args,
                    opt("--type"), others=others_of(body), kw=kw, pool=pool, label=f"{company} {opt('--file')}", corpus=corpus, jd_terms=jd_terms)
    else:
        s = from_session(company)
        if not s["body"]:
            print("❌ session.md 「현재 초안」이 비어 있다")
            return 1
        errs = lint(s["body"], s["limit"], s["no_space"], s["qtype"], locked=s["locked"],
                    others=others_of(s["body"]), kw=kw, pool=pool, label=s["head"], corpus=corpus, jd_terms=jd_terms)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
