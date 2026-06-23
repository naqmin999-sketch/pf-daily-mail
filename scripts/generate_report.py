"""
PF Daily Market Intelligence — HTML 리포트 생성기 v3.0
구조: ① 시황 요약 3박스 (A채권금리|B유동화증권|C가계대출COFIX)
     ② 채권금리 추이 (30일 스파크라인)
     ③ 부동산 금융시장 뉴스 (5건 × 2)
     ④ Deal Watch
     ⑤ 건설사 신용등급
"""
import json
import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"


# ─── 공통 헬퍼 ────────────────────────────────────────────────────

def badge(dtype):
    cfg = {
        "auto":         ("AUTO",    "#059669", "#d1fae5"),
        "auto_derived": ("계산",    "#7c3aed", "#ede9fe"),
        "manual":       ("MANUAL",  "#d97706", "#fef3c7"),
        "fallback":     ("FALLBACK","#dc2626", "#fee2e2"),
    }
    lbl, fg, bg = cfg.get(dtype, ("?", "#6b7280", "#f3f4f6"))
    return (f'<span style="display:inline-block;padding:1px 5px;border-radius:3px;'
            f'font-size:9px;font-weight:700;color:{fg};background:{bg};">{lbl}</span>')


def chg_color(chg):
    if chg is None:
        return '<span style="color:#e2e8f0;">—</span>'
    try:
        chg = float(chg)
    except (ValueError, TypeError):
        return '<span style="color:#e2e8f0;">—</span>'
    if chg == 0:
        return '<span style="color:#94a3b8;font-weight:600;font-size:10px;">±0.00%</span>'
    sym = "▲" if chg > 0 else "▼"
    clr = "#dc2626" if chg > 0 else "#16a34a"
    return f'<span style="color:{clr};font-weight:600;font-size:10px;">{sym}{abs(chg):.2f}%</span>'


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
    return (f'<span style="background:{bg};color:{fg};padding:1px 5px;border-radius:3px;'
            f'font-size:9px;font-weight:700;">{lbl}</span>')


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


# ─── Header ───────────────────────────────────────────────────────

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


# ─── Section 1: 시황 요약 3박스 ──────────────────────────────────

def _box_bond_rates(bonds, rate_history):
    """Box A — 채권금리"""
    # (key, label, highlight)
    items = [
        ("base_rate",  "기준금리",   False),
        ("cd_91",      "CD 91일",    True),
        ("gov_3y",     "국고채 3Y",  True),
        ("corp_aa_3y", "회사채 AA-", True),
    ]
    rows = ""
    for key, label, highlight in items:
        item = bonds.get(key, {})
        val  = item.get("value")

        if val is not None:
            val_s = f'<b style="font-size:11px;color:#0f172a;">{val:.2f}%</b>'
        else:
            val_s = '<span style="color:#cbd5e1;font-size:10px;">N/A</span>'

        hist  = rate_history.get(key, [])
        chg_s = (chg_color(round(hist[-1][1] - hist[-2][1], 3))
                 if len(hist) >= 2
                 else '<span style="color:#e2e8f0;font-size:9px;">—</span>')

        bg = "#fafafa" if highlight else "#fff"
        rows += f"""
<tr style="background:{bg};border-bottom:1px solid #f3f4f6;">
  <td style="width:28%;padding:4px 6px;font-size:10px;color:#475569;white-space:nowrap;">{label}</td>
  <td style="padding:4px 6px;text-align:right;white-space:nowrap;">{val_s}</td>
  <td style="width:24%;padding:4px 6px;text-align:right;white-space:nowrap;">{chg_s}</td>
</tr>"""

    return f"""
<div style="border:1px solid #c7d2fe;border-radius:6px;overflow:hidden;">
  <div style="background:#1e3a8a;padding:7px 10px;display:flex;align-items:center;gap:6px;">
    <span style="font-size:11px;font-weight:800;color:#fff;">A. 채권금리</span>
    <span style="font-size:9px;color:#a5b4fc;">{badge('auto')} ECOS</span>
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff;table-layout:fixed;">
    <tr style="background:#eff6ff;">
      <th style="width:28%;padding:4px 6px;font-size:9px;color:#3730a3;text-align:left;font-weight:700;">항목</th>
      <th style="padding:4px 6px;font-size:9px;color:#3730a3;text-align:right;font-weight:700;">금리</th>
      <th style="width:24%;padding:4px 6px;font-size:9px;color:#3730a3;text-align:right;font-weight:700;">전일비</th>
    </tr>
    {rows}
  </table>
</div>"""


