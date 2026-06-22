"""
PF Daily Market Intelligence — 실행 진입점

사용법:
  python main.py                    # 전체 파이프라인 (수집 → HTML → PDF → 발송)
  python main.py --no-send          # 이메일 발송 생략
  python main.py --no-pdf           # PDF 변환 생략
  python main.py --only-report      # 기존 JSON으로 HTML/PDF만 재생성
  python main.py --diagnose         # 데이터 소스 연결 진단만 실행 (발송 없음)
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def run():
    parser = argparse.ArgumentParser(description="PF Daily Market Intelligence")
    parser.add_argument("--no-send",     action="store_true", help="이메일 발송 생략")
    parser.add_argument("--no-pdf",      action="store_true", help="PDF 변환 생략")
    parser.add_argument("--only-report", action="store_true", help="데이터 재수집 없이 HTML/PDF만 재생성")
    parser.add_argument("--diagnose",    action="store_true", help="데이터 소스 연결 진단 (발송 없음)")
    args = parser.parse_args()

    if args.diagnose:
        from scripts.diagnose_sources import run_diagnose
        fail_count = run_diagnose()
        sys.exit(1 if fail_count > 0 else 0)

    from scripts.collect_data    import collect_all
    from scripts.generate_report import generate_report
    from scripts.generate_pdf    import generate_pdf
    from scripts.send_email      import send_report

    data = None

    if not args.only_report:
        print("=" * 55)
        print("  [1단계] 데이터 수집")
        print("=" * 55)
        data = collect_all()
    else:
        print("  [--only-report] 기존 data/latest_report.json 사용")

    print()
    print("=" * 55)
    print("  [2단계] HTML 리포트 생성")
    print("=" * 55)
    html_path = generate_report(data)

    pdf_path = None
    if not args.no_pdf:
        print()
        print("=" * 55)
        print("  [3단계] PDF 변환")
        print("=" * 55)
        pdf_path = generate_pdf(html_path, html_path.with_suffix(".pdf"))

    if not args.no_send:
        print()
        print("=" * 55)
        print("  [4단계] 이메일 발송")
        print("=" * 55)
        send_report(html_path, pdf_path)
    else:
        print(f"\n  [--no-send] 이메일 발송 생략")
        print(f"  HTML : {html_path}")
        if pdf_path:
            print(f"  PDF  : {pdf_path}")

    print("\n✓ 완료")


if __name__ == "__main__":
    run()
