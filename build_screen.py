# -*- coding: utf-8 -*-
"""
СЪБОТНИЯТ ЕКРАН v2 — детерминистичен билдър (5 етажа).
Етаж 0 икономиката (сателит state.json: лещи + аномалии + брифинг) ·
Етаж 1 режимът (episodes CSV + data-core state READ-ONLY) ·
Етаж 2 гласовете (vote_consistency_13w.csv, [ВЪТРЕШЕН ПОГЛЕД]) ·
Етаж 3 платното (price-archive) · Етаж 4 разбивката на сектора (радар data.json + S10 матрица + bridge.json).
Числата пише САМО този код. Пише единствено в C:\\Projects\\_weekly_screen\\.

Ритуалната последователност (съботно): build_storms.py → build_screen.py → build_vrm_screen.py.
build_storms.py пише storms_state.json (именуваните бури, мандат №26); този билд го ЧЕТЕ
READ-ONLY за възел-картата на Етаж 1 (до режима). Зависимост само в тази посока.
"""
import json, csv, statistics
from collections import Counter
from pathlib import Path
from datetime import date as _date

ARCHIVE = Path(r"C:\Projects\price-archive\archive")
OUT = Path(r"C:\Projects\_weekly_screen")
SAT = Path(r"C:\Projects\dashboards\macro-satellite\docs\state.json")
BRIEF_DIR = Path(r"C:\Projects\dashboards\macro-satellite\briefings")
VOTES = Path(r"C:\Projects\_votes_retro_analytics\vote_consistency_13w.csv")
EPIS = Path(r"C:\Projects\_votes_retro_analytics\regime_episodes.csv")
DC = Path(r"C:\Projects\data-core\data\state")
BRIDGE = Path(r"C:\Projects\data-core\migrations\m_bridge\bridge.json")
RADAR = Path(r"C:\Projects\dashboards\SP500-rotationradar\docs\data.json")
BARO = Path(r"C:\Projects\_etf_remote\docs\barometer_feed.json")   # Ф-4: чете се директно при рендер; НЕ влиза в screen_data.json
STORMS_STATE = OUT / "storms_state.json"   # мандат №26: пише го build_storms.py; тук READ-ONLY за възел-картата на Етаж 1

WEEK_START, WEEK_END = "2026-07-06", "2026-07-10"
WEEK_LABEL = "W28 · 06–10.07.2026"
MONTH_TDAYS = 21

GROUPS = [
    ("Индекси", [("SPY","S&P 500"),("QQQ","Nasdaq 100"),("IWM","Russell 2000"),
                 ("DIA","Dow 30"),("EFA","Развити ex-US"),("EEM","Развиващи се")]),
    ("Облигации и кредит", [("TLT","Трежъри 20+г"),("IEF","Трежъри 7–10г"),("TIP","TIPS"),
                            ("LQD","IG кредит"),("HYG","HY кредит")]),
    ("Суровини и долар", [("GLD","Злато"),("SLV","Сребро"),("USO","Петрол WTI"),("CPER","Мед"),
                          ("DBC","Суровини широк"),("DBA","Селскостопански"),("UUP","Долар индекс")]),
    ("Сектори (SPDR)", [("XLK","Технологии"),("XLC","Комуникации"),("XLY","Потр. циклични"),
                        ("XLF","Финанси"),("XLI","Индустрия"),("XLB","Материали"),("XLE","Енергия"),
                        ("XLV","Здравеопазване"),("XLP","Потр. базови"),("XLU","Комунални"),("XLRE","Имоти")]),
    ("Индустрии и региони", [("SMH","Чипове (полупроводници)"),("EWY","Южна Корея")]),
]
# Ядрото на лицето на ЕТАЖ 3: постоянни редове, точно в този ред.
CORE = ["SPY","QQQ","IWM","TLT","GLD","USO","UUP"]
ETF2GICS = {"XLE":"Energy","XLB":"Materials","XLK":"Information Technology","XLV":"Health Care",
            "XLF":"Financials","XLY":"Consumer Discretionary","XLC":"Communication Services",
            "XLI":"Industrials","XLP":"Consumer Staples","XLU":"Utilities","XLRE":"Real Estate"}
LENS_BG = {"labor":"Труд","growth":"Растеж","inflation":"Инфлация","liquidity":"Ликвидност",
           "credit":"Кредит","external":"Външна","property":"Имоти"}
STATE_BG = {"OK":"Съгласен","WATCH":"Наблюдава","UNDER":"Против","OVER":"OVER"}
# ЕТАЖ 4 разбивка: рафтовете (quadrant_1m), цветовете и S10 присъдите.
# Стойностите на quadrant_1m се ЕНУМЕРИРАТ от данните; тук е само реда/абревиатурата/цвета.
QUAD_ORDER = ["Stable Winner","Quality Dip","Neutral","Faded Bounce","Chronic Loser"]
QUAD_ABBR  = {"Stable Winner":"SW","Quality Dip":"QD","Faded Bounce":"FB",
              "Chronic Loser":"CL","Neutral":"Neutral"}
QUAD_COLOR = {"Stable Winner":"var(--up)","Quality Dip":"var(--warn)","Faded Bounce":"var(--dn)",
              "Neutral":"#666","Chronic Loser":"#444"}   # останалите → сиви нюанси
VERDICT_BG = {"confirm":("ПОТВЪРЖДАВА","up"),"contradict-watch":("ВНИМАНИЕ","warn"),
              "contradict":("ПРОТИВОРЕЧИ","dn"),"no-trend":("БЕЗ ТРЕНД","muted")}

# ------------------------------------------------------------------ данни --
def load_rows(t):
    d = ARCHIVE / f"px_{t.lower()}_daily"; rows = []
    for y in ("2025","2026"):
        f = d / f"{y}.jsonl"
        if f.exists():
            rows += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: r["as_of"]); return rows

def pct(a,b): return (a/b-1.0)*100.0

def calc(t):
    rows = load_rows(t)
    if not rows: return None
    week = [r for r in rows if WEEK_START <= r["as_of"] <= WEEK_END]
    before = [r for r in rows if r["as_of"] < WEEK_START]
    if not week or not before: return None
    prev = before[-1]; wc = week[-1]["close"]
    lo, hi = min(r["low"] for r in week), max(r["high"] for r in week)
    wk = {"chg":pct(wc,prev["close"]),"lo":pct(lo,prev["close"]),"hi":pct(hi,prev["close"]),
          "pos":(wc-lo)/(hi-lo)*100.0 if hi>lo else 50.0,"prev_date":prev["as_of"],
          "provisional":any(r.get("provisional") for r in week)}
    upto = [r for r in rows if r["as_of"] <= WEEK_END]; mo=None
    if len(upto) >= MONTH_TDAYS+1:
        base = upto[-(MONTH_TDAYS+1)]; win = upto[-MONTH_TDAYS:]
        l,h = min(r["low"] for r in win), max(r["high"] for r in win)
        mo = {"chg":pct(win[-1]["close"],base["close"]),"lo":pct(l,base["close"]),
              "hi":pct(h,base["close"]),"pos":(win[-1]["close"]-l)/(h-l)*100.0 if h>l else 50.0}
    return {"week":wk,"month":mo}

def weekly_z(t):
    """Седмичен z по метода на сателита (analytics/z_scores.weekly_z):
    седмични затваряния = последният daily запис по as_of във всяка ISO седмица (пон-нед) ≤ WEEK_END;
    седмични промени в % между съседни седмици;
    текущата промяна (W28) срещу mean/std на предходните 13 седмични промени.
    std = population (pstdev, ddof=0) — точно както сателитът (statistics.pstdev).
    Връща None ако няма ≥14 седмични промени (13 baseline + текуща)."""
    rows = load_rows(t)
    if not rows: return None
    byweek = {}
    for r in rows:
        if r["as_of"] > WEEK_END: continue
        y,m,d = (int(x) for x in r["as_of"].split("-"))
        key = _date(y,m,d).isocalendar()[:2]           # (ISO year, ISO week)
        if key not in byweek or r["as_of"] > byweek[key]["as_of"]:
            byweek[key] = r
    closes = [byweek[k]["close"] for k in sorted(byweek)]
    if len(closes) < 15: return None
    chgs = [(closes[i]/closes[i-1]-1.0)*100.0 for i in range(1,len(closes))]
    cur = chgs[-1]; base = chgs[-14:-1]                # 13 промени, точно преди текущата
    if len(base) != 13: return None
    m = statistics.fmean(base); s = statistics.pstdev(base)
    if s == 0: return None
    return (cur - m)/s

def load_satellite():
    s = json.load(open(SAT, encoding="utf-8"))
    return s

def load_brief_tldr():
    f = BRIEF_DIR / "2026-W28.md"
    if not f.exists(): return []
    lines = f.read_text(encoding="utf-8").splitlines()
    out, on = [], False
    for l in lines:
        if l.startswith("## TL;DR"): on=True; continue
        if on and l.startswith("---"): break
        if on and l.strip().startswith("- "): out.append(l.strip()[2:])
    return out

def load_votes():
    rows = list(csv.DictReader(open(VOTES, encoding="utf-8-sig")))
    for r in rows:
        r["ok_pct"]=float(r["ok_pct"]); r["under_pct"]=float(r["under_pct"])
        r["flips"]=int(r["flips"]); r["end_streak"]=int(r["end_streak"])
    return sorted(rows, key=lambda r:-r["ok_pct"])

