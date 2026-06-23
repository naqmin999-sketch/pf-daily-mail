"""
PF Daily Market Intelligence — 데이터 수집 모듈
AUTO  : ECOS API (금리/환율), Naver 뉴스 API, 은행연합회 COFIX
MANUAL: manual_data/*.csv (CP금리, Deal Watch, 신용등급, PF금리)
"""
import os
import re
import json
import csv
import datetime
import time
import requests
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = Path(__file__).parent.parent
DATA_DIR    = BASE_DIR / "data"
MANUAL_DIR  = BASE_DIR / "manual_data"

ECOS_API_KEY        = os.getenv("ECOS_API_KEY", "")
NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

# 확인된 ECOS 통계코드 (stat_code, cycle, item_code, 표시명)
# A+/A0/A- 3개는 item_code 미확인 — 응답 없으면 N/A 표시
# 정확한 코드 확인: python -c "from scripts.collect_data import discover_ecos_items; discover_ecos_items()"
ECOS_ITEMS = {
    "base_rate":      ("722Y001", "D", "0101000",   "기준금리"),
    "cd_91":          ("817Y002", "D", "010502000", "CD 91일"),
    "cp_91":          ("817Y002", "D", "010503000", "CP 91일"),
    "gov_3y":         ("817Y002", "D", "010200000", "국고채 3Y"),
    "gov_10y":        ("817Y002", "D", "010210000", "국고채 10Y"),
    "corp_aa_3y":     ("817Y002", "D", "010300000", "회사채 3Y AA-"),
    "corp_aplus_3y":  ("817Y002", "D", "010305000", "회사채 3Y A+"),   # 미확인
    "corp_a0_3y":     ("817Y002", "D", "010310000", "회사채 3Y A0"),   # 미확인
    "corp_aminus_3y": ("817Y002", "D", "010315000", "회사채 3Y A-"),   # 미확인
}

# 스파크라인용 30일 이력 수집 대상
HISTORY_KEYS = ["cd_91", "gov_3y", "gov_10y", "corp_aa_3y"]

# PF/조달 금융 뉴스 키워드
PF_KEYWORDS = [
    "PF대출 건설",
    "프로젝트파이낸싱 부동산",
    "브릿지론 차환",
    "본PF 착공",
    "ABCP 건설사",
    "PF 부실 건설",
    "유동화 건설사",
    "건설사 CP 발행",
    "PF 차환",
    "ABSTB 건설",
]

# 부동산 정책/감독 뉴스 키워드
POLICY_KEYWORDS = [
    "국토교통부 부동산 정책",
    "금융위원회 부동산금융",
    "금감원 PF 감독",
    "HUG 전세보증",
    "가계대출 규제",
    "DSR 부동산",
    "미분양 대책",
    "부동산 공급대책",
    "주택도시기금",
    "전세보증 사고",
]


# ─── ECOS API ─────────────────────────────────────────────────────

def fetch_ecos(stat_code, cycle, item_code, label):
    if not ECOS_API_KEY:
        return {"value": None, "date": None, "label": label,
                "source": "한국은행 ECOS", "type": "auto",
                "error": "API키 미설정 (.env → ECOS_API_KEY)"}
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=8)
    url = (f"{ECOS_BASE}/{ECOS_API_KEY}/json/kr/1/10/{stat_code}/{cycle}"
           f"/{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}/{item_code}")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        rows = r.json().get("StatisticSearch", {}).get("row", [])
        if not rows:
            return {"value": None, "date": None, "label": label,
                    "source": "한국은행 ECOS", "type": "auto",
                    "error": "응답 없음 (item_code 미확인)"}
        latest = rows[-1]
        raw    = latest.get("DATA_VALUE", "")
        return {
            "value":  float(raw) if raw and raw.strip() else None,
            "date":   latest.get("TIME", ""),
            "label":  label,
            "source": "한국은행 ECOS",
            "type":   "auto",
        }
    except Exception as e:
        return {"value": None, "date": None, "label": label,
                "source": "한국은행 ECOS", "type": "auto", "error": str(e)}


