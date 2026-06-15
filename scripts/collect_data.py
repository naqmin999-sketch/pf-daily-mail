"""
PF Daily Market Intelligence — 데이터 수집 모듈
AUTO 수집: ECOS API(금리/환율), pykrx(주가지수), Naver(뉴스)
MANUAL 관리: manual_data/credit_ratings.csv, manual_data/pf_rates.csv
"""
import os
import json
import csv
import datetime
import time
import requests
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
MANUAL_DIR = BASE_DIR / "manual_data"

ECOS_API_KEY       = os.getenv("ECOS_API_KEY", "")
NAVER_CLIENT_ID    = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

# 한국은행 ECOS 통계코드 (stat_code, cycle, item_code, 표시명)
ECOS_ITEMS = {
    "base_rate":  ("722Y001", "D", "0101000",   "기준금리"),
    "cd_91":      ("817Y002", "D", "010190000", "CD 91일"),
    "cp_91":      ("817Y002", "D", "010200000", "CP 91일"),
    "gov_3y":     ("817Y002", "D", "010300000", "국고채 3Y"),
    "gov_10y":    ("817Y002", "D", "010320000", "국고채 10Y"),
    "corp_aa_3y": ("817Y002", "D", "010400000", "회사채 3Y AA-"),
}

# 상장 건설사 종목코드 (KRX)
LISTED_STOCKS = {
    "DL이앤씨":        "375500",
    "현대건설":        "000720",
    "GS건설":          "006360",
    "대우건설":        "047040",
    "HDC현대산업개발": "294870",
    "포스코이앤씨":    "047050",
    "태영건설":        "009410",
}
NON_LISTED    = ["롯데건설", "SK에코플랜트"]
ALL_COMPANIES = list(LISTED_STOCKS.keys()) + NON_LISTED

PF_KEYWORDS = [
    "PF대출", "프로젝트파이낸싱", "브릿지론", "본PF",
    "ABCP 건설", "ABSTB", "PF 차환", "미분양 PF", "PF 부실",
]

INDEX_TICKERS = {
    "KOSPI":  "1001",
    "KOSDAQ": "2001",
    "KRX건설": "1028",  # KOSPI 건설업 업종지수
}


# ─── ECOS API ─────────────────────────────────────────────────────

def _ecos_date_range(days_back=8):
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_ecos(stat_code, cycle, item_code, label):
    if not ECOS_API_KEY:
        return {
            "value": None, "date": None, "label": label,
            "source": "한국은행 ECOS", "type": "auto",
            "error": "API키 미설정 (.env → ECOS_API_KEY)",
        }
    start, end = _ecos_date_range(8)
    url = f"{ECOS_BASE}/{ECOS_API_KEY}/json/kr/1/10/{stat_code}/{cycle}/{start}/{end}/{item_code}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        rows = r.json().get("StatisticSearch", {}).get("row", [])
        if not rows:
            return {"value": None, "date": None, "label": label,
                    "source": "한국은행 ECOS", "type": "auto", "error": "응답 데이터 없음"}
        latest = rows[-1]
        raw    = latest.get("DATA_VALUE", "")
        return {
            "value":  float(raw) if raw else None,
            "date":   latest.get("TIME", ""),
            "label":  label,
            "source": "한국은행 ECOS",
            "type":   "auto",
        }
    except Exception as e:
        return {"value": None, "date": None, "label": label,
                "source": "한국은행 ECOS", "type": "auto", "error": str(e)}


def collect_funding_market():
    result = {}
    for key, (stat, cycle, item, label) in ECOS_ITEMS.items():
        result[key] = fetch_ecos(stat, cycle, item, label)
        time.sleep(0.15)

    # AA- 스프레드 자동 계산
    corp_val = result.get("corp_aa_3y", {}).get("value")
    gov_val  = result.get("gov_3y", {}).get("value")
    if corp_val and gov_val:
        result["aa_spread"] = {
            "value":  round(corp_val - gov_val, 3),
            "label":  "AA- 스프레드 (회사채3Y - 국고채3Y)",
            "source": "ECOS 계산값",
            "type":   "auto_derived",
        }
    return result


# ─── 환율 ─────────────────────────────────────────────────────────

