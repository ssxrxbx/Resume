#!/usr/bin/env python3
"""PDF·이미지 → 텍스트 파일 + 목차. 이미지를 대화에 직접 쌓지 않기 위한 도구.

    python3 portfolio/_extract.py <파일> <회사명>            # 추출 → companies/<회사명>/sources/<파일명>.md, 목차 출력
    python3 portfolio/_extract.py <파일> <회사명> --find "IT 인프라,네트워크"   # 키워드가 있는 페이지만
    python3 portfolio/_extract.py <파일> <회사명> --page 12-14  # 그 페이지 본문만 출력
    python3 portfolio/_extract.py <이력서.pdf> _portfolio        # /exp-add 임포트용 → portfolio/_sources/

이미지 한 장은 대화에 들어가면 이후 매 호출마다 다시 전송된다(한 장 ≈ 1,500토큰).
그래서 PDF·이미지는 Read로 직접 보지 말고, 이 스크립트로 텍스트 파일을 만든 뒤 필요한 페이지만 읽는다.

추출 방식(자동 선택, 위에서부터):
  1. macOS           — PDFKit 텍스트 층 + Vision OCR(한국어·영어). 설치 불필요.
  2. 그 외 OS        — pypdf 텍스트 층 + Tesseract OCR(kor). 설치된 것만 쓴다.
  3. OCR 불가 페이지 — 「미추출」로 남기고, 하위 에이전트 전사 지시문을 출력한다(설치 불필요).
환경변수 EXTRACT_BACKEND=portable 로 2·3번 경로를 강제할 수 있다(테스트용).
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BIN = ROOT / ".bin" / "extract"          # portfolio/.bin 은 git 제외(개인 폴더 규칙)
SWIFT_SRC = ROOT / "_extract.swift"
MIN_TEXT = 20                            # 이보다 짧으면 텍스트 층이 없는 페이지로 본다
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".tif", ".tiff", ".bmp"}
MISSING = "(미추출 — 하위 에이전트 전사 필요)"


# ── 백엔드 1: macOS ─────────────────────────────────────────
def mac_backend(src):
    if os.environ.get("EXTRACT_BACKEND") == "portable" or platform.system() != "Darwin":
        return None
    if not shutil.which("swiftc"):
        return None
    if not BIN.exists() or BIN.stat().st_mtime < SWIFT_SRC.stat().st_mtime:
        BIN.parent.mkdir(exist_ok=True)
        print("· macOS 추출기 최초 컴파일 중 (한 번만, 30초 안팎)…", file=sys.stderr)
        r = subprocess.run(["swiftc", "-O", str(SWIFT_SRC), "-o", str(BIN)], capture_output=True, text=True)
        if r.returncode:
            print("· 컴파일 실패 — 이식형 경로로 전환:\n" + r.stderr[-400:], file=sys.stderr)
            return None
    r = subprocess.run([str(BIN), str(src), str(MIN_TEXT)], capture_output=True, text=True)
    if r.returncode:
        print("· macOS 추출 실패 — 이식형 경로로 전환: " + (r.stdout + r.stderr)[-200:], file=sys.stderr)
        return None
    pages = []
    for m in re.finditer(r"^<<<PAGE (\d+) (\w+)>>>\n(.*?)(?=^<<<PAGE |\Z)", r.stdout, re.S | re.M):
        pages.append((int(m.group(1)), m.group(2), m.group(3).strip()))
    return pages, "macOS PDFKit + Vision OCR"


# ── 백엔드 2: 이식형 (pypdf + Tesseract) ───────────────────────
def tesseract_ok():
    if not shutil.which("tesseract"):
        return False
    r = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
    return "kor" in r.stdout


def tesseract(img_path):
    r = subprocess.run(["tesseract", str(img_path), "-", "-l", "kor+eng"], capture_output=True, text=True)
    return r.stdout.strip()


def render_pdf_page(src, n, out_dir):
    """PDF n쪽을 PNG로. pdftoppm(poppler) 또는 pypdfium2 중 있는 것."""
    if shutil.which("pdftoppm"):
        base = Path(out_dir) / f"p{n}"
        subprocess.run(["pdftoppm", "-f", str(n), "-l", str(n), "-r", "200", "-png", "-singlefile",
                        str(src), str(base)], capture_output=True)
        return base.with_suffix(".png") if base.with_suffix(".png").exists() else None
    try:
        import pypdfium2 as pdfium
        pg = pdfium.PdfDocument(str(src))[n - 1]
        p = Path(out_dir) / f"p{n}.png"
        pg.render(scale=200 / 72).to_pil().save(p)
        return p
    except Exception:
        return None


def portable_backend(src):
    used, pages = [], []
    ocr = tesseract_ok()
    if src.suffix.lower() in IMG_EXT:
        if ocr:
            return [(1, "ocr", tesseract(src))], "Tesseract OCR"
        return [(1, "missing", "")], "OCR 도구 없음"
    try:
        from pypdf import PdfReader
        texts = [(p.extract_text() or "").strip() for p in PdfReader(str(src)).pages]
        used.append("pypdf")
    except ImportError:
        texts = None
    if texts is None:                       # 텍스트 층도 못 읽으면 쪽수부터 모른다
        n = page_count_guess(src)
        return [(i, "missing", "") for i in range(1, n + 1)], "pypdf 없음"
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(texts, 1):
            if len(t) >= MIN_TEXT:
                pages.append((i, "text", t))
                continue
            img = render_pdf_page(src, i, tmp) if ocr else None
            if img:
                pages.append((i, "ocr", tesseract(img)))
                if "Tesseract OCR" not in used:
                    used.append("Tesseract OCR")
            else:
                pages.append((i, "missing", ""))
    return pages, " + ".join(used) or "없음"


def page_count_guess(src):
    data = Path(src).read_bytes()
    return max(1, len(re.findall(rb"/Type\s*/Page[^s]", data)))


# ── 저장·출력 ────────────────────────────────────────────────
def out_path(src, company):
    d = ROOT / "_sources" if company == "_portfolio" else REPO / "companies" / company / "sources"
    d.mkdir(parents=True, exist_ok=True)
    return d / (Path(src).stem + ".md")


def write_md(dst, src, pages, how):
    stat = {k: sum(1 for _, h, _ in pages if h == k) for k in ("text", "ocr", "missing")}
    lines = [f"# {Path(src).name} — 추출 텍스트",
             f"> 원본: `{src}` · 추출일: {date.today()} · 방식: {how}",
             f"> 텍스트 층 {stat['text']}쪽 · OCR {stat['ocr']}쪽 · 미추출 {stat['missing']}쪽",
             "> ⚠️ OCR은 숫자·자격 요건을 잘못 읽을 수 있다. 답안에 인용할 수치·필수 요건은 그 페이지 원본으로 확인한다.",
             ""]
    for n, h, t in pages:
        lines += [f"## p.{n} ({h})", t if h != "missing" else MISSING, ""]
    dst.write_text("\n".join(lines), encoding="utf-8")
    return stat


def read_md(dst):
    t = dst.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^## p\.(\d+) \((\w+)\)\n(.*?)(?=^## p\.|\Z)", t, re.S | re.M):
        out.append((int(m.group(1)), m.group(2), m.group(3).strip()))
    return out


def first_line(t):
    for l in t.split("\n"):
        l = l.strip()
        if len(l) > 1:
            return l[:56] + ("…" if len(l) > 56 else "")
    return ""


def print_index(dst, pages):
    print(f"■ {dst.relative_to(REPO)} — {len(pages)}쪽")
    for n, h, t in pages:
        tag = {"text": " ", "ocr": "·", "agent": "·", "missing": "✗"}.get(h, "?")
        print(f"  p.{n:<3}{tag} {first_line(t) if h != 'missing' else '(미추출)'}  [{0 if h == 'missing' else len(t)}자]")
    print("  (· = OCR·에이전트 전사, ✗ = 미추출) 필요한 페이지만: --page 12-14 / 키워드로 찾기: --find \"키워드1,키워드2\"")


def print_subagent_brief(src, dst, pages):
    miss = [n for n, h, _ in pages if h == "missing"]
    if not miss:
        return
    rng = compress(miss)
    print(f"\n⚠️  미추출 {len(miss)}쪽({rng}) — 이 환경엔 OCR 도구가 없다. 메인 대화에서 이미지를 직접 읽지 말고")
    print("   하위 에이전트(Agent 도구, general-purpose)에 아래 지시를 그대로 넘긴다:\n")
    print(f"   「`{src}`의 {rng}쪽을 Read 도구로 읽어(PDF면 pages 인자로 20쪽씩), 각 쪽의 글자를 빠짐없이 텍스트로 옮겨라. "
          f"`{dst}`에서 해당 `## p.N (missing)` 섹션의 본문 `{MISSING}`을 옮긴 텍스트로 바꾸고 헤딩의 (missing)을 (agent)로 바꿔라. "
          "숫자·고유명사는 보이는 그대로 적고, 읽을 수 없는 부분은 [판독 불가]로 표시하라. "
          "끝나면 본문은 돌려주지 말고 쪽마다 첫 줄 한 줄씩의 목차만 돌려줘라. "
          "Read가 PDF를 열지 못하면(poppler 없음) 억지로 우회하지 말고 그 사실만 보고하라.」")
    print("\n   ※ 이미지 파일(PNG·JPG)은 Read가 바로 연다. PDF는 Read도 poppler가 있어야 열린다 —")
    print("     열리지 않으면 사용자에게 poppler 설치(mac: brew install poppler / Win: winget·choco / Linux: apt install poppler-utils)를 요청한다.")
    print("\n   (또는 설치 후 재실행: macOS 불필요 / Windows·Linux → pip install pypdf pypdfium2 + Tesseract kor)")


def compress(nums):
    out, s = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None]):
        if b != a + 1:
            out.append(f"{s}" if s == a else f"{s}-{a}")
            s = b
    return ",".join(out)


def parse_range(r):
    got = set()
    for part in r.split(","):
        a, _, b = part.partition("-")
        got |= set(range(int(a), int(b or a) + 1))
    return got


def main(argv):
    if len(argv) < 3 or argv[1].startswith("-"):
        print(__doc__)
        return 1
    src, company, args = Path(argv[1]).expanduser().resolve(), argv[2], argv[3:]
    if not src.exists():
        print(f"❌ 파일 없음: {src}")
        return 1
    dst = out_path(src, company)
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and "--refresh" not in args:
        pages = read_md(dst)                               # 이미 추출됨 → 재사용
    else:
        res = mac_backend(src) or portable_backend(src)
        pages, how = res
        write_md(dst, src, pages, how)
        pages = read_md(dst)
        print(f"· 추출 방식: {how}", file=sys.stderr)

    opt = lambda k: args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None
    if opt("--page"):
        want = parse_range(opt("--page"))
        for n, h, t in pages:
            if n in want:
                print(f"## p.{n} ({h})\n{t}\n")
    elif opt("--find"):
        kws = [k.strip() for k in opt("--find").split(",") if k.strip()]
        hit = 0
        for n, h, t in pages:
            found = [k for k in kws if k.lower() in t.lower()]
            if found:
                hit += 1
                line = next((l.strip() for l in t.split("\n") if any(k.lower() in l.lower() for k in found)), "")
                print(f"  p.{n:<3} [{', '.join(found)}] {line[:60]}")
        print(f"→ {hit}/{len(pages)}쪽에서 발견. 본문은 --page 로 읽는다")
    else:
        print_index(dst, pages)
    print_subagent_brief(src, dst, pages)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
