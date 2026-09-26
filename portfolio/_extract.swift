// macOS 백엔드 — `_extract.py`가 컴파일해 호출한다 (직접 실행할 일은 없다).
// PDF: 페이지마다 텍스트 층을 읽고, 없으면 렌더링해 Vision OCR(한국어·영어).
// 이미지(PNG·JPG 등): Vision OCR.
// 출력: 페이지마다 "<<<PAGE n text|ocr>>>" 다음 줄부터 본문.
import AppKit
import Foundation
import PDFKit
import Vision

func ocr(_ cg: CGImage) -> String {
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["ko-KR", "en-US"]
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    return (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

let args = CommandLine.arguments
guard args.count > 1 else { print("usage: extract <file> [minTextChars]"); exit(2) }
let path = args[1]
let minText = args.count > 2 ? Int(args[2]) ?? 20 : 20
let url = URL(fileURLWithPath: path)

if path.lowercased().hasSuffix(".pdf") {
    guard let doc = PDFDocument(url: url) else { print("ERR cannot open PDF"); exit(1) }
    for i in 0..<doc.pageCount {
        guard let page = doc.page(at: i) else { continue }
        var text = (page.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        var how = "text"
        if text.count < minText {
            let b = page.bounds(for: .mediaBox)
            let s = 2200 / max(b.width, b.height)
            let img = page.thumbnail(of: NSSize(width: b.width * s, height: b.height * s), for: .mediaBox)
            if let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) {
                text = ocr(cg)
                how = "ocr"
            }
        }
        print("<<<PAGE \(i + 1) \(how)>>>")
        print(text)
    }
} else {
    guard let img = NSImage(contentsOf: url),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("ERR cannot open image"); exit(1)
    }
    print("<<<PAGE 1 ocr>>>")
    print(ocr(cg))
}
