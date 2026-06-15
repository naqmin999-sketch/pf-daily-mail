# PF Daily Market Intelligence — 프로젝트 상태 파일

> **작성일**: 2026-06-15  
> **목적**: 내일 이어서 작업하기 위한 현황 스냅샷  
> **다음 우선순위**: Python 실행 테스트 → API 키 설정 → HTML 확인 → 스케줄러 등록

---

## 1. 프로젝트 목적

**국내 건설사 금융팀용 일일 PF 시황 HTML 이메일 자동 발송 시스템**

- 매일 오전 8시 자동 실행
- 홈페이지 아님 — HTML 이메일 리포트 1장 생성 후 SMTP 발송
- 국내 PF 조달시장 중심 (미국채 등 해외지표 제외 또는 보조)
- 실데이터(AUTO) vs 수동관리(MANUAL) 명확히 구분 표시

**리포트 5개 섹션:**
1. Executive Summary (핵심 5줄 + PF 조달영향 + 주의 건설사)
2. 국내 시장 동향 (KOSPI, KOSDAQ, KRX건설, USD/KRW)
3. Funding Market (기준금리~회사채AA- 채권금리 + PF ABCP/브릿지론 수동금리)
4. PF Market 뉴스 (키워드 자동 수집)
5. Construction Company Watch (주가 + 신용등급 + 뉴스)

---

## 2. 현재 파일 구조

```
C:\Users\naqmi\pf-daily-mail\
├── main.py                        ✅ 완료 (1,629 bytes)
├── requirements.txt               ✅ 완료 (87 bytes)
├── .env.example                   ✅ 완료 (1,667 bytes)
├── .gitignore                     ✅ 완료
├── README.md                      ✅ 완료 (5,536 bytes)
├── PROJECT_STATUS.md              ✅ 이 파일
│
├── scripts/
│   ├── __init__.py                ✅ 완료 (빈 파일)
│   ├── collect_data.py            ✅ 완료 (15,433 bytes)
│   ├── generate_report.py         ✅ 완료 (18,222 bytes)
│   └── send_email.py              ✅ 완료 (2,442 bytes)
│
├── data/                          ✅ 디렉터리 생성됨
│   └── latest_report.json         ❌ 미생성 (첫 실행 시 자동 생성)
│
├── reports/                       ✅ 디렉터리 생성됨
│   └── YYYY-MM-DD_report.html     ❌ 미생성 (첫 실행 시 자동 생성)
│
└── manual_data/
    ├── credit_ratings.csv          ✅ 완료 (793 bytes) — 샘플 데이터 입력됨
    └── pf_rates.csv                ✅ 완료 (691 bytes) — 샘플 데이터 입력됨
```

**누락 파일 없음. 모든 핵심 스크립트 작성 완료.**

---

## 3. 완료된 작업

### 3-1. 설계 완료
- [x] 데이터 소스 전략 확정 (AUTO vs MANUAL 구분)
- [x] 리포트 섹션 구성 설계
- [x] 파일 구조 설계

### 3-2. 파일 생성 완료

| 파일 | 내용 | 상태 |
|------|------|------|
| `requirements.txt` | requests, pykrx, beautifulsoup4, python-dotenv, lxml | ✅ |
| `.env.example` | ECOS_API_KEY, NAVER_CLIENT_ID/SECRET, EMAIL_* | ✅ |
| `manual_data/credit_ratings.csv` | 9개 건설사 신용등급 샘플 입력 | ✅ |
| `manual_data/pf_rates.csv` | PF ABCP/ABSTB/브릿지론/본PF 금리 샘플 | ✅ |
| `scripts/collect_data.py` | 전체 데이터 수집 로직 | ✅ |
| `scripts/generate_report.py` | HTML 리포트 생성 로직 | ✅ |
| `scripts/send_email.py` | SMTP 이메일 발송 | ✅ |
| `main.py` | 파이프라인 오케스트레이터 | ✅ |
| `README.md` | 설치/실행/자동화 가이드 | ✅ |

---

## 4. 미완료 작업 (남은 TODO)

### ❗ 즉시 필요 (내일 첫 번째 작업)

- [ ] **Python 실행 테스트** — 세션에서 `python main.py --no-send` 실행 안 됨
  - PowerShell에서 `pip` / `python` 명령어를 찾지 못하는 문제 발생
  - 터미널에서 직접 실행 필요: `! python main.py --no-send`
  - 또는 `py main.py --no-send` 시도
- [ ] **`.env` 파일 생성** — `.env.example` 복사 후 실제 API 키 입력
- [ ] **생성된 HTML 브라우저로 확인** — `reports/2026-06-16_report.html` 열어보기

### 🔧 API 키 설정 (우선순위 높음)

- [ ] **ECOS API 키** 발급 및 `.env` 입력
  - 발급: https://ecos.bok.or.kr/api/ (무료, 즉시 발급)
  - 없으면 금리 데이터 전부 N/A
