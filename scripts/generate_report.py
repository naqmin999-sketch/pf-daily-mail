"""
PF Daily Market Intelligence — HTML 리포트 생성기 v2.0
data/latest_report.json → reports/YYYY-MM-DD_report.html
사용 키: bonds, rate_history, cp_rates, cofix, deal_watch,
         pf_news, policy_news, company_credit, usd_krw
"""
import json
import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"


# ─── 헬퍼 ────────────────────────────────────────────────────────

def badge(dtype):
    cfg = {
        "auto":         ("AUTO",   "#059669", "#d1fae5"),
        "auto_derived": ("계산",   "#7c3aed", "#ede9fe"),
        "manual":       ("MANUAL", "#d97706", "#fef3c7"),
        "fallback":     ("FALLBACK","#dc2626","#fee2e2"),
    }
    lbl, fg, bg = cfg.get(dtype, ("?", "#6b7280", "#f3f4f6"))
    return (f'<span style="display:inline-block;padding:1px 6px;border-radius:3px;'
            f'font-size:10px;font-weight:700;color:{fg};background:{bg};">{lbl}</span>')


def chg_color(chg):
    if chg is None:
        return '<span style="color:#e2e8f0;">—</span>'
    try:
        chg = float(chg)
    except (ValueError, TypeError):
        return '<span style="color:#e2e8f0;">—</span>'
    if chg == 0:
        return '<span style="color:#94a3b8;">±0</span>'
    sym = "▲" if chg > 0 else "▼"
    clr = "#dc2626" if chg > 0 else "#16a34a"
    return f'<span style="color:{clr};font-weight:600;">{sym}{abs(chg):.3f}</span>'


def spread_badge(val):
    if val is None:
        return ""
    if val < 0.5:
        lbl, bg, fg = "TIGHT",  "#dcfce7", "#15803d"
    elif val < 1.0:
        lbl, bg, fg = "NORMAL", "#fef9c3", "#854d0e"
    elif val < 1.5:
        lbl, bg, fg = "WIDE",   "#ffedd5", "#c2410c"
    else:
        lbl, bg, fg = "ALERT",  "#fee2e2", "#991b1b"
    return (f'<span style="background:{bg};color:{fg};padding:1px 6px;border-radius:3px;'
            f'font-size:10px;font-weight:700;">{lbl}</span>')


def rating_color(r):
    if not r:
        return "#94a3b8"
    if r.startswith(("AAA", "AA")):
        return "#059669"
    if r.startswith("A"):
        return "#2563eb"
    if r.startswith("BBB"):
        return "#d97706"
    return "#dc2626"


def sec_header(num, title, accent="#1d4ed8"):
    return (
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">'
        f'<span style="background:{accent};color:#fff;border-radius:4px;'
        f'padding:3px 9px;font-size:11px;font-weight:800;flex-shrink:0;">{num}</span>'
        f'<span style="font-size:14px;font-weight:800;color:#0f172a;">{title}</span>'
        f'</div>'
    )


def sub_header(title, color="#475569"):
    return (
        f'<div style="font-size:11px;font-weight:700;color:{color};'
        f'border-left:3px solid {color};padding-left:8px;margin:14px 0 8px;">'
        f'{title}</div>'
    )


def sparkline(history, width=110, height=26, color="#3b82f6"):
    """[(date_str, float), ...] → inline SVG 스파크라인"""
    vals = [v for _, v in history] if history else []
    if len(vals) < 2:
        return (f'<span style="display:inline-block;width:{width}px;'
                f'text-align:center;color:#e2e8f0;font-size:9px;">—</span>')
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 0.01
    W, H = width - 6, height - 6
    pts = " ".join(
        f"{round(i / (len(vals)-1) * W + 3, 1)},{round((1 - (v-mn)/rng) * H + 3, 1)}"
        for i, v in enumerate(vals)
    )
    lx = round(W + 3, 1)
    ly = round((1 - (vals[-1] - mn) / rng) * H + 3, 1)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:inline-block;vertical-align:middle;">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2.5" fill="{color}"/>'
        f'</svg>'
    )


def fmt_date(d):
    d = str(d or "").strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d


SP      = 'style="background:#fff;padding:16px 22px;border-bottom:1px solid #e8edf4;"'
SP_LAST = 'style="background:#fff;padding:16px 22px;"'


# ─── Header ──────────────────────────────────────────────────────

