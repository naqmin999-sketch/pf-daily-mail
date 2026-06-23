# DATA SOURCE MATRIX
> 작성일: 2026-06-24 | 기준: collect_data.py 현재 코드

---

## 1. 리포트 데이터 항목 전체 목록

| # | 항목명 | 표시 섹션 | 수집 방식 | 상태 |
|---|--------|-----------|-----------|------|
| 1 | 기준금리 | ① 시황 요약 / 채권금리 | AUTO | ✅ 정상 |
| 2 | CD 91일 | ① / ② 스파크라인 | AUTO | ✅ 정상 |
| 3 | CP 91일 | ① 시황 요약 | AUTO | ✅ 정상 |
| 4 | 국고채 3Y | ① / ② 스파크라인 | AUTO | ✅ 정상 |
| 5 | 국고채 10Y | ① / ② 스파크라인 | AUTO | ✅ 정상 |
| 6 | 회사채 AA- | ① / ② 스파크라인 | AUTO | ✅ 정상 |
| 7 | 회사채 A+ | ① 시황 요약 | AUTO | ⚠️ item_code 미확인 (N/A 가능) |
| 8 | 회사채 A0 | ① 시황 요약 | AUTO | ⚠️ item_code 미확인 (N/A 가능) |
| 9 | 회사채 A- | ① 시황 요약 | AUTO | ⚠️ item_code 미확인 (N/A 가능) |
| 10 | AA- 스프레드 | ① 시황 요약 | CALC | ✅ 자동 계산 (회사채AA- − 국고채3Y) |
| 11 | A- 스프레드 | ① 시황 요약 | CALC | ⚠️ A- 수집 성공 시 자동 계산 |
| 12 | USD/KRW | ① 시황 요약 | AUTO→FALLBACK | ✅ ECOS → FDR/Yahoo → Naver 순차 |
| 13 | CP 등급별 금리 (A1~A3) | ① 유동화증권 | MANUAL | ❌ 값 미입력 |
| 14 | PF ABCP / ABSTB | ① 유동화증권 | MANUAL | ✅ 샘플 입력됨 (2026-06-01 기준) |
| 15 | 브릿지론 금리 | ① 유동화증권 | MANUAL | ✅ 샘플 입력됨 |
| 16 | 본PF 금리 | ① 유동화증권 | MANUAL | ✅ 샘플 입력됨 |
| 17 | COFIX (신규취급액/잔액/신잔액) | ① 가계대출 | AUTO→FALLBACK | ❌ 자동수집 실패 + CSV 값 미입력 |
| 18 | PF/조달 뉴스 5건 | ③ 뉴스 | AUTO | ✅ Naver API 키 있으면 정상 |
| 19 | 부동산 정책 뉴스 5건 | ③ 뉴스 | AUTO | ✅ Naver API 키 있으면 정상 |
| 20 | Deal Watch | ④ Deal Watch | MANUAL | ❌ 값 미입력 |
| 21 | 신용등급 (건설사 9개사) | ⑤ 신용등급 | MANUAL | ✅ 샘플 입력됨 (2025-01-01 기준) |

---

## 2. AUTO / MANUAL / FALLBACK 구분표

### 2-1. AUTO — ECOS API (한국은행)

| 변수 키 | stat_code | item_code | 표시명 | 검증 상태 |
|---------|-----------|-----------|--------|-----------|
| `base_rate` | 722Y001 | 0101000 | 기준금리 | ✅ 확인 |
| `cd_91` | 817Y002 | 010502000 | CD 91일 | ✅ 확인 |
| `cp_91` | 817Y002 | 010503000 | CP 91일 | ✅ 확인 |
| `gov_3y` | 817Y002 | 010200000 | 국고채 3Y | ✅ 확인 |
| `gov_10y` | 817Y002 | 010210000 | 국고채 10Y | ✅ 확인 |
| `corp_aa_3y` | 817Y002 | 010300000 | 회사채 AA- | ✅ 확인 |
| `corp_aplus_3y` | 817Y002 | 010305000 | 회사채 A+ | ⚠️ **미확인** |
| `corp_a0_3y` | 817Y002 | 010310000 | 회사채 A0 | ⚠️ **미확인** |
| `corp_aminus_3y` | 817Y002 | 010315000 | 회사채 A- | ⚠️ **미확인** |
| `usd_krw` | 731Y001 | 0000001 | USD/KRW | ✅ 확인 (1차 시도) |

> 확인 명령어: `python -c "from scripts.collect_data import discover_ecos_items; discover_ecos_items()"`

### 2-2. AUTO — Naver 뉴스 API

| 항목 | 방식 | 키워드 수 | 결과 건수 | 조건 |
|------|------|-----------|-----------|------|
| PF/조달 뉴스 | Naver 뉴스 API | 10개 키워드 | 최대 5건 | NAVER_CLIENT_ID/SECRET 필요 |
| 부동산 정책 뉴스 | Naver 뉴스 API | 10개 키워드 | 최대 5건 | 동일 |

