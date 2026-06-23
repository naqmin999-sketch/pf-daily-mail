"""
PF Daily Market Intelligence — 데이터 소스 진단 모듈
메일 발송 없이 각 데이터 소스의 연결 상태를 점검합니다.

실행: python main.py --diagnose
     python scripts/diagnose_sources.py
"""
import os
import csv
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent.parent
MANUAL_DIR = BASE_DIR / "manual_data"
DATA_DIR   = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"

OK   = "[OK]  "
WARN = "[WARN]"
FAIL = "[FAIL]"

_results        = []
_critical_count = 0  # API 키·이메일 설정 누락만 카운트 → exit code 기준


def _log(tag, label, msg="", critical=False):
    """critical=True: exit code 1 유발 (API 키/이메일 설정 누락 한정)"""
    global _critical_count
    line = f"  {tag} {label}"
    if msg:
        line += f": {msg}"
    print(line)
    _results.append((tag.strip("[] "), label, msg))
    if critical and "FAIL" in tag:
        _critical_count += 1


def _mask(val):
    if not val:
        return "(미설정)"
    if len(val) <= 4:
        return "****"
    return val[:3] + "****" + val[-1]


# ── A. ECOS API ────────────────────────────────────────────────────

def check_ecos():
    print("\n[A] ECOS API (한국은행)")
    print("-" * 56)

    import sys
    sys.path.insert(0, str(BASE_DIR))
    from scripts.collect_data import fetch_ecos, ECOS_ITEMS

    key = os.getenv("ECOS_API_KEY", "")
    if not key:
        _log(FAIL, "ECOS API 키", "미설정 — ECOS_API_KEY 필요", critical=True)
        return
    _log(OK, "ECOS API 키", f"{_mask(key)} (설정됨)")

    for item_key, (stat, cycle, item_code, label) in ECOS_ITEMS.items():
        r   = fetch_ecos(stat, cycle, item_code, label)
        val = r.get("value")
        err = r.get("error", "")
        _transient = ("timed out" in err or "Max retries" in err
                      or "ConnectionPool" in err or "ConnectTimeout" in err)
        if val is not None:
            _log(OK, f"ECOS {label}", f"{val} / {r.get('date', '')}")
        elif "응답 없음" in err or "item_code 미확인" in err:
            _log(WARN, f"ECOS {label}", "item_code 미확인 — 응답 없음 (N/A 표시)")
        elif _transient:
            _log(WARN, f"ECOS {label}", "일시적 네트워크 오류 — send 모드에서 재시도됨")
        else:
            # 기타 오류: 보조 데이터이므로 WARN (send 모드에서는 N/A 표시)
            _log(WARN, f"ECOS {label}", f"수집 오류 — {err[:60] if err else '원인 미상'}")


# ── B. Naver API ───────────────────────────────────────────────────

def check_naver():
    print("\n[B] Naver 뉴스 API")
    print("-" * 56)

    import sys
    sys.path.insert(0, str(BASE_DIR))
    from scripts.collect_data import collect_pf_news, collect_policy_news

    cid = os.getenv("NAVER_CLIENT_ID", "")
    sec = os.getenv("NAVER_CLIENT_SECRET", "")
    if not cid or not sec:
        _log(FAIL, "Naver API 키", "미설정 — NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 필요",
             critical=True)
        return
    _log(OK, "Naver API 키", f"Client-ID {_mask(cid)} (설정됨)")

    for label, news_fn in [("PF 뉴스", collect_pf_news), ("부동산 정책 뉴스", collect_policy_news)]:
        news   = news_fn()
        titles = [a["title"] for a in news]
        unique = len(set(titles))
        if len(news) == 0:
            # 키는 있으나 수집 0건 — 일시적 오류이므로 WARN
            _log(WARN, f"Naver {label}", "0건 — 일시적 API 오류 가능성, 재실행 권장")
        else:
            dup = f" / 중복 {len(news) - unique}건 제거됨" if unique < len(news) else ""
            _log(OK, f"Naver {label}", f"{len(news)}건 (고유 {unique}건){dup}")


# ── C. Manual CSV ──────────────────────────────────────────────────