def _box_securitization(pf_rates, cp_rates):
    """Box B — 주요 건설사 신용등급"""

    def grade_color(g):
        g = str(g).strip()
        if g.startswith("AA"):  return "#1e40af", "#dbeafe"
        if g.startswith("A+"):  return "#065f46", "#d1fae5"
        if g in ("A", "A-"):    return "#92400e", "#fef3c7"
        if g.startswith("BBB"): return "#7c2d12", "#fee2e2"
        return "#374151", "#f3f4f6"

    rows = ""
    for r in cp_rates:
        rank    = r.get("rank", "")
        company = r.get("company", "")
        cg      = r.get("corp_grade", "입력필요")
        pg      = r.get("cp_grade",   "입력필요")
        note    = r.get("note", "")
        name_s  = f'{company}<span style="font-size:8px;color:#94a3b8;margin-left:2px;">{note}</span>' if note else company
        cfg, cbg = grade_color(cg)
        pfg, pbg = grade_color(pg)
        rows += f"""
<tr style="border-bottom:1px solid #f3f4f6;">
  <td style="padding:3px 5px;font-size:8px;color:#94a3b8;text-align:center;white-space:nowrap;">{rank}</td>
  <td style="padding:3px 5px;font-size:9px;color:#374151;white-space:nowrap;">{name_s}</td>
  <td style="padding:3px 5px;font-size:9px;font-weight:700;color:{cfg};background:{cbg};text-align:center;white-space:nowrap;">{cg}</td>
  <td style="padding:3px 5px;font-size:9px;font-weight:700;color:{pfg};background:{pbg};text-align:center;white-space:nowrap;">{pg}</td>
</tr>"""

    if not rows:
        rows = '<tr><td colspan="4" style="padding:6px;font-size:9px;color:#94a3b8;">cp_rates.csv 업데이트 필요</td></tr>'

    today = datetime.date.today().strftime("%Y-%m-%d")

    return f"""
<div style="border:1px solid #fde68a;border-radius:6px;overflow:hidden;">
  <div style="background:#92400e;padding:7px 10px;display:flex;align-items:center;gap:6px;">
    <span style="font-size:11px;font-weight:800;color:#fff;">B. 유동화증권</span>
    <span style="font-size:9px;color:#fcd34d;">{badge('manual')} CSV</span>
  </div>
  <div style="font-size:9px;color:#92400e;padding:4px 6px;background:#fef9c3;font-weight:700;">
    주요 건설사 신용등급 &nbsp;·&nbsp; 기준일 {today}
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#fffbeb;table-layout:fixed;">
    <tr style="background:#fef3c7;">
      <th style="width:10%;padding:3px 5px;font-size:9px;color:#92400e;text-align:center;font-weight:700;">순위</th>
      <th style="padding:3px 5px;font-size:9px;color:#92400e;text-align:left;font-weight:700;">건설사</th>
      <th style="width:22%;padding:3px 5px;font-size:9px;color:#92400e;text-align:center;font-weight:700;">회사채</th>
      <th style="width:22%;padding:3px 5px;font-size:9px;color:#92400e;text-align:center;font-weight:700;">단기CP</th>
    </tr>
    {rows}
  </table>
</div>"""


def _cofix_trend_svg(cofix, width=196, height=52):
    """COFIX 신규취급액기준 월별 추이 — 인라인 SVG"""
    pts_data = []
    for r in sorted([r for r in cofix if r.get("ym")], key=lambda r: r["ym"]):
        v = str(r.get("new_all_rate", "")).strip()
        try:
            pts_data.append((r["ym"][5:], float(v)))
        except (ValueError, TypeError):
            pass
    if len(pts_data) < 2:
        return ""

    vals = [v for _, v in pts_data]
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 0.5

    pad_l, pad_r, pad_t, pad_b = 4, 24, 6, 14
    W = width - pad_l - pad_r
    H = height - pad_t - pad_b

    points = " ".join(
        f"{round(i / (len(vals)-1) * W + pad_l, 1)},"
        f"{round((1-(v-mn)/rng) * H + pad_t, 1)}"
        for i, (_, v) in enumerate(pts_data)
    )
    lx = round(W + pad_l, 1)
    ly = round((1-(vals[-1]-mn)/rng) * H + pad_t, 1)

    mo_labels = ""
    for i, (mo, _) in enumerate(pts_data):
        if i == 0 or i == len(pts_data) - 1:
            x = round(i / (len(pts_data)-1) * W + pad_l, 1)
            mo_labels += (f'<text x="{x}" y="{height-1}" font-size="7" fill="#94a3b8" '
                          f'text-anchor="middle">{mo}</text>')

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:block;overflow:visible;">'
        f'<polyline points="{points}" fill="none" stroke="#0ea5e9" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2.5" fill="#0ea5e9"/>'
        f'<text x="{lx+3}" y="{ly+3}" font-size="8" fill="#0369a1" font-weight="bold">'
        f'{vals[-1]:.2f}%</text>'
        f'{mo_labels}'
        f'</svg>'
    )