def html_header(data):
    today    = datetime.datetime.strptime(data["report_date"], "%Y-%m-%d")
    kor_date = today.strftime("%Y년 %m월 %d일")
    weekday  = ["월","화","수","목","금","토","일"][today.weekday()]
    usd      = data.get("usd_krw", {})
    usd_val  = f"{usd['value']:,.1f}원" if usd.get("value") else "—"
    return f"""
<tr><td style="background:linear-gradient(135deg,#0f2744 0%,#1e3a8a 100%);
               padding:20px 24px;border-radius:8px 8px 0 0;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-size:18px;font-weight:800;color:#fff;letter-spacing:.3px;">
        PF Daily Market Intelligence
      </div>
      <div style="font-size:11px;color:#93c5fd;margin-top:4px;">
        DL이앤씨 금융팀 · 일일 PF/조달금융 브리핑
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:15px;font-weight:700;color:#fff;">{kor_date} ({weekday})</div>
      <div style="font-size:11px;color:#bfdbfe;margin-top:3px;">
        USD/KRW {usd_val} &nbsp;|&nbsp; 수집 {data['collected_at']}
      </div>
    </div>
  </div>
</td></tr>"""


# ─── Section 1: Executive Summary ────────────────────────────────

def html_exec_summary(data):
    bonds   = data.get("bonds", {})
    base    = bonds.get("base_rate", {})
    gov3    = bonds.get("gov_3y", {})
    corp_aa = bonds.get("corp_aa_3y", {})
    corp_am = bonds.get("corp_aminus_3y", {})
    aa_sp   = bonds.get("aa_spread", {})
    am_sp   = bonds.get("aminus_spread", {})
    cd91    = bonds.get("cd_91", {})
    cofix   = data.get("cofix", [])
    pf_news = data.get("pf_news", [])
    policy  = data.get("policy_news", [])

    points = []

    if base.get("value"):
        points.append(("🏦", f"기준금리 {base['value']:.2f}%"))

    if gov3.get("value") and corp_aa.get("value"):
        sp_val = aa_sp.get("value")
        sp_s   = f" · AA- 스프레드 {sp_val:+.2f}%p" if sp_val is not None else ""
        am_val = corp_am.get("value")
        am_s   = f" / A- {am_val:.2f}%" if am_val else ""
        points.append(("📊",
            f"국고채3Y {gov3['value']:.2f}% · 회사채AA- {corp_aa['value']:.2f}%{am_s}{sp_s}"))
    elif gov3.get("value"):
        points.append(("📊", f"국고채 3Y {gov3['value']:.2f}% (회사채 수집 확인 필요)"))

    if cd91.get("value"):
        points.append(("💹", f"CD 91일 {cd91['value']:.2f}% — 단기조달 기준"))

    sorted_cf = sorted(
        [r for r in cofix if r.get("ym", "").strip()],
        key=lambda r: r.get("ym", ""), reverse=True,
    )
    if sorted_cf:
        cf_rate = sorted_cf[0].get("new_all_rate", "").strip()
        if cf_rate:
            points.append(("🏠",
                f"COFIX 신규취급액 {cf_rate}% ({sorted_cf[0].get('ym','')})"))

    n_pf  = len(pf_news)
    n_pol = len(policy)
    if n_pf or n_pol:
        points.append(("📰", f"PF/조달 뉴스 {n_pf}건 · 부동산 정책 뉴스 {n_pol}건"))

    bullets = ""
    for icon, text in points[:5]:
        bullets += (
            f'<div style="display:flex;gap:9px;align-items:baseline;padding:5px 0;'
            f'border-bottom:1px solid #f1f5f9;">'
            f'<span style="font-size:13px;flex-shrink:0;">{icon}</span>'
            f'<span style="font-size:12.5px;color:#1e293b;line-height:1.6;">{text}</span>'
            f'</div>'
        )
    if not bullets:
        bullets = '<div style="font-size:12px;color:#94a3b8;padding:8px 0;">데이터 없음 — ECOS API 연결 확인</div>'

    sp_val = aa_sp.get("value")
    impacts = []
    if sp_val is not None:
        if sp_val < 0.5:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p — 조달여건 양호")
        elif sp_val < 1.0:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p — 정상 범위")
        elif sp_val < 1.5:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p 확대 — PF 조달비용 상승 주의")
        else:
            impacts.append(f"AA- 스프레드 {sp_val:.2f}%p 급확대 — 조달 위험 신호")
    am_val = am_sp.get("value")
    if am_val is not None:
        impacts.append(f"A- 스프레드 {am_val:.2f}%p")
    usd = data.get("usd_krw", {})
    if usd.get("value") and usd["value"] > 1400:
        impacts.append(f"고환율 {usd['value']:,.0f}원 — 외화조달 부담")
    impact_str = " / ".join(impacts) if impacts else "ECOS 데이터 수집 확인 필요"

    credits = data.get("company_credit", {})
    watch_list = [
        f"{co}({crd.get('rating','')}, {crd.get('outlook','')})"
        for co, crd in credits.items()
        if crd.get("rating","").startswith("BB") or "부정적" in crd.get("outlook","")
    ]
    watch_str = " / ".join(watch_list) if watch_list else "특이 이슈 없음 (credit_ratings.csv 기준)"

    return f"""
<tr><td {SP}>
  {sec_header("① ", "EXECUTIVE SUMMARY")}
  <div style="background:#f8fafc;border-radius:6px;padding:10px 14px;margin-bottom:12px;">
    {bullets}
  </div>
  <div style="display:flex;gap:10px;">
    <div style="flex:1;background:#eff6ff;border-left:3px solid #3b82f6;
                border-radius:0 6px 6px 0;padding:10px 14px;">
      <div style="font-size:10px;font-weight:700;color:#1d4ed8;margin-bottom:5px;">
        💡 PF/조달 시장 영향
      </div>
      <div style="font-size:12px;color:#334155;line-height:1.7;">{impact_str}</div>
    </div>
    <div style="flex:1;background:#fff7ed;border-left:3px solid #f97316;
                border-radius:0 6px 6px 0;padding:10px 14px;">
      <div style="font-size:10px;font-weight:700;color:#c2410c;margin-bottom:5px;">
        ⚠ 주의 건설사 / 이슈
      </div>
      <div style="font-size:12px;color:#334155;line-height:1.7;">{watch_str}</div>
    </div>
  </div>
</td></tr>"""