_CSV_SPECS = {
    "pf_rates.csv": {
        "label":      "PF 시장금리",
        "required":   ["category", "rate_pct", "as_of_date"],
        "value_cols": ["rate_pct"],
        "date_col":   "as_of_date",
    },
    "cp_rates.csv": {
        "label":      "CP 등급별 금리",
        "required":   ["grade", "tenor_3m", "tenor_1y", "as_of_date"],
        "value_cols": ["tenor_3m", "tenor_1y"],
        "date_col":   "as_of_date",
    },
    "cofix.csv": {
        "label":      "COFIX (CSV fallback)",
        "required":   ["ym", "new_all_rate"],
        "value_cols": ["new_all_rate"],
        "date_col":   "ym",
    },
    "deal_watch.csv": {
        "label":      "Deal Watch",
        "required":   ["type", "party", "as_of_date"],
        "value_cols": ["borrower"],
        "date_col":   "as_of_date",
    },
    "credit_ratings.csv": {
        "label":      "건설사 신용등급",
        "required":   ["company", "rating", "rating_date"],
        "value_cols": ["rating"],
        "date_col":   "rating_date",
    },
}


def check_cofix_auto():
    """우리은행 COFIX 고시 자동수집 테스트 (Playwright)"""
    print("\n[C-AUTO] COFIX 자동수집 (우리은행 COFIX 고시)")
    print("-" * 56)

    import sys
    sys.path.insert(0, str(BASE_DIR))
    from scripts.collect_data import collect_cofix_from_woori

    result = collect_cofix_from_woori()
    if result and (result.get("new_all_rate") is not None or
                   result.get("balance_rate") is not None):
        _log(OK, "COFIX 자동수집 (우리은행)",
             f"성공 — {result['ym']} / 신규취급액 {result.get('new_all_rate')}%"
             f" / 잔액 {result.get('balance_rate')}%"
             f" / 신잔액 {result.get('new_balance_rate')}%")
    elif result:
        _log(WARN, "COFIX 자동수집 (우리은행)",
             f"접속 성공, 값 파싱 불완전 ({result.get('ym','?')}) — CSV fallback 사용")
    else:
        _log(WARN, "COFIX 자동수집 (우리은행)",
             "수집 실패 (네트워크 또는 페이지 구조 변경) — CSV fallback 사용")


def check_csv():
    print("\n[C] Manual CSV")
    print("-" * 56)

    for filename, spec in _CSV_SPECS.items():
        path  = MANUAL_DIR / filename
        label = spec["label"]

        if not path.exists():
            _log(WARN, f"{filename} ({label})", "파일 없음 — manual_data/ 에 추가 필요")
            continue

        with open(path, encoding="utf-8-sig") as f:
            reader  = csv.DictReader(f)
            rows    = list(reader)
            headers = reader.fieldnames or []

        missing_cols = [c for c in spec["required"] if c not in headers]
        if missing_cols:
            _log(WARN, f"{filename} ({label})", f"필수 컬럼 누락: {', '.join(missing_cols)}")
            continue

        if len(rows) == 0:
            _log(WARN, f"{filename} ({label})", "0건 (파일은 있으나 데이터 없음)")
            continue

        filled = (
            sum(1 for row in rows if any(row.get(c, "").strip() for c in spec["value_cols"]))
            if spec["value_cols"] else len(rows)
        )

        date_note = ""
        if spec["date_col"]:
            dates = [r.get(spec["date_col"], "").strip() for r in rows if r.get(spec["date_col"], "").strip()]
            if dates:
                date_note = f" / 최근 기준: {sorted(dates)[-1]}"

        if spec["value_cols"] and filled == 0:
            _log(WARN, f"{filename} ({label})", f"{len(rows)}행 있으나 값 모두 비어있음{date_note}")
        elif spec["value_cols"] and filled < len(rows):
            _log(WARN, f"{filename} ({label})", f"{len(rows)}행 / 값 입력: {filled}행{date_note}")
        else:
            _log(OK, f"{filename} ({label})", f"{len(rows)}행{date_note}")


# ── D. 생성 파일 확인 ──────────────────────────────────────────────

def _age_str(path):
    delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime)
    h = delta.total_seconds() / 3600
    return f"{h:.1f}시간 전" if h < 48 else f"{h / 24:.0f}일 전"


