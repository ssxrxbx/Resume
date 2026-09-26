#!/usr/bin/env python3
"""포트폴리오 정합성 검사 — /exp-add 직후, /retro 딥 회고 시 실행.

    python3 portfolio/_check.py

경험 파일(frontmatter·증거 조각)과 INDEX.md의 드리프트를 잡는다.
INDEX는 frontmatter의 파생물이므로, 불일치가 나오면 INDEX를 고친다(반대 아님).
"""
import glob, os, re, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# 자소서 단골 문항이 요구하는 역량 — 각 최소 2건은 있어야 선택지가 생긴다
STAPLE = ['실패극복', '갈등조정', '리더십', '위기관리', '성장', '협업',
          '주도성', '문제해결', '고객지향', '커뮤니케이션', '수상']

err, warn = [], []


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
        if sec:
            for line in sec.group(1).split('\n'):
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
            frag=frag, n_frag=n_frag, links=links - {i},
            has_star=bool(re.search(r'^## S — 상황', t, re.M)),
            projects=re.findall(r'prj-\d+', g('projects')),
            heads=re.findall(r'^## (.+)$', t, re.M),
        )
    return exps


E = load()
idx = open('INDEX.md', encoding='utf-8').read()
std = set(re.findall(r'^\| ([가-힣A-Za-z]+) \|', open('TAGS.md', encoding='utf-8').read(), re.M)) - {'태그'}

print(f"경험 {len(E)}건 (container {sum(1 for v in E.values() if v['type']=='container')} / "
      f"episode {sum(1 for v in E.values() if v['type']=='episode')})\n")

# 1. INDEX 행 수 == 파일 수
n_rows = len(re.findall(r'^\| (?:car|act|prj)-\d+ \|', idx, re.M))
(err if n_rows != len(E) else print)(
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

print()
for w in warn:
    print("⚠️ ", w)
for e in err:
    print("❌ ", e)
print(f"\n{'='*60}\n오류 {len(err)} · 경고 {len(warn)}")
sys.exit(1 if err else 0)