# ─── Section 2: Funding Market ────────────────────────────────────

def _bond_row(key, label, bonds, rate_history,
              highlight=False, show_spread=False, is_spread=False):
    item  = bonds.get(key, {})
    val   = item.get("value")
    err   = item.get("error", "")
    dtype = item.get("type", "auto")
    date  = fmt_date(item.get("date", ""))

    if val is not None:
        if is_spread:
            val_s = f'<b style="font-size:13px;color:#7c3aed;">{val:+.3f}%p</b>'
            sig   = spread_badge(val) if show_spread else ""
        else:
            val_s = f'<b style="font-size:13px;color:#0f172a;">{val:.2f}%</b>'
            sig   = ""
    else:
        val_s = '<span style="color:#94a3b8;font-size:12px;">N/A</span>'
        sig   = ""

    hist  = rate_history.get(key, [])
    if len(hist) >= 2 and not is_spread:
        chg_s = chg_color(round(hist[-1][1] - hist[-2][1], 3))
    else:
        chg_s = '<span style="color:#e2e8f0;">—</span>'

    bg    = "#fefce8" if highlight else "#fff"
    err_s = (f' <span style="color:#ef4444;font-size:9px;">{err[:32]}</span>'
             if err and not val else "")

    return f"""
<tr style="background:{bg};">
  <td style="padding:7px 10px;font-size:12px;font-weight:500;color:#334155;
             border-bottom:1px solid #f1f5f9;white-space:nowrap;">{label}</td>
  <td style="padding:7px 10px;text-align:right;border-bottom:1px solid #f1f5f9;">
    {val_s} {sig}
  </td>
  <td style="padding:7px 10px;text-align:right;border-bottom:1px solid #f1f5f9;
             white-space:nowrap;">{chg_s}</td>
  <td style="padding:7px 10px;font-size:10px;color:#94a3b8;text-align:right;
             border-bottom:1px solid #f1f5f9;white-space:nowrap;">
    {badge(dtype)} {date}{err_s}
  </td>
</tr>"""


def _build_bond_table(bonds, rate_history):
    BOND_ROWS = [
        ("base_rate",      "기준금리",       False),
        ("cd_91",          "CD 91일",        False),
        ("cp_91",          "CP 91일",        False),
        ("gov_3y",         "국고채 3Y",      False),
        ("gov_10y",        "국고채 10Y",     False),
        ("corp_aa_3y",     "회사채 3Y AA-",  True),
        ("corp_aplus_3y",  "회사채 3Y A+",   False),
        ("corp_a0_3y",     "회사채 3Y A0",   False),
        ("corp_aminus_3y", "회사채 3Y A-",   True),
    ]
    SPREAD_ROWS = [
        ("aa_spread",     "AA- 스프레드", True),
        ("aminus_spread", "A- 스프레드",  False),
    ]

    rows = ""
    for key, label, hl in BOND_ROWS:
        rows += _bond_row(key, label, bonds, rate_history, highlight=hl)

    rows += '<tr><td colspan="4" style="height:4px;background:#f8fafc;"></td></tr>'
    for key, label, show_sig in SPREAD_ROWS:
        if bonds.get(key, {}).get("value") is not None:
            rows += _bond_row(key, label, bonds, rate_history,
                              highlight=show_sig, show_spread=show_sig, is_spread=True)

    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
  <tr style="background:#f8fafc;">
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:left;font-weight:700;">항목</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">금리</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">전일대비</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">기준일·출처</th>
  </tr>
  {rows}