def fetch_ecos_history(stat_code, cycle, item_code, days=40):
    """최근 N일 시계열 [(date_str, float), ...] — 스파크라인용"""
    if not ECOS_API_KEY:
        return []
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    url = (f"{ECOS_BASE}/{ECOS_API_KEY}/json/kr/1/60/{stat_code}/{cycle}"
           f"/{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}/{item_code}")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        rows = r.json().get("StatisticSearch", {}).get("row", [])
        return [
            (row["TIME"], float(row["DATA_VALUE"]))
            for row in rows
            if row.get("DATA_VALUE") and row["DATA_VALUE"].strip()
        ]
    except Exception:
        return []


def collect_bonds():
    """채권 금리 수집 + 스프레드 자동 계산"""
    result = {}
    for key, (stat, cycle, item, label) in ECOS_ITEMS.items():
        result[key] = fetch_ecos(stat, cycle, item, label)
        time.sleep(0.15)

    for corp_key, spread_key, spread_label in [
        ("corp_aa_3y",    "aa_spread",     "AA- 스프레드 (회사채3Y − 국고채3Y)"),
        ("corp_aminus_3y","aminus_spread",  "A- 스프레드 (회사채3Y − 국고채3Y)"),
    ]:
        c = result.get(corp_key, {}).get("value")
        g = result.get("gov_3y", {}).get("value")
        if c and g:
            result[spread_key] = {
                "value":  round(c - g, 3),
                "label":  spread_label,
                "source": "ECOS 계산값",
                "type":   "auto_derived",
            }
    return result


def collect_rate_history():
    """주요 금리 30일 이력 수집 (스파크라인용)"""
    history = {}
    for key in HISTORY_KEYS:
        stat, cycle, item, _ = ECOS_ITEMS[key]
        history[key] = fetch_ecos_history(stat, cycle, item, days=40)
        time.sleep(0.15)
    return history


def collect_usd_krw():
    r = fetch_ecos("731Y001", "D", "0000001", "USD/KRW")
    if r.get("value"):
        return r

    try:
        import FinanceDataReader as fdr
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=7)
        df = fdr.DataReader("USD/KRW", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if df is not None and not df.empty:
            return {"value": round(float(df.iloc[-1]["Close"]), 2),
                    "date":  df.index[-1].strftime("%Y-%m-%d"),
                    "label": "USD/KRW", "source": "FinanceDataReader/Yahoo", "type": "auto"}
    except Exception:
        pass

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(
            "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        el = BeautifulSoup(resp.text, "lxml").select_one(".rate_value")
        if el:
            return {"value": float(el.get_text(strip=True).replace(",", "")),
                    "date":  datetime.date.today().isoformat(),
                    "label": "USD/KRW", "source": "네이버금융(스크래핑)", "type": "auto"}
    except Exception:
        pass

    return {"value": None, "date": None, "label": "USD/KRW",
            "source": "N/A", "type": "auto", "error": "수집 실패"}


# ─── Manual CSV 로드 ──────────────────────────────────────────────

def _load_csv(filename):
    path = MANUAL_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_credit_ratings():
    path = MANUAL_DIR / "credit_ratings.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {
            row["company"]: {
                "ticker":      row.get("ticker", ""),
                "listed":      row.get("listed", "").upper() == "TRUE",
                "rating":      row.get("rating", ""),
                "rating_date": row.get("rating_date", ""),
                "outlook":     row.get("outlook", ""),
                "rater":       row.get("rater", ""),
                "note":        row.get("note", ""),
                "source":      "manual_data/credit_ratings.csv",
                "type":        "manual",
            }
            for row in csv.DictReader(f)
        }


def load_pf_rates():
    return [{**r, "source": "manual_data/pf_rates.csv", "type": "manual"}
            for r in _load_csv("pf_rates.csv")]


def load_cp_rates():
    return [{**r, "source": "manual_data/cp_rates.csv", "type": "manual"}
            for r in _load_csv("cp_rates.csv")]


def load_cofix():
    return [{**r, "source": "manual_data/cofix.csv", "type": "manual"}
            for r in _load_csv("cofix.csv")]


def load_deal_watch():
    return [{**r, "source": "manual_data/deal_watch.csv", "type": "manual"}
            for r in _load_csv("deal_watch.csv")]


# ─── 뉴스 수집 ────────────────────────────────────────────────────

def _clean(s):
    return (s.replace("<b>", "").replace("</b>", "")
             .replace("&amp;", "&").replace("&quot;", '"')
             .replace("&lt;", "<").replace("&gt;", ">").strip())


def fetch_naver_news(keyword, display=5):
    if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
        try:
            r = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers={"X-Naver-Client-Id":     NAVER_CLIENT_ID,
                         "X-Naver-Client-Secret": NAVER_CLIENT_SECRET},
                params={"query": keyword, "display": display, "sort": "date"},
                timeout=10,
            )
            if r.status_code == 200:
                return [
                    {
                        "title":    _clean(it.get("title", "")),
                        "link":     it.get("originallink") or it.get("link", ""),
                        "pub_date": it.get("pubDate", "")[:16],
                        "desc":     _clean(it.get("description", ""))[:80],
                        "keyword":  keyword,
                    }
                    for it in r.json().get("items", [])
                ]
        except Exception:
            pass
    return []


