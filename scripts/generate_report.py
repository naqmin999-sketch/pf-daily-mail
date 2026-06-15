"""
PF Daily Market Intelligence — HTML 리포트 생성기
data/latest_report.json 를 읽어 reports/YYYY-MM-DD_report.html 을 생성합니다.
"""
import json
import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"


# ─── 헬퍼 함수 ────────────────────────────────────────────────────

def badge(dtype):
    cfg = {
        "auto":         ("AUTO",   "#059669", "#d1fae5"),
        "auto_derived": ("계산",   "#7c3aed", "#ede9fe"),
        "manual":       ("MANUAL", "#d97706", "#fef3c7"),
    }
    lbl, fg, bg = cfg.get(dtype, ("?", "#6b7280", "#f3f4f6"))
    return (f'<span style="display:inline-block;padding:1px 6px;border-radius:3px;'
            f'font-size:10px;font-weight:700;color:{fg};background:{bg};">{lbl}</span>')


def chg_html(chg, pct, is_int=False):
    if chg is None:
        return '<span style="color:#9ca3af;">—</span>'
    if chg == 0:
        return '<span style="color:#6b7280;">-</span>'
    sym = "▲" if chg > 0 else "▼"
    clr = "#059669" if chg > 0 else "#dc2626"
    abs_s = f"{abs(chg):,}" if is_int else f"{abs(chg):.2f}"
    pct_s = f"({abs(pct):.1f}%)" if pct is not None else ""
    return f'<span style="color:{clr};">{sym} {abs_s} {pct_s}</span>'


def rating_color(r):
    if not r:
        return "#6b7280"
    if r.startswith(("AAA", "AA")):
        return "#059669"
    if r.startswith("A"):
        return "#2563eb"
    if r.startswith("BBB"):
        return "#d97706"
    return "#dc2626"


# ─── Executive Summary 데이터 빌드 ────────────────────────────────

def build_exec_summary(data):
    points = []

    kospi = data["market"].get("KOSPI", {})
    kosdaq = data["market"].get("KOSDAQ", {})
    if kospi.get("value"):
        pct = kospi.get("change_pct") or 0
        sym = "▲" if pct > 0 else "▼"
        kd  = f" / KOSDAQ {kosdaq['value']:,.2f}" if kosdaq.get("value") else ""
        points.append(f"KOSPI {kospi['value']:,.2f} ({sym}{abs(pct):.1f}%){kd}")

    fx = data["market"].get("USD_KRW", {})
    if fx.get("value"):
        points.append(f"USD/KRW {fx['value']:,.1f}원")

    base = data["funding"].get("base_rate", {})
    corp = data["funding"].get("corp_aa_3y", {})
    sp   = data["funding"].get("aa_spread", {})
    if base.get("value"):
        corp_s = f" / 회사채 3Y AA- {corp['value']:.2f}%" if corp.get("value") else ""
        sp_s   = f" / AA- 스프레드 {sp['value']:+.3f}%p" if sp.get("value") else ""
        points.append(f"기준금리 {base['value']:.2f}%{corp_s}{sp_s}")

    n = len(data.get("pf_news", []))
    if n:
        points.append(f"오늘 PF/건설 뉴스 {n}건 수집 — Section ④ 참고")

    neg = [co for co, info in data.get("company_watch", {}).items()
           if (info.get("stock") or {}).get("change_pct") and info["stock"]["change_pct"] < -2]
    if neg:
        points.append(f"건설주 2% 이상 급락: {', '.join(neg[:3])}")

    # PF 조달 영향 분석
    impacts = []
    sp_val = sp.get("value")
    fx_val = fx.get("value")
    if sp_val:
        if sp_val > 1.5:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p 확대 → PF 조달비용 상승 압력")
        elif sp_val > 1.0:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p 정상 범위")
        else:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p 축소 → 조달여건 개선")
    if fx_val and fx_val > 1400:
        impacts.append(f"고환율 {fx_val:,.0f}원 → 외화 조달 부담")
    impact_str = " / ".join(impacts) if impacts else "데이터 수집 중 — 수동 확인 필요"

    # 주의 건설사
    watch = []
    for co, info in data.get("company_watch", {}).items():
        rt = info.get("credit", {}).get("rating", "")
        ot = info.get("credit", {}).get("outlook", "")
        if rt and (rt.startswith("BB") or "부정적" in ot):
            watch.append(f"{co} ({rt}, {ot})")
    watch_str = " / ".join(watch) if watch else "특이 이슈 없음 (manual_data 기준)"

    return {"points": points[:5], "impact": impact_str, "watch": watch_str}