def load_age():
    rows = list(csv.DictReader(open(EPIS, encoding="utf-8-sig")))
    cur = rows[-1]
    refl = [int(r["weeks"]) for r in rows if r["regime"]=="REFLATION"]
    return {"regime":cur["regime"],"start":cur["start"],"age":int(cur["weeks"]),
            "asof":cur["end"],"median":statistics.median(refl),"max":max(refl),"n":len(refl)}

def last(f): d=json.load(open(DC/f,encoding="utf-8")); return d[-1] if isinstance(d,list) else d

def load_core():
    vel, ov, dv = last("vrm_ks_velocity.json"), last("vrm_overlay.json"), last("vrm_b6_divergence.json")
    ks = last("vrm_ks_state.json")
    return {"margin":vel["margin_pct"],"ks_asof":vel["as_of"],"ks_active":ks["active"],
            "gms":ov["gms"],"align":ov["alignment_score"],
            "align_total":len(ov["alignment_flags"]),"vrm_asof":ov["as_of"],
            "s11_net":dv["confirmation"]["net_confirm"],"s11":dv["confirmation"]["counts"],
            "s10":"ПОТВЪРЖДАВА" if json.load(open(DC/"vrm_confirmation_matrix.json",encoding="utf-8"))[-1]["assets"]["etf_spy"]["confluence"]["verdict"]=="confirm" else "ВНИМАНИЕ"}

def load_bridge():
    return json.load(open(BRIDGE, encoding="utf-8"))

def load_radar():
    return json.load(open(RADAR, encoding="utf-8"))

def load_matrix_last():
    d = json.load(open(DC/"vrm_confirmation_matrix.json", encoding="utf-8"))
    return d[-1]["assets"]

def load_barometer():
    """Ф-4 чекмеджето: barometer_feed.json READ-ONLY при рендер. Липсващ/счупен feed →
    None (честен fallback ред, билдът НЕ крашва). Нищо оттук не влиза в screen_data.json."""
    try:
        d = json.load(open(BARO, encoding="utf-8"))
        assert d.get("snapshot") and d.get("confluence") and d.get("as_of")
        return d
    except Exception:
        return None

def load_storms():
    """Именуваните бури (мандат №26): storms_state.json, писан от build_storms.py, READ-ONLY.
    Липсва/счупен → честен празен ред (нула бури). Нищо оттук не влиза в screen_data.json."""
    try:
        d = json.load(open(STORMS_STATE, encoding="utf-8"))
        assert isinstance(d.get("storms"), list)
        return d
    except Exception:
        return {"as_of": None, "storms": []}

# Барометърът (Ф-4): преводите на дисплея. Зоните/семействата се ЕНУМЕРИРАТ от feed-а;
# тук е само човешката дума + цветът.
BARO_ZONE = {"base":("база","firm"),"gray":("сива","swing"),"alarm":("тревога","against")}
BARO_TREND = {"up":"расте ↑","down":"пада ↓","flat":"плоско →"}
BARO_GROUP_BG = {"credit":"кредит","volatility":"волатилност","infl_rates":"инфлация/лихви",
                 "risk_appetite":"риск-апетит","growth_value":"растеж/стойност"}

def barometer_card(baro):
    """Картата „ТЪЛПАТА (Барометърът)" в зоната на ЕТАЖ 3. Изводът-ред се ГЕНЕРИРА от
    direction_grouped + броячите + кривата — нула хардкоднати числа."""
    link = '<a class="dlink" href="https://tsvetoslavtsachev.github.io/ETF-rotationradar/" target="_blank">пълният радар →</a>'
    if baro is None:
        return ('<div class="slot">ТЪЛПАТА (Барометърът): барометърът недостъпен — '
                f'barometer_feed.json не се чете · {link}</div>')
    snap = baro["snapshot"]; conf = baro["confluence"]
    total = len(snap)
    base_n = conf.get("base_count", sum(1 for s in snap if s.get("zone")=="base"))
    agc = conf.get("alarm_group_count", 0)
    ag = conf.get("alarm_groups") or []
    dg = conf.get("direction_grouped")
    ctx = conf.get("context_rows") or {}
    t10 = ctx.get("t10y2y") or {}
    gld = ctx.get("gld_tlt") or {}
    y,m,d_ = baro["as_of"].split("-"); asof = f"{d_}.{m}.{y}"
    # изводът-ред (от данните)
    word = {"base":"спокойна","alarm":"струпана в тревога"}.get(dg, "разделена")
    groups_txt = (f'{agc} фактор-семейства в тревога'
                  + (f' ({", ".join(BARO_GROUP_BG.get(g,g) for g in ag)})' if ag else ''))
    curve_txt = f' · кривата: {t10["label"]}' if t10.get("label") else ''
    verdict = (f'Тълпата е <b>{word}</b> — {base_n}/{total} индикатора в база, '
               f'{groups_txt}{curve_txt}.')
    # таблицата на 10-те гласа
    rows=[]
    for s in snap:
        zw, zc = BARO_ZONE.get(s.get("zone"), (s.get("zone","?"), "neutral"))
        tw = BARO_TREND.get(s.get("trend"), s.get("trend","?"))
        tip = f'стойност {s.get("value")} · z {s.get("z")} · тип {s.get("kind")}'
        rows.append(f'<tr title="{tip}"><td class="nm">{s["indicator"]}</td>'
                    f'<td><span class="badge2 {zc}">{zw}</span></td>'
                    f'<td class="v">{tw}</td></tr>')
    head = ('<tr><th title="10-те поведенчески индикатора — гласовете на тълпата (позициониране и сентимент)">Индикатор</th>'
            '<th title="Зоната по праговете на уреда: база = в нормалната си зона · сива = междинна · тревога = отвъд тревожния праг (abs или robust-z)">Зона</th>'
            '<th title="4-седмичната посока на самия индикатор (не е добро/лошо само по себе си)">Тренд</th></tr>')
    # контекстните редове — отделени, НЕ гласове
    ctx_rows=[]
    if gld:
        gzw, gzc = BARO_ZONE.get(gld.get("zone"), (gld.get("zone","?"),"neutral"))
        ctx_rows.append(f'<div class="meta">GLD/TLT: <span class="badge2 {gzc}">{gzw}</span> · {gld.get("note","")}</div>')
    if t10:
        tzw, tzc = BARO_ZONE.get(t10.get("zone"), (t10.get("zone","?"),"neutral"))
        ctx_rows.append(f'<div class="meta">Кривата 2s10s: <b>{t10.get("label","?")}</b> ({t10.get("value","?")}) '
                        f'<span class="badge2 {tzc}">{tzw}</span> · {t10.get("note","")}</div>')
    ctx_html = ('<div class="bctx"><b>Контекст, не глас</b> — двата реда оцветяват прочита, не влизат в брояча:'
                + "".join(ctx_rows) + '</div>') if ctx_rows else ''
    return (f'<details class="baro"><summary><span class="bk">ТЪЛПАТА (Барометърът) '
            f'<span class="tag">наблюдение, не сигнал</span> <span class="small">до {asof} · клик за 10-те гласа</span></span>'
            f'<span class="bl">{verdict}</span></summary>'
            f'<table class="scr bscr">{head}{"".join(rows)}</table>'
            f'{ctx_html}'
            f'<div class="foot">Зоните и семействата идват от feed-а на Барометъра (ETF радара) — confluence-ът се чете като '
            f'капитулационен/контрариан маркер, не изпреварващо предупреждение · {link}</div></details>')

def sector_breakdown(gics, etf, radar, mtx):
    """Разбивката на един сектор (READ-ONLY): рафтове, ротация, дисперсия, ножове, S10.
    members = членовете на сектора от rank_all_stocks (филтър sector == GICS)."""
    members = [s for s in radar["rank_all_stocks"] if s.get("sector") == gics]
    N = len(members)
    cnt = Counter(m["quadrant_1m"] for m in members)          # стойностите — от данните
    ordered = ([q for q in QUAD_ORDER if cnt.get(q,0) > 0]
               + [q for q in cnt if q not in QUAD_ORDER and cnt[q] > 0])
    shelves = [(q, cnt[q]) for q in ordered]
    sr = next((r for r in radar["sector_rotation"] if r.get("sector") == gics), None)
    scores = sorted(m["score"] for m in members)
    med  = statistics.median(scores) if scores else 0.0
    top3 = statistics.fmean(scores[-3:]) if scores else 0.0
    bot3 = statistics.fmean(scores[:3])  if scores else 0.0
    knives = sum(1 for m in members
                 if m["quadrant_1m"] == "Quality Dip" and m["abs_strength"] < 50)  # Е6б
    s10 = mtx.get("etf_" + etf.lower())
    return {"gics":gics,"etf":etf,"members":N,"shelves":shelves,
            "rotation":sr,"median":med,"top3":top3,"bot3":bot3,"knives":knives,"s10":s10}

def _tok_color(q):
    c = QUAD_COLOR.get(q, "#555")
    return c if c.startswith("var(") else "var(--ink2)"   # сивите → четим текст, не дим