def collect_usd_krw():
    # 1차: ECOS
    r = fetch_ecos("731Y001", "D", "0000001", "USD/KRW")
    if r.get("value"):
        return r

    # 2차: Naver Finance 스크래핑 (fallback)
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(
            "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        el = soup.select_one(".rate_value")
        if el:
            val = float(el.get_text(strip=True).replace(",", ""))
            return {"value": val, "date": datetime.date.today().isoformat(),
                    "label": "USD/KRW", "source": "네이버 금융 (스크래핑)", "type": "auto"}
    except Exception:
        pass

    return {"value": None, "date": None, "label": "USD/KRW",
            "source": "N/A", "type": "auto", "error": "수집 실패 — ECOS·Naver 모두 실패"}


# ─── pykrx 주가/지수 ──────────────────────────────────────────────

def _latest_biz_date():
    d = datetime.date.today() - datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y%m%d")


def _week_ago():
    return (datetime.date.today() - datetime.timedelta(days=10)).strftime("%Y%m%d")


def collect_market_indices():
    result = {}
    try:
        from pykrx import stock as krx
        end_d, start_d = _latest_biz_date(), _week_ago()
        for name, ticker in INDEX_TICKERS.items():
            try:
                df = krx.get_index_ohlcv_by_date(start_d, end_d, ticker)
                if df is None or df.empty:
                    result[name] = {"value": None, "source": "KRX/pykrx",
                                    "type": "auto", "error": "데이터 없음"}
                    continue
                latest = df.iloc[-1]
                prev   = df.iloc[-2] if len(df) >= 2 else None
                close  = float(latest["종가"])
                chg    = round(close - float(prev["종가"]), 2) if prev is not None else None
                pct    = round(chg / float(prev["종가"]) * 100, 2) if chg is not None and float(prev["종가"]) else None
                result[name] = {
                    "value": close, "change": chg, "change_pct": pct,
                    "date":  df.index[-1].strftime("%Y-%m-%d"),
                    "label": name, "source": "KRX/pykrx", "type": "auto",
                }
            except Exception as e:
                result[name] = {"value": None, "source": "KRX/pykrx",
                                "type": "auto", "error": str(e)}
    except ImportError:
        for name in INDEX_TICKERS:
            result[name] = {"value": None, "source": "pykrx",
                            "type": "auto", "error": "pykrx 미설치 — pip install pykrx"}
    return result


def collect_stock_prices():
    prices = {}
    try:
        from pykrx import stock as krx
        end_d, start_d = _latest_biz_date(), _week_ago()
        for company, ticker in LISTED_STOCKS.items():
            try:
                df = krx.get_market_ohlcv_by_date(start_d, end_d, ticker)
                if df is None or df.empty:
                    prices[company] = {"ticker": ticker, "value": None,
                                       "source": "KRX/pykrx", "type": "auto", "error": "데이터 없음"}
                    continue
                latest = df.iloc[-1]
                prev   = df.iloc[-2] if len(df) >= 2 else None
                close  = int(latest["종가"])
                chg    = int(latest["종가"] - prev["종가"]) if prev is not None else None
                pct    = round(chg / int(prev["종가"]) * 100, 2) if chg is not None and int(prev["종가"]) else None
                prices[company] = {
                    "ticker": ticker, "value": close,
                    "change": chg,    "change_pct": pct,
                    "date":   df.index[-1].strftime("%Y-%m-%d"),
                    "source": "KRX/pykrx", "type": "auto",
                }
            except Exception as e:
                prices[company] = {"ticker": ticker, "value": None,
                                   "source": "KRX/pykrx", "type": "auto", "error": str(e)}
    except ImportError:
        for company, ticker in LISTED_STOCKS.items():
            prices[company] = {"ticker": ticker, "value": None,
                               "source": "pykrx", "type": "auto", "error": "pykrx 미설치"}

    for company in NON_LISTED:
        prices[company] = {"ticker": None, "value": None,
                           "source": "비상장", "type": "manual", "note": "비상장사 — 주가 없음"}
    return prices


# ─── 뉴스 수집 ────────────────────────────────────────────────────

def _clean(s):
    return (s.replace("<b>", "").replace("</b>", "")
             .replace("&amp;", "&").replace("&quot;", '"').strip())


def fetch_naver_news(keyword, display=5):
    # 1차: Naver Developer API
    if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
        try:
            r = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers={
                    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                },
                params={"query": keyword, "display": display, "sort": "date"},
                timeout=10,
            )
            if r.status_code == 200:
                return [
                    {
                        "title":    _clean(it.get("title", "")),
                        "link":     it.get("originallink") or it.get("link", ""),
                        "pub_date": it.get("pubDate", "")[:16],
                        "desc":     _clean(it.get("description", ""))[:100],
                        "press":    "네이버 뉴스 API",
                        "keyword":  keyword,
                    }
                    for it in r.json().get("items", [])
                ]
        except Exception:
            pass

    # 2차: 웹 스크래핑 fallback
    results = []
    try:
        from bs4 import BeautifulSoup
        today = datetime.date.today().strftime("%Y.%m.%d")
        url = (f"https://search.naver.com/search.naver?where=news"
               f"&query={quote(keyword)}&sort=1&ds={today}&de={today}")
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        soup = BeautifulSoup(r.text, "lxml")
        for art in soup.select("div.news_area")[:display]:
            title_el = art.select_one("a.news_tit")
            press_el = art.select_one("a.info.press")
            if title_el:
                results.append({
                    "title":    title_el.get_text(strip=True),
                    "link":     title_el.get("href", ""),
                    "pub_date": "",
                    "desc":     "",
                    "press":    press_el.get_text(strip=True) if press_el else "네이버",
                    "keyword":  keyword,
                })
    except Exception:
        pass
    return results