def check_files():
    # diagnose 모드는 파일을 생성하지 않으므로 생성 파일 부재는 WARN 처리
    print("\n[D] 생성 파일 (JSON / HTML / PDF)")
    print("-" * 56)

    json_path = DATA_DIR / "latest_report.json"
    if json_path.exists():
        _log(OK, "data/latest_report.json", f"존재 ({_age_str(json_path)} 생성)")
    else:
        _log(WARN, "data/latest_report.json", "없음 (send 모드 실행 전 정상)")

    if not REPORT_DIR.exists():
        _log(WARN, "reports/ 폴더", "없음 (send 모드 실행 전 정상)")
        return

    today = datetime.date.today().isoformat()
    for ext, label in [(".html", "HTML 리포트"), (".pdf", "PDF 리포트")]:
        today_file = REPORT_DIR / f"{today}_report{ext}"
        if today_file.exists():
            _log(OK, label, today_file.name)
        else:
            recents = sorted(REPORT_DIR.glob(f"*_report{ext}"), reverse=True)
            if recents:
                _log(WARN, label, f"오늘 파일 없음 — 최근: {recents[0].name} ({_age_str(recents[0])})")
            else:
                _log(WARN, label, "없음 (send 모드 실행 전 정상)")


# ── E. 이메일 설정 확인 ────────────────────────────────────────────

def check_email():
    print("\n[E] 이메일 설정 (발송 테스트 없음)")
    print("-" * 56)

    configs = [
        ("EMAIL_SENDER",     "발신자 주소",   True,  False),
        ("EMAIL_PASSWORD",   "앱 비밀번호",   True,  True),
        ("EMAIL_RECIPIENTS", "수신자 목록",   True,  False),
        ("EMAIL_SMTP_HOST",  "SMTP 호스트",   False, False),
        ("EMAIL_SMTP_PORT",  "SMTP 포트",     False, False),
    ]

    for env_key, label, required, is_secret in configs:
        val = os.getenv(env_key, "")
        if val:
            if is_secret:
                display = "****"
            elif env_key == "EMAIL_RECIPIENTS":
                display = f"{len(val.split(','))}명 설정됨"
            else:
                display = _mask(val)
            _log(OK, f"{label} ({env_key})", display)
        elif required:
            _log(FAIL, f"{label} ({env_key})", "미설정", critical=True)
        else:
            _log(WARN, f"{label} ({env_key})", "미설정 (기본값 사용)")


# ── 요약 ──────────────────────────────────────────────────────────

def _summary():
    print("\n" + "=" * 56)
    ok   = sum(1 for r in _results if r[0] == "OK")
    warn = sum(1 for r in _results if r[0] == "WARN")
    fail = sum(1 for r in _results if r[0] == "FAIL")
    print(f"  진단 결과: {ok + warn + fail}개 항목 점검")
    print(f"  ✓ OK   : {ok}개")
    if warn:
        print(f"  △ WARN : {warn}개")
    if fail:
        print(f"  ✕ FAIL : {fail}개  ← 치명적: {_critical_count}개")

    if _critical_count == 0 and fail == 0 and warn == 0:
        print("\n  → 모든 항목 정상. 메일 발송 가능 상태.")
    elif _critical_count == 0 and fail == 0:
        print("\n  → 필수 항목 OK. WARN 항목은 데이터 미입력 또는 일시적 오류.")
    elif _critical_count == 0:
        print(f"\n  → 보조 항목 {fail}개 오류. 메일 발송 동작 가능 — WARN 내용 확인 권장.")
    else:
        print(f"\n  → 치명적 오류 {_critical_count}개: API 키 또는 이메일 설정 확인 필요.")
    print("=" * 56)
    print(f"  exit code: {'1 (치명적 오류)' if _critical_count > 0 else '0'}")
    print("=" * 56)

    return _critical_count


# ── 진입점 ────────────────────────────────────────────────────────

def run_diagnose():
    print("=" * 56)
    print("  PF Daily Market Intelligence — 데이터 소스 진단")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 56)

    check_ecos()
    check_naver()
    check_cofix_auto()
    check_csv()
    check_files()
    check_email()
    return _summary()


if __name__ == "__main__":
    import sys
    sys.exit(1 if run_diagnose() > 0 else 0)