</table>
<div style="font-size:9px;color:#94a3b8;margin-top:4px;">
  전일대비: 30일 이력 기준 &nbsp;|&nbsp; A+/A0/A-: ECOS item_code 미확인
  — <code>discover_ecos_items()</code> 실행 후 업데이트 가능
</div>"""


def _build_short_term_table(pf_rates, cp_rates):
    pf_rows = ""
    for r in pf_rates:
        cat  = r.get("category", "")
        sub  = r.get("subcategory", "")
        rp   = r.get("rate_pct", "")
        rs   = f"{float(rp):.2f}%" if rp and str(rp).strip() else "—"
        aod  = r.get("as_of_date", "")
        pf_rows += f"""
<tr style="border-bottom:1px solid #fde68a;">
  <td style="padding:5px 8px;font-size:11px;color:#374151;">
    <span style="font-weight:600;">{cat}</span>
    {"&nbsp;<span style='color:#94a3b8;font-size:10px;'>"+sub+"</span>" if sub else ""}
  </td>
  <td style="padding:5px 8px;font-size:12px;font-weight:700;color:#b45309;
             text-align:right;">{rs}</td>
  <td style="padding:5px 8px;font-size:9px;color:#94a3b8;text-align:right;
             white-space:nowrap;">{aod}</td>
</tr>"""
    if not pf_rows:
        pf_rows = ('<tr><td colspan="3" style="padding:10px 8px;font-size:11px;color:#94a3b8;">'
                   'pf_rates.csv 업데이트 필요</td></tr>')

    cp_rows = ""
    for r in cp_rates:
        grade = r.get("grade_label", r.get("grade", ""))
        t3m   = r.get("tenor_3m", "")
        t1y   = r.get("tenor_1y", "")
        t3m_s = f"{float(t3m):.2f}%" if t3m and str(t3m).strip() else "—"
        t1y_s = f"{float(t1y):.2f}%" if t1y and str(t1y).strip() else "—"
        cp_rows += f"""
<tr style="border-bottom:1px solid #dbeafe;">
  <td style="padding:5px 8px;font-size:11px;font-weight:600;color:#1e3a8a;">{grade}</td>
  <td style="padding:5px 8px;font-size:11px;color:#1e40af;text-align:right;">{t3m_s}</td>
  <td style="padding:5px 8px;font-size:11px;color:#1d4ed8;text-align:right;">{t1y_s}</td>
</tr>"""
    if not cp_rows:
        cp_rows = ('<tr><td colspan="3" style="padding:10px 8px;font-size:11px;color:#94a3b8;">'
                   'cp_rates.csv 업데이트 필요</td></tr>')

    pf_date = pf_rates[0].get("as_of_date", "—") if pf_rates else "—"
    cp_date = cp_rates[0].get("as_of_date", "—") if cp_rates else "—"

    return f"""
<div style="display:flex;gap:14px;">
  <div style="flex:1;">
    <div style="font-size:10px;color:#64748b;margin-bottom:5px;">
      PF 시장금리 &nbsp;{badge('manual')} 기준일 {pf_date}
    </div>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #fde68a;border-radius:6px;overflow:hidden;background:#fffbeb;">
      <tr style="background:#fef9c3;">
        <th style="padding:5px 8px;font-size:10px;color:#92400e;text-align:left;
                   font-weight:700;">구분</th>
        <th style="padding:5px 8px;font-size:10px;color:#92400e;text-align:right;
                   font-weight:700;">금리</th>
        <th style="padding:5px 8px;font-size:10px;color:#92400e;text-align:right;
                   font-weight:700;">기준일</th>
      </tr>
      {pf_rows}
    </table>
  </div>
  <div style="flex:1;">
    <div style="font-size:10px;color:#64748b;margin-bottom:5px;">
      CP 등급별 금리 &nbsp;{badge('manual')} 기준일 {cp_date}
    </div>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #dbeafe;border-radius:6px;overflow:hidden;background:#eff6ff;">
      <tr style="background:#dbeafe;">
        <th style="padding:5px 8px;font-size:10px;color:#1e3a8a;text-align:left;
                   font-weight:700;">등급</th>
        <th style="padding:5px 8px;font-size:10px;color:#1e3a8a;text-align:right;
                   font-weight:700;">3개월</th>
        <th style="padding:5px 8px;font-size:10px;color:#1e3a8a;text-align:right;
                   font-weight:700;">1년</th>
      </tr>
      {cp_rows}
    </table>
  </div>