- [ ] **Naver Developer API** 발급 및 `.env` 입력
  - 발급: https://developers.naver.com/ (무료)
  - 없으면 뉴스 수집이 웹 스크래핑 fallback으로 전환 (불안정)

### 🐛 코드 검증 필요 사항

- [ ] **KRX건설 지수 ticker 확인**
  - 현재 코드: `"KRX건설": "1028"` (KOSPI 건설업)
  - 실제 ticker가 다를 수 있음 → pykrx 설치 후 아래 코드로 확인:
    ```python
    from pykrx import stock
    tickers = stock.get_index_ticker_list(market="KOSPI")
    for t in tickers:
        name = stock.get_index_ticker_name(t)
        if "건설" in name:
            print(t, name)
    ```
- [ ] **ECOS 817Y002 item_code 검증**
  - 현재 설정값 (문서 기반):
    ```
    CD 91일:    010190000
    CP 91일:    010200000
    국고채 3Y:  010300000
    국고채 10Y: 010320000
    회사채 AA-: 010400000
    ```
  - API 키 발급 후 실제 응답 확인 필요
  - 오류 시 `scripts/collect_data.py` → `ECOS_ITEMS` 딕셔너리 수정
- [ ] **Naver 스크래핑 HTML 구조 확인**
  - `div.news_area` 셀렉터가 현재 Naver 구조와 맞는지 확인
  - Naver API 키 있으면 스크래핑 불필요

### 📧 이메일 발송 테스트 (2단계)

- [ ] Gmail 앱 비밀번호 발급 (Google 계정 → 보안 → 2단계인증 → 앱 비밀번호)
- [ ] `.env` EMAIL_* 항목 입력
- [ ] `python scripts/send_email.py` 테스트 발송

### ⏱️ 자동화 설정 (3단계)

- [ ] Windows 작업 스케줄러 등록 (매일 08:00)
  ```powershell
  # 관리자 PowerShell에서 실행
  $action  = New-ScheduledTaskAction -Execute "python" `
               -Argument "C:\Users\naqmi\pf-daily-mail\main.py" `
               -WorkingDirectory "C:\Users\naqmi\pf-daily-mail"
  $trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
  Register-ScheduledTask -TaskName "PF-Daily-Report" `
    -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
  ```
- [ ] 또는 GitHub Actions 설정 (`.github/workflows/daily_report.yml` — README에 템플릿 있음)

### 🎨 HTML 디자인 고도화 (4단계, 선택)

- [ ] 섹션별 미니 차트 (pyecharts 또는 Chart.js inline SVG)
- [ ] 금리 추이 스파크라인 (최근 5일 데이터 저장 후 시각화)
- [ ] 모바일 최적화 (현재 max-width 720px)

---

## 5. 실행 방법

### 사전 준비

```bash
# 1. 의존성 설치
pip install -r requirements.txt
# 또는
python -m pip install -r requirements.txt

# 2. .env 파일 생성
copy .env.example .env
# .env 파일을 열어 API 키 입력
```

### 실행 명령어

```bash
# API 키 없어도 동작 (금리/뉴스 N/A로 표시, 수동 CSV는 항상 표시됨)
python main.py --no-send

# 전체 파이프라인 (이메일 발송 포함)
python main.py

# HTML만 재생성 (데이터 수집 생략)
python main.py --only-report

# 개별 스크립트 실행
python scripts/collect_data.py    # → data/latest_report.json 생성
python scripts/generate_report.py # → reports/YYYY-MM-DD_report.html 생성
python scripts/send_email.py      # → 이메일 발송
```

### 실행 결과 확인

```
pf-daily-mail/
├── data/latest_report.json          ← 수집 데이터 (JSON 직접 열어서 확인 가능)
└── reports/2026-06-16_report.html   ← 브라우저로 열어서 디자인 확인
```

---

## 6. 코드 핵심 구조

### collect_data.py — 데이터 수집 흐름

```
collect_all()
  ├── collect_funding_market()    # ECOS API → 금리 7종
  ├── collect_usd_krw()           # ECOS → Naver 스크래핑 fallback
  ├── collect_market_indices()    # pykrx → KOSPI/KOSDAQ/KRX건설
  ├── collect_stock_prices()      # pykrx → 건설사 7종 주가
  ├── collect_pf_news()           # Naver → PF 키워드 뉴스
  ├── collect_company_news()      # Naver → 건설사별 뉴스
  ├── load_credit_ratings()       # CSV → 신용등급
  └── load_pf_rates()             # CSV → PF 금리
```

**모든 함수가 try/except 처리 → API 실패해도 N/A로 계속 진행됨**

### generate_report.py — HTML 생성 흐름

```
generate_report(data)
  └── build_html(data)
        ├── html_header(data)
        ├── html_exec_summary(data)   # build_exec_summary() 호출
        ├── html_market(data)
        ├── html_funding(data)
        ├── html_pf_news(data)
        ├── html_company_watch(data)
        └── html_footer(data)
