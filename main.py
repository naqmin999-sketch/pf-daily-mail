"""
PF Daily Market Intelligence — 실행 진입점

사용법:
  python main.py                # 전체 파이프라인 (수집 → 생성 → 발송)
  python main.py --no-send      # 이메일 발송 생략
  python main.py --only-report  # 기존 JSON으로 HTML만 재생성
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def run():
    parser = argparse.ArgumentParser(description="PF Daily Market Intelligence")
    parser.add_argument("--no-send",     action="store_true", help="이메일 발송 생략")
    parser.add_argument("--only-report", action="store_true", help="데이터 재수집 없이 HTML만 재생성")
    args = parser.parse_args()

    from scripts.collect_data    import collect_all
    from scripts.generate_report import generate_report
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
    report_path = generate_report(data)

    if not args.no_send:
        print()
        print("=" * 55)
        print("  [3단계] 이메일 발송")
        print("=" * 55)
        send_report(report_path)
    else:
        print(f"\n  [--no-send] 이메일 발송 생략")
        print(f"  리포트 위치: {report_path}")

    print("\n✓ 완료")


if __name__ == "__main__":
    run()