def collect_pf_news():
    all_news, seen = [], set()
    for kw in PF_KEYWORDS:
        for art in fetch_naver_news(kw, display=3):
            if art["title"] not in seen:
                seen.add(art["title"])
                art["category"] = "PF시장"
                all_news.append(art)
        time.sleep(0.25)
    return all_news[:15]


def collect_company_news():
    news_map = {}
    for co in ALL_COMPANIES:
        arts = fetch_naver_news(f"{co} PF 건설", display=2)
        if not arts:
            arts = fetch_naver_news(co, display=2)
        news_map[co] = arts
        time.sleep(0.25)
    return news_map


# ─── Manual CSV 로드 ──────────────────────────────────────────────

def load_credit_ratings():
    path = MANUAL_DIR / "credit_ratings.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {
            row["company"]: {
                "ticker":       row.get("ticker", ""),
                "listed":       row.get("listed", "").upper() == "TRUE",
                "rating":       row.get("rating", ""),
                "rating_date":  row.get("rating_date", ""),
                "outlook":      row.get("outlook", ""),
                "rater":        row.get("rater", ""),
                "note":         row.get("note", ""),
                "source":       "manual_data/credit_ratings.csv",
                "type":         "manual",
            }
            for row in csv.DictReader(f)
        }


def load_pf_rates():
    path = MANUAL_DIR / "pf_rates.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [
            {**row, "source": "manual_data/pf_rates.csv", "type": "manual"}
            for row in csv.DictReader(f)
        ]


# ─── 메인 수집 ────────────────────────────────────────────────────

def collect_all():
    print("[1/6] 금리 데이터 수집 중 (ECOS API)...")
    funding = collect_funding_market()

    print("[2/6] 환율 수집 중...")
    usd_krw = collect_usd_krw()

    print("[3/6] 주가지수 수집 중 (pykrx)...")
    indices = collect_market_indices()

    print("[4/6] 건설사 주가 수집 중 (pykrx)...")
    stocks = collect_stock_prices()

    print("[5/6] PF·건설 뉴스 수집 중 (Naver)...")
    pf_news      = collect_pf_news()
    company_news = collect_company_news()

    print("[6/6] Manual CSV 로드 중...")
    credit_ratings = load_credit_ratings()
    pf_rates       = load_pf_rates()

    company_watch = {
        co: {
            "stock":  stocks.get(co, {}),
            "credit": credit_ratings.get(co, {"type": "manual", "error": "CSV 미입력"}),
            "news":   company_news.get(co, []),
        }
        for co in ALL_COMPANIES
    }

    data = {
        "collected_at":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "report_date":   datetime.date.today().isoformat(),
        "market":        {**indices, "USD_KRW": usd_krw},
        "funding":       funding,
        "pf_rates":      pf_rates,
        "pf_news":       pf_news,
        "company_watch": company_watch,
    }

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / "latest_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → 저장 완료: {out}")
    return data


if __name__ == "__main__":
    collect_all()