def breakdown_html(bd):
    segs = "".join(
        f'<span class="seg" style="flex:{c};background:{QUAD_COLOR.get(q,"#555")}" '
        f'title="{QUAD_ABBR.get(q,q)} {c}"></span>' for q,c in bd["shelves"])
    toks = " · ".join(
        f'<span style="color:{_tok_color(q)}">{c} {QUAD_ABBR.get(q,q)}</span>'
        for q,c in bd["shelves"])
    rows = [f'<div class="stack" title="състав по рафтове (1м квадрант, {bd["members"]} члена)">{segs}</div>',
            f'<div class="meta"><b>Състав</b> · {bd["members"]} имена: {toks}</div>']
    sr = bd["rotation"]
    if sr:
        rows.append(f'<div class="meta"><b>Ротация</b> · Δранг 1м {sr["mean_delta_1m"]:+.1f} · '
                    f'{sr["n_risers"]}↑/{sr["n_decayers"]}↓ от {sr["n_total"]}</div>')
    else:
        rows.append('<div class="meta"><b>Ротация</b> · няма ред в sector_rotation</div>')
    rows.append(f'<div class="meta"><b>Дисперсия</b> · медиана {bd["median"]:.0f} · '
                f'топ3 {bd["top3"]:.0f} / дъно3 {bd["bot3"]:.0f}</div>')
    n = bd["knives"]
    kv = f'<span class="b dn">{n}</span>' if n > 0 else f'{n}'
    rows.append(f'<div class="meta"><b>Ножове</b> <span class="small">(QD &amp; abs&lt;50)</span> · {kv}</div>')
    row = bd["s10"]
    if row:
        t = (row.get("trend") or {}).get("label","?")
        m = row.get("momentum") or {}
        mlab = m.get("label","?"); dvg = m.get("divergence","none")
        if dvg not in (None,"none") and dvg not in (mlab or ""):
            mlab = f'{mlab} ({dvg})'
        vo = (row.get("volatility") or {}).get("label","?")
        vd = (row.get("confluence") or {}).get("verdict","?")
        vtxt, vcol = VERDICT_BG.get(vd, (vd, "muted"))
        rows.append(f'<div class="meta"><b>S10</b> · {bd["etf"]}: тренд {t} · момент {mlab} · '
                    f'вол {vo} → <span class="b {vcol}">{vtxt}</span></div>')
    else:
        rows.append(f'<div class="meta"><b>S10</b> · {bd["etf"]}: няма ред за този ETF '
                    f'<span class="small">(матрицата покрива 9 сектора, без XLC/XLRE)</span></div>')
    return '<div class="brk">' + "".join(rows) + '</div>'

# ------------------------------------------------------------------ помощни --
def x(v,lo,hi): return (v-lo)/(hi-lo)*100.0

def bar(seg,lo,hi):
    if seg is None: return '<div class="track"><span class="na">n/a</span></div>'
    s = "up" if seg["chg"]>=0 else "dn"
    l,r,c,z = x(seg["lo"],lo,hi),x(seg["hi"],lo,hi),x(seg["chg"],lo,hi),x(0,lo,hi)
    tip = f"диапазон {seg['lo']:+.2f}% … {seg['hi']:+.2f}% · затваряне {seg['chg']:+.2f}% · позиция {seg['pos']:.0f}%"
    return (f'<div class="track" title="{tip}"><div class="zero" style="left:{z:.2f}%"></div>'
            f'<div class="range {s}" style="left:{l:.2f}%;width:{max(r-l,0.6):.2f}%"></div>'
            f'<div class="dot {s}" style="left:{c:.2f}%"></div></div>')

def badge(seg):
    if seg is None: return '<span class="b muted">—</span>'
    s = "up" if seg["chg"]>=0 else "dn"
    return f'<span class="b {s}">{seg["chg"]:+.2f}%</span><span class="pos">{seg["pos"]:.0f}%</span>'

CSS = """
:root{--srf:#1a1a19;--pg:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;
--ax:#383835;--up:#0ca30c;--dn:#d03b3b;--warn:#fab219;--ring:rgba(255,255,255,.1)}
*{box-sizing:border-box}body{margin:0;background:var(--pg);color:var(--ink);
font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding:20px}
.wrap{max-width:1060px;margin:0 auto}
h1{font-size:19px;margin:0 0 2px}.sub{color:var(--ink2);font-size:13px;margin-bottom:14px}
.prov{border:1px solid var(--warn);color:var(--warn);border-radius:9px;padding:1px 8px;font-size:12px;margin-left:8px;cursor:help}
.tag{border:1px solid var(--ring);color:var(--mut);border-radius:9px;padding:1px 8px;font-size:11.5px;margin-left:6px}
.hero{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 16px}
.tile{background:var(--srf);border:1px solid var(--ring);border-radius:10px;padding:10px 14px;min-width:150px}
.tile .k{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.4px}
.tile .n{font-size:20px;font-weight:650;margin-top:2px}.tile .m{color:var(--ink2);font-size:12px}
.n.up,.b.up{color:var(--up)}.n.dn,.b.dn{color:var(--dn)}.b.warn{color:var(--warn)}
.floor{background:var(--srf);border:1px solid var(--ring);border-radius:12px;padding:14px 16px;margin-bottom:14px}
.fh{display:flex;align-items:baseline;gap:10px;margin-bottom:10px}
.fh .n{color:var(--mut);font-size:11px;letter-spacing:1px}.fh .t{font-weight:700;font-size:15px}
.fh .d{color:var(--mut);font-size:12px;margin-left:auto;cursor:help}
.lens4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.lcard{border:1px solid var(--ring);border-radius:12px;padding:12px 14px;cursor:pointer;background:#151514;transition:border-color .15s}
.lcard:hover,.lcard.open{border-color:var(--warn)}
.lcard .rg{font-size:15px;font-weight:700;margin:2px 0 1px}
.lcard .reg{color:var(--mut);font-size:10.5px;letter-spacing:.8px}
.mini{display:flex;gap:4px;margin-top:8px}
.mini .m{flex:1;position:relative;height:46px;background:#0f0f0e;border-radius:4px}
.mini .m i{position:absolute;left:0;right:0;bottom:0;border-radius:4px;background:var(--ink2);opacity:.4}
.mini .m b{position:absolute;left:0;right:0;bottom:2px;text-align:center;font-size:9px;color:var(--mut);font-weight:600}
.mini .m u{position:absolute;left:0;right:0;top:2px;text-align:center;font-size:9.5px;color:var(--ink2);text-decoration:none}
.dvg{display:inline-block;margin-top:8px;border:1px solid var(--ring);border-radius:8px;padding:0 7px;font-size:11px;color:var(--warn)}
.drawer{display:none;border:1px solid var(--warn);border-radius:12px;padding:14px 16px;margin-top:10px;background:#151514}
.drawer.on{display:block}
.drawer h4{margin:10px 0 6px;font-size:12px;color:var(--mut);letter-spacing:.5px;text-transform:uppercase}
.drawer h4:first-child{margin-top:0}
.brief{color:var(--ink2);font-size:13px;border-left:2px solid var(--ax);padding-left:10px;margin:4px 0}
.dlink{color:var(--warn);font-size:12px;text-decoration:none}
.row{display:grid;grid-template-columns:220px 1fr 165px;gap:12px;align-items:center;padding:4px 0;border-bottom:1px solid var(--grid)}
.row:last-child{border-bottom:none}
.nm{white-space:nowrap;font-size:13px}.nm .t{font-weight:700;margin-right:6px}
.small{color:var(--mut);font-size:11.5px}
.lk a{color:var(--mut);font-size:11px;margin-left:5px;text-decoration:none;border:1px solid var(--ring);border-radius:4px;padding:0 4px}
.lk a:hover{color:var(--ink)}
.track{position:relative;height:16px;background:#0f0f0e;border-radius:8px;cursor:help}
.zero{position:absolute;top:0;bottom:0;width:1px;background:var(--ax)}
.mark{position:absolute;top:0;bottom:0;width:1px;background:var(--mut)}
.range{position:absolute;top:5px;height:6px;border-radius:4px;opacity:.55}
.range.up{background:var(--up)}.range.dn{background:var(--dn)}.range.warn{background:var(--warn)}
.dot{position:absolute;top:50%;width:9px;height:9px;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 0 2px #151514}
.dot.up{background:var(--up)}.dot.dn{background:var(--dn)}.dot.warn{background:var(--warn)}.dot.neu{background:#c3c2b7}
.v{font-variant-numeric:tabular-nums;font-size:13px;white-space:nowrap}
.b{font-weight:650}.b.muted{color:var(--mut)}
.pos{color:var(--mut);font-size:11.5px;margin-left:7px}
.na{color:var(--mut);font-size:12px;padding-left:8px}
.badge2{border-radius:8px;padding:0 7px;font-size:11.5px;border:1px solid var(--ring);color:var(--ink2)}
.badge2.firm{color:var(--up);border-color:var(--up)}
.badge2.against{color:var(--dn);border-color:var(--dn)}
.badge2.swing{color:var(--warn);border-color:var(--warn)}
.slot{border:1px dashed var(--ax);border-radius:9px;padding:8px 12px;color:var(--mut);font-size:12.5px;margin-top:8px}
.cards2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.scard{border:1px solid var(--ring);border-radius:10px;padding:10px 12px;background:#151514}
.scard h3{margin:0 0 6px;font-size:14px}
.scard .meta{color:var(--mut);font-size:11.5px;margin-top:6px}
.cand{display:flex;gap:8px;align-items:center;padding:3px 0;font-size:13px}
.cand .t{font-weight:700;width:50px}
.rank{flex:1;position:relative;height:10px;background:#0f0f0e;border-radius:5px}
.rank .fill{position:absolute;top:2px;bottom:2px;left:0;background:var(--up);opacity:.55;border-radius:4px}
.rank .dt{position:absolute;top:50%;width:8px;height:8px;border-radius:50%;transform:translate(-50%,-50%);background:var(--up);box-shadow:0 0 0 2px #151514}
.stack{display:flex;gap:2px;height:14px;border-radius:4px;margin:2px 0 5px;overflow:hidden}
.stack .seg{min-width:2px;border-radius:2px}
table.scr{width:100%;border-collapse:collapse}
.scr th{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.4px;font-weight:600;text-align:left;padding:9px 10px;border-bottom:1px solid var(--grid);cursor:help}
.scr td{padding:5px 10px;border-bottom:1px solid var(--grid)}
.scr tr:last-child td{border-bottom:none}
.ghead td{background:#151514;color:var(--ink2);font-weight:650;font-size:12.5px;letter-spacing:.3px;padding:7px 10px}
.scr .nm{width:220px}.scr .c{width:290px}.scr .v{width:110px}
.legend{display:flex;gap:18px;align-items:center;color:var(--ink2);font-size:12.5px;margin:12px 2px}
details{margin-top:16px;color:var(--ink2)}summary{cursor:pointer;color:var(--mut)}
table.flat{border-collapse:collapse;margin-top:8px;font-variant-numeric:tabular-nums;font-size:12.5px}
.flat td,.flat th{border:1px solid var(--grid);padding:3px 8px;text-align:right}
.flat td:first-child,.flat td:nth-child(2){text-align:left}
.foot{color:var(--mut);font-size:11.5px;margin-top:8px}
/* ── Барометър-чекмеджето (Ф-4): малка карта в стила на лещи-картите ── */
.baro{border:1px solid var(--ring);border-radius:12px;background:#151514;padding:10px 14px;margin-top:12px;transition:border-color .15s}
.baro:hover,.baro[open]{border-color:var(--warn)}
.baro>summary{list-style:none;cursor:pointer}
.baro>summary::-webkit-details-marker{display:none}
.baro .bk{display:block;color:var(--mut);font-size:11px;letter-spacing:.8px;text-transform:uppercase}
.baro .bk .tag{text-transform:none;letter-spacing:0}
.baro .bl{display:block;font-size:13.5px;margin-top:4px;color:var(--ink2)}
.baro .bl b{color:var(--ink)}
.baro table.bscr{margin-top:10px}
.baro .bscr td{font-size:12.5px}
.baro .bctx{border:1px dashed var(--ax);border-radius:9px;padding:8px 12px;margin-top:10px;font-size:12px;color:var(--ink2)}
.baro .bctx .meta{color:var(--mut);font-size:11.5px;margin-top:4px}
/* ── Възел-картата на именуваните бури (мандат №26, спец §5) ── */
.storms{border:1px solid var(--ring);border-radius:12px;background:#151514;padding:11px 14px;margin-top:12px}
.storms .sh{margin-bottom:6px}
.storms .sk{display:block;color:var(--mut);font-size:11px;letter-spacing:.8px;text-transform:uppercase}
.storms .sk .tag{text-transform:none;letter-spacing:0}
.sverdict{font-size:13.5px;color:var(--ink);margin:4px 0 2px}
.storm{border:1px solid var(--ring);border-radius:10px;padding:9px 12px;margin-top:9px;background:#191918}
.storm .sth{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.storm .sth .small{margin-left:auto}
.sconds{margin:4px 0 6px}
.scond{display:flex;align-items:baseline;gap:6px;padding:2px 0;font-size:12.5px;cursor:help}
.scond .ck{font-weight:700}.scond .ck.up{color:var(--up)}.scond .ck.dn{color:var(--dn)}
.scond .sl{color:var(--ink2)}.scond .sv{color:var(--mut)}
.sfals{font-size:12px;color:var(--ink2);border-left:2px solid var(--ax);padding-left:9px;margin-top:5px}
.sfals b{color:var(--mut)}
.sfoot{color:var(--mut);font-size:11.5px;margin-top:8px}
/* ── Работната врата (М19): тънка топ-лента, стил на страницата ── */
.topnav{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:6px;flex-wrap:wrap;
background:var(--pg);border-bottom:1px solid var(--ring);margin:-20px 0 16px;padding:9px 0}
.nvbrand{font-size:11px;letter-spacing:.5px;color:var(--mut);font-weight:700;text-transform:uppercase;margin-right:4px}
.topnav a{color:var(--ink2);text-decoration:none}
.nvlink{font-size:12.5px;padding:5px 10px;border:1px solid var(--ring);border-radius:8px;background:var(--srf)}
.nvlink:hover{border-color:var(--warn);color:var(--ink)}
.nvgrp{position:relative}
.nvgrp>summary{list-style:none;cursor:pointer;font-size:12.5px;padding:5px 10px;border:1px solid var(--ring);
border-radius:8px;background:var(--srf);color:var(--ink2);user-select:none}
.nvgrp>summary::-webkit-details-marker{display:none}
.nvgrp>summary::after{content:" \\25BE";color:var(--mut)}
.nvgrp[open]>summary{border-color:var(--warn);color:var(--ink)}
.nvpop{position:absolute;top:calc(100% + 4px);left:0;z-index:60;display:flex;flex-direction:column;gap:1px;
min-width:220px;background:var(--srf);border:1px solid var(--ring);border-radius:10px;padding:6px;
box-shadow:0 8px 24px rgba(0,0,0,.5)}
.nvpop a{font-size:12.5px;padding:6px 9px;border-radius:6px;white-space:nowrap}
.nvpop a:hover{background:#232322;color:var(--ink)}
.nvpop .nvhead{font-size:10px;letter-spacing:.5px;text-transform:uppercase;color:var(--mut);padding:6px 9px 2px}
.nvmut{color:var(--mut);font-size:11px}
"""

