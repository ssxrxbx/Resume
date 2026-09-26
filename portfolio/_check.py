#!/usr/bin/env python3
"""포트폴리오 정합성 검사 — /exp-add 직후, /retro 딥 회고 시 실행.

    python3 portfolio/_check.py

경험 파일(frontmatter·증거 조각)과 INDEX.md의 드리프트를 잡는다.
INDEX는 frontmatter의 파생물이므로, 불일치가 나오면 INDEX를 고친다(반대 아님).
"""
import glob, os, re, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
os.chdir(ROOT)

# 규칙 파일 분량 예산(글자 수). 증액은 사용자 승인 후에만 — CLAUDE.md 「규칙 파일 관리」
DOC_BUDGET = {
    '.claude/CLAUDE.md': 4800,
    '.claude/skills/answer/SKILL.md': 10000,
    '.claude/skills/company-analyze/SKILL.md': 4800,
    '.claude/skills/exp-add/SKILL.md': 3500,
    '.claude/skills/retro/SKILL.md': 3600,
}
# Codex 사본: 원본 → 사본 (스킬 사본은 CLAUDE.md 표기를 AGENTS.md로)
MIRRORS = [('.claude/CLAUDE.md', 'AGENTS.md')] + [
    (p, p.replace('.claude/skills/', '.agents/skills/')) for p in DOC_BUDGET if '/skills/' in p]


def mirror_text(src):
    t = open(os.path.join(REPO, src), encoding='utf-8').read()
    return t if src == '.claude/CLAUDE.md' else t.replace('CLAUDE.md', 'AGENTS.md')


if '--sync' in sys.argv:
    for src, dst in MIRRORS:
        os.makedirs(os.path.dirname(os.path.join(REPO, dst)) or REPO, exist_ok=True)
        open(os.path.join(REPO, dst), 'w', encoding='utf-8').write(mirror_text(src))
        print(f"동기화 {src} → {dst}")
    sys.exit(0)

# 자소서 단골 문항이 요구하는 역량 — 각 최소 2건은 있어야 선택지가 생긴다
STAPLE = ['실패극복', '갈등조정', '리더십', '위기관리', '성장', '협업',
          '주도성', '문제해결', '고객지향', '커뮤니케이션', '수상']

err, warn = [], []


NUM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(%|배|건|명|개사|개|종|곳|팀|위|회|주|개월|년|시간|초|분|만|억|천)")


def body_only_nums(t, frag):
    """본문(STAR·개요·구성·전체 성과)에 있는데 증거 조각엔 없는 수치 — ⛔ 사용 제한 줄은 제외."""
    body = "".join(m.group(1) for m in re.finditer(
        r'^## (?:S — 상황|T — 과제|A — 행동|R — 결과|개요|구성|전체 성과)[^\n]*\n(.*?)(?=^## |\Z)', t, re.S | re.M))
    body = "\n".join(l for l in body.split("\n") if not l.lstrip("> ").startswith("⛔")).replace(",", "")
    frag = frag.replace(",", "")
    return sorted({m.group(0) for m in NUM.finditer(body)
                   if not re.search(rf"(?<![\d.]){re.escape(m.group(1).replace(',', ''))}\s*{re.escape(m.group(2))}", frag)})


def load_banned():
    """portfolio/_terms.md 「금지」 표 → [(표현, [문맥])]."""
    f = os.path.join(ROOT, '_terms.md')
    out, cur = [], False
    if not os.path.exists(f):
        return out
    for line in open(f, encoding='utf-8'):
        if line.startswith('## '):
            cur = '금지' in line
            continue
        c = [x.strip() for x in line.strip().strip('|').split('|')] if cur and line.startswith('|') else []
        if c and c[0] not in ('표현', '') and not set(c[0]) <= set('-: ') and not c[0].startswith('('):
            out.append((c[0], [x.strip() for x in c[1].split(',') if x.strip()] if len(c) > 1 else []))
    return out


BANNED = load_banned()