def _box_cofix(cofix):
    """Box C — 가계대출 COFIX"""
    sorted_cf = sorted(
        [r for r in cofix if r.get("ym", "").strip()],
        key=lambda r: r.get("ym", ""), reverse=True,
    )
    latest = sorted_cf[0] if sorted_cf else None
    prev_m = sorted_cf[1] if len(sorted_cf) > 1 else None

    src_type  = (latest.get("type", "manual") if latest else "manual")
    src_badge = badge("auto") if src_type == "auto" else badge("manual")
    src_label = "우리은행 자동수집" if src_type == "auto" else "CSV 수동입력"
    today_label = datetime.date.today().strftime("%Y-%m-%d")

    def _val(row, field):
        if not row:
            return None
        v = str(row.get(field, "")).strip()
        try:
            return float(v) if v else None
        except ValueError:
            return None

    def _row(field, label):
        cv  = _val(latest, field)
        pv  = _val(prev_m, field)
        cv_s = f'<b style="color:#0369a1;font-size:11px;">{cv:.2f}%</b>' if cv is not None \
               else '<span style="color:#d1d5db;font-size:10px;">—</span>'
        if cv is not None and pv is not None:
            d = round(cv - pv, 2)
            sym = "▲" if d > 0 else "▼"
            clr = "#dc2626" if d > 0 else "#16a34a"
            diff = f'<span style="color:{clr};font-size:9px;">{sym}{abs(d):.2f}</span>'
        else:
            diff = '<span style="color:#e2e8f0;font-size:9px;">—</span>'
        return f"""
<tr style="border-bottom:1px solid #e0f2fe;">
  <td style="padding:5px 6px;font-size:9px;color:#0c4a6e;white-space:nowrap;">{label}</td>
  <td style="padding:5px 6px;text-align:right;white-space:nowrap;">{cv_s}</td>
  <td style="padding:5px 6px;text-align:right;white-space:nowrap;">{diff}</td>
</tr>"""

    trend = _cofix_trend_svg(cofix)

    return f"""
<div style="border:1px solid #bae6fd;border-radius:6px;overflow:hidden;">
  <div style="background:#075985;padding:7px 10px;display:flex;align-items:center;gap:6px;">
    <span style="font-size:11px;font-weight:800;color:#fff;">C. 가계대출 (COFIX)</span>
    <span style="font-size:9px;color:#7dd3fc;">{src_badge}</span>
  </div>
  <div style="padding:4px 6px;background:#e0f2fe;font-size:9px;color:#0369a1;font-weight:700;">
    기준일: {today_label} &nbsp;·&nbsp; {src_label}
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f9ff;">
    <tr style="background:#e0f2fe;">
      <th style="padding:4px 6px;font-size:9px;color:#075985;text-align:left;font-weight:700;">구분</th>
      <th style="padding:4px 6px;font-size:9px;color:#075985;text-align:right;font-weight:700;">금리</th>
      <th style="padding:4px 6px;font-size:9px;color:#075985;text-align:right;font-weight:700;">전월비</th>
    </tr>
    {_row("new_all_rate",    "신규취급액기준")}
    {_row("balance_rate",    "잔액기준")}
    {_row("new_balance_rate","신잔액기준")}
  </table>
  {('<div style="padding:6px 6px 4px;border-top:1px solid #e0f2fe;">' + trend + '</div>') if trend else
   '<div style="padding:6px;font-size:8px;color:#94a3b8;">추이: 값 입력 후 자동 생성</div>'}
</div>"""