JS = """
function dr(id, card){
  var d=document.getElementById('dr-'+id);
  var was=d.classList.contains('on');
  document.querySelectorAll('.drawer').forEach(function(x){x.classList.remove('on')});
  document.querySelectorAll('.lcard').forEach(function(x){x.classList.remove('open')});
  if(!was){d.classList.add('on');card.classList.add('open');}
}
/* Работната врата: отвориш ли едно чекмедже, другите се затварят; клик навън затваря. */
document.querySelectorAll('.nvgrp').forEach(function(d){
  d.addEventListener('toggle',function(){
    if(d.open){document.querySelectorAll('.nvgrp').forEach(function(o){if(o!==d)o.open=false;});}
  });
});
document.addEventListener('click',function(e){
  if(!e.target.closest('.nvgrp')){document.querySelectorAll('.nvgrp[open]').forEach(function(o){o.open=false;});}
});
"""

# ── Работната врата (М19): статична навигационна лента. Двата дома се линкват взаимно
# (витрината → тук; тук → витрината). Светофарите = живите GitHub Pages сензори;
# флотата = локалните табла (портове от .claude/launch.json); щабът = Obsidian таблото.
NAV = """<nav class="topnav" aria-label="Работната врата — навигация">
<span class="nvbrand">Работната врата</span>
<a class="nvlink" href="vrm.html" title="VRM екранът — режимното ядро (зад VRM картата)">VRM екран</a>
<a class="nvlink" href="https://regime-compass.pages.dev" target="_blank" rel="noopener" title="Режимният компас — позиция (компас) и скорост (VRM) върху квадранта растеж×инфлация; съботен CI инджест">Режимен компас</a>
<details class="nvgrp"><summary>Светофари</summary><div class="nvpop">
<div class="nvhead">живи сензори · GitHub Pages</div>
<a href="https://tsvetoslavtsachev.github.io/treasury-funding-radar/" target="_blank" rel="noopener">Funding радар — доларова ликвидност</a>
<a href="https://tsvetoslavtsachev.github.io/ai-hype-monitor/" target="_blank" rel="noopener">AI Hype монитор</a>
<a href="https://tsvetoslavtsachev.github.io/collectors/" target="_blank" rel="noopener">Петрол (Два часовника)</a>
</div></details>
<details class="nvgrp"><summary>Флота</summary><div class="nvpop">
<div class="nvhead">публични табла · GitHub Pages</div>
<a href="https://tsvetoslavtsachev.github.io/macro-web-dashboard/" target="_blank" rel="noopener">Макро web · 8765</a>
<a href="https://tsvetoslavtsachev.github.io/SP500-momentumrank/" target="_blank" rel="noopener">Моментум US (S&amp;P 500) · 8141</a>
<a href="https://tsvetoslavtsachev.github.io/stoxx600-momentumrank/" target="_blank" rel="noopener">Моментум EU (STOXX 600) · 8142</a>
<a href="https://tsvetoslavtsachev.github.io/SP500-rotationradar/" target="_blank" rel="noopener">Ротация US (S&amp;P 500) · 8143</a>
<a href="https://tsvetoslavtsachev.github.io/STOXX600-rotationradar/" target="_blank" rel="noopener">Ротация EU (STOXX 600) · 8144</a>
<a href="https://tsvetoslavtsachev.github.io/cot-monitor/" target="_blank" rel="noopener">COT монитор · 8771</a>
<a href="https://tsvetoslavtsachev.github.io/stock-selection-dashboard/" target="_blank" rel="noopener">Stock selection · 8130</a>
<a href="https://tsvetoslavtsachev.github.io/ETF-rotationradar/" target="_blank" rel="noopener">ETF радар · 8137</a>
<a href="https://tsvetoslavtsachev.github.io/us-macro-dashboard/" target="_blank" rel="noopener">Брифинг US · 8773</a>
<a href="https://tsvetoslavtsachev.github.io/china-macro-dashboard/" target="_blank" rel="noopener">Брифинг Китай · 8774</a>
<a href="https://tsvetoslavtsachev.github.io/eu-macro-dashboard/" target="_blank" rel="noopener">Брифинг EU · 8775</a>
</div></details>
<a class="nvlink" href="glossary.html" title="Единният речник на вътрешните кодове (канонът §1, правило 4)">Речник</a>
<details class="nvgrp"><summary>Щаб</summary><div class="nvpop">
<div class="nvhead">tsachev-ops · локални файлове</div>
<a href="file:///C:/Tsachev%20Knowledge%20OS/tsachev-ops/Dashboard/index.html" title="Щабското табло (Obsidian)">Щаб табло</a>
<a href="file:///C:/Tsachev%20Knowledge%20OS/tsachev-ops/chronicle/" title="Папката на съботната хроника (.md файловете се отварят като текст)">Хроника (съботният дневник)</a>
</div></details>
<a class="nvlink" href="https://tsvetoslavtsachev.github.io/projects-overview/" target="_blank" rel="noopener" title="Публичната витрина — фоайето">Витрина</a>
</nav>
"""