</div>"""


def _build_cofix_table(cofix):
    sorted_cf = sorted(
        [r for r in cofix if r.get("ym", "").strip()],
        key=lambda r: r.get("ym", ""), reverse=True,
    )
    if not sorted_cf:
        return (f'<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;'
                f'padding:12px;font-size:12px;color:#64748b;">'
                f'{badge("manual")} manual_data/cofix.csv 업데이트 필요 '
                f'(은행연합회 공시 기준 월별 입력)</div>')

    yms    = [r.get("ym", "") for r in sorted_cf]
    latest = yms[0] if len(yms) > 0 else ""
    prev_m = yms[1] if len(yms) > 1 else ""
    prev_3 = yms[3] if len(yms) > 3 else ""

    prev_y = ""
    if latest and "-" in latest:
        yr, mo = latest.split("-")
        ym_yy  = f"{int(yr)-1}-{mo}"
        if any(r.get("ym") == ym_yy for r in cofix):
            prev_y = ym_yy

    def get_val(ym, field):
        row = next((r for r in cofix if r.get("ym") == ym), None)
        if not row:
            return None
        v = str(row.get(field, "")).strip()
        return float(v) if v else None

    def diff_s(ym_a, ym_b, field):
        if not ym_a or not ym_b:
            return '<span style="color:#e2e8f0;">—</span>'
        a, b = get_val(ym_a, field), get_val(ym_b, field)
        if a is None or b is None:
            return '<span style="color:#e2e8f0;">—</span>'
        d   = round(a - b, 2)
        sym = "▲" if d > 0 else "▼"
        clr = "#dc2626" if d > 0 else "#16a34a"
        return f'<span style="color:{clr};font-size:11px;">{sym}{abs(d):.2f}</span>'

    TYPES = [
        ("new_all_rate",    "신규취급액기준"),
        ("balance_rate",    "잔액기준"),
        ("new_balance_rate","신잔액기준"),
    ]
    rows = ""
    for field, label in TYPES:
        cv   = get_val(latest, field)
        cv_s = (f'<b style="color:#0369a1;">{cv:.2f}%</b>'
                if cv is not None
                else '<span style="color:#94a3b8;">—</span>')
        rows += f"""
<tr style="border-bottom:1px solid #e0f2fe;">
  <td style="padding:7px 10px;font-size:12px;font-weight:600;color:#0c4a6e;">{label}</td>
  <td style="padding:7px 10px;text-align:right;">{cv_s}</td>
  <td style="padding:7px 10px;text-align:right;">{diff_s(latest, prev_m, field)}</td>
  <td style="padding:7px 10px;text-align:right;">{diff_s(latest, prev_3, field)}</td>
  <td style="padding:7px 10px;text-align:right;">{diff_s(latest, prev_y, field)}</td>
</tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #bae6fd;border-radius:6px;overflow:hidden;">
  <tr style="background:#e0f2fe;">
    <th style="padding:6px 10px;font-size:10px;color:#075985;text-align:left;
               font-weight:700;">구분</th>
    <th style="padding:6px 10px;font-size:10px;color:#075985;text-align:right;
               font-weight:700;">{latest or "최신"}</th>
    <th style="padding:6px 10px;font-size:10px;color:#075985;text-align:right;
               font-weight:700;">전월</th>
    <th style="padding:6px 10px;font-size:10px;color:#075985;text-align:right;
               font-weight:700;">전분기</th>
    <th style="padding:6px 10px;font-size:10px;color:#075985;text-align:right;
               font-weight:700;">전년동기</th>
  </tr>
  {rows}
</table>
<div style="font-size:9px;color:#94a3b8;margin-top:4px;">
  {badge('manual')} 은행연합회 공시 기준 — manual_data/cofix.csv 월별 업데이트 필요
