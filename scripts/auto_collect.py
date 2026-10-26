# -*- coding: utf-8 -*-
"""
scripts/auto_collect.py — 딜/신용등급 자동수집 (완전 자동 · 검증필요 태그)

흐름: Naver 뉴스 검색 → Claude API 구조화 추출 → manual_data/*.csv 자동 반영
  · 딜:      신규 행 append (중복 자동 스킵)
  · 신용등급: 기존 회사 행만 갱신 (등급/전망 변동 시)
  · 모든 자동 반영 건에는 "[자동수집·검증필요]" 태그가 note/remark에 붙음

추출 방식 (자동 선택):
  · ANTHROPIC_API_KEY 있으면 → Claude API로 구조화 추출 (고정밀)
  · 없으면 → 규칙 기반 추출 (무료): 제목에 금액 + 본PF/약정/조달 키워드가 있는 기사만 딜로 채택
  ※ GitHub Models(무료 AI)는 2026-07-30 GitHub이 서비스 종료 → 제거함
환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, (선택) ANTHROPIC_API_KEY
실패해도 예외를 밖으로 던지지 않고 로그만 남김 → 리포트 생성은 계속 진행
"""
import csv, json, os, re, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DEALS_CSV = ROOT / "manual_data" / "deal_watch.csv"
# 리포트에서 빠진 과거 딜 보관소 — 같은 딜이 다시 '신규'로 잡히지 않게 중복 판정에만 사용
DEAL_HISTORY_CSV = ROOT / "manual_data" / "deal_history.csv"
RATINGS_CSV = ROOT / "manual_data" / "credit_ratings.csv"

CLAUDE_MODEL = os.environ.get("AUTO_COLLECT_MODEL", "claude-sonnet-5-5")
LOOKBACK_DAYS = int(os.environ.get("AUTO_COLLECT_LOOKBACK_DAYS", "7"))
TAG = "[자동수집·검증필요]"

DEAL_QUERIES = ["본PF 약정", "PF 조달 완료", "브릿지론 본PF 전환", "PF 주관 증권",
                "PF 대주단", "리파이낸싱 PF", "PF 금융약정 체결"]
RATING_QUERIES = ["건설사 신용등급 하향", "건설사 신용등급 상향", "건설 등급전망 변경"]

DEAL_FIELDS = ["type","party","borrower","guarantee_type","rate_pct","maturity",
               "project_name","amount_bn","remark","as_of_date","source","url"]
RATING_FIELDS = ["company","ticker","listed","rating","rating_date","outlook","rater","note"]


# ── 외부 호출 ────────────────────────────────────────────────
def _gh_warn(title, msg):
    """GitHub Actions 화면(요약/주석)에 경고로 표시. 로컬에선 일반 출력."""
    msg = str(msg).replace("\n", " ")[:900]
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning title={title}::{msg}")
    else:
        print(f"  ⚠ {title}: {msg}")