# ------------------------------------------------------------------ етажи --
def lens_face(key, reg_label, asof_note, lenses, dvg_html):
    bars = "".join(
        f'<span class="m" title="{LENS_BG.get(k,k)} {v:.1f} · health-скор 0–100 (50 = близката норма; над 50 по-здраво, под 50 по-зле)"><i style="height:{max(min(v,100),3):.0f}%"></i>'
        f'<b>{LENS_BG.get(k,k)[:2].upper()}</b></span>' for k,v in lenses)
    return (f'<div class="lcard" onclick="dr(\'{key}\',this)"><div class="reg">{asof_note}</div>'
            f'<div class="rg">{reg_label}</div><div class="mini">{bars}</div>{dvg_html}</div>')

def anomaly_rows(items):
    # Магнитуден измерител: лентата е |z| (размерът на отклонението), НЕ биполярна ос.
    # Знакът/посоката (нагоре/надолу) не е в този канал — feed-ът носи само avg/max(|z|).
    ZMAX = 6.0                       # скала 0 → 6σ (конвенцията за клип на скора)
    thr = 2.0 / ZMAX * 100           # праг за влизане |z| ≥ 2
    out=[]
    for a in items:
        z=a["mean_abs_z"]; mx=a["max_abs_z"]
        w = min(z / ZMAX * 100, 100)
        new=' · НОВ екстремум' if a.get("new_extreme") else ''
        tip=(f"|z| средно {z:.2f} (макс {mx:.2f}) · размер на отклонението в σ спрямо близката норма — "
             f"по-високо = по-необичайно движение · лентата показва средното |z|; праг за влизане: макс |z| ≥ 2 · "
             f"без посока (нагоре/надолу): виж дашборда")
        out.append(f'<div class="row"><span class="nm">{a["label_bg"]} <span class="small">{a["occurrences"]} седм.{new}</span></span>'
                   f'<div class="track" title="{tip}">'
                   f'<div class="mark" style="left:{thr:.1f}%" title="праг |z| = 2"></div>'
                   f'<div class="range warn" style="left:0;width:{max(w,1.5):.1f}%"></div>'
                   f'<div class="dot warn" style="left:{w:.1f}%"></div></div>'
                   f'<span class="v"><span class="b warn">|z| {z:.1f}</span></span></div>')
    return "\n".join(out)

def sublens_rows(lenses):
    out=[]
    for k,v in sorted(lenses.items(), key=lambda kv:-kv[1]):
        out.append(f'<div class="row"><span class="nm">{LENS_BG.get(k,k)}</span>'
                   f'<div class="track" title="{v:.1f} health-скор · 50 = близката норма (робастен z спрямо плъзгащ 10-годишен прозорец); над 50 = по-здраво от нормата, под 50 = по-зле — ориентирано по полярност (за инфлация/лихви отклонение в двете посоки сваля скора). ±2σ ≈ 88/12."><div class="mark" style="left:50%"></div>'
                   f'<div class="dot neu" style="left:{max(min(v,99),1):.1f}%"></div></div>'
                   f'<span class="v">{v:.1f}</span></div>')
    return "\n".join(out)

def floor0(sat, brief, core):
    # VRM редовете пият от каноничната верига (data-core: vrm_overlay + vrm_ks_state)
    # — сателитният regimes.vrm блок е окълцан след мандат №36 (без alignment_total,
    # ks_status='unknown' при NULL) и остава само за us/eu/cn лещите.
    rg = sat["regimes"]
    an = sat["persistent_anomalies"]
    tl = "".join(f'<div class="brief">{b}</div>' for b in brief[:4])
    us, eu, cn = rg["us_macro"], rg["eu_macro"], rg["cn_macro"]
    faces = "".join([
        lens_face("vrm","РЕФЛАЦИЯ", f"VRM · до {core['vrm_asof'][:10]} (седмичен)",
                  [("alignment", core["align"]/core["align_total"]*100),
                   ("KS", 90 if core["ks_active"] else 15),
                   ("GMS", 50)],
                  '<span class="dvg">гласовете → етаж 2</span>'),
        lens_face("us", us["regime_label_bg"], f"САЩ · до {us['as_of'][:10]}",
                  list(us["lens_scores"].items()),
                  f'<span class="dvg">{us["cross_lens_divergences_count"]} дивергенции</span>'),
        lens_face("eu", eu["regime_label_bg"], f"ЕВРОЗОНА · до {eu['as_of'][:10]}",
                  list(eu["lens_scores"].items()),
                  f'<span class="dvg">{eu["cross_lens_divergences_count"]} дивергенции</span>'),
        lens_face("cn", f'{cn["regime_label_bg"]} · {cn.get("composite_score","")}',
                  f"КИТАЙ · до {cn['as_of'][:10]}", list(cn["lens_scores"].items()),
                  f'<span class="dvg">{cn["cross_lens_divergences_count"]} дивергенции</span>'),
    ])
    def drawer(key, title, lenses, anoms, link, extra=""):
        return (f'<div class="drawer" id="dr-{key}"><h4>Под-лещите (health-скор 0–100)</h4>'
                f'<div class="foot">50 = близката норма (робастен z спрямо плъзгащ 10-годишен прозорец) · над 50 = по-здраво от нормата, под 50 = по-зле · ориентирано по полярност (за инфлация/лихви високо и ниско са еднакво „далеч от нормата") · ±2σ ≈ 88/12. Health-скор = не „колко високо е числото", а „колко здраво спрямо близката норма".</div>'
                f'{sublens_rows(lenses)}'
                f'<h4>Упоритите аномалии — сериите, които постоянно се отклоняват (по |z|)</h4>'
                f'<div class="foot">|z| = размерът на отклонението в стандартни отклонения (σ) спрямо близката норма; по-високо = по-необичайно движение · лентата = средното |z|, чертата = прагът за влизане (макс |z| ≥ 2 за поне 2 от 4 седмици) · знакът/посоката (нагоре/надолу) НЕ е в този канал — виж дашборда.</div>'
                f'{anomaly_rows(anoms)}'
                f'<h4>Седмичният брифинг (W28, рязан петък сутрин — еднодневна разлика с екрана)</h4>{tl}'
                f'{extra}<a class="dlink" href="{link}" target="_blank">→ пълният дашборд</a></div>')
    dvrm = (f'<div class="drawer" id="dr-vrm"><h4>VRM — режимното ядро</h4>'
            f'<div class="row"><span class="nm">Alignment</span><div class="track"><div class="mark" style="left:50%"></div>'
            f'<div class="dot up" style="left:{core["align"]/core["align_total"]*100:.0f}%"></div></div>'
            f'<span class="v"><span class="b up">{core["align"]:.0f}/{core["align_total"]}</span></span></div>'
            f'<div class="foot">кой крепи тези {core["align"]:.0f} от {core["align_total"]} → етаж 2 · възрастта на епизода → етаж 1</div>'
            f'<div class="slot"><a class="dlink" href="vrm.html">→ Отвори пълния VRM екран</a> <span class="small">(мандат 17 изпълнен · билд: build_vrm_screen.py, пуска се СЛЕД build_screen.py)</span></div></div>')
    return (f'<div class="floor"><div class="fh"><span class="n">ЕТАЖ 0</span>'
            f'<span class="t">Икономиката — четирите лещи (клик за чекмеджето)</span>'
            f'<span class="d" title="Лицето: режим + под-лещите (health-скор 0–100; 50 = близката норма) + брой вътрешни дивергенции. Кликът отваря цялата дъска: всички под-лещи, упоритите аномалии (по |z| — размер на отклонението, без посока), брифингът, линкът към дашборда.">ⓘ</span></div>'
            f'<div class="lens4">{faces}</div>'
            + dvrm
            + drawer("us","САЩ", us["lens_scores"], an["us"], "https://tsvetoslavtsachev.github.io/us-macro-dashboard/")
            + drawer("eu","ЕВРОЗОНА", eu["lens_scores"], an["eu"], "https://tsvetoslavtsachev.github.io/eu-macro-dashboard/",
                     '<div class="foot">EU дашбордът няма собствен index — линкът води към папката с брифингите (мини-билет)</div>')
            + drawer("cn","КИТАЙ", cn["lens_scores"], an["cn"], "https://tsvetoslavtsachev.github.io/china-macro-dashboard/")
            + '</div>')