def load():
    exps = {}
    for p in sorted(glob.glob('career/*.md') + glob.glob('activities/*.md') + glob.glob('projects/*.md')):
        t = open(p, encoding='utf-8').read()
        fm = t.split('---')[1]
        g = lambda k: (re.search(rf'^{k}:\s*(.*?)(?:\s*#.*)?$', fm, re.M) or [None, ''])[1].strip().strip('"')
        i = g('id')
        frag = Counter()
        sec = re.search(r'## 증거 조각(.*?)(?=\n## |\Z)', t, re.S)
        n_frag = 0
        bad_frag = []
        if sec:
            for line in sec.group(1).split('\n'):
                if re.match(r'- \[[^\]]+\]', line.strip()):
                    bad_frag.append(line.strip()[:30])
                m = re.match(r'- `((?:\[[^\]]+\])+)`', line.strip())
                if m:
                    n_frag += 1
                    frag.update(re.findall(r'\[([^\]]+)\]', m.group(1)))
        links = set()
        for k in ('related', 'projects', 'activity', 'career'):
            links |= set(re.findall(r'(?:car|act|prj)-\d+', g(k)))
        exps[i] = dict(
            path=p, type=g('type'), quant=g('quant').startswith('true'),
            ready=g('material_ready').startswith('true'),
            tags=set(x.strip() for x in re.sub(r'[\[\]]', '', g('tags')).split(',') if x.strip()),
            frag=frag, n_frag=n_frag, bad_frag=bad_frag, links=links - {i},
            has_star=bool(re.search(r'^## S — 상황', t, re.M)),
            projects=re.findall(r'prj-\d+', g('projects')),
            heads=re.findall(r'^## (.+)$', t, re.M),
            face=(g('title') + ' ' + ((re.search(r'^## 한 줄 요약\n+(?!#)(.+)$', t, re.M) or [None, ''])[1])),
            body_only_nums=body_only_nums(t, sec.group(1) if sec else ''),
            sec_links=set(re.findall(r'(?:car|act|prj)-\d+', ''.join(
                m.group(1) for m in re.finditer(r'^## (?:연결|구성|하위 프로젝트)[^\n]*\n(.*?)(?=^## |\Z)', t, re.S | re.M)))),
            hist=(re.findall(r'\d{4}-\d{2}-\d{2}', t) + re.findall(r'^## .*(?:정정|역류).*$', t, re.M))[:2],
        )
    return exps


E = load()
idx = open('INDEX.md', encoding='utf-8').read()
std = set(re.findall(r'^\| ([가-힣A-Za-z]+) \|', open('TAGS.md', encoding='utf-8').read(), re.M)) - {'태그'}

print(f"경험 {len(E)}건 (container {sum(1 for v in E.values() if v['type']=='container')} / "
      f"episode {sum(1 for v in E.values() if v['type']=='episode')})\n")

# 1. INDEX 행 수 == 파일 수
n_rows = len(re.findall(r'^\| (?:car|act|prj)-\d+ \|', idx, re.M))
(err.append if n_rows != len(E) else print)(
    f"[1] INDEX 행 수 불일치: 파일 {len(E)} vs INDEX {n_rows}" if n_rows != len(E)
    else f"[1] INDEX 행 수 == 파일 수 ({len(E)}) ✅")

# 2. 태그 역색인 양방향
sec = idx.split('## 태그별 인덱스')[1].split('\n## ')[0]
inv = {}
for line in sec.strip().split('\n'):
    m = re.match(r'- \*\*(.+?)\*\*:\s*(.+)', line.strip())
    if m:
        inv[m.group(1)] = set(x.strip() for x in m.group(2).split(','))
fwd = [(i, t) for i, v in E.items() for t in v['tags'] if i not in inv.get(t, set())]
rev = [(t, i) for t, ids in inv.items() for i in ids if t not in E.get(i, {}).get('tags', set())]
for i, t in fwd:
    err.append(f"[2] 색인 누락: {i}의 '{t}' 태그가 INDEX 태그별 인덱스에 없음")
for t, i in rev:
    err.append(f"[2] 유령 항목: INDEX '{t}'에 {i} 있으나 실제 tags에 없음")
if not fwd and not rev:
    print("[2] 태그 역색인 양방향 일치 ✅")

