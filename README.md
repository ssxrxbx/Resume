# 지원서 에이전트

내 경험을 체계적인 포트폴리오로 정리하고(1단계), 기업별 JD·신년사를 분석해(2단계),
지원서·자소서 질문에 최적의 답을 도출하는(3단계) Claude Code 에이전트.

이 저장소에는 **에이전트 구조(규칙·스킬·검사 스크립트·템플릿)만** 들어 있다.
경험·회사 분석·답안 같은 개인 데이터는 `.gitignore`로 제외되어 각자의 로컬에만 남는다.

## 3단계 구조

| 단계 | 폴더 | 역할 | 갱신 주기 |
|------|------|------|-----------|
| 1. 경험·포트폴리오 | `portfolio/` | 진실 공급원. 기업과 무관한 내 자산 | 경험 생길 때마다 |
| 2. 기업 분석 | `companies/` | JD·신년사 분석 + 핏 매칭 | 지원 기업마다 |
| 3. 답안 생성 | `applications/` | 질문별 최적 답안 | 지원할 때마다 |

데이터는 **1 → 2 → 3** 방향으로 흐른다. 3단계 답안은 항상 1단계 경험에 근거한다.

## 시작하기

```bash
git clone https://github.com/ssxrxbx/Resume.git
cd Resume
cp portfolio/_templates/profile.md portfolio/profile.md
cp portfolio/_templates/INDEX.md portfolio/INDEX.md
cp portfolio/_templates/TAGS.md portfolio/TAGS.md
cp portfolio/_templates/IMPROVEMENTS.md IMPROVEMENTS.md
```

그다음 Claude Code에서 이 폴더를 열고 `/exp-add`로 경험부터 채운다.
`portfolio/profile.md`의 「에이전트 설정」에는 톤 기준 답안 같은 개인 설정을 적는다.

## 업데이트 받기

```bash
git pull
```

개인 데이터는 추적되지 않으므로 `git pull`로 덮어써지지 않는다. 버전은 태그(`v1.0.0` 등)로 관리한다.

## 세션 운영 (토큰 절약)

API 호출마다 대화 전체가 다시 전송되므로 **세션을 작업 단위로 끊는 게** 토큰을 가장 크게 줄인다
(과거 30세션 재생 시뮬레이션: 전체 -28%, 긴 세션 최대 -65%).

1. `/company-analyze {회사}` → 분석 저장 후 **새 세션**
2. `/answer {회사} 이어서` → 문항 1개 승인·저장 후 **새 세션**
3. 다음 문항도 `/answer {회사} 이어서`

세션 사이 상태는 `applications/{회사}/session.md`(인계 파일)가 넘긴다 —
문항 상태표, 이번 지원 전용 지시, 확정된 전략 카드·뼈대, 🔒 승인 문장, 최신 초안.
경계에 도달하면 에이전트가 먼저 새 세션을 제안한다.

## 사용법 (슬래시 커맨드)

```
/exp-add           경험을 STAR + 태그로 추가·정리          (1단계)
/company-analyze   JD·신년사 분석 + 핏 매칭표 생성          (2단계)
/answer            질문 → 관련 경험 매칭 → 최적 답안 초안   (3단계)
/retro             산출물·시스템 자체 평가 → 개선 반영
```

## 폴더 구조

```
.claude/CLAUDE.md         운영 규칙 (매 대화 로드)
.claude/skills/           스킬 4종
AGENTS.md, .agents/       Codex용 미러
portfolio/
  _check.py               정합성 검사 (python3 portfolio/_check.py)
  _usage.py               회사별 경험 사용 이력·편중 집계
  _templates/             경험·INDEX·TAGS·profile·session 템플릿
  career/      car-*      경력              ┐
  activities/  act-*      대외활동           │
  projects/    prj-*      프로젝트           │ 개인 데이터
  profile.md · INDEX.md · TAGS.md          │ (로컬 전용,
companies/{회사명}/        jd · context · fit-matrix │  git 제외)
applications/{회사명}/     answers · session │
IMPROVEMENTS.md           개선 로그          ┘
```

경험 1건 = 파일 1개(원자 단위). 활동↔프로젝트는 frontmatter `activity:`/`projects:[]`로 연결.

## 저장 정책
- 원본은 **로컬 마크다운**, Notion은 미러(읽기 편의용). 충돌 시 로컬 우선.
- 경험은 절대 한 파일에 합치지 않는다(원자 단위).
- 답안에 거짓·과장 금지. 빈 곳은 인터뷰로 채운다.