def html_top_3box(data):
    bonds        = data.get("bonds", {})
    rate_history = data.get("rate_history", {})
    pf_rates     = data.get("pf_rates", [])
    cp_rates     = data.get("cp_rates", [])
    cofix        = data.get("cofix", [])

    box_a = _box_bond_rates(bonds, rate_history)
    box_b = _box_securitization(pf_rates, cp_rates)
    box_c = _box_cofix(cofix)

    return f"""
<tr><td style="background:#fff;padding:16px 22px;border-bottom:1px solid #e8edf4;">
  {sec_header("① ", "시황 요약", "#0f172a")}
  <div style="display:flex;gap:10px;align-items:flex-start;">
    <div style="flex:1;min-width:0;">{box_a}</div>
    <div style="flex:1;min-width:0;">{box_b}</div>
    <div style="flex:1;min-width:0;">{box_c}</div>
  </div>
</td></tr>"""


# ─── Section 2: 채권금리 추이 ─────────────────────────────────────

def _hist_at(hist, days_ago):
    """N일 전 값 — 날짜 기준 가장 가까운 과거값 반환"""
    if not hist:
        return None
    target = (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y%m%d")
    candidates = [(d, v) for d, v in hist if d <= target]
    return candidates[-1][1] if candidates else None


def _diff_s(curr, past):
    """현재 − 과거 차이 문자열 (색상 포함)"""
    if curr is None or past is None:
        return '<span style="color:#cbd5e1;">—</span>'
    d = round(curr - past, 3)
    clr = "#dc2626" if d > 0 else ("#16a34a" if d < 0 else "#64748b")
    sym = "▲" if d > 0 else ("▼" if d < 0 else "")
    return f'<span style="color:{clr};font-size:10px;">{sym}{abs(d):.2f}</span>'


def _build_rate_chart(rate_history, bonds):
    ITEMS = [
        ("cd_91",      "CD 91일",    "#06b6d4"),
        ("gov_3y",     "국고채 3Y",  "#3b82f6"),
        ("corp_aa_3y", "회사채 AA-", "#f59e0b"),
    ]
    has_data = any(rate_history.get(k) for k, _, _ in ITEMS)
    if not has_data:
        return '<div style="color:#94a3b8;font-size:11px;padding:8px 0;">이력 데이터 없음 — ECOS_API_KEY 확인</div>'

    rows = ""
    for key, label, color in ITEMS:
        hist  = rate_history.get(key, [])
        curr  = bonds.get(key, {}).get("value")
        curr_s = f"<b>{curr:.2f}%</b>" if curr is not None else "—"
        svg   = sparkline(hist, width=160, height=26, color=color)
        d30   = _diff_s(curr, _hist_at(hist, 30))
        d90   = _diff_s(curr, _hist_at(hist, 90))
        d180  = _diff_s(curr, _hist_at(hist, 180))
        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9;">
  <td style="padding:5px 8px;font-size:11px;font-weight:500;color:#334155;white-space:nowrap;">{label}</td>
  <td style="padding:5px 8px;">{svg}</td>
  <td style="padding:5px 8px;font-size:11px;color:#0f172a;text-align:right;white-space:nowrap;">{curr_s}</td>
  <td style="padding:5px 8px;text-align:right;white-space:nowrap;">{d30}</td>
  <td style="padding:5px 8px;text-align:right;white-space:nowrap;">{d90}</td>
  <td style="padding:5px 8px;text-align:right;white-space:nowrap;">{d180}</td>
</tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
  <tr style="background:#f8fafc;">
    <th style="padding:5px 8px;font-size:10px;color:#64748b;text-align:left;font-weight:700;">항목</th>
    <th style="padding:5px 8px;font-size:10px;color:#64748b;text-align:center;font-weight:700;">추이 (1년)</th>
    <th style="padding:5px 8px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">현재</th>
    <th style="padding:5px 8px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">30일전▲▼</th>
    <th style="padding:5px 8px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">90일전▲▼</th>
    <th style="padding:5px 8px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">180일전▲▼</th>
  </tr>
  {rows}
</table>"""


def html_rate_charts(data):
    bonds        = data.get("bonds", {})
    rate_history = data.get("rate_history", {})

    return f"""
<tr><td {SP}>
  {sec_header("② ", "채권금리 추이 (최근 1년)", "#475569")}
  {_build_rate_chart(rate_history, bonds)}
  <div style="font-size:9px;color:#94a3b8;margin-top:4px;">
    {badge('auto')} 한국은행 ECOS 일별 데이터 기준 &nbsp;|&nbsp; 전일비: 직전 영업일 대비
  </div>
</td></tr>"""


# ─── Section 3: 뉴스 ──────────────────────────────────────────────

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
                           text-decoration:none;">{title}</a>
  <span style="flex-shrink:0;font-size:10px;color:#94a3b8;white-space:nowrap;">{date}</span>
</div>"""
    return rows


def html_market_news(data):
    pf_news     = data.get("pf_news", [])
    policy_news = data.get("policy_news", [])

    return f"""
<tr><td {SP}>
  {sec_header("③ ", "부동산 금융시장 및 정책 동향", "#ec4899")}
  <div style="display:flex;gap:14px;">
    <div style="flex:1;">
      {sub_header(f"금융시장 뉴스 ({len(pf_news)}건)", "#1e40af")}
      {_news_list(pf_news, "#dbeafe", "#1e40af")}
      <div style="font-size:9px;color:#94a3b8;margin-top:6px;">
        {badge('auto')} Naver API · PF/브릿지론/ABCP/유동화/CP 키워드
      </div>
    </div>
    <div style="flex:1;border-left:1px solid #f1f5f9;padding-left:14px;">
      {sub_header(f"부동산 정책 뉴스 ({len(policy_news)}건)", "#059669")}
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
      컬럼: type(도시정비/PF/브릿지론) · party(당사/타사) · borrower(조달주체) ·
      guarantee_type(HUG/연대보증/책임준공/기타) · rate_pct · maturity ·
      project_name · amount_bn · remark · as_of_date · source
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
        t      = d.get("type", "")
        bg, fg = TYPE_STYLE.get(t, ("#f3f4f6", "#374151"))
        party  = d.get("party", "")
        borrower = d.get("borrower", "")
        guar   = d.get("guarantee_type", "")
        rp     = d.get("rate_pct", "")
        rate_s = f"{float(rp):.2f}%" if rp and str(rp).strip() else "—"
        mat    = d.get("maturity", "")
        proj   = d.get("project_name", "")
        amt    = d.get("amount_bn", "")
        amt_s  = f"{amt}억" if amt and str(amt).strip() else "—"
        rmk    = d.get("remark", "")
        src    = d.get("source", "")
        aod    = d.get("as_of_date", "")

        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9;">
  <td style="padding:5px 7px;white-space:nowrap;">
    <span style="background:{bg};color:{fg};font-size:10px;font-weight:700;
                 padding:2px 5px;border-radius:3px;">{t}</span>
  </td>
  <td style="padding:5px 7px;font-size:11px;color:#374151;white-space:nowrap;">{party}</td>
  <td style="padding:5px 7px;font-size:11px;color:#374151;">{borrower}</td>
  <td style="padding:5px 7px;font-size:11px;color:#374151;white-space:nowrap;">{guar}</td>
  <td style="padding:5px 7px;font-size:12px;font-weight:700;color:#b45309;
             text-align:right;white-space:nowrap;">{rate_s}</td>
  <td style="padding:5px 7px;font-size:11px;text-align:right;white-space:nowrap;">{mat}</td>
  <td style="padding:5px 7px;font-size:11px;color:#0f172a;">{proj}</td>
  <td style="padding:5px 7px;font-size:11px;font-weight:600;
             text-align:right;white-space:nowrap;">{amt_s}</td>
  <td style="padding:5px 7px;font-size:10px;color:#64748b;">{rmk}</td>
  <td style="padding:5px 7px;font-size:9px;color:#94a3b8;white-space:nowrap;">{aod}</td>
</tr>"""

    return f"""
<tr><td {SP}>
  {sec_header("④ ", "Deal / 조달 사례 Watch", "#f59e0b")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
    <tr style="background:#f8fafc;">
      <th style="padding:5px 7px;font-size:10px;color:#64748b;text-align:left;font-weight:700;">구분</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;font-weight:700;">당사/타사</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;font-weight:700;">조달주체</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;font-weight:700;">보증형태</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">금리</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">만기</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;font-weight:700;">현장명</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;text-align:right;font-weight:700;">금액</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;font-weight:700;">비고</th>
      <th style="padding:5px 7px;font-size:10px;color:#64748b;font-weight:700;">기준일</th>
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
      <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:left;font-weight:700;">건설사</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:center;font-weight:700;">등급</th>
      <th style="padding:6px 10px;font-size:10px;color:#64748b;text-align:center;font-weight:700;">전망</th>
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
      {badge('auto')} AUTO: ECOS/Naver/은행연합회 자동수집 &nbsp;
      {badge('manual')} MANUAL: CSV 수동입력<br>
      본 리포트는 자동 생성된 내부 참고자료 — 최종 판단은 담당자 확인 필수
    </div>
    <div style="font-size:10px;color:#475569;text-align:right;">
      생성 {data['collected_at']}<br>
      pf-daily-mail v3.0
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
        html_top_3box(data)       +
        html_rate_charts(data)    +
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