# ─── HTML 섹션 생성 ───────────────────────────────────────────────

S = 'style="background:#fff;padding:22px 28px;border-bottom:2px solid #f1f5f9;"'
H2 = 'style="margin:0 0 14px;color:#0f2744;font-size:14px;font-weight:700;"'


def html_header(data):
    return f"""
<tr><td style="background:linear-gradient(135deg,#0f2744 0%,#1e4080 100%);padding:22px 28px;border-radius:8px 8px 0 0;">
  <div style="font-size:18px;font-weight:800;color:#fff;">&#128202; PF Daily Market Intelligence</div>
  <div style="font-size:12px;color:#93c5fd;margin-top:5px;">
    국내 건설사 금융팀 일일 시황 브리핑 &nbsp;&#183;&nbsp;
    <b style="color:#fff;">{data['report_date']}</b> &nbsp;&#183;&nbsp; 수집 {data['collected_at']}
  </div>
</td></tr>"""


def html_exec_summary(data):
    es = build_exec_summary(data)
    bullets = "".join(f"<li style='margin-bottom:5px;'>{p}</li>" for p in es["points"]) \
              or "<li>데이터 수집 중</li>"
    return f"""
<tr><td {S}>
  <div {H2}>&#9312; EXECUTIVE SUMMARY</div>
  <div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:12px 16px;margin-bottom:12px;border-radius:0 6px 6px 0;">
    <ul style="margin:0;padding-left:18px;color:#1e293b;font-size:13px;line-height:1.9;">{bullets}</ul>
  </div>
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="width:50%;padding-right:8px;vertical-align:top;">
      <div style="background:#eff6ff;border-radius:6px;padding:11px 14px;">
        <div style="font-size:11px;font-weight:700;color:#1d4ed8;margin-bottom:5px;">&#128161; PF 조달시장 영향</div>
        <div style="font-size:12px;color:#374151;line-height:1.65;">{es['impact']}</div>
      </div>
    </td>
    <td style="width:50%;padding-left:8px;vertical-align:top;">
      <div style="background:#fff7ed;border-radius:6px;padding:11px 14px;">
        <div style="font-size:11px;font-weight:700;color:#c2410c;margin-bottom:5px;">&#9888; 주의할 건설사/이슈</div>
        <div style="font-size:12px;color:#374151;line-height:1.65;">{es['watch']}</div>
      </div>
    </td>
  </tr></table>
</td></tr>"""


def _kpi_card(label, item):
    val   = item.get("value")
    is_fx       = "KRW" in label
    is_cons_avg = "건설" in label  # 건설사 평균등락 → % 표시
    if val is None:
        val_s = "N/A"
    elif is_cons_avg:
        val_s = f"{val:+.2f}%"   # 건설사 평균등락률
    elif is_fx:
        val_s = f"{val:,.1f}"
    else:
        val_s = f"{val:,.2f}"
    chg_s = chg_html(item.get("change"), item.get("change_pct"))
    clr   = "#9ca3af" if val is None else "#0f2744"
    err   = item.get("error", "")
    note  = item.get("note", "")
    sub   = note[:30] if note else (err[:35] if err else "")
    sub_color = "#9ca3af" if note else "#ef4444"
    return f"""
<td style="width:25%;padding:6px;">
  <div style="border:1px solid #e2e8f0;border-radius:8px;padding:14px 10px;text-align:center;background:#fafafa;">
    <div style="font-size:11px;color:#6b7280;font-weight:600;margin-bottom:4px;">{label}</div>
    <div style="font-size:19px;font-weight:800;color:{clr};margin-bottom:3px;">{val_s}</div>
    <div style="font-size:12px;">{chg_s if not is_cons_avg else ""}</div>
    <div style="margin-top:6px;">{badge(item.get('type','auto'))}</div>
    {"<div style='font-size:10px;color:"+sub_color+";margin-top:3px;'>"+sub+"</div>" if sub else ""}
  </div>
</td>"""