# ── Възел-картата на именуваните бури (мандат №26, спец §5; ФОРМА-КАНОН §1) ──
STORM_STATUS = {"active":("АКТИВНА","up"),"weakening":("ОТСЛАБВА","warn"),
                "inactive":("ДЕАКТИВИРАНА","dn")}

def _storm_cond_row(c):
    ok = c.get("holds")
    mark = '<span class="ck up">✓</span>' if ok else '<span class="ck dn">✗</span>'
    lbl = c.get("label") or f'{c.get("field")} {c.get("test")}'
    core = ' <span class="small">· носещо</span>' if c.get("core") else ''
    tip = (c.get("lies_when") or "").replace('"', "'")
    detail = f'{c.get("field")} {c.get("test")}'
    lk = (f' <a class="dlink" href="{c["link"]}" target="_blank">уред →</a>' if c.get("link") else '')
    return (f'<div class="scond" title="кога лъже: {tip}">{mark} '
            f'<span class="sl">{lbl}{core}</span> <span class="sv small">({detail})</span>{lk}</div>')

def _storm_block(s):
    txt, col = STORM_STATUS.get(s.get("status"), (s.get("status","?"), "muted"))
    says = s.get("says") or ''
    rows = "".join(_storm_cond_row(c) for c in (s.get("conditions") or []))
    age = s.get("age_days"); aget = f'{age} дни' if age is not None else 'от кръщенето'
    fals = s.get("falsifier") or '—'
    born = f' · кръстена {s.get("born")}' if s.get("born") else ''
    return (f'<div class="storm"><div class="sth"><b>{s.get("name","?")}</b> '
            f'<span class="badge2 {col}">{txt}</span>'
            f'<span class="small">{s.get("n_hold","?")}/{s.get("n_total","?")} условия · възраст {aget}{born}</span></div>'
            + (f'<div class="sverdict">{says}</div>' if says else '')
            + f'<div class="sconds">{rows}</div>'
            + f'<div class="sfals"><b>Опровергава се ако:</b> {fals}</div></div>')

def storms_card(storms):
    """Възел-картата на Етаж 1 (до режима): изводът първо · условията ✓/✗ с линк и „кога лъже" ·
    K/N · възраст · falsifier отдолу. Без графове. Нула бури → честният празен ред (спец §5)."""
    asof = storms.get("as_of")
    aso = f'до {asof}' if asof else 'as-of: storms_state.json не е генериран'
    lst = storms.get("storms") or []
    # живите (АКТИВНА/ОТСЛАБВА) първи, после най-много 1 честна деактивация (§6)
    live = [s for s in lst if s.get("status") in ("active","weakening")]
    dead = [s for s in lst if s.get("status") == "inactive"]
    show = live + dead[:1]
    head = ('<div class="sh"><span class="sk">ИМЕНУВАНИТЕ БУРИ '
            f'<span class="tag">наблюдение, не сигнал</span> <span class="tag">[ВЪТРЕШЕН ПОГЛЕД]</span> '
            f'<span class="small">{aso}</span></span></div>')
    if not show:
        return ('<div class="storms">' + head +
                '<div class="sverdict">Няма именувана буря — организмът не вижда съгласувана конфигурация.</div>'
                '<div class="sfoot">Именувана буря = кръстена от собственика конфигурация: N машинно '
                'проверими условия + falsifier, замразени ПРЕДИ да гледаме развитието. Машината само брои '
                'колко условия стоят и сваля статуса; имена дава САМО собственикът (пре-регистрирано). '
                'Механиката: build_storms.py + vault chronicle/storms/.</div></div>')
    blocks = "".join(_storm_block(s) for s in show)
    more = (f'<div class="sfoot">Показани {len(show)} от {len(lst)} · ✓/✗ = условието стои/пало · '
            'статуса го сваля машината (dwell 2), некрологът е на собственика · журнал: chronicle/STORMS.md.</div>')
    return '<div class="storms">' + head + blocks + more + '</div>'

def floor1(age, core, storms=None):
    agp = age["age"]/age["max"]*100; mdp = age["median"]/age["max"]*100
    marg = core["margin"]; mp = min(20+marg/15*76,96)
    g = core["gms"]
    return (f'<div class="floor"><div class="fh"><span class="n">ЕТАЖ 1</span><span class="t">Режимът и възрастта му</span>'
            f'<span class="d" title="Възрастта на епизода върху историческото разпределение ({age["n"]} рефлационни епизода от 2007). KS = дистанция до предпазителя.">ⓘ</span></div>'
            f'<div class="row"><span class="nm">{age["regime"]} — възраст <span class="small">от {age["start"]} · среза {age["asof"]}</span></span>'
            f'<div class="track" title="{age["age"]} седмици · медиана {age["median"]:.0f}с (чертата) · най-дълъг {age["max"]}с">'
            f'<div class="mark" style="left:{mdp:.1f}%"></div><div class="range warn" style="left:0;width:{agp:.1f}%"></div>'
            f'<div class="dot warn" style="left:{agp:.1f}%"></div></div>'
            f'<span class="v"><span class="b warn">{age["age"]} седм.</span> <span class="small">медиана {age["median"]:.0f}с · макс {age["max"]}с</span></span></div>'
            f'<div class="row"><span class="nm">KS margin <span class="small">S7 · {core["ks_asof"]}</span></span>'
            f'<div class="track" title="margin {marg:+.2f}% до прага −7.5%"><div class="zero" style="left:20%"></div>'
            f'<div class="range up" style="left:20%;width:{mp-20:.0f}%"></div><div class="dot up" style="left:{mp:.0f}%"></div></div>'
            f'<span class="v"><span class="b up">{marg:+.2f}%</span> <span class="small">{"АКТИВЕН" if core["ks_active"] else "НЕАКТИВЕН"}</span></span></div>'
            f'<div class="hero" style="margin:10px 0 0"><div class="tile"><div class="k">GMS</div><div class="n">{g["score"]}/{g["max"]}</div><div class="m">{g["tier"]}</div></div>'
            f'<div class="tile"><div class="k">S10 бенчмарк</div><div class="n">{core["s10"]}</div><div class="m">SPY confluence</div></div>'
            f'<div class="tile"><div class="k">S11 дивергенция</div><div class="n">net {core["s11_net"]:+.2f}</div>'
            f'<div class="m">{core["s11"]["confirm"]} потв. · {core["s11"]["contradict_watch"]} набл. · {core["s11"]["contradict"]} против</div></div></div>'
            f'<div class="slot">ИГЛИТЕ — пантата лещи↔режим (шевът Етаж 0↔1): <i>„млада потвърдена рефлация, '
            f'5-и месец — часовникът превърта ~август 2026"</i> <span class="small">[scout/provisional, един пазарен цикъл]</span> · '
            f'механичната карта = празно гнездо до подписа на мандат 15 + PASS на потвърдителния тест</div>'
            + (storms_card(storms) if storms is not None else '')
            + '</div>')

def floor2(votes):
    rows=[]
    for v in votes:
        cls = {"твърд поддръжник":"firm","твърдо против":"against","люлее се":"swing"}.get(v["class"],"")
        col = {"firm":"up","against":"dn","swing":"warn"}.get(cls,"neu")
        w = v["ok_pct"]
        extra = f' · {v["flips"]} флипа' if v["flips"]>=3 else ""
        rows.append(f'<div class="row"><span class="nm">{v["human_name"]}</span>'
                    f'<div class="track" title="{v["ok_pct"]:.0f}% Съгласен · {v["under_pct"]:.0f}% Против · {v["flips"]} флипа · серия {v["end_streak"]}с {STATE_BG.get(v["last_state"],v["last_state"])}">'
                    f'<div class="range {"dn" if cls=="against" else ("warn" if cls=="swing" else "up")}" style="left:0;width:{max(w,2):.0f}%"></div>'
                    f'<div class="dot {col}" style="left:{max(w,2):.0f}%"></div></div>'
                    f'<span class="v"><span class="badge2 {cls}">{v["class"]}</span> <span class="small">{w:.0f}% · серия {v["end_streak"]}с {STATE_BG.get(v["last_state"],"")}{extra}</span></span></div>')
    return (f'<div class="floor"><div class="fh"><span class="n">ЕТАЖ 2</span><span class="t">Гласовете под режима — кой го крепи</span>'
            f'<span class="d" title="Ретро-погледът 8×13 [ВЪТРЕШЕН ПОГЛЕД]: % седмици Съгласен + класификация + текуща серия. Данните са със среза на ретро анализа (03.07).">ⓘ</span></div>'
            + "\n".join(rows) +
            f'<div class="hero" style="margin:10px 0 0"><div class="tile"><div class="k">M-INTER</div><div class="n">2 флага</div><div class="m">GLD/TLT · GLD/SPY</div></div>'
            f'<div class="tile"><div class="k">Диагнозата</div><div class="n" style="font-size:15px">редуващ се състав</div><div class="m">1 твърд за · 1 твърд против · 6 смесени</div></div></div></div>')

