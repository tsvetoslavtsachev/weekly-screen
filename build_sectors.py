# -*- coding: utf-8 -*-
"""
РАЗБИВКАТА за всичките 11 SPDR сектора — детерминистичен билдър → sectors.html.
Отделна страница ЗАД Етаж 4 на съботния екран (решение на Ц., 12.07): същата
разбивка, каквато Етаж 4 показва за най-силния и най-слабия сектор, но разгъната
за ВСИЧКИТЕ 11 сектора. Главната страница НЕ наддава — само дискретен линк.

ПРЕИЗПОЛЗВА логиката на build_screen (без ново изчисление):
  bs.sector_breakdown() + bs.breakdown_html()  → петте реда (състав/ротация/дисперсия/ножове/S10)
  bs.calc() / bs.weekly_z()                     → седмична промяна + седмичен z (метод на сателита)
  bs.load_radar/load_matrix_last/load_bridge    → същите източници (READ-ONLY)
  bs.CSS + bs.ETF2GICS + bs.VERDICT_BG …        → същият стил и речник

Числата пише САМО този код. Пише единствено в C:\\Projects\\_weekly_screen\\sectors.html.
ФОРМА-КАНОН §1: извод първо · всяко име → Finviz/Yahoo · tooltip на всеки термин ·
as-of дата · О4 бадж · back-link към екрана · речникът (glossary.html) споделен.
"""
import json
from pathlib import Path
import build_screen as bs

OUT = bs.OUT
RADAR = bs.RADAR
BRIDGE = bs.BRIDGE

# as-of датите на отделните източници (видими на страницата — канон §1, практика 2)
RADAR_ASOF  = json.load(open(RADAR, encoding="utf-8"))["metadata"]["as_of"]      # rank/ротация/дисперсия/ножове
BRIDGE_ASOF = json.load(open(BRIDGE, encoding="utf-8")).get("rotation_as_of", "?")  # трите имена
S10_ASOF    = json.load(open(bs.DC / "vrm_confirmation_matrix.json", encoding="utf-8"))[-1].get("as_of", "?")

# допълнителни стилове върху палитрата на екрана (нищо не се предефинира разрушително)
EXTRA_CSS = """
a.back{color:var(--warn);font-size:12px;text-decoration:none}a.back:hover{color:var(--ink)}
.lede{color:var(--ink2);font-size:13.5px;margin:0 0 16px;border-left:3px solid var(--warn);
background:#151514;padding:11px 13px;border-radius:0 8px 8px 0}
.lede b{color:var(--ink)}.lede .up{color:var(--up)}.lede .dn{color:var(--dn)}
.scard h3{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}
.srank{color:var(--mut);font-size:11.5px;font-weight:700}
.zpill{border:1px solid var(--ring);border-radius:8px;padding:0 6px;font-size:11px;color:var(--ink2);cursor:help}
.gloss a{color:var(--warn);text-decoration:none}
.legend .meta{color:var(--ink2);font-size:12.5px;margin:5px 0}
.legend .meta b{color:var(--ink)}
"""

def _fin(t): return f'https://finviz.com/quote.ashx?t={t}'
def _yah(t): return f'https://finance.yahoo.com/quote/{t}'

def cand_and_meta(gics, bridge):
    """Трите имена + режимната/ширинната мета — точно както Етаж 4 ги вади (bridge.json)."""
    sec = bridge["sectors"][gics]; d = sec.get("data", sec)
    cands = d["candidates"] if "candidates" in d else sec["candidates"]
    rc = d.get("regime_context") or {}
    cell = rc.get("current_regime_cell") or {}
    rel = (cell.get("rel_vs_SPY") or {})
    bm = (d.get("breadth") or {}).get("metrics") or {}
    cr = []
    for c in cands:
        shelf = c["rotation_shelf"]
        scls = {"Stable Winner": "firm", "Quality Dip": "swing"}.get(shelf, "")
        av = ' <span class="badge2 against" title="ножът е вдигнат: Quality Dip с абсолютна сила под 50 (Е6б)">AVOID</span>' if c.get("avoid_flag") else ''
        cr.append(
            f'<div class="cand"><span class="t">{c["ticker"]}</span>'
            f'<div class="rank" title="сектор-z ранг {c["sector_z_rank"]} — z-скор спрямо секторните съседи (0–100): „лидер ли е В сектора си", не „бие ли пазара"">'
            f'<div class="fill" style="width:{c["sector_z_rank"]:.1f}%"></div><div class="dt" style="left:{c["sector_z_rank"]:.1f}%"></div></div>'
            f'<span class="v">{c["sector_z_rank"]:.1f} <span class="badge2 {scls}" title="рафтът (квадрант по ранг и посока): Stable Winner=висок и стабилен · Quality Dip=висок, но отслабващ · Faded Bounce=изгаснал отскок · Chronic Loser=хронично назад · Neutral">{shelf}</span>{av}'
            f'<span class="lk"><a href="{_fin(c["ticker"])}" target="_blank" title="Finviz графика">F</a>'
            f'<a href="{_yah(c["ticker"])}" target="_blank" title="Yahoo Finance">Y</a></span></span></div>')
    meta = []
    if cell:
        meta.append(f'клетка {rc.get("current_regime","")}: N={cell.get("N")} · rel_vs_SPY {rel.get("median_pct",0):+.2f}% · win {rel.get("win_pct",0):.0f}%')
    if bm:
        meta.append(f'ширина: {bm.get("pct_above_50sma",0):.0f}% над 50SMA / {bm.get("pct_above_200sma",0):.0f}% над 200SMA')
    meta.append('нива: E6A запис или „няма запис" · струва ли: оценъчния орган')
    return "".join(cr), " · ".join(meta)