# 3. 조각 태그 ⊄ frontmatter + 표준 어휘 위반
#    승격 기준(조각 2개↑)은 여기서 자동 판정한다. 조각 1개짜리 부수 태그는
#    의도적으로 조각에만 두는 정상 상태이므로 침묵한다(경고 피로 방지).
n_minor = 0
for i, v in E.items():
    bad = set(v['frag']) - std
    if bad:
        err.append(f"[3] {i}: 조각 태그가 표준 어휘 아님 → {sorted(bad)}")
    miss = {t: c for t, c in v['frag'].items() if t not in v['tags'] and t not in bad}
    promote = sorted(t for t, c in miss.items() if c >= 2)
    n_minor += len(miss) - len(promote)
    if promote:
        warn.append(f"[3] {i}: 조각 2개 이상인데 tags에 없음 → {promote} "
                    f"(승격 대상 — 그 역량으로 검색해도 안 걸림)")
if not any(x.startswith('[3]') for x in err + warn):
    print(f"[3] 조각 태그 정합 ✅ (부수 태그 {n_minor}건은 조각에만 유지 — 정상)")

# 4. 연결 대칭 + 고립
asym = [(a, b) for a, v in E.items() for b in v['links'] if b in E and a not in E[b]['links']]
for a, b in asym:
    err.append(f"[4] 연결 비대칭: {a}→{b} 인데 {b}→{a} 없음")
iso = [i for i, v in E.items() if not v['links']]
if iso:
    warn.append(f"[4] 고립 경험(연결 없음): {', '.join(iso)} — 진짜 독립이면 그대로 두되 인지")
if not asym:
    print("[4] 연결 대칭 ✅")

# 5. 유형 ↔ 본문 구조 정합
for i, v in E.items():
    if v['type'] == 'container' and v['has_star']:
        warn.append(f"[5] {i}: container인데 STAR 본문 있음 (episode가 맞는지 확인)")
    if v['type'] == 'episode' and not v['has_star']:
        err.append(f"[5] {i}: episode인데 STAR 본문 없음 (container이거나 미작성)")
    if v['type'] == 'container':
        miss = [h for h in ('개요', '구성', '전체 성과') if not any(x.split(' (')[0] == h for x in v['heads'])]
        if miss:
            err.append(f"[5] {i}: container 섹션 누락 — {', '.join(miss)} (이름 고정: 개요 / 구성 (하위 프로젝트) / 전체 성과)")
    for w, ctx in BANNED:
        if w in v['face'] and (not ctx or any(c in v['face'] for c in ctx)):
            err.append(f"[5-c] {i}: 제목·한 줄 요약에 금지 표현 \"{w}\" — 로스터에 매번 노출돼 답안에 옮겨진다. 사실은 본문(⛔ 표시)에 두고 여기선 뺀다(_terms.md)")
    if v['body_only_nums']:
        warn.append(f"[6-c] {i}: 본문에만 있는 수치 {', '.join(v['body_only_nums'][:5])} — 답안에 쓸 사실이면 증거 조각으로 옮긴다")
    stray = v['sec_links'] - v['links'] - {i}
    if stray:
        err.append(f"[4-b] {i}: 「연결·구성」 섹션의 {', '.join(sorted(stray))}가 frontmatter 연결에 없음 — frontmatter(related 등)에 추가하거나 섹션에서 지운다")
    if v['type'] == 'container' and len(v['tags']) > 10:
        kids = set().union(*[E[k]['tags'] for k in v['projects'] if k in E]) if v['projects'] else set()
        if kids and len(v['tags'] & kids) / len(v['tags']) >= 0.7:
            warn.append(f"[3-b] {i}: container 태그 {len(v['tags'])}개 중 대부분이 하위 프로젝트 태그 복사 — container 레벨 역량만 남긴다(과다 매칭·편중 원인)")
    if v['bad_frag']:
        err.append(f"[6] {i}: 증거 조각 형식 — 태그를 백틱으로 감싼다: - `[태그]` 사실 (현재: {v['bad_frag'][0]}…)")
    if v['hist']:
        err.append(f"[5] {i}: 정정 경위가 파일에 있음 — {v['hist']} → portfolio/_history.md로 옮기고 현재 사실만 남길 것")
    if v['type'] not in ('episode', 'container'):
        err.append(f"[5] {i}: type이 episode/container가 아님 → '{v['type']}'")
