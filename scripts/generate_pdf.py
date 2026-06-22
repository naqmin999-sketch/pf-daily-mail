"""
PF Daily Market Intelligence — HTML → PDF 변환
playwright chromium 사용. 최초 1회: playwright install chromium
"""
from pathlib import Path


def generate_pdf(html_path: Path, pdf_path: Path):
    """HTML 파일을 A4 PDF로 변환. 실패 시 None 반환."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠ playwright 미설치 — pip install playwright && playwright install chromium")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            uri = Path(html_path).resolve().as_uri()
            page.goto(uri, wait_until="networkidle", timeout=30000)
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "12mm", "bottom": "12mm",
                        "left": "8mm",  "right": "8mm"},
            )
            browser.close()
        print(f"  → PDF 생성 완료: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"  ⚠ PDF 생성 실패: {e}")
        return None


if __name__ == "__main__":
    import sys
    from pathlib import Path
    if len(sys.argv) >= 2:
        hp = Path(sys.argv[1])
        pp = hp.with_suffix(".pdf")
        generate_pdf(hp, pp)
    else:
        print("사용법: python scripts/generate_pdf.py reports/2026-06-16_report.html")