def floor3_rows(data, wlo, whi, mlo, mhi):
    rows=[]
    for g in data:
        rows.append(f'<tr class="ghead"><td colspan="5">{g["group"]}</td></tr>')
        for a in sorted(g["assets"], key=lambda a:-a["week"]["chg"]):
            fin=f'https://finviz.com/quote.ashx?t={a["ticker"]}'; yah=f'https://finance.yahoo.com/quote/{a["ticker"]}'
            nm=(f'<td class="nm"><span class="t">{a["ticker"]}</span> {a["name"]}'
                f'<span class="lk"><a href="{fin}" target="_blank">F</a><a href="{yah}" target="_blank">Y</a></span></td>')
            rows.append(f'<tr>{nm}<td class="c">{bar(a["week"],wlo,whi)}</td><td class="v">{badge(a["week"])}</td>'
                        f'<td class="c">{bar(a["month"],mlo,mhi)}</td><td class="v">{badge(a["month"])}</td></tr>')
    return "\n".join(rows)

def scr_head(wlo, whi, mlo, mhi):
    return (f'<tr><th title="Име и тикер; F = Finviz, Y = Yahoo — графиката е на един клик">Актив</th>'
            f'<th title="Седмицата като свещ. Обща скала {wlo:+.1f}% … {whi:+.1f}%">Седмица</th>'
            f'<th title="Промяната · позицията в диапазона (0% дъно, 100% връх)">Δ седм. · поз.</th>'
            f'<th title="Последните {MONTH_TDAYS} търговски дни. Обща скала {mlo:+.1f}% … {mhi:+.1f}%">Месец</th>'
            f'<th title="Промяната · позицията в месечния диапазон">Δ мес. · поз.</th></tr>')

def floor3_face_rows(core_assets, guest_assets, wlo, whi, mlo, mhi):
    """Лицето на ЕТАЖ 3: ядрото (фиксиран ред) + гостите (до 3). z се подава само за гости."""
    def one(a, z):
        t=a["ticker"]
        fin=f'https://finviz.com/quote.ashx?t={t}'; yah=f'https://finance.yahoo.com/quote/{t}'
        g=(f' <span class="badge2">ГОСТ</span> <span class="small">· z {z:+.2f}</span>' if z is not None else '')
        nm=(f'<td class="nm"><span class="t">{t}</span> {a["name"]}{g}'
            f'<span class="lk"><a href="{fin}" target="_blank">F</a><a href="{yah}" target="_blank">Y</a></span></td>')
        return (f'<tr>{nm}<td class="c">{bar(a["week"],wlo,whi)}</td><td class="v">{badge(a["week"])}</td>'
                f'<td class="c">{bar(a["month"],mlo,mhi)}</td><td class="v">{badge(a["month"])}</td></tr>')
    rows=[one(a, None) for a in core_assets]
    if guest_assets:
        rows+=[one(a, z) for a,z in guest_assets]
    else:
        rows.append('<tr><td colspan="5"><div class="slot">тиха седмица — нула гости над 1.5σ</div></td></tr>')
    return "\n".join(rows)

def floor4(bridge, flat, radar, mtx):
    xl = {t:flat[t]["week"]["chg"] for t in ETF2GICS if t in flat}
    top = max(xl, key=xl.get); bot = min(xl, key=xl.get)
    def card(etf, tone):
        gics = ETF2GICS[etf]; sec = bridge["sectors"][gics]; d = sec.get("data", sec)
        cands = d["candidates"] if "candidates" in d else sec["candidates"]
        rc = d.get("regime_context") or {}
        cell = rc.get("current_regime_cell") or {}
        rel = (cell.get("rel_vs_SPY") or {})
        br = d.get("breadth") or {}
        bm = br.get("metrics") or {}
        cr=[]
        for c in cands:
            shelf=c["rotation_shelf"]; scls={"Stable Winner":"firm","Quality Dip":"swing"}.get(shelf,"")
            av=' <span class="badge2 against">AVOID</span>' if c.get("avoid_flag") else ''
            fin=f'https://finviz.com/quote.ashx?t={c["ticker"]}'; yah=f'https://finance.yahoo.com/quote/{c["ticker"]}'
            cr.append(f'<div class="cand"><span class="t">{c["ticker"]}</span>'
                      f'<div class="rank" title="сектор-z ранг {c["sector_z_rank"]}"><div class="fill" style="width:{c["sector_z_rank"]:.1f}%"></div><div class="dt" style="left:{c["sector_z_rank"]:.1f}%"></div></div>'
                      f'<span class="v">{c["sector_z_rank"]:.1f} <span class="badge2 {scls}">{shelf}</span>{av}'
                      f'<span class="lk"><a href="{fin}" target="_blank">F</a><a href="{yah}" target="_blank">Y</a></span></span></div>')
        meta=[]
        if cell: meta.append(f'клетка {rc.get("current_regime","")}: N={cell.get("N")} · rel_vs_SPY {rel.get("median_pct",0):+.2f}% · win {rel.get("win_pct",0):.0f}%')
        if bm: meta.append(f'ширина: {bm.get("pct_above_50sma",0):.0f}% над 50SMA / {bm.get("pct_above_200sma",0):.0f}% над 200SMA')
        meta.append('нива: E6A запис или „няма запис" · струва ли: оценъчния орган')
        lbl = "най-силен" if tone=="up" else "най-слаб"
        bd = sector_breakdown(gics, etf, radar, mtx)   # петте реда ПРЕДИ имената
        return (f'<div class="scard"><h3>{etf} {gics} <span class="b {tone}" style="font-size:12px">{lbl}: {xl[etf]:+.2f}%</span></h3>'
                + breakdown_html(bd)
                + "\n".join(cr) + f'<div class="meta">{" · ".join(meta)}</div></div>')
    return (f'<div class="floor"><div class="fh"><span class="n">ЕТАЖ 4</span><span class="t">РАЗБИВКАТА на сектора</span>'
            f'<span class="d" title="За най-силния и най-слабия сектор на седмицата (избрани от платното): пет реда разбивка — състав по рафтове (1м квадрант), ротационен поток, дисперсия на ранга, ножове (Е6б: QD и abs&lt;50), S10 прочит на секторния ETF — и НАКРАЯ трите имена от Е6б моста (bridge.json, ротация към {bridge.get("rotation_as_of","?")}, read-only). Наблюдение, не сигнал: НЕ избира сектора и НЕ казва купи.">ⓘ</span></div>'
            f'<div class="cards2">{card(top,"up")}{card(bot,"dn")}</div>'
            f'<div class="foot" style="margin-top:9px"><a class="dlink" href="sectors.html">→ Разбивката за всичките 11 сектора</a></div>'
            f'<div class="slot">слот КАИШКАТА (AI G-зона + пукнатини 4/10): влиза СЛЕД уикендното решение за формата ѝ · друг сектор: python export_bridge.py --sector X</div>'
            f'<div class="foot">Разбивката: радарът (rank_all_stocks + sector_rotation, docs/data.json) за състав/ротация/дисперсия/ножове · S10 матрицата (vrm_confirmation_matrix.json, последен запис — 9 сектора, без XLC/XLRE) за секторния прочит · трите имена: bridge.json — всичко READ-ONLY.</div></div>')