def sector_card(rank, etf, gics, bd, wk_chg, z, bridge):
    cr, meta = cand_and_meta(gics, bridge)
    tone = "up" if (wk_chg is not None and wk_chg >= 0) else "dn"
    ztxt = f'{z:+.2f}' if z is not None else 'n/a'
    return (
        f'<div class="scard"><h3><span class="srank">#{rank}</span>{etf} {gics} '
        f'<span class="b {tone}" style="font-size:12px" title="седмична промяна на секторния ETF спрямо предходното затваряне">{wk_chg:+.2f}%</span>'
        f'<span class="zpill" title="седмичен z по метода на сателита (ddof=0): текущата седмична промяна срещу mean/std на предходните 13 седмични промени — колко необичайно е движението на сектора спрямо близката му норма. Контекст, не ключ: подредбата на страницата е по седмичната промяна.">z {ztxt}</span></h3>'
        + bs.breakdown_html(bd)
        + cr
        + f'<div class="meta">{meta}</div></div>')

def build():
    radar = bs.load_radar()
    mtx = bs.load_matrix_last()
    bridge = bs.load_bridge()

    # За всеки от 11-те сектора: седмична промяна (bs.calc) + седмичен z (bs.weekly_z) + разбивката (bs.sector_breakdown)
    recs = []
    for etf, gics in bs.ETF2GICS.items():
        c = bs.calc(etf)
        wk = c["week"]["chg"] if c else None
        z = bs.weekly_z(etf)
        bd = bs.sector_breakdown(gics, etf, radar, mtx)
        recs.append({"etf": etf, "gics": gics, "wk": wk, "z": z, "bd": bd})

    # Подредба: по СЕДМИЧНАТА ПРОМЯНА на секторния ETF (най-силен → най-слаб) —
    # СЪЩИЯТ ключ, по който Етаж 4 избира топ/дъно (checker присъда 12.07: една истина,
    # никоя бъдеща седмица не може да покаже различен лидер тук и на Етаж 4).
    # wk=None пада най-долу, детерминистично. z-то остава видимо като контекст, не е ключ.
    recs.sort(key=lambda r: (r["wk"] is None, -(r["wk"] if r["wk"] is not None else 0.0), r["etf"]))

    lead, lag = recs[0], recs[-1]
    # изводът-ред (канон §1, правило 1) — извлечен от данните, не по памет
    s10_confirm = sum(1 for r in recs if (r["bd"]["s10"] or {}).get("confluence", {}).get("verdict") == "confirm")
    s10_covered = sum(1 for r in recs if r["bd"]["s10"])
    knives_total = sum(r["bd"]["knives"] for r in recs)
    lede = (
        f'<div class="lede">Изводът: тази седмица <b class="up">води {lead["etf"]} {lead["gics"]}</b> '
        f'({lead["wk"]:+.2f}%, z {lead["z"]:+.2f}) · <b class="dn">отпада {lag["etf"]} {lag["gics"]}</b> '
        f'({lag["wk"]:+.2f}%, z {lag["z"]:+.2f}). S10 потвърждава {s10_confirm} от {s10_covered}-те покрити сектора '
        f'(XLC/XLRE нямат ред). Ножове (падащи лидери, Е6б) в целия пазар: {knives_total}. '
        f'Подредбата отдолу е по седмичната промяна, най-силен → най-слаб — същият ключ като Етаж 4. '
        f'<span class="gloss">Термините — в <a href="glossary.html">речника</a>.</span></div>')

    cards = "".join(
        sector_card(i + 1, r["etf"], r["gics"], r["bd"], r["wk"], r["z"], bridge)
        for i, r in enumerate(recs))

    legend = (
        '<details class="legend"><summary>Как да четеш картата (петте реда + подредбата) — механиката в сгъвка</summary>'
        '<div class="meta"><b>Състав по рафтове</b> — цветната стек-лента: колко имена в кой квадрант (1м). '
        'SW <span style="color:var(--up)">зелено</span> · QD <span style="color:var(--warn)">жълто</span> · '
        'FB <span style="color:var(--dn)">червено</span> · Neutral/CL сиво.</div>'
        '<div class="meta"><b>Ротация · Δранг 1м</b> — средната промяна на ранга за месец (посоката на потока) и колко имена се качват ↑ / падат ↓.</div>'
        '<div class="meta"><b>Дисперсия</b> — медианата на сектор-скора + средното на топ-3 и дъно-3: колко разтеглен е секторът вътре в себе си.</div>'
        '<div class="meta"><b>Ножове (QD &amp; abs&lt;50)</b> — Quality Dip имена с абсолютна сила под 50: отслабващи лидери („падащ нож"). Броячът отчита, не забранява.</div>'
        '<div class="meta"><b>S10</b> — секторната потвърждаваща матрица (тренд · момент · вол → присъда). Покрива 9 сектора; XLC/XLRE нямат ред.</div>'
        '<div class="meta"><b>Трите имена</b> — топ-3 по сектор-z ранг от Е6б моста (bridge.json): рафт · AVOID · Finviz/Yahoo. Проекция на съществуващ ранг, не нов сигнал.</div>'
        '<div class="meta"><b>Подредбата</b> — по седмичната промяна на секторния ETF, най-силен → най-слаб — същият ключ, по който Етаж 4 избира топ/дъно (една истина; крайните двойки съвпадат по конструкция). Седмичният z (пилюлата в заглавието) е контекст „колко необичайно", не ключ.</div>'
        '</details>')

    html = f"""<!doctype html><html lang="bg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>РАЗБИВКАТА · всичките 11 сектора · {bs.WEEK_LABEL}</title>
<style>{bs.CSS}{EXTRA_CSS}</style></head><body><div class="wrap">
<h1>РАЗБИВКАТА — всичките 11 сектора<span class="tag">[ВЪТРЕШЕН ПОГЛЕД]</span><span class="tag">наблюдение, не сигнал</span></h1>
<div class="sub">{bs.WEEK_LABEL} · разбивката на Етаж 4, разгъната за всичките 11 SPDR сектора ·
състав/ротация/дисперсия/ножове към {RADAR_ASOF} · S10 към {S10_ASOF} · трите имена (bridge) към {BRIDGE_ASOF} ·
детерминистичен билд (build_sectors.py) · <a class="back" href="index.html">← обратно към екрана</a></div>
{lede}
{legend}
<div class="cards2">{cards}</div>
<div class="foot">Наблюдение, не сигнал (О4): описва състояние, не дава препоръка и не обещава бъдеще.
Числата: детерминистичен код, преизползва разбивката на build_screen (sector_breakdown + breakdown_html) от
радара (rank_all_stocks + sector_rotation, docs/data.json) · S10 матрицата (vrm_confirmation_matrix.json, последен запис —
9 сектора, без XLC/XLRE) · трите имена от bridge.json (Е6б мост) — всичко READ-ONLY. Подредбата ползва същия ключ
като Етаж 4 (седмичната промяна) — крайните двойки съвпадат по конструкция.</div>
</div></body></html>"""

    (OUT / "sectors.html").write_text(html, encoding="utf-8")

    # --- кръстосана сверка Етаж4 ↔ sectors (докладва се) ---
    # Възпроизвеждаме избора на Етаж 4 (топ/дъно по седмична % на ETF) и сверяваме разбивката 1:1.
    flat = {r["etf"]: r for r in recs}
    xl = {etf: r["wk"] for etf, r in flat.items() if r["wk"] is not None}
    g4_top = max(xl, key=xl.get); g4_bot = min(xl, key=xl.get)
    for tag, etf in (("TOP", g4_top), ("BOT", g4_bot)):
        r = flat[etf]; bd = r["bd"]
        v10 = (bd["s10"] or {}).get("confluence", {}).get("verdict") if bd["s10"] else "няма ред"
        shelves = ", ".join(f"{q}:{c}" for q, c in bd["shelves"])
        print(f'SECTORS {tag} {etf} ({r["gics"]}): members={bd["members"]}, shelves={{{shelves}}}, '
              f'median={bd["median"]:.2f}, top3={bd["top3"]:.2f}, bot3={bd["bot3"]:.2f}, '
              f'avoid={bd["knives"]}, s10={v10}, wk={r["wk"]:+.2f}%, z={r["z"]:+.3f}')
    print("ORDER (wk% desc, ключът на Етаж 4):", [r["etf"] for r in recs])
    print("OK ->", OUT / "sectors.html")

if __name__ == "__main__":
    build()
