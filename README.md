# PF Daily Market Intelligence

국내 건설사 금융팀을 위한 일일 PF 시황 HTML 이메일 리포트 자동 생성/발송 시스템.

## 파일 구조

```
pf-daily-mail/
├── main.py                      # 실행 진입점 (수집 → 생성 → 발송)
├── requirements.txt
├── .env.example                 # 환경변수 템플릿
├── scripts/
│   ├── collect_data.py          # 데이터 수집 (ECOS, pykrx, Naver)
│   ├── generate_report.py       # HTML 리포트 생성
│   └── send_email.py            # SMTP 이메일 발송
├── data/
│   └── latest_report.json       # 최신 수집 결과 (자동 생성)
├── reports/
│   └── YYYY-MM-DD_report.html   # 일별 리포트 (자동 생성)
└── manual_data/
    ├── credit_ratings.csv        # 건설사 신용등급 (수동 관리)
    └── pf_rates.csv              # PF 시장금리 (수동 관리)
```

## 데이터 소스 구분

| 구분 | 항목 | 소스 | 표시 |
|------|------|------|------|
| 자동 | 기준금리, CD/CP, 국고채, 회사채 AA- | 한국은행 ECOS API | `[AUTO]` |
| 자동 | KOSPI, KOSDAQ, KRX건설, 건설사 주가 | KRX/pykrx | `[AUTO]` |
| 자동 | USD/KRW | ECOS → Naver 스크래핑 fallback | `[AUTO]` |
| 자동 | PF/건설 뉴스 | Naver 뉴스 API → 스크래핑 fallback | `[AUTO]` |
| 자동계산 | AA- 스프레드 | 회사채 - 국고채 | `[계산]` |
| 수동 | 신용등급, 전망 | manual_data/credit_ratings.csv | `[MANUAL]` |
| 수동 | PF ABCP/ABSTB/브릿지론 금리 | manual_data/pf_rates.csv | `[MANUAL]` |

## 설치

```bash
cd pf-daily-mail
pip install -r requirements.txt
```

## 설정

```bash
# .env.example 을 복사하여 실제 값 입력
copy .env.example .env
```

`.env` 필수 항목:

```env
# 한국은행 ECOS API 키 (무료)
# 발급: https://ecos.bok.or.kr/api/
ECOS_API_KEY=your_key_here

# 네이버 개발자 API (뉴스 검색, 무료)
# 발급: https://developers.naver.com/
NAVER_CLIENT_ID=your_id
NAVER_CLIENT_SECRET=your_secret

# 이메일 발송 (Gmail 앱 비밀번호)
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENTS=team@company.com
```

> **Gmail 앱 비밀번호**: Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호

## 실행

```bash
# 전체 파이프라인 (수집 → HTML 생성 → 이메일 발송)
python main.py

# 이메일 발송 없이 리포트만 생성 (테스트용)
python main.py --no-send

# 기존 수집 데이터로 HTML만 재생성
python main.py --only-report

# 개별 실행
python scripts/collect_data.py
python scripts/generate_report.py
python scripts/send_email.py
```

생성된 리포트: `reports/YYYY-MM-DD_report.html` (브라우저로 바로 열 수 있음)

## 수동 데이터 관리

### 신용등급 (`manual_data/credit_ratings.csv`)

```csv
company,ticker,listed,rating,rating_date,outlook,rater,note
태영건설,009410,TRUE,BB,2026-06-01,부정적,한국기업평가,워크아웃 진행
```

- `rating_date`: 등급 발표일 (분기마다 확인 권장)
- `outlook`: 안정적 / 긍정적 / 부정적 / 크레딧워치 긍정 / 크레딧워치 부정

### PF 금리 (`manual_data/pf_rates.csv`)

```csv
category,subcategory,rate_pct,as_of_date,source,note
PF ABCP,우량사업장,4.50,2026-06-01,수기입력,금투협 채권정보센터 참고
```

- 매주 1회 시장 체크 후 업데이트 권장
- 금융투자협회 채권정보센터 (kofiabond.or.kr) 참고

## 자동화 설정

### Windows 작업 스케줄러 (매일 08:00 실행)

관리자 권한 PowerShell에서:

```powershell
$action  = New-ScheduledTaskAction -Execute "python" `
             -Argument "C:\Users\naqmi\pf-daily-mail\main.py" `
             -WorkingDirectory "C:\Users\naqmi\pf-daily-mail"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "PF-Daily-Report" `
  -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
```

### GitHub Actions (`.github/workflows/daily_report.yml`)

```yaml
name: PF Daily Report
on:
  schedule:
    - cron: '0 23 * * 0-4'  # UTC 23:00 = KST 08:00 (평일)
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          ECOS_API_KEY: ${{ secrets.ECOS_API_KEY }}
          NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          EMAIL_SENDER: ${{ secrets.EMAIL_SENDER }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          EMAIL_RECIPIENTS: ${{ secrets.EMAIL_RECIPIENTS }}
```

## 개발 로드맵

- **1단계 (MVP)**: ECOS + pykrx + Naver + manual CSV → HTML 리포트 ✅
- **2단계**: HTML 디자인 고도화, 섹션별 차트 추가
- **3단계**: SMTP 발송 안정화, 발송 이력 로깅
- **4단계**: Windows 스케줄러 또는 GitHub Actions 자동화

## 주의사항

- API 키 미설정 시 자동수집 항목은 `N/A`로 표시됨 (리포트 생성은 정상 동작)
- pykrx 미설치 시 주가/지수 항목 `N/A` (ECOS 금리는 독립적으로 동작)
- 장 개장 전(08:00) 실행 시 전일 종가 기준으로 표시됨
- 네이버 스크래핑은 HTML 구조 변경 시 중단될 수 있음 → Naver API 키 권장