def html_market(data):
    m = data.get("market", {})
    cards = (
        _kpi_card("KOSPI",    m.get("KOSPI",   {})) +
        _kpi_card("KOSDAQ",   m.get("KOSDAQ",  {})) +
        _kpi_card("KRX 건설", m.get("KRX건설", {})) +
        _kpi_card("USD/KRW",  m.get("USD_KRW", {}))
    )
    return f"""
<tr><td {S}>
  <div {H2}>&#9313; 국내 시장 동향</div>
  <table width="100%" cellpadding="0" cellspacing="0"><tr>{cards}</tr></table>
  <div style="font-size:10px;color:#9ca3af;margin-top:8px;">출처: KRX/pykrx &nbsp;&#183;&nbsp; 전일 종가 기준</div>
</td></tr>"""


def _rate_row(label, item, highlight=False):
    val   = item.get("value")
    val_s = f"{val:.2f}%" if val is not None else '<span style="color:#9ca3af;">N/A</span>'
    date_s = item.get("date", "")
    err   = item.get("error", "")
    bg    = "#fefce8" if highlight else "transparent"
    err_html = f'<span style="color:#ef4444;font-size:10px;">&nbsp;{err[:35]}</span>' if err else ""
    return f"""
<tr style="background:{bg};">
  <td style="padding:7px 10px;font-size:12px;color:#374151;border-bottom:1px solid #f1f5f9;">{label}</td>
  <td style="padding:7px 10px;font-size:14px;font-weight:700;color:#0f2744;text-align:right;border-bottom:1px solid #f1f5f9;">{val_s}</td>
  <td style="padding:7px 10px;font-size:10px;color:#9ca3af;text-align:right;border-bottom:1px solid #f1f5f9;">{badge(item.get('type','auto'))} {date_s}{err_html}</td>
</tr>"""


def html_funding(data):
    fd = data.get("funding", {})
    pf = data.get("pf_rates", [])

    rate_rows = (
        _rate_row("기준금리",      fd.get("base_rate",  {})) +
        _rate_row("CD 91일",       fd.get("cd_91",      {})) +
        _rate_row("CP 91일",       fd.get("cp_91",      {})) +
        _rate_row("국고채 3Y",     fd.get("gov_3y",     {})) +
        _rate_row("국고채 10Y",    fd.get("gov_10y",    {})) +
        _rate_row("회사채 3Y AA-", fd.get("corp_aa_3y", {}), highlight=True) +
        _rate_row("AA- 스프레드",  fd.get("aa_spread",  {}), highlight=True)
    )

    pf_rows = ""
    for r in pf:
        rp = r.get("rate_pct", "")
        rs = f"{float(rp):.2f}%" if rp else "N/A"
        pf_rows += f"""
<tr>
  <td style="padding:6px 8px;font-size:11px;color:#374151;border-bottom:1px solid #fde68a;">
    {r.get('category','')} <span style="color:#9ca3af;">{r.get('subcategory','')}</span>
  </td>
  <td style="padding:6px 8px;font-size:13px;font-weight:700;color:#d97706;text-align:right;border-bottom:1px solid #fde68a;">{rs}</td>
</tr>"""

    manual_date = pf[0].get("as_of_date", "") if pf else "—"

    return f"""
<tr><td {S}>
  <div {H2}>&#9314; Funding Market</div>
  <table width="100%" cellpadding="0" cellspacing="0"><tr style="vertical-align:top;">
    <td style="width:58%;padding-right:14px;">
      <div style="font-size:11px;font-weight:700;color:#64748b;margin-bottom:6px;">
        채권시장 금리 &nbsp; {badge('auto')} AUTO: 한국은행 ECOS
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
        {rate_rows}
      </table>
    </td>
    <td style="width:42%;">
      <div style="font-size:11px;font-weight:700;color:#64748b;margin-bottom:6px;">
        PF 시장금리 &nbsp; {badge('manual')} MANUAL 기준일: {manual_date}
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid #fde68a;border-radius:6px;overflow:hidden;background:#fffbeb;">
        {pf_rows if pf_rows else '<tr><td style="padding:10px;font-size:12px;color:#9ca3af;">manual_data/pf_rates.csv 업데이트 필요</td></tr>'}
      </table>
      <div style="font-size:10px;color:#9ca3af;margin-top:6px;">* PF 금리는 수동입력 — 매주 갱신 권장</div>
    </td>
  </tr></table>
</td></tr>"""


