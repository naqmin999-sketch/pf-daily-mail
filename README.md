# PF Daily Market Intelligence

DL이앤씨 금융팀용 일일 PF/조달금융 브리핑 리포트 자동 생성·발송 시스템.  
매일 오전 8시 KST에 GitHub Actions가 데이터를 수집하고 PDF 리포트를 이메일로 발송합니다.

---

## 리포트 구성

| 섹션 | 내용 |
|------|------|
| ① 시황 요약 | A.채권금리 / B.유동화증권(PF·CP금리) / C.가계대출(COFIX) — 3박스 |
| ② 채권금리 추이 | CD91 / 국고채 3Y·10Y / 회사채 AA- 최근 30일 스파크라인 |
| ③ 부동산 금융시장 동향 | PF/조달 뉴스 5건 + 부동산 정책 뉴스 5건 |
| ④ Deal Watch | 도시정비·PF·브릿지론 조달 사례 (수동 입력) |
| ⑤ 신용등급 현황 | 건설사 9개사 등급·전망 |

---

## 파일 구조

```
pf-daily-mail/
├── main.py                       # 실행 진입점
├── requirements.txt
├── run_daily.bat                 # 로컬 Windows 수동 실행용
├── .env                          # API키·이메일 설정 (Git 제외)
├── .github/
│   └── workflows/
│       └── daily-report.yml     # GitHub Actions 자동화
├── scripts/
│   ├── collect_data.py           # 데이터 수집 (ECOS, Naver)
│   ├── generate_report.py        # HTML 리포트 생성
│   ├── generate_pdf.py           # HTML → PDF 변환 (Playwright)
│   ├── send_email.py             # SMTP 이메일 발송
│   └── diagnose_sources.py       # 데이터 소스 연결 진단
├── manual_data/
│   ├── credit_ratings.csv        # 건설사 신용등급 (수동 관리)
│   ├── pf_rates.csv              # PF 시장금리 (수동 관리)
│   ├── cp_rates.csv              # CP 등급별 금리 (수동 관리)
│   ├── cofix.csv                 # COFIX 월별 (수동 관리)
│   └── deal_watch.csv            # 조달 사례 Watch (수동 관리)
├── data/                         # 자동 생성 (Git 제외)
└── reports/                      # 자동 생성 (Git 제외)
```

---

## 데이터 소스

| 배지 | 항목 | 소스 |
|------|------|------|
| `AUTO` | 기준금리, CD/CP 91일, 국고채 3Y/10Y, 회사채 AA- | 한국은행 ECOS API |
| `AUTO` | 회사채 A+/A0/A- (item_code 미확인 → N/A 가능) | 한국은행 ECOS API |
| `AUTO` | USD/KRW | ECOS → FDR/Yahoo → Naver 순차 fallback |
| `AUTO` | PF/조달 뉴스 5건, 부동산 정책 뉴스 5건 | Naver 뉴스 API |
| `AUTO` | COFIX (자동수집 시도) | 은행연합회 공시 크롤링 → 실패 시 CSV fallback |
| `계산` | AA- 스프레드, A- 스프레드 | 회사채 − 국고채 3Y |
| `MANUAL` | CP 등급별 금리 | manual_data/cp_rates.csv |
| `MANUAL` | COFIX fallback | manual_data/cofix.csv |
| `MANUAL` | PF 시장금리 | manual_data/pf_rates.csv |
| `MANUAL` | Deal Watch | manual_data/deal_watch.csv |
| `MANUAL` | 신용등급 | manual_data/credit_ratings.csv |

---

## 로컬 설치 및 실행

```bash
pip install -r requirements.txt
playwright install chromium
```

`.env` 파일 생성 (`.env` 는 Git에 포함되지 않습니다):

```env
ECOS_API_KEY=your_key
NAVER_CLIENT_ID=your_id
NAVER_CLIENT_SECRET=your_secret
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENTS=team@company.com,other@company.com
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

```bash
# 데이터 소스 연결 진단 (발송 없음, API 키/CSV/파일 상태 점검)
python main.py --diagnose

# 테스트 (이메일 발송 없이 HTML/PDF 생성)
python main.py --no-send

# 전체 실행 (수집 → HTML → PDF → 발송)
python main.py

# 기존 데이터로 HTML/PDF만 재생성
python main.py --only-report
```

---

## GitHub Actions 자동화

### 동작 방식

```
매일 UTC 23:00 (= KST 08:00)
  → GitHub Actions 실행
  → 데이터 수집 (ECOS, Naver)
  → HTML 생성
  → PDF 변환 (Playwright Chromium)
  → 이메일 발송 (PDF 첨부)
  → 완료
```

수동 실행: GitHub 저장소 → Actions 탭 → `PF Daily Market Intelligence` → `Run workflow`

`mode` 입력 옵션:
- `send` (기본값): 전체 파이프라인 실행 (수집 → HTML → PDF → 발송)
- `diagnose`: 데이터 소스 연결 진단만 실행 (발송 없음 — Actions 로그에서 결과 확인)

### GitHub Secrets 설정

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 내용 | 필수 |
|-------------|------|------|
| `ECOS_API_KEY` | 한국은행 ECOS API 키 | ✅ |
| `NAVER_CLIENT_ID` | Naver 개발자 Client ID | ✅ |
| `NAVER_CLIENT_SECRET` | Naver 개발자 Secret | ✅ |
| `EMAIL_SENDER` | 발신자 Gmail 주소 | ✅ |
| `EMAIL_PASSWORD` | Gmail 앱 비밀번호 (16자리) | ✅ |
| `EMAIL_RECIPIENTS` | 수신자 목록 (쉼표 구분) | ✅ |
| `EMAIL_SMTP_HOST` | SMTP 서버 (기본: smtp.gmail.com) | ✅ |
| `EMAIL_SMTP_PORT` | SMTP 포트 (기본: 587) | ✅ |
| `DATA_GO_KR_API_KEY` | 공공데이터포털 API 키 (향후 사용) | — |

> **Gmail 앱 비밀번호 발급**: Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호

---

## 수동 데이터 관리

수동 CSV 파일은 정기적으로 직접 업데이트합니다.

### `manual_data/cp_rates.csv`
CP 등급별 3개월/1년 금리. 주 1회 업데이트 권장.

### `manual_data/cofix.csv`
COFIX 신규취급액·잔액·신잔액 기준. 은행연합회 공시 기준 월 1회 업데이트.

### `manual_data/pf_rates.csv`
PF ABCP/ABSTB/브릿지론/본PF 시장금리. 금융투자협회 채권정보센터 참고.

### `manual_data/deal_watch.csv`
당사/타사 도시정비·PF·브릿지론 조달 사례.  
컬럼: `type / party / borrower / guarantee_type / rate_pct / maturity / project_name / amount_bn / remark / as_of_date`

### `manual_data/credit_ratings.csv`
건설사 9개사 신용등급. 분기 1회 확인 업데이트 권장.

---

## ECOS item_code 확인 (A+/A0/A- 코드 미확인 시)

```bash
python -c "from scripts.collect_data import discover_ecos_items; discover_ecos_items()"
```

출력된 코드를 `scripts/collect_data.py`의 `ECOS_ITEMS` 딕셔너리에 업데이트.