</div>"""


def _build_rate_chart(rate_history, bonds):
    ITEMS = [
        ("cd_91",      "CD 91일",    "#06b6d4"),
        ("gov_3y",     "국고채 3Y",  "#3b82f6"),
        ("gov_10y",    "국고채 10Y", "#8b5cf6"),
        ("corp_aa_3y", "회사채 AA-", "#f59e0b"),
    ]
    has_data = any(rate_history.get(k) for k, _, _ in ITEMS)
    if not has_data:
        return '<div style="color:#94a3b8;font-size:11px;padding:8px 0;">이력 데이터 없음 — ECOS_API_KEY 확인</div>'

    rows = ""
    for key, label, color in ITEMS:
        hist    = rate_history.get(key, [])
        vals    = [v for _, v in hist]
        curr    = bonds.get(key, {}).get("value")
        curr_s  = f"{curr:.2f}%" if curr is not None else "—"
        first_s = f"{vals[0]:.2f}%" if vals else "—"
        svg     = sparkline(hist, color=color)
        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9;">
  <td style="padding:6px 10px;font-size:12px;font-weight:500;color:#334155;
             white-space:nowrap;">{label}</td>
  <td style="padding:6px 10px;">{svg}</td>
  <td style="padding:6px 10px;font-size:12px;font-weight:700;color:#0f172a;
             text-align:right;white-space:nowrap;">{curr_s}</td>
  <td style="padding:6px 10px;font-size:11px;color:#64748b;
             text-align:right;white-space:nowrap;">{first_s}</td>
  <td style="padding:6px 10px;font-size:9px;color:#94a3b8;
             text-align:right;">{len(vals)}일</td>
</tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
  <tr style="background:#f8fafc;">
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:left;
               font-weight:700;">항목</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:center;
               font-weight:700;">추이 (~30일)</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:right;
               font-weight:700;">현재</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:right;
               font-weight:700;">30일전</th>
    <th style="padding:6px 10px;font-size:10px;color:#64748b;font-weight:700;"></th>
  </tr>
  {rows}
</table>"""


def html_funding_market(data):
    bonds        = data.get("bonds", {})
    rate_history = data.get("rate_history", {})
    pf_rates     = data.get("pf_rates", [])
    cp_rates     = data.get("cp_rates", [])
    cofix        = data.get("cofix", [])

    return f"""
<tr><td {SP}>
  {sec_header("② ", "Funding Market", "#7c3aed")}

  {sub_header("2-1. 채권 금리", "#7c3aed")}
  {_build_bond_table(bonds, rate_history)}

  {sub_header("2-2. 유동화증권 / 단기조달 금리", "#d97706")}
  {_build_short_term_table(pf_rates, cp_rates)}

  {sub_header("2-3. COFIX", "#0ea5e9")}
  {_build_cofix_table(cofix)}

  {sub_header("2-4. 채권금리 추이 (30일)", "#475569")}
  {_build_rate_chart(rate_history, bonds)}
  <div style="font-size:9px;color:#94a3b8;margin-top:4px;">
    {badge('auto')} 한국은행 ECOS 일별 데이터 기준
  </div>
</td></tr>"""


# ─── Section 3: 금융/정책 뉴스 ───────────────────────────────────

def _news_list(news, kw_bg="#dbeafe", kw_fg="#1e40af"):
    if not news:
        return '<div style="color:#94a3b8;font-size:12px;padding:8px 0;">수집된 뉴스 없음</div>'
    rows = ""
    for art in news:
        kw    = art.get("keyword", "")[:9]
        title = art.get("title", "")
        link  = art.get("link", "#")
        date  = art.get("pub_date", "")[:16]
        rows += f"""
<div style="display:flex;align-items:baseline;gap:7px;padding:5px 0;
            border-bottom:1px solid #f1f5f9;line-height:1.4;">
  <span style="flex-shrink:0;background:{kw_bg};color:{kw_fg};padding:1px 5px;
               border-radius:3px;font-size:9px;font-weight:700;
               white-space:nowrap;">{kw}</span>
  <a href="{link}" style="flex:1;font-size:12px;color:#0f172a;font-weight:500;
                           text-decoration:none;overflow:hidden;">{title}</a>
  <span style="flex-shrink:0;font-size:10px;color:#94a3b8;white-space:nowrap;">{date}</span>
</div>"""
    return rows


