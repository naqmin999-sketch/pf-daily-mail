# -*- coding: utf-8 -*-
"""
scripts/auto_collect.py — 딜/신용등급 자동수집 (완전 자동 · 검증필요 태그)

흐름: Naver 뉴스 검색 → Claude API 구조화 추출 → manual_data/*.csv 자동 반영
  · 딜:      신규 행 append (중복 자동 스킵)
  · 신용등급: 기존 회사 행만 갱신 (등급/전망 변동 시)
  · 모든 자동 반영 건에는 "[자동수집·검증필요]" 태그가 note/remark에 붙음

LLM 백엔드 (자동 선택):
  · ANTHROPIC_API_KEY 있으면 → Claude API (유료·고정밀)
  · 없으면 → GitHub Models (GITHUB_TOKEN, 무료) ← 기본. 워크플로에
    permissions: models: read 필요. 추가 비용 없음.
환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, (선택) ANTHROPIC_API_KEY
실패해도 예외를 밖으로 던지지 않고 로그만 남김 → 리포트 생성은 계속 진행
"""
import csv, json, os, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DEALS_CSV = ROOT / "manual_data" / "deal_watch.csv"
RATINGS_CSV = ROOT / "manual_data" / "credit_ratings.csv"

CLAUDE_MODEL = os.environ.get("AUTO_COLLECT_MODEL", "claude-sonnet-4-6")
LOOKBACK_DAYS = int(os.environ.get("AUTO_COLLECT_LOOKBACK_DAYS", "2"))
TAG = "[자동수집·검증필요]"

DEAL_QUERIES = ["본PF 약정", "PF 조달 완료", "브릿지론 본PF 전환", "PF 주관 증권"]
RATING_QUERIES = ["건설사 신용등급 하향", "건설사 신용등급 상향", "건설 등급전망 변경"]

DEAL_FIELDS = ["type","party","borrower","guarantee_type","rate_pct","maturity",
               "project_name","amount_bn","remark","as_of_date","source"]
RATING_FIELDS = ["company","ticker","listed","rating","rating_date","outlook","rater","note"]


# ── 외부 호출 ────────────────────────────────────────────────
def naver_news(query, display=15):
    cid, csec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        raise RuntimeError("NAVER_CLIENT_ID/SECRET 미설정")
    url = ("https://openapi.naver.com/v1/search/news.json?query="
           + urllib.parse.quote(query) + f"&display={display}&sort=date")
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r).get("items", [])


GITHUB_MODEL = os.environ.get("AUTO_COLLECT_GH_MODEL", "openai/gpt-4o")