def html_pf_news(data):
    news = data.get("pf_news", [])
    if not news:
        body = '<div style="color:#9ca3af;font-size:13px;padding:8px 0;">수집된 뉴스 없음 — Naver API 키 설정 또는 스크래핑 결과 확인 필요</div>'
    else:
        items = []
        for art in news:
            link  = art.get("link", "#")
            title = art.get("title", "")
            press = art.get("press", "")
            kw    = art.get("keyword", "")
            date  = art.get("pub_date", "")
            desc  = art.get("desc", "")
            items.append(f"""
<div style="border:1px solid #e2e8f0;border-radius:6px;padding:10px 14px;margin-bottom:7px;background:#fafafa;">
  <div style="font-size:11px;color:#6b7280;margin-bottom:4px;">
    <span style="background:#dbeafe;color:#1e40af;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;">{kw}</span>
    &nbsp; <span style="color:#9ca3af;">{press} &nbsp;&#183;&nbsp; {date}</span>
  </div>
  <a href="{link}" style="font-size:13px;font-weight:600;color:#0f2744;text-decoration:none;">{title}</a>
  {"<div style='font-size:11px;color:#6b7280;margin-top:3px;'>"+desc+"</div>" if desc else ""}
</div>""")
        body = "".join(items)

    return f"""
<tr><td {S}>
  <div {H2}>&#9315; PF Market 뉴스 &nbsp; {badge('auto')} AUTO: 네이버 뉴스</div>
  {body}
</td></tr>"""


def html_company_watch(data):
    watch = data.get("company_watch", {})
    rows = ""
    for co, info in watch.items():
        stk  = info.get("stock", {})
        crd  = info.get("credit", {})
        news = info.get("news", [])

        val   = stk.get("value")
        if stk.get("source") == "비상장":
            val_s = '<span style="color:#9ca3af;">비상장</span>'
            chg_s = "—"
        else:
            val_s = f"{val:,}" if val else '<span style="color:#9ca3af;">N/A</span>'
            chg_s = chg_html(stk.get("change"), stk.get("change_pct"), is_int=True)

        rt   = crd.get("rating", "")
        ot   = crd.get("outlook", "")
        rc   = rating_color(rt)
        rt_s = f'<span style="font-weight:800;color:{rc};">{rt or "—"}</span> <span style="font-size:10px;color:#6b7280;">{ot}</span>'

        news_s = ""
        if news:
            a = news[0]
            t = a.get("title", "")[:44]
            news_s = f'<a href="{a.get("link","#")}" style="font-size:11px;color:#2563eb;text-decoration:none;">{t}...</a>'

        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9;">
  <td style="padding:8px 10px;font-size:12px;font-weight:600;color:#0f2744;white-space:nowrap;">{co}</td>
  <td style="padding:8px 10px;font-size:13px;font-weight:700;color:#0f2744;text-align:right;">{val_s}</td>
  <td style="padding:8px 10px;font-size:12px;text-align:right;">{chg_s}</td>
  <td style="padding:8px 10px;text-align:center;">{rt_s}</td>
  <td style="padding:8px 10px;">{news_s}</td>