def html_market_news(data):
    pf_news    = data.get("pf_news", [])
    policy_news = data.get("policy_news", [])

    return f"""
<tr><td {SP}>
  {sec_header("③ ", "부동산 금융시장 및 정책 동향", "#ec4899")}
  <div style="display:flex;gap:14px;">
    <div style="flex:1;">
      {sub_header(f"3-1. 금융시장 뉴스 ({len(pf_news)}건)", "#1e40af")}
      {_news_list(pf_news, "#dbeafe", "#1e40af")}
      <div style="font-size:9px;color:#94a3b8;margin-top:6px;">
        {badge('auto')} Naver API · PF대출/브릿지론/ABCP/유동화/CP 키워드
      </div>
    </div>
    <div style="flex:1;border-left:1px solid #f1f5f9;padding-left:14px;">
      {sub_header(f"3-2. 부동산 정책 뉴스 ({len(policy_news)}건)", "#059669")}
      {_news_list(policy_news, "#dcfce7", "#15803d")}
      <div style="font-size:9px;color:#94a3b8;margin-top:6px;">
        {badge('auto')} Naver API · 국토부/금융위/금감원/HUG/DSR/가계대출 키워드
      </div>
    </div>
  </div>
</td></tr>"""


# ─── Section 4: Deal Watch ────────────────────────────────────────

def html_deal_watch(data):
    deals = data.get("deal_watch", [])
    real  = [d for d in deals
             if d.get("project_name", "").strip() or d.get("borrower", "").strip()]

    if not real:
        return f"""
<tr><td {SP}>
  {sec_header("④ ", "Deal / 조달 사례 Watch", "#f59e0b")}
  <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:14px;">
    <div style="font-size:12px;color:#92400e;margin-bottom:6px;">
      {badge('manual')} manual_data/deal_watch.csv 에 실제 딜 정보 입력 필요
    </div>
    <div style="font-size:10px;color:#94a3b8;line-height:1.8;">
      컬럼: type(도시정비/PF/브릿지론) · party(당사/타사) · borrower ·
      guarantee_type(HUG/연대보증/책임준공/기타) · rate_pct · maturity ·
      project_name · amount_bn · remark · as_of_date
    </div>
  </div>
</td></tr>"""

    TYPE_STYLE = {
        "도시정비": ("#dbeafe", "#1e3a8a"),
        "PF":       ("#dcfce7", "#14532d"),
        "브릿지론": ("#fef3c7", "#78350f"),
    }
    rows = ""
    for d in real:
        t        = d.get("type", "")
        bg, fg   = TYPE_STYLE.get(t, ("#f3f4f6", "#374151"))
        party    = d.get("party", "")
        borrower = d.get("borrower", "")
        guar     = d.get("guarantee_type", "")
        rp       = d.get("rate_pct", "")
        rate_s   = f"{float(rp):.2f}%" if rp and str(rp).strip() else "—"
        mat      = d.get("maturity", "")
        proj     = d.get("project_name", "")
        amt      = d.get("amount_bn", "")
        amt_s    = f"{amt}억" if amt and str(amt).strip() else "—"
        rmk      = d.get("remark", "")

        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9;">
  <td style="padding:6px 8px;white-space:nowrap;">
    <span style="background:{bg};color:{fg};font-size:10px;font-weight:700;
                 padding:2px 6px;border-radius:3px;">{t}</span>
  </td>
  <td style="padding:6px 8px;font-size:11px;color:#374151;white-space:nowrap;">{party}</td>
  <td style="padding:6px 8px;font-size:11px;color:#374151;">{borrower}</td>
  <td style="padding:6px 8px;font-size:11px;color:#374151;white-space:nowrap;">{guar}</td>
  <td style="padding:6px 8px;font-size:12px;font-weight:700;color:#b45309;
             text-align:right;white-space:nowrap;">{rate_s}</td>
  <td style="padding:6px 8px;font-size:11px;text-align:right;white-space:nowrap;">{mat}</td>
  <td style="padding:6px 8px;font-size:11px;color:#0f172a;">{proj}</td>
  <td style="padding:6px 8px;font-size:11px;font-weight:600;
             text-align:right;white-space:nowrap;">{amt_s}</td>
  <td style="padding:6px 8px;font-size:10px;color:#64748b;">{rmk}</td>
</tr>"""

    return f"""