if not any(x.startswith('[5]') for x in err + warn):
    print("[5] 유형 ↔ 본문 구조 정합 ✅")

# 6. 증거 조각 보유·개수
no_frag = [i for i, v in E.items() if v['n_frag'] == 0]
if no_frag:
    err.append(f"[6] 증거 조각 없음: {', '.join(no_frag)}")
odd = [f"{i}({v['n_frag']})" for i, v in E.items() if v['n_frag'] and not 3 <= v['n_frag'] <= 8]
if odd:
    warn.append(f"[6] 조각 개수가 3~8 범위 밖: {', '.join(odd)}")
if not no_frag:
    print(f"[6] 증거 조각 보유 {len(E)}/{len(E)} ✅")

# 7. 커버리지 — 단골 문항별 최소 2건
tc = Counter(t for v in E.values() for t in v['tags'])
thin = [(t, tc.get(t, 0)) for t in STAPLE if tc.get(t, 0) < 2]
for t, n in thin:
    warn.append(f"[7] 커버리지 부족: '{t}' {n}건 — 그 문항이 나오면 선택지 없음 "
                f"(under-tagging인지 경험 부족인지 확인)")
if not thin:
    print("[7] 단골 문항 커버리지(각 2건↑) ✅")

# 8. 재료·정량 상태
not_ready = [i for i, v in E.items() if not v['ready']]
if not_ready:
    warn.append(f"[8] material_ready=false: {', '.join(not_ready)} — 주력 배정 전 보강 필요")
print(f"[8] 재료 확보 {len(E)-len(not_ready)}/{len(E)} · 정량 확보 {sum(1 for v in E.values() if v['quant'])}/{len(E)}")

# 8-b. 중복 섹션 헤딩 (편집 누적으로 같은 제목이 두 번 생기는 드리프트)
for i, v in E.items():
    dup = [h for h, n in Counter(v['heads']).items() if n > 1]
    if dup:
        err.append(f"[8-b] {i}: 같은 섹션 제목이 중복 — {', '.join(dup)} (편집 누적 드리프트, 병합 필요)")
if not any(x.startswith('[8-b]') for x in err):
    print("[8-b] 섹션 헤딩 중복 없음 ✅")

# 9. 계열 편중 참고치 (답안 작성 시 분산 판단용)
fam = {i: set([i] + v['projects']) for i, v in E.items() if v['type'] == 'container'}
solo = [i for i, v in E.items() if v['type'] == 'episode' and not any(i in f for f in fam.values())]
print(f"[9] 계열 {len(fam)}개 " + " · ".join(f"{k}+{len(v)-1}" for k, v in fam.items()) + f" · 독립 {len(solo)}건")

# 10. 규칙 파일 분량 예산 + Codex 사본 동기화
sizes = []
for pth, cap in DOC_BUDGET.items():
    fp = os.path.join(REPO, pth)
    if not os.path.exists(fp):
        continue
    n = len(open(fp, encoding='utf-8').read())
    name = 'CLAUDE.md' if pth.endswith('CLAUDE.md') else pth.split('/')[-2]
    sizes.append(f"{name} {n:,}/{cap:,}")
    if n > cap:
        err.append(f"[10] {pth} {n:,}자 > 예산 {cap:,}자 — 합치거나 대체해 줄이고, 불가능하면 사용자에게 증액 제안")
print("[10] 규칙 분량 " + " · ".join(sizes))
for src, dst in MIRRORS:
    d = os.path.join(REPO, dst)
    if os.path.exists(os.path.join(REPO, src)) and (not os.path.exists(d) or open(d, encoding='utf-8').read() != mirror_text(src)):
        err.append(f"[10] Codex 사본 불일치 {dst} — python3 portfolio/_check.py --sync")

print()
for w in warn:
    print("⚠️ ", w)
for e in err:
    print("❌ ", e)
print(f"\n{'='*60}\n오류 {len(err)} · 경고 {len(warn)}")
sys.exit(1 if err else 0)