```

**badge('auto') / badge('manual') / badge('auto_derived')** — 데이터 타입 시각적 구분

### send_email.py — SMTP 흐름

```
send_report(html_path)
  └── SMTP(gmail.com:587) → TLS → login → sendmail
```

---

## 7. 데이터 소스 상세

### ECOS API 통계코드 (요주의)

| 변수명 | stat_code | item_code | 표시명 |
|--------|-----------|-----------|--------|
| base_rate | 722Y001 | 0101000 | 기준금리 |
| cd_91 | 817Y002 | 010190000 | CD 91일 |
| cp_91 | 817Y002 | 010200000 | CP 91일 |
| gov_3y | 817Y002 | 010300000 | 국고채 3Y |
| gov_10y | 817Y002 | 010320000 | 국고채 10Y |
| corp_aa_3y | 817Y002 | 010400000 | 회사채 3Y AA- |
| usd_krw | 731Y001 | 0000001 | USD/KRW |

코드 위치: `scripts/collect_data.py` → `ECOS_ITEMS` 딕셔너리 (31~38번째 줄)

### pykrx 종목코드

| 회사 | 코드 | 상장 |
|------|------|------|
| DL이앤씨 | 375500 | ✅ |
| 현대건설 | 000720 | ✅ |
| GS건설 | 006360 | ✅ |
| 대우건설 | 047040 | ✅ |
| HDC현대산업개발 | 294870 | ✅ |
| 포스코이앤씨 | 047050 | ✅ |
| 태영건설 | 009410 | ✅ |
| 롯데건설 | — | ❌ 비상장 |
| SK에코플랜트 | — | ❌ 비상장 |

---

## 8. 알려진 이슈 및 주의사항

### 이슈 1: Python 경로 문제 (세션 내 미해결)
- 이 Claude 세션에서 `pip` / `python` 명령어가 PowerShell에서 실행되지 않음
- **해결**: 터미널을 직접 열어 `python main.py --no-send` 실행
- 또는 Claude 채팅창에서 `! python main.py --no-send` 입력

### 이슈 2: pykrx 첫 실행 지연
- pykrx는 첫 실행 시 KRX 데이터를 다운로드하여 캐시 → 수분 소요 가능

### 이슈 3: KRX 건설업 지수 ticker 불확실
- 코드에 `"1028"` 사용 중 (KOSPI 건설업)
- 실제 ticker가 다를 경우 `"KRX건설"` 항목이 `N/A`로 표시됨
- 확인 방법:
  ```python
  from pykrx import stock
  for t in stock.get_index_ticker_list(market="KOSPI"):
      if "건설" in stock.get_index_ticker_name(t):
          print(t, stock.get_index_ticker_name(t))
  ```

### 이슈 4: Naver 스크래핑 불안정
- Naver 뉴스 HTML 구조가 변경되면 스크래핑 실패
- Naver Developer API 키 발급 권장 (안정적, 무료)
- API 없이도 리포트 생성됨 (뉴스 섹션만 빈 상태)

---

## 9. 다음 작업 우선순위 (내일 할 일)

### Step 1 — 즉시 실행 (30분)
```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. .env 생성 (API 키 없어도 일단 실행 가능)
copy .env.example .env

# 3. 첫 실행 (이메일 없이)
python main.py --no-send

# 4. 생성된 HTML 브라우저로 확인
start reports\2026-06-16_report.html
```

### Step 2 — API 키 설정 (1시간)
- ECOS API 키 발급 → `.env` 입력 → 재실행
- Naver API 키 발급 → `.env` 입력 → 재실행
- 금리/환율/뉴스 데이터가 실제값으로 채워지는지 확인

### Step 3 — 오류 수정
- `data/latest_report.json` 열어서 수집된 데이터 확인
- N/A 항목이 있으면 해당 API 코드 확인 및 수정
- KRX건설 ticker 수정 필요시 `collect_data.py` 수정

### Step 4 — 이메일 테스트
```bash
python main.py   # .env에 EMAIL_* 입력 후
```

### Step 5 — 자동화 (최종)
- Windows 작업 스케줄러 또는 GitHub Actions 등록

---

## 10. 세션 히스토리 요약

**2026-06-15 세션에서 한 일:**
1. 프로젝트 설계 (데이터소스 전략, 리포트 구성, 파일구조 확정)
2. 디렉터리 구조 생성 (`pf-daily-mail/` 하위 4개 디렉터리)
3. 9개 파일 전체 작성 완료
4. Python 실행 테스트는 PATH 문제로 미완료 → **내일 첫 작업**

**작성된 코드 규모:**
- `collect_data.py`: 약 240줄, 6개 수집 함수
- `generate_report.py`: 약 270줄, 7개 HTML 섹션 함수
- `send_email.py`: 약 60줄
- `main.py`: 약 45줄

---

*이 파일은 2026-06-15 작업 종료 시점 기준입니다.*