<tr><td {SP}>
  {sec_header("④ ", "Deal / 조달 사례 Watch", "#f59e0b")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
    <tr style="background:#f8fafc;">
      <th style="padding:6px 8px;font-size:10px;color:#64748b;text-align:left;
                 font-weight:700;">구분</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;font-weight:700;">당사/타사</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;font-weight:700;">조달주체</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;font-weight:700;">보증형태</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;text-align:right;
                 font-weight:700;">금리</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;text-align:right;
                 font-weight:700;">만기</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;font-weight:700;">현장명</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;text-align:right;
                 font-weight:700;">금액</th>
      <th style="padding:6px 8px;font-size:10px;color:#64748b;font-weight:700;">비고</th>
    </tr>
    {rows}
  </table>
  <div style="font-size:9px;color:#94a3b8;margin-top:5px;">
    {badge('manual')} MANUAL — manual_data/deal_watch.csv 직접 입력
  </div>
</td></tr>"""


# ─── Section 5: 신용등급 현황 ─────────────────────────────────────

def html_company_credit(data):
    credits = data.get("company_credit", {})
    if not credits:
        return ""

    rows = ""
    for co, crd in credits.items():
        rt  = crd.get("rating", "—")
        ot  = crd.get("outlook", "")
        rtr = crd.get("rater", "")
        dt  = crd.get("rating_date", "")
        nt  = crd.get("note", "")
        rc  = rating_color(rt)
        alert_bg = "background:#fff7ed;" if (rt.startswith("BB") or "부정적" in ot) else ""
        rows += f"""
<tr style="{alert_bg}border-bottom:1px solid #f1f5f9;">
  <td style="padding:6px 10px;font-size:12px;font-weight:600;color:#0f172a;
             white-space:nowrap;">{co}</td>
  <td style="padding:6px 10px;text-align:center;">
    <b style="color:{rc};font-size:13px;">{rt}</b>
  </td>
  <td style="padding:6px 10px;font-size:11px;color:#64748b;text-align:center;
             white-space:nowrap;">{ot}</td>
  <td style="padding:6px 10px;font-size:10px;color:#94a3b8;white-space:nowrap;">{rtr}</td>
  <td style="padding:6px 10px;font-size:10px;color:#94a3b8;white-space:nowrap;">{dt}</td>
  <td style="padding:6px 10px;font-size:10px;color:#94a3b8;">{nt[:40] if nt else ""}</td>
</tr>"""

    return f"""
<tr><td {SP_LAST}>
  {sec_header("⑤ ", "건설사 신용등급 현황", "#64748b")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
    <tr style="background:#f8fafc;">
      <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:left;
                 font-weight:700;">건설사</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:center;
                 font-weight:700;">등급</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:center;
                 font-weight:700;">전망</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;font-weight:700;">평가사</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;font-weight:700;">평가일</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;font-weight:700;">비고</th>
    </tr>
    {rows}
  </table>
  <div style="font-size:9px;color:#94a3b8;margin-top:5px;">
    {badge('manual')} MANUAL — manual_data/credit_ratings.csv 직접 업데이트
  </div>
</td></tr>"""


# ─── Footer ───────────────────────────────────────────────────────

def html_footer(data):
    return f"""
<tr><td style="background:#1e293b;padding:12px 22px;border-radius:0 0 8px 8px;">
  <div style="display:flex;justify-content:space-between;align-items:center;
              flex-wrap:wrap;gap:6px;">
    <div style="font-size:10px;color:#64748b;line-height:1.8;">
      {badge('auto')} AUTO: ECOS/Naver 자동수집 &nbsp;
      {badge('auto_derived')} 계산값 &nbsp;
      {badge('manual')} MANUAL: CSV 수동입력<br>
      본 리포트는 자동 생성된 내부 참고자료 — 최종 판단은 담당자 확인 필수
    </div>
    <div style="font-size:10px;color:#475569;text-align:right;">
      생성 {data['collected_at']}<br>
      pf-daily-mail v2.0
    </div>
  </div>
</td></tr>"""


# ─── HTML 조립 ────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0; background: #f1f5f9;
  font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', Arial, sans-serif;
}
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
table { border-collapse: collapse; }
@media print { body { background: white !important; } }
"""


def build_html(data):
    body = (
        html_header(data)         +
        html_exec_summary(data)   +
        html_funding_market(data) +
        html_market_news(data)    +
        html_deal_watch(data)     +
        html_company_credit(data) +
        html_footer(data)
    )
    return (
        '<!DOCTYPE html>\n<html lang="ko">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
        f'<title>PF Daily — {data["report_date"]}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n'
        '<table width="100%" cellpadding="0" cellspacing="0"'
        ' style="background:#f1f5f9;padding:16px 0;">\n'
        '  <tr><td align="center">\n'
        '    <table width="720" cellpadding="0" cellspacing="0"\n'
        '     style="max-width:720px;box-shadow:0 4px 24px rgba(0,0,0,.12);border-radius:8px;">\n'
        + body +
        '    </table>\n'
        '  </td></tr>\n'
        '</table>\n</body>\n</html>'
    )


# ─── 메인 ─────────────────────────────────────────────────────────

def generate_report(data=None):
    if data is None:
        src = DATA_DIR / "latest_report.json"
        if not src.exists():
            raise FileNotFoundError(f"데이터 파일 없음: {src}")
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