def _open_json(req, timeout):
    """urlopen + JSON. 실패 시 HTTP 상태코드와 응답 본문을 예외 메시지에 포함."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return json.loads(raw)
            except ValueError:
                raise RuntimeError(
                    f"JSON 아닌 응답 HTTP {r.status} [{r.headers.get('Content-Type')}] "
                    f"{req.full_url.split('?')[0]} — {raw[:200].decode('utf-8', 'replace')!r}") from None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code} {req.full_url.split('?')[0]} — {body}") from None


def naver_news(query, display=30):
    cid, csec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        raise RuntimeError("NAVER_CLIENT_ID/SECRET 미설정")
    url = ("https://openapi.naver.com/v1/search/news.json?query="
           + urllib.parse.quote(query) + f"&display={display}&sort=date")
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec})
    return _open_json(req, 15).get("items", [])


# 앞에서부터 시도. 한 모델이 단종·한도초과여도 다음 모델로 넘어감.


def _parse_json(text):
    """AI 응답에서 JSON 배열 추출. 앞뒤 설명문·코드블록·{"deals":[...]} 형태도 허용."""
    raw = (text or "").strip()
    t = re.sub(r"```(?:json)?", "", raw).strip()
    if not t:
        return []
    try:
        val = json.loads(t)
    except ValueError:
        # 설명문 사이에 섞인 [ ... ] 또는 { ... } 덩어리만 잘라서 재시도
        for open_c, close_c in (("[", "]"), ("{", "}")):
            i, j = t.find(open_c), t.rfind(close_c)
            if i != -1 and j > i:
                try:
                    val = json.loads(t[i:j + 1]); break
                except ValueError:
                    continue
        else:
            raise ValueError(f"JSON 아님 — 응답 앞부분: {raw[:150]!r}")
    if isinstance(val, dict):  # {"deals":[...]} / 단일 객체
        lists = [v for v in val.values() if isinstance(v, list)]
        val = lists[0] if lists else [val]
    return val if isinstance(val, list) else []


class NoLLM(Exception):
    """AI 키 없음 → 규칙 기반 추출로 대체"""


def llm_extract(prompt):
    """Claude API 구조화 추출. 키 없으면 NoLLM."""
    akey = os.environ.get("ANTHROPIC_API_KEY")
    if not akey:
        raise NoLLM()
    body = json.dumps({
        "model": CLAUDE_MODEL, "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": akey,
                 "anthropic-version": "2023-06-01"})
    data = _open_json(req, 60)
    return _parse_json("".join(b.get("text", "") for b in data.get("content", [])))


# ── 규칙 기반 딜 추출 (AI 키 없을 때) ─────────────────────────────
_AMT = re.compile(r"(\d+(?:\.\d+)?)\s*조(?:\s*(\d{1,4}(?:,\d{3})?)\s*억)?|(\d{1,3}(?:,\d{3})+|\d+)\s*억")
_DEAL_KW = re.compile(r"본PF|브릿지론|PF|리파이낸싱|대주단|금융약정|GPU|데이터센터|AI\s*금융")
_DONE_KW = re.compile(r"약정|완료|확보|체결|성공|조달|전환|마무리|실행|주관")
_SKIP_KW = re.compile(r"부실|연체|정책|전망|대책|시장\s*동향|감독|규제|금리\s*인상|우려|위기|사설|칼럼|공모|IPO")


def _amount_bn(text):
    """'1조5000억'→15000, '3,500억'→3500 (억원 단위). 가장 큰 금액 채택."""
    # '2천억'→'2000억', '5백억'→'500억', '1조5천억'→'1조5000억'
    text = re.sub(r"(\d+(?:\.\d+)?)\s*천\s*억", lambda m: f"{int(float(m.group(1))*1000)}억", text)
    text = re.sub(r"(\d+)\s*백\s*억", lambda m: f"{int(m.group(1))*100}억", text)
    best = 0
    for m in _AMT.finditer(text):
        if m.group(1):
            v = float(m.group(1)) * 10000 + (int(m.group(2).replace(",", "")) if m.group(2) else 0)
        else:
            v = int(m.group(3).replace(",", ""))
        best = max(best, int(v))
    return best


MAX_DEALS = int(os.environ.get("AUTO_COLLECT_MAX_DEALS", "2"))


def rule_extract_deals(news):
    """검색어로 찾은 뉴스 중 딜 기사 최대 MAX_DEALS건.
    1순위: 제목에 PF 키워드 + 약정/조달 등 + 금액 / 2순위(없는 날): 제목에 PF 키워드만 있는 최신 기사"""
    strict = _rule_pick(news, strict=True)
    if strict:
        return strict[:MAX_DEALS]
    return _rule_pick(news, strict=False)[:MAX_DEALS]


def _rule_pick(news, strict):
    deals = []
    for n in sorted(news, key=lambda x: x["date"], reverse=True):
        title, desc = n["title"], n.get("desc", "")
        if not _DEAL_KW.search(title) or _SKIP_KW.search(title):
            continue
        amt = _amount_bn(title) or _amount_bn(desc)
        if strict and (not _DONE_KW.search(title) or amt < 100):
            continue
        # 5조 초과는 시장 전체 규모 등 오인 가능성 → 금액은 비우고 기사만 남김(링크로 확인)
        amt_s = str(amt) if 100 <= amt <= 50000 else ""
        dtype = "브릿지론" if "브릿지" in title else "PF"
        src = urllib.parse.urlparse(n["link"]).netloc.replace("www.", "")
        deals.append({"type": dtype, "party": "", "borrower": "", "guarantee_type": "",
                      "rate_pct": "", "maturity": "", "project_name": title,
                      "amount_bn": amt_s, "remark": desc[:80],
                      "as_of_date": n["date"], "source": src, "url": n["link"]})
    return deals


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

응답은 반드시 '['로 시작해 ']'로 끝나는 JSON 배열 하나만 출력하세요. 인사말·설명·마크다운 금지. 딜이 없으면 [] 만 출력.
각 딜 형식:
[{"type":"PF|브릿지론|도시정비 중 하나(본PF는 PF로 표기)","party":"시공사/주요 관련사 이름","borrower":"조달주체(SPC명 등)","guarantee_type":"보증형태(예: 시공사 책임준공)","rate_pct":"금리 숫자 또는 빈문자열","maturity":"YYYY-MM 또는 빈문자열","project_name":"사업장명(위치·규모 포함)","amount_bn":"조달금액(억원 단위 정수)","remark":"주관사·대주단·우발채무 등 핵심 요약 1문장","as_of_date":"약정일 YYYY-MM-DD(기사일 아님, 불명확하면 빈문자열)","source":"언론사명","url":"해당 기사의 링크(목록 괄호 안 URL을 그대로 복사)"}]

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
        listing = "\n".join(f"- [{n['date']}] {n['title']} — {n['desc']} ({n['link']})" for n in news[:40])
        try:
            deals = llm_extract(DEAL_PROMPT.replace("{NEWS}", listing))
        except NoLLM:
            deals = rule_extract_deals(news)
            print(f"  [auto] AI 키 없음 → 규칙 기반 추출: 후보 {len(news)}건 중 {len(deals)}건")
        current = _read_csv(DEALS_CSV)
        history = _read_csv(DEAL_HISTORY_CSV)
        new_rows = []
        for d in deals:
            # 금액이 없어도 기사 링크가 있으면 채택 (링크로 확인 가능)
            if not d.get("project_name") or not (str(d.get("amount_bn", "")).strip() or d.get("url")):
                continue
            if is_dup_deal(d, current + history + new_rows):
                print(f"  [auto] 중복 스킵: {d['project_name'][:30]}"); continue
            # 링크는 실제 검색된 기사 URL만 허용 (AI가 지어낸 주소 차단)
            if d.get("url") not in seen:
                d["url"] = ""
            d["remark"] = f"{TAG} {d.get('remark','')}".strip()
            new_rows.append({k: str(d.get(k, "")) for k in DEAL_FIELDS})
            print(f"  [auto] 딜 추가: {d['project_name'][:40]} / {d['amount_bn']}억")
        new_rows = new_rows[:MAX_DEALS]
        if new_rows:
            # 신규 딜이 있으면: 기존(과거) 딜은 리포트에서 삭제 → 보관소로 이동, 신규 딜만 남김
            # 신규 딜이 없으면: 기존 딜 그대로 유지 (리포트가 비지 않도록)
            if current:
                _write_csv(DEAL_HISTORY_CSV, DEAL_FIELDS, history + current)
                print(f"  [auto] 과거 딜 {len(current)}건 리포트에서 삭제(보관소 이동)")
            _write_csv(DEALS_CSV, DEAL_FIELDS, new_rows)
        print(f"  [auto] 신규 딜 {len(new_rows)}건 반영")
        return len(new_rows)
    except Exception as e:
        _gh_warn("딜 자동수집 실패", e)
        return 0


# ── ② 신용등급 자동수집 ──────────────────────────────────────
RATING_PROMPT = """다음은 건설사 신용등급 관련 뉴스 목록입니다. "실제 등급 또는 전망이 변경된 건"만 추출하세요.

응답은 반드시 '['로 시작해 ']'로 끝나는 JSON 배열 하나만 출력 (설명 금지, 없으면 []):
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
        listing = "\n".join(f"- [{n['date']}] {n['title']} — {n['desc']}" for n in news[:40])
        try:
            changes = llm_extract(RATING_PROMPT.replace("{NEWS}", listing))
        except NoLLM:
            print("  [auto] AI 키 없음 → 신용등급 자동갱신 생략 (credit_ratings.csv 수기 관리)")
            return 0
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
        _gh_warn("신용등급 자동수집 실패", e)
        return 0


if __name__ == "__main__":
    collect_deals()
    collect_ratings()