</tr>"""

    return f"""
<tr><td {S}>
  <div {H2}>&#9316; Construction / Company Watch</div>
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
    <tr style="background:#f8fafc;">
      <th style="padding:8px 10px;font-size:11px;color:#6b7280;text-align:left;font-weight:600;">건설사</th>
      <th style="padding:8px 10px;font-size:11px;color:#6b7280;text-align:right;font-weight:600;">주가(원) {badge('auto')}</th>
      <th style="padding:8px 10px;font-size:11px;color:#6b7280;text-align:right;font-weight:600;">등락</th>
      <th style="padding:8px 10px;font-size:11px;color:#6b7280;text-align:center;font-weight:600;">신용등급 {badge('manual')}</th>
      <th style="padding:8px 10px;font-size:11px;color:#6b7280;text-align:left;font-weight:600;">최신 뉴스 {badge('auto')}</th>
    </tr>
    {rows}
  </table>
  <div style="font-size:10px;color:#9ca3af;margin-top:8px;">
    주가: KRX/pykrx 전일 기준 &nbsp;&#183;&nbsp; 신용등급: manual_data/credit_ratings.csv (수동 업데이트)
  </div>
</td></tr>"""


def html_footer(data):
    return f"""
<tr><td style="background:#1e293b;padding:14px 28px;border-radius:0 0 8px 8px;text-align:center;">
  <div style="font-size:11px;color:#94a3b8;line-height:1.8;">
    본 리포트는 자동 생성된 내부 참고자료입니다 &nbsp;&#183;&nbsp; 최종 판단은 담당자 확인 필수<br>
    {badge('auto')} 자동수집 &nbsp; {badge('auto_derived')} 계산값 &nbsp; {badge('manual')} 수동입력<br>
    <span style="color:#475569;">생성: {data['collected_at']} &nbsp;&#183;&nbsp; pf-daily-mail v1.0 MVP</span>
  </div>
</td></tr>"""


# ─── HTML 조립 ────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; }
body { margin:0; padding:0; background:#f0f4f8;
       font-family: 'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',Arial,sans-serif; }
a:hover { text-decoration: underline !important; }
table { border-collapse: collapse; }
"""


def build_html(data):
    body = (
        html_header(data) +
        html_exec_summary(data) +
        html_market(data) +
        html_funding(data) +
        html_pf_news(data) +
        html_company_watch(data) +
        html_footer(data)
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"ko\">\n<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">\n"
        f"<title>PF Daily Market Intelligence — {data['report_date']}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n"
        "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f0f4f8;padding:20px 0;\">\n"
        "  <tr><td align=\"center\">\n"
        "    <table width=\"720\" cellpadding=\"0\" cellspacing=\"0\"\n"
        "           style=\"max-width:720px;box-shadow:0 2px 12px rgba(0,0,0,.09);border-radius:8px;\">\n"
        + body +
        "    </table>\n"
        "  </td></tr>\n"
        "</table>\n</body>\n</html>"
    )


# ─── 메인 ─────────────────────────────────────────────────────────

def generate_report(data=None):
    if data is None:
        src = DATA_DIR / "latest_report.json"
        if not src.exists():
            raise FileNotFoundError(f"데이터 파일 없음: {src}\n먼저 collect_data.py 를 실행하세요.")
        with open(src, encoding="utf-8") as f:
            data = json.load(f)

    REPORT_DIR.mkdir(exist_ok=True)
    out  = REPORT_DIR / f"{data['report_date']}_report.html"
    html = build_html(data)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  → 리포트 생성 완료: {out}")
    return out


if __name__ == "__main__":
    generate_report()