# ------------------------------------------------------------------ main --
def main():
    data, missing = [], []
    for gname, members in GROUPS:
        g={"group":gname,"assets":[]}
        for t,name in members:
            c=calc(t)
            if c is None: missing.append(t); continue
            g["assets"].append({"ticker":t,"name":name,**c})
        data.append(g)
    flat={a["ticker"]:a for g in data for a in g["assets"]}

    sat=load_satellite(); brief=load_brief_tldr(); votes=load_votes(); age=load_age()
    core=load_core(); bridge=load_bridge(); radar=load_radar(); mtx=load_matrix_last()
    baro=load_barometer()   # Ф-4: само за рендер; НЕ влиза в screen_data.json
    storms=load_storms()    # мандат №26: storms_state.json READ-ONLY; НЕ влиза в screen_data.json

    checks=[]
    try:
        satmov={m["symbol"]:m["weekly_change_pct"] for m in sat["week_movements_etf"]}
        for sym,sv in satmov.items():
            if sym in flat:
                ours=flat[sym]["week"]["chg"]; checks.append({"symbol":sym,"ours":round(ours,4),"satellite":round(sv,4),"pass":abs(ours-sv)<0.05})
    except Exception as e:
        checks.append({"error":str(e)})

    # --- седмичен z (метод на сателита, ddof=0) за всичките активи ---
    zmap={}
    for a in flat.values():
        z=weekly_z(a["ticker"])
        if z is not None: zmap[a["ticker"]]=z
    # Г3: CHECK-Z срещу сателита (week_movements_etf: symbol, z_score)
    checks_z=[]
    try:
        for m in sat["week_movements_etf"]:
            sym=m["symbol"]
            if sym in zmap:
                oz=zmap[sym]; sz=m["z_score"]
                checks_z.append({"symbol":sym,"ours":round(oz,4),"satellite":round(sz,4),"pass":abs(oz-sz)<0.05})
    except Exception as e:
        checks_z.append({"error":str(e)})
    # Гости: извън ядрото И извън 11-те XL* сектора (те живеят на ЕТАЖ 4);
    # влизат |z|>=1.5, максимум 3, сортирани по |z| низходящо.
    XL_SECTORS=set(ETF2GICS)
    guest_pool=[t for t in zmap if t not in set(CORE) and t not in XL_SECTORS]
    guest_ticks=sorted((t for t in guest_pool if abs(zmap[t])>=1.5), key=lambda t:-abs(zmap[t]))[:3]
    core_assets=[flat[t] for t in CORE if t in flat]
    guest_assets=[(flat[t], zmap[t]) for t in guest_ticks]
    guest_desc=(" · ".join(f'{t} z {zmap[t]:+.2f}' for t in guest_ticks) if guest_ticks
                else "нула гости над 1.5σ")

    all_a=[a for g in data for a in g["assets"]]
    wlo=min(a["week"]["lo"] for a in all_a); whi=max(a["week"]["hi"] for a in all_a)
    mlo=min(a["month"]["lo"] for a in all_a if a["month"]); mhi=max(a["month"]["hi"] for a in all_a if a["month"])
    wp=(whi-wlo)*.06; mp=(mhi-mlo)*.06; wlo,whi,mlo,mhi=wlo-wp,whi+wp,mlo-mp,mhi+mp
    # Скалата на ЛИЦЕТО (ядро + гости) — само от редовете на лицето.
    face_a=core_assets+[a for a,_ in guest_assets]
    fwlo=min(a["week"]["lo"] for a in face_a); fwhi=max(a["week"]["hi"] for a in face_a)
    fmlo=min(a["month"]["lo"] for a in face_a if a["month"]); fmhi=max(a["month"]["hi"] for a in face_a if a["month"])
    fwp=(fwhi-fwlo)*.06; fmp=(fmhi-fmlo)*.06; fwlo,fwhi,fmlo,fmhi=fwlo-fwp,fwhi+fwp,fmlo-fmp,fmhi+fmp
    ups=sum(1 for a in all_a if a["week"]["chg"]>0); downs=sum(1 for a in all_a if a["week"]["chg"]<0)
    best=max(all_a,key=lambda a:a["week"]["chg"]); worst=min(all_a,key=lambda a:a["week"]["chg"])
    spy=flat["SPY"]; prov=any(a["week"]["provisional"] for a in all_a)

    prov_b=('<span class="prov" title="Петъчният запис в архива е провизорен (recorded 11.07)">петъкът е провизорен</span>' if prov else "")
    trows=[]
    for g in data:
        for a in g["assets"]:
            w,m=a["week"],a["month"]
            trows.append(f'<tr><td>{a["ticker"]}</td><td>{a["name"]}</td>'
                         f'<td>{w["chg"]:+.2f}%</td><td>{w["lo"]:+.2f}%</td><td>{w["hi"]:+.2f}%</td><td>{w["pos"]:.0f}%</td>'
                         +(f'<td>{m["chg"]:+.2f}%</td><td>{m["lo"]:+.2f}%</td><td>{m["hi"]:+.2f}%</td><td>{m["pos"]:.0f}%</td>' if m else '<td colspan="4">n/a</td>')+"</tr>")

    html=f"""<!doctype html><html lang="bg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>СЪБОТНИЯТ ЕКРАН · {WEEK_LABEL}</title><style>{CSS}</style></head><body><div class="wrap">
{NAV}
<h1>СЪБОТНИЯТ ЕКРАН {prov_b}<span class="tag">[ВЪТРЕШЕН ПОГЛЕД]</span></h1>
<div class="sub">{WEEK_LABEL} · веригата: икономика → режим → гласове → пазар → сектор → имена ·
седмицата спрямо {spy["week"]["prev_date"]} · месецът = последните {MONTH_TDAYS} търговски дни · детерминистичен билд</div>
<div class="hero">
<div class="tile"><div class="k">S&amp;P 500 (SPY)</div><div class="n {'up' if spy['week']['chg']>=0 else 'dn'}">{spy['week']['chg']:+.2f}%</div><div class="m">позиция {spy['week']['pos']:.0f}%</div></div>
<div class="tile"><div class="k">Ширина на седмицата</div><div class="n">{ups}↑ · {downs}↓</div><div class="m">от {len(all_a)} актива</div></div>
<div class="tile"><div class="k">Най-силен</div><div class="n up">{best['ticker']} {best['week']['chg']:+.2f}%</div><div class="m">{best['name']}</div></div>
<div class="tile"><div class="k">Най-слаб</div><div class="n dn">{worst['ticker']} {worst['week']['chg']:+.2f}%</div><div class="m">{worst['name']}</div></div>
</div>
{floor0(sat,brief,core)}
{floor1(age,core,storms)}
{floor2(votes)}
<div class="floor"><div class="fh"><span class="n">ЕТАЖ 3</span><span class="t">Пазарното платно — лицето</span>
<span class="d" title="Лицето: 7 постоянни реда (ядро) + до 3 госта за седмицата (|z| ≥ 1.5σ по метода на сателита). Всеки актив като свещ: лентата = диапазонът low→high спрямо предишното затваряне; точката = затварянето. Общата скала per колона се смята САМО от редовете на лицето. Пълното платно (31 актива по групи) е в сгъвката отдолу.">ⓘ</span></div>
<table class="scr">{scr_head(fwlo,fwhi,fmlo,fmhi)}
{floor3_face_rows(core_assets,guest_assets,fwlo,fwhi,fmlo,fmhi)}
</table>
<div class="foot">Лицето = 7 постоянни (ядро: SPY · QQQ · IWM · TLT · GLD · USO · UUP) + до 3 госта по |z| ≥ 1.5σ. Тази седмица: {guest_desc}. Скалата на колоните е само от редовете на лицето; пълното платно — в сгъвката.</div>
{barometer_card(baro)}
<details><summary>Пълното платно (31 актива по групи)</summary>
<table class="scr">{scr_head(wlo,whi,mlo,mhi)}
{floor3_rows(data,wlo,whi,mlo,mhi)}
</table>
<details><summary>Таблична версия (пълните числа)</summary>
<table class="flat"><tr><th>Тикер</th><th>Име</th><th>Δ седм</th><th>low</th><th>high</th><th>поз.</th><th>Δ мес</th><th>low</th><th>high</th><th>поз.</th></tr>
{"".join(trows)}</table></details>
</details></div>
{floor4(bridge,flat,radar,mtx)}
<div class="foot">Наблюдение, не сигнал. Числата: детерминистичен код (build_screen.py) от price-archive · сателита ·
ретро гласовете (срез 03.07, [ВЪТРЕШЕН ПОГЛЕД]) · data-core state · bridge.json — всичко READ-ONLY. Кръстосана сверка
на седмичните промени срещу сателита: {sum(1 for c in checks if c.get("pass"))}/{len([c for c in checks if "pass" in c])} PASS ·
сверка на седмичния z (ddof=0): {sum(1 for c in checks_z if c.get("pass"))}/{len([c for c in checks_z if "pass" in c])} PASS.
Правилото на ЕТАЖ 3: лицето = 7 постоянни (ядро) + до 3 госта по |z| ≥ 1.5σ; пълното платно (31 актива) — в сгъвката.
Аномалиите са |z| без посока (посоката: в дашборда — кандидат-доработка). Липсващи: VUG/VTV/MOVE/VIX — падат честно.</div>
</div><script>{JS}</script></body></html>"""

    # --- Г3 sanity на ЕТАЖ 4: разбивката на двата избрани сектора ---
    xlchg={t:flat[t]["week"]["chg"] for t in ETF2GICS if t in flat}
    g4_top=max(xlchg,key=xlchg.get); g4_bot=min(xlchg,key=xlchg.get)
    sb_payload=[]; sb_lines=[]; sb_notes=[]
    for etf in (g4_top,g4_bot):
        bd=sector_breakdown(ETF2GICS[etf], etf, radar, mtx)
        shelf_sum=sum(c for _,c in bd["shelves"])
        v10=(bd["s10"] or {}).get("confluence",{}).get("verdict") if bd["s10"] else "няма ред"
        sb_lines.append(f'SECTOR-BREAKDOWN {etf}: members={bd["members"]}, '
                        f'shelves={{'+", ".join(f'{q}:{c}' for q,c in bd["shelves"])+'}, '
                        f'avoid={bd["knives"]}, s10={v10}  [sum(shelves)={shelf_sum}=={bd["members"]}: {shelf_sum==bd["members"]}]')
        sr=bd["rotation"]
        if sr and sr.get("n_total")!=bd["members"]:
            sb_notes.append(f'{etf}: sector_rotation.n_total={sr.get("n_total")} != members(rank_all_stocks)={bd["members"]}')
        sb_payload.append({"etf":etf,"gics":ETF2GICS[etf],"members":bd["members"],
            "shelves":bd["shelves"],"rotation":sr,"median":round(bd["median"],2),
            "top3":round(bd["top3"],2),"bot3":round(bd["bot3"],2),
            "avoid":bd["knives"],"s10_verdict":v10})

    (OUT/"index.html").write_text(html, encoding="utf-8")
    (OUT/"screen_data.json").write_text(json.dumps({"week":WEEK_LABEL,"groups":data,"checks":checks,"checks_z":checks_z,
        "z":{k:round(v,4) for k,v in zmap.items()},"guests":guest_ticks,
        "sector_breakdown":sb_payload,
        "age":age,"core":{k:v for k,v in core.items() if k!="s11"},"missing":missing}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for c in checks: print("CHECK", c)
    for c in checks_z: print("CHECK-Z", c)
    print("GUESTS", [(t, round(zmap[t],3)) for t in guest_ticks])
    for l in sb_lines: print(l)
    for n in sb_notes: print("NOTE n_total!=members:", n)
    if missing: print("MISSING:", missing)
    print("OK ->", OUT/"index.html")

if __name__ == "__main__":
    main()