def collect_pf_news():
    all_news, seen = [], set()
    for kw in PF_KEYWORDS:
        for art in fetch_naver_news(kw, display=2):
            if art["title"] not in seen:
                seen.add(art["title"])
                all_news.append(art)
        time.sleep(0.2)
        if len(all_news) >= 5:
            break
    return all_news[:5]


def collect_policy_news():
    all_news, seen = [], set()
    for kw in POLICY_KEYWORDS:
        for art in fetch_naver_news(kw, display=2):
            if art["title"] not in seen:
                seen.add(art["title"])
                all_news.append(art)
        time.sleep(0.2)
        if len(all_news) >= 5:
            break
    return all_news[:5]


# ─── 우리은행 COFIX 자동수집 (Playwright) ────────────────────────
# 은행연합회 portal.kfb.or.kr는 IP 차단으로 접근 불가 →
# 우리은행 COFIX 고시 페이지 (spot.wooribank.com) 로 대체

def collect_cofix_from_woori():
    """
    우리은행 COFIX 고시 페이지에서 최신 값 수집 (Playwright headless).
    성공 시 dict 반환, 실패 시 None → collect_all()에서 CSV fallback.
    - 신규취급액기준 / 잔액기준 : Table 1 (행별 구분)
    - 신잔액기준 : Table 2 (앞 형제 heading으로 구분)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(
                "https://spot.wooribank.com/pot/Dream?withyou=POLON0068",
                timeout=30000,
            )
            page.wait_for_load_state("networkidle", timeout=20000)

            # 고시일 파싱
            text = page.inner_text("body")
            date_m = re.search(r"고시일\s*:\s*(\d{4})\.(\d{2})\.(\d{2})", text)
            if date_m:
                ym = f"{date_m.group(1)}-{date_m.group(2)}"
                note = f"우리은행 COFIX 고시 {date_m.group(1)}.{date_m.group(2)}.{date_m.group(3)}"
            else:
                ym = datetime.date.today().strftime("%Y-%m")
                note = "우리은행 COFIX 고시"

            tables = page.query_selector_all("table")

            def _get_heading(tbl):
                """테이블 앞 형제 요소 텍스트로 테이블 종류 판별"""
                siblings = page.evaluate("""(el) => {
                    let texts = [];
                    let prev = el.previousElementSibling;
                    while (prev && texts.length < 2) {
                        if (prev.innerText && prev.innerText.trim())
                            texts.push(prev.innerText.trim().slice(0, 80));
                        prev = prev.previousElementSibling;
                    }
                    return texts;
                }""", tbl)
                return " ".join(siblings)

            def _parse_val(s):
                try:
                    return float(str(s).replace(",", "").replace("%", "").strip())
                except (ValueError, TypeError):
                    return None

            new_all_rate = balance_rate = new_balance_rate = None

            for tbl in tables:
                heading = _get_heading(tbl)
                rows = tbl.query_selector_all("tr")
                current_cat = None
                for row in rows:
                    cells = [td.inner_text().strip()
                             for td in row.query_selector_all("th, td")]
                    if not cells or cells[0] in ("구분", "기간", "기준금리", "비고"):
                        continue

                    if len(cells) >= 3:
                        # 카테고리가 있는 행: ['신규취급액기준', '6개월', '2.90', ...]
                        if cells[0] in ("신규취급액기준", "잔액기준"):
                            current_cat = cells[0]
                            period, val = cells[1], cells[2]
                        else:
                            period, val = cells[0], cells[1]
                    elif len(cells) == 2:
                        period, val = cells[0], cells[1]
                    else:
                        continue

                    fval = _parse_val(val)
                    if fval is None:
                        continue

                    # 신잔액기준 테이블: heading에 "신잔액" 포함
                    if "신잔액" in heading:
                        if period == "1년" and new_balance_rate is None:
                            new_balance_rate = fval
                        elif period == "6개월" and new_balance_rate is None:
                            new_balance_rate = fval
                    # 일반 COFIX 테이블
                    elif current_cat == "신규취급액기준":
                        if period == "1년" and new_all_rate is None:
                            new_all_rate = fval
                        elif period == "6개월" and new_all_rate is None:
                            new_all_rate = fval
                    elif current_cat == "잔액기준":
                        if period == "1년" and balance_rate is None:
                            balance_rate = fval
                        elif period == "6개월" and balance_rate is None:
                            balance_rate = fval

            browser.close()

            if all(v is None for v in (new_all_rate, balance_rate, new_balance_rate)):
                return None

            return {
                "ym":               ym,
                "new_all_rate":     new_all_rate,
                "balance_rate":     balance_rate,
                "new_balance_rate": new_balance_rate,
                "note":             note,
                "source":           "우리은행 COFIX 고시 (spot.wooribank.com)",
                "type":             "auto",
            }
    except Exception:
        return None


# ─── ECOS 항목 조회 유틸 (수동 실행) ─────────────────────────────

def discover_ecos_items(stat_code="817Y002"):
    """stat_code 전체 항목 목록 출력 (item_code 확인용)
    실행: python -c "from scripts.collect_data import discover_ecos_items; discover_ecos_items()"
    """
    if not ECOS_API_KEY:
        print("ECOS_API_KEY 필요")
        return
    url = (f"https://ecos.bok.or.kr/api/StatisticItemList"
           f"/{ECOS_API_KEY}/json/kr/1/200/{stat_code}")
    r = requests.get(url, timeout=10)
    items = r.json().get("StatisticItemList", {}).get("row", [])
    print(f"[{stat_code}] 항목 수: {len(items)}")
    for it in items:
        print(f"  {it.get('ITEM_CODE',''):15} | {it.get('ITEM_NAME',''):35} | {it.get('ITEM_NAME2','')}")


# ─── 메인 수집 ────────────────────────────────────────────────────

def collect_all():
    print("[1/7] 채권 금리 수집 중 (ECOS API)...")
    bonds = collect_bonds()

    print("[2/7] 금리 이력 수집 중 (스파크라인용)...")
    rate_history = collect_rate_history()

    print("[3/7] 환율 수집 중...")
    usd_krw = collect_usd_krw()

    print("[4/7] PF/금융 뉴스 수집 중 (Naver)...")
    pf_news = collect_pf_news()

    print("[5/7] 부동산 정책 뉴스 수집 중 (Naver)...")
    policy_news = collect_policy_news()

    print("[6/7] Manual CSV 로드 + COFIX 자동수집 중...")
    pf_rates       = load_pf_rates()
    cp_rates       = load_cp_rates()
    deal_watch     = load_deal_watch()
    company_credit = load_credit_ratings()

    # COFIX: 우리은행 고시 페이지 자동수집 → 실패 시 CSV fallback
    cofix_auto = collect_cofix_from_woori()
    cofix_csv  = load_cofix()
    if cofix_auto:
        csv_other = [r for r in cofix_csv if r.get("ym") != cofix_auto["ym"]]
        cofix = [cofix_auto] + csv_other
        print(f"  → COFIX 자동수집 성공: {cofix_auto['ym']}"
              f" (신규취급액 {cofix_auto.get('new_all_rate')}%)")
    else:
        cofix = cofix_csv
        print("  → COFIX 자동수집 실패 — CSV fallback 사용")

    data = {
        "collected_at":   datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "report_date":    datetime.date.today().isoformat(),
        "bonds":          bonds,
        "rate_history":   rate_history,
        "usd_krw":        usd_krw,
        "pf_rates":       pf_rates,
        "cp_rates":       cp_rates,
        "cofix":          cofix,
        "deal_watch":     deal_watch,
        "pf_news":        pf_news,
        "policy_news":    policy_news,
        "company_credit": company_credit,
    }

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / "latest_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[7/7] 저장 완료: {out}")
    return data


if __name__ == "__main__":
    collect_all()