> API 키 없으면 빈 리스트 반환 (오류 없음, 섹션만 빈 상태)

### 2-3. FALLBACK — AUTO 실패 시 대체

| 항목 | 1차 (AUTO) | 2차 (FALLBACK) | 3차 (FALLBACK) | 현재 상태 |
|------|------------|----------------|----------------|-----------|
| USD/KRW | ECOS API | FinanceDataReader/Yahoo | Naver 스크래핑 | ✅ 1차 성공 |
| COFIX | 은행연합회 크롤링 | `cofix.csv` | — | ❌ 1차 실패, 2차 값 없음 |

### 2-4. MANUAL — CSV 수동 입력

| 파일 | 항목 | 업데이트 주기 | 현재 상태 |
|------|------|---------------|-----------|
| `manual_data/pf_rates.csv` | PF ABCP/ABSTB, 브릿지론, 본PF, 차환금리 (11행) | 수시 (시장변동 시) | ✅ 샘플 있음 — **실제값 갱신 필요** |
| `manual_data/cp_rates.csv` | CP 등급별 3개월/1년 금리 (A1~A3, 6행) | 주 1회 | ❌ **값 모두 비어있음** |
| `manual_data/cofix.csv` | COFIX 신규취급액/잔액/신잔액 (8행) | 월 1회 (매월 15일경) | ❌ **값 모두 비어있음** |
| `manual_data/deal_watch.csv` | 도시정비/PF/브릿지론 조달 사례 | 수시 | ❌ **값 모두 비어있음** |
| `manual_data/credit_ratings.csv` | 건설사 9개사 신용등급 | 분기 1회 | ✅ 샘플 있음 — **2025-01-01 기준, 갱신 필요** |

### 2-5. CALC — 코드에서 자동 계산

| 항목 | 계산식 | 조건 |
|------|--------|------|
| AA- 스프레드 | 회사채AA- − 국고채3Y | 두 값 모두 수집 성공 시 |
| A- 스프레드 | 회사채A- − 국고채3Y | A- 수집 성공 시 (현재 미확인) |

---

## 3. 현재 미해결 이슈 (우선순위 순)

| 우선순위 | 이슈 | 영향 섹션 | 해결 방법 |
|----------|------|-----------|-----------|
| 🔴 HIGH | 회사채 A+/A0/A- item_code 미확인 | ① 시황 요약 | `discover_ecos_items()` 실행 → item_code 확인 후 `collect_data.py` 수정 |
| 🔴 HIGH | cp_rates.csv 값 미입력 | ① 유동화증권 | 실제 CP 발행금리 입력 (금투협 채권정보센터 참고) |
| 🔴 HIGH | cofix.csv 값 미입력 | ① 가계대출 | 은행연합회 공시 → 최근 6~8개월 값 입력 |
| 🟡 MED | deal_watch.csv 값 미입력 | ④ Deal Watch | 실제 딜 정보 입력 |
| 🟡 MED | COFIX 자동수집 실패 (은행연합회 크롤링) | ① 가계대출 | HTML 구조 재확인 또는 크롤링 URL 수정 |
| 🟢 LOW | 신용등급 2025-01-01 기준 (오래됨) | ⑤ 신용등급 | 최신 등급으로 갱신 |
| 🟢 LOW | pf_rates.csv 2026-06-01 기준 (샘플) | ① 유동화증권 | 현재 시장금리로 갱신 |

---

## 4. 데이터 흐름 요약

```
collect_all()
  ├── [AUTO]     collect_bonds()          → ECOS API (금리 9종 + 스프레드 2종)
  ├── [AUTO]     collect_rate_history()   → ECOS API (30일 이력, 스파크라인)
  ├── [AUTO→FB]  collect_usd_krw()        → ECOS → FDR/Yahoo → Naver
  ├── [AUTO]     collect_pf_news()        → Naver API (PF 키워드 10개)
  ├── [AUTO]     collect_policy_news()    → Naver API (정책 키워드 10개)
  ├── [MANUAL]   load_pf_rates()          → manual_data/pf_rates.csv
  ├── [MANUAL]   load_cp_rates()          → manual_data/cp_rates.csv    ← 값 없음
  ├── [MANUAL]   load_deal_watch()        → manual_data/deal_watch.csv  ← 값 없음
  ├── [MANUAL]   load_credit_ratings()    → manual_data/credit_ratings.csv
  └── [AUTO→FB]  collect_cofix_from_kfb() → 은행연합회 크롤링 실패 시 cofix.csv ← 값 없음
                                             → data/latest_report.json 저장
```

---

## 5. GitHub Actions 상태

| 모드 | 트리거 | 상태 |
|------|--------|------|
| `diagnose` | 수동 실행 | ✅ exit code 0 확인 |
| `send` | 매일 KST 08:00 (UTC 23:00) | 미확인 (실 발송 미완료) |

---

*최종 업데이트: 2026-06-24*