def _parse_json(text):
    text = re.sub(r"^```(json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    return json.loads(text) if text else []


def llm_extract(prompt):
    """구조화 추출. ANTHROPIC_API_KEY 있으면 Claude, 없으면 GitHub Models(무료)."""
    akey = os.environ.get("ANTHROPIC_API_KEY")
    if akey:
        body = json.dumps({
            "model": CLAUDE_MODEL, "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body, method="POST",
            headers={"content-type": "application/json", "x-api-key": akey,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return _parse_json("".join(b.get("text", "") for b in data.get("content", [])))

    gtoken = os.environ.get("GITHUB_TOKEN")
    if not gtoken:
        raise RuntimeError("ANTHROPIC_API_KEY도 GITHUB_TOKEN도 없음 — LLM 백엔드 불가")
    body = json.dumps({
        "model": GITHUB_MODEL, "max_tokens": 2000, "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://models.github.ai/inference/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {gtoken}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return _parse_json(data["choices"][0]["message"]["content"])


# 하위호환 별칭
claude_extract = llm_extract


# ── 공통 유틸 ────────────────────────────────────────────────
def _clean(s):
    return re.sub(r"<[^>]+>|&\w+;", "", s or "").strip()


def _recent(items):
    cutoff = datetime.now(KST) - timedelta(days=LOOKBACK_DAYS)
    out = []
    for it in items:
        try:
            pub = datetime.strptime(it["pubDate"], "%a, %d %b %Y %H:%M:%S %z")
        except Exception:
            continue
        if pub >= cutoff:
            out.append({"title": _clean(it["title"]),
                        "desc": _clean(it.get("description")),
                        "link": it.get("originallink") or it.get("link", ""),
                        "date": pub.strftime("%Y-%m-%d")})
    return out


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def _tokens(s):
    return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", s or ""))


def is_dup_deal(new, existing_rows):
    """프로젝트명 토큰 겹침 60%↑ 또는 (조달주체+금액) 동일 → 중복."""
    nt = _tokens(new.get("project_name"))
    for r in existing_rows:
        et = _tokens(r.get("project_name"))
        if nt and et and len(nt & et) / max(len(nt | et), 1) >= 0.6:
            return True
        if (new.get("borrower") and new.get("borrower") == r.get("borrower")
                and str(new.get("amount_bn")) == str(r.get("amount_bn"))):
            return True
    return False


# ── ① 딜 자동수집 ────────────────────────────────────────────
DEAL_PROMPT = """다음은 한국 부동산 PF 관련 뉴스 목록입니다. 이 중 "실제로 성사/약정된 PF 자금조달 딜"만 추출하세요.
정책·시황·전망 기사, 단순 계획 단계는 제외합니다.

각 딜을 아래 JSON 배열로만 응답하세요 (설명·마크다운 금지, 딜이 없으면 []):
[{"type":"PF|브릿지론|도시정비 중 하나(본PF는 PF로 표기)","party":"시공사/주요 관련사 이름","borrower":"조달주체(SPC명 등)","guarantee_type":"보증형태(예: 시공사 책임준공)","rate_pct":"금리 숫자 또는 빈문자열","maturity":"YYYY-MM 또는 빈문자열","project_name":"사업장명(위치·규모 포함)","amount_bn":"조달금액(억원 단위 정수)","remark":"주관사·대주단·우발채무 등 핵심 요약 1문장","as_of_date":"약정일 YYYY-MM-DD(기사일 아님, 불명확하면 빈문자열)","source":"언론사명"}]

기사에 명시되지 않은 값은 빈 문자열로 두고, 추측하지 마세요. 금액이 '조' 단위면 억으로 환산하세요(1.5조→15000).

뉴스 목록:
{NEWS}"""


def collect_deals():
    print("  [auto] 딜 자동수집 시작")
    try:
        news, seen = [], set()
        for q in DEAL_QUERIES:
            for it in _recent(naver_news(q)):
                if it["link"] not in seen:
                    seen.add(it["link"]); news.append(it)
        if not news:
            print("  [auto] 최근 딜 후보 기사 없음"); return 0
        listing = "\n".join(f"- [{n['date']}] {n['title']} — {n['desc']} ({n['link']})" for n in news[:30])
        deals = llm_extract(DEAL_PROMPT.replace("{NEWS}", listing))
        existing = _read_csv(DEALS_CSV)
        added = 0
        for d in deals:
            if not d.get("project_name") or not str(d.get("amount_bn", "")).strip():
                continue
            if is_dup_deal(d, existing):
                print(f"  [auto] 중복 스킵: {d['project_name'][:30]}"); continue
            d["remark"] = f"{TAG} {d.get('remark','')}".strip()
            row = {k: str(d.get(k, "")) for k in DEAL_FIELDS}
            existing.append(row); added += 1
            print(f"  [auto] 딜 추가: {d['project_name'][:40]} / {d['amount_bn']}억")
        if added:
            _write_csv(DEALS_CSV, DEAL_FIELDS, existing)
        print(f"  [auto] 딜 {added}건 반영")
        return added
    except Exception as e:
        print(f"  [auto] ⚠ 딜 수집 실패(리포트는 계속): {e}")
        return 0


# ── ② 신용등급 자동수집 ──────────────────────────────────────
RATING_PROMPT = """다음은 건설사 신용등급 관련 뉴스 목록입니다. "실제 등급 또는 전망이 변경된 건"만 추출하세요.

JSON 배열로만 응답 (없으면 []):
[{"company":"회사명(정식명)","rating":"변경 후 등급(예: A+)","outlook":"안정적|긍정적|부정적","rating_date":"평가일 YYYY-MM-DD(불명확하면 빈문자열)","rater":"평가사(NICE신용평가|한국기업평가|한국신용평가)","summary":"변경 사유 1문장"}]

기사에 명시되지 않은 값은 빈 문자열. 추측 금지.

뉴스 목록:
{NEWS}"""


def collect_ratings():
    print("  [auto] 신용등급 자동수집 시작")
    try:
        news, seen = [], set()
        for q in RATING_QUERIES:
            for it in _recent(naver_news(q)):
                if it["link"] not in seen:
                    seen.add(it["link"]); news.append(it)
        if not news:
            print("  [auto] 최근 등급 변동 기사 없음"); return 0
        listing = "\n".join(f"- [{n['date']}] {n['title']} — {n['desc']}" for n in news[:30])
        changes = llm_extract(RATING_PROMPT.replace("{NEWS}", listing))
        rows = _read_csv(RATINGS_CSV)
        by_name = {r["company"]: r for r in rows}
        updated = 0
        today = datetime.now(KST).strftime("%Y-%m-%d")
        for c in changes:
            r = by_name.get(c.get("company"))
            if not r:
                print(f"  [auto] 관리 외 회사 스킵: {c.get('company')}"); continue
            if (c.get("rating") or r["rating"]) == r["rating"] and \
               (c.get("outlook") or r["outlook"]) == r["outlook"]:
                continue  # 변동 없음
            old = f"{r['rating']}/{r['outlook']}"
            if c.get("rating"):  r["rating"] = c["rating"]
            if c.get("outlook"): r["outlook"] = c["outlook"]
            if c.get("rater"):   r["rater"] = c["rater"]
            r["rating_date"] = c.get("rating_date") or today
            r["note"] = f"{TAG} {old}→{r['rating']}/{r['outlook']} · {c.get('summary','')}".strip()
            updated += 1
            print(f"  [auto] 등급 갱신: {r['company']} {old} → {r['rating']}/{r['outlook']}")
        if updated:
            _write_csv(RATINGS_CSV, RATING_FIELDS, rows)
        print(f"  [auto] 등급 {updated}건 반영")
        return updated
    except Exception as e:
        print(f"  [auto] ⚠ 등급 수집 실패(리포트는 계속): {e}")
        return 0


if __name__ == "__main__":
    collect_deals()
    collect_ratings()
