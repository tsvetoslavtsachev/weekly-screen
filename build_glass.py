"""Стъклото на илюминатора (ИЛЮ4): първата страница на седмичния екран.

Чете САМО файла със светлините на линийката (ИЛЮ2):
  C:\\Projects\\data-core\\migrations\\m_ilu\\out\\ilu_lights_<петък>.json
и не смята нищо: цветът, най-силният член, възрастта, петте от първия ред, чужбината и
лентата на машинното отделение идват готови оттам. Тук само се подреждат и се форматират
(закръгляне до показаните знаци, датата като ДД.ММ, превод на етикет).

Единственото изключение е зоната „вратите“ най-долу (листът, т. 5 и Поправките в брифа):
датата на последния изход на Пулса, бюрото и кокпита. Тя не е от светлините, стои в
отделен блок с data-zone="doors" и проверката G2 я мери отделно.

Пише (по подразбиране в корена на weekly-screen):
  staklo/<петък>.html, staklo/<петък>.txt   архивът, всяка седмица се пази
  staklo/index.html                         списъкът на седмиците
  index.html, tekst.html                    само ако седмицата е най-новата в архива

  python build_glass.py --week-end 2026-11-20 [--lights ФАЙЛ] [--out-dir ПАПКА]

Изход 0: построено. Изход 2: файлът със светлините липсва или е счупен; тогава стъклото
за седмицата казва това на самата страница (всички плочки сиви), не мълчи. Изход 3: стъклото
е построено, но оптиката зад плочките (ИЛЮ5, build_optics.py, optika/<петък>/) падна.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIGHTS_DIR = Path(r"C:\Projects\data-core\migrations\m_ilu\out")
DC = Path(r"C:\Projects\data-core")

STATE_BG = {"krayno": "крайно", "neobichayno": "необичайно", "spokoyno": "спокойно", "sivo": "сиво"}
ROWS = [
    ("pazari", "Пазарите"),
    ("ikonomika", "Икономиката и централните банки"),
    ("model", "Моделът"),
]
# Областите на макро таблата (във файла „Леща X“; на стъклото само името на областта, Ц. 23.11.2026)
AREA_BG = {"labor": "пазар на труда", "growth": "растеж", "inflation": "инфлация", "liquidity": "ликвидност",
           "credit": "кредит", "external": "външен сектор", "property": "имоти", "housing": "имоти"}
VERDICT_BG = {"policy dilemma": "дилема за политиката"}
# Цветът на режима на VRM в хода (само за различаване; непознат режим е първият цвят)
REGIME_CLASS = {"GROWTH": "rg4", "REFLATION": "rg2", "STAGFLATION": "rg3", "DEFLATION": "rg1"}
FLAG_BG = {"amber": "жълт", "yellow": "жълт", "red": "червен", "green": "зелен", "alarm": "аларма",
           "mixed": "смесен", "contracting": "свиване", "expanding": "разширение", "base": "в база",
           "gray": "сива зона"}
UNIT = {"bp": " б.т.", "pct": "%", "pts": " т."}

# Старите етажи зад плочката (листът, 5.1). Оптиката на ИЛЮ5 (optika/<петък>/t<N>.html) стои
# първа на всяка плочка; тези връзки са до нея.
OPTICS = {
    3: [("ekran.html#talpata", "барометърът")],
    5: [("ekran.html#etazh3", "платното")],
    6: [("ekran.html#etazh3", "платното"), ("sectors.html", "секторите")],
    7: [("ekran.html#etazh3", "платното")],
    13: [("vrm.html", "моделът")],
}

PATH_RE = re.compile(r"[A-Za-z]:\\[^\s;,)]*")


# ── формат ──────────────────────────────────────────────────────────────────
def num(x: float, d: int, signed: bool = False) -> str:
    s = f"{abs(x):.{d}f}".replace(".", ",")
    if signed:
        return ("+" if x > 0 else "−" if x < 0 else "") + s
    return ("−" if x < 0 else "") + s


def ddmm(iso: str | None, year: bool = False) -> str:
    if not iso:
        return "?"
    d = dt.date.fromisoformat(iso[:10])
    return d.strftime("%d.%m.%Y" if year else "%d.%m")


def isoize(text: str) -> str:
    """ISO датите в готовия текст на файла стават ДД.ММ.ГГГГ (само формат)."""
    return re.sub(r"(\d{4})-(\d{2})-(\d{2})", lambda m: f"{m[3]}.{m[2]}.{m[1]}", text)


def clean(text: str) -> str:
    """Готов текст от файла за показване: без пътища, без английски етикети, дати като ДД.ММ.ГГГГ,
    десетична запетая."""
    t = PATH_RE.sub("файл", text or "")
    t = re.sub(r"Леща (\w+)", lambda m: AREA_BG.get(m[1], m[1]), t)
    t = t.replace("health_z на лещата", "отклонението от нормалното")
    t = t.replace("health_z", "отклонението от нормалното")
    t = re.sub(r"лещ(ата|ите|а)\b", lambda m: {"ата": "областта", "ите": "областите", "а": "област"}[m[1]], t)
    t = re.sub(r"зона (alarm|base|gray)", lambda m: "зона " + FLAG_BG[m[1]], t)
    t = isoize(t)
    t = re.sub(r"(?<=\d)\.(?=\d)", ",", t)
    t = re.sub(r"(?<![\w,])-(?=\d)", "−", t)
    return t


def member_name(name: str) -> str:
    m = re.match(r"Леща (\w+)$", name or "")
    return AREA_BG.get(m[1], m[1]) if m else (name or "")


def source_name(src: str, series: str) -> str:
    s = (src or "").lower()
    for key, nm in [("price-archive", "ценовият архив"), ("treasury-funding-radar", "радарът за финансирането"),
                    ("barometer_feed", "барометърът"), ("us-macro-dashboard", "таблото на САЩ"),
                    ("eu-macro-dashboard", "таблото на еврозоната"), ("china-macro-dashboard", "таблото на Китай"),
                    ("jp-macro-dashboard", "таблото на Япония"), ("policy_path", "пътят от фючърсите"),
                    ("vrm_overlay", "седмичният ход на модела"), ("vrm_ks_state", "седмичният ход на модела"),
                    ("breadth", "ширината"), ("ttf_front", "фючърсът на TTF"), ("canonical", "канонът на data-core")]:
        if key in s:
            return nm
    if (series or "").startswith("px_"):
        return "ценовият архив"
    return "уредът"


# ── котвата на члена: спрямо какво се мери ──────────────────────────────────
def anchor(m: dict) -> str:
    if m.get("hi52"):
        return "връх за година"
    if m.get("lo52"):
        return "дъно за година"
    z = m.get("z_week")
    if z is not None and abs(z) >= 2:
        return f"z {num(z, 2, True)} спрямо обичайната седмица"
    if m.get("hi13"):
        return "връх за 13 седмици"
    if m.get("lo13"):
        return "дъно за 13 седмици"
    if z is not None:
        return f"z {num(z, 2, True)} спрямо обичайната седмица"
    zo = m.get("z_own")
    if zo is not None:
        return f"z {num(zo, 2, True)} спрямо собствената си история"
    if m.get("flag"):
        f = str(m["flag"])
        return f"флаг на уреда: {FLAG_BG.get(f, clean(f))}"
    return clean(m.get("why") or "")


def headline(m: dict) -> str:
    """Числото на члена: седмичната промяна с мярката ѝ; уред без промяна няма число тук."""
    ch, kind = m.get("change"), m.get("change_kind")
    if ch is not None and kind in UNIT:
        d = 1 if kind == "bp" else 2
        return num(ch, d, True) + UNIT[kind]
    return ""


def find_member(tile: dict, name: str) -> dict:
    for m in tile.get("members", []):
        if m.get("name") == name:
            return m
    return {}


def age_text(tile: dict, week_end: str) -> str:
    if tile.get("as_of_newest") == week_end:
        return "данни към петъка"
    if tile.get("as_of_newest") is None:
        return "без дата на данните"
    a = tile.get("age_days")
    return f"данни към {ddmm(tile['as_of_newest'])}" + (f" · {a} д." if a is not None else "")


# ── плочката ────────────────────────────────────────────────────────────────
def tile_view(t: dict, week_end: str) -> dict:
    st = t.get("state", "sivo")
    s = t.get("strongest") or {}
    m = find_member(t, s.get("name")) or s
    v = {"id": t["id"], "name": t["name"], "state": st, "state_bg": STATE_BG.get(st, st),
         "member": "", "num": "", "anchor": "", "extra": [], "age": age_text(t, week_end),
         "source": "", "grey": [], "why_grey": ""}
    if st == "sivo":
        v["why_grey"] = clean(t.get("color_why") or "")
    if s:
        v["member"] = member_name(s.get("name", ""))
        v["source"] = source_name(m.get("source", ""), m.get("series", ""))
        if t["id"] == 13:
            v["anchor"] = clean(m.get("why") or s.get("why") or "")
        else:
            v["num"] = headline(m)
            v["anchor"] = anchor(m)
    lupa = t.get("lupa")
    if lupa is not None:
        if lupa.get("has_series"):
            ls = lupa.get("strongest") or {}
            line = f"светят {lupa.get('lit')} от {lupa.get('total')} серии"
            if ls and lupa.get("lit"):
                line += f"; най-силна: {clean(ls.get('name', ''))}"
            v["extra"].append(line)
        else:
            v["extra"].append("лупа няма: таблото няма файл със сериите")
    elif t["id"] == 11:
        v["extra"].append("лупа няма: таблото няма файл със сериите")
    if t["id"] == 13:
        reg = find_member(t, "Режимът (седмичен ход)")
        if reg and s.get("name") != "Режимът (седмичен ход)":
            v["extra"].append(f"режимът {reg.get('value')}: {clean(reg.get('why') or '')}")
    v["grey"] = [member_name(g.get("name", "")) for g in t.get("grey_members", [])]
    # какво показват уредите на таблото: присъдата му и областите като ленти (оценка 0-100)
    vd = t.get("verdict")
    if vd and st != "sivo":
        lab = str(vd.get("label") or "")
        for en, bgl in VERDICT_BG.items():
            lab = re.sub(re.escape(en), bgl, lab, flags=re.I)
        lab = lab.lower() if lab.isupper() else lab
        comp = vd.get("composite")
        v["verdict"] = (lab, num(comp, 1) if isinstance(comp, (int, float)) else "")
        v["areas"] = [(member_name(m["name"]), m.get("value"), m.get("state", "sivo"))
                      for m in t.get("members", []) if str(m.get("name", "")).startswith("Леща ")]
    # ходът на модела по седмици (от файла, последните 13)
    if t.get("trail") and st != "sivo":
        v["trail"] = t["trail"]
    return v


def verdict_html(v: dict) -> str:
    e = html.escape
    out = []
    if v.get("verdict"):
        lab, comp = v["verdict"]
        out.append(f'<p class="verdict">таблото: <b>{e(lab)}</b>'
                   + (f', общата оценка {e(comp)}' if comp else "") + "</p>")
    if v.get("areas"):
        rows = []
        for name, score, st in v["areas"]:
            # най-малко 4 %, за да се вижда цветът и при оценка около нула
            w = max(4.0, min(100.0, float(score))) if isinstance(score, (int, float)) else 0.0
            tip = f"{name}: оценка {num(score, 1) if isinstance(score, (int, float)) else 'няма'} от 100, {STATE_BG.get(st, st)}"
            rows.append(f'<span>{e(name)}</span><span class="b s-{st}" title="{e(tip)}"><i style="width:{w:.0f}%"></i></span>')
        out.append('<div class="areas">' + "".join(rows) + "</div>")
    return "".join(out)


def trail_html(trail: list) -> str:
    e = html.escape
    pts = [r for r in trail if r.get("as_of")]
    if not pts:
        return ""
    bars, segs = [], []
    for r in pts:
        sc = r.get("alignment_score")
        h = max(3.0, float(sc) / 8 * 100) if isinstance(sc, (int, float)) else 3.0
        cls = REGIME_CLASS.get(str(r.get("regime")), "rg1")
        tip = f"{ddmm(r['as_of'])}: {r.get('regime')}, гласове {sc if sc is not None else 'няма'} от 8"
        bars.append(f'<i class="{cls}" style="height:{h:.0f}%" title="{e(tip)}"></i>')
        if segs and segs[-1][0] == r.get("regime"):
            segs[-1][1] += 1
        else:
            segs.append([r.get("regime"), 1])
    regs = "".join(f'<span class="{REGIME_CLASS.get(str(g), "rg1")}" style="flex:{n}">{e(str(g))}</span>' for g, n in segs)
    f0, f1 = pts[0], pts[-1]
    s0, s1 = f0.get("alignment_score"), f1.get("alignment_score")
    ends = (f'<div class="ends"><span title="{e(ddmm(f0["as_of"]))}">в началото {e(str(s0))}</span>'
            f'<span>сега <b>{e(str(s1))}</b></span></div>')
    return (f'<div class="trail" title="гласовете за режима по седмици, {len(pts)} седмици, височината е от 8">'
            f'<div class="bars">{"".join(bars)}</div><div class="regs">{regs}</div>{ends}</div>')


def tile_html(v: dict, base: str, week_end: str = "") -> str:
    e = html.escape
    # Ж2 (ИЛЮ5): оптиката е местен инструмент (optika/ е извън git); вратата е скрита и се показва
    # само когато страницата е отворена от този компютър (file:), иначе на публикувания екран я няма
    opt = (f'<a class="opt" href="{base}optika/{week_end}/t{v["id"]}.html" data-optics-door="1" '
           f'data-local-only="1" hidden>оптиката →</a>' if week_end else "")
    opt += "".join(f'<a class="opt" href="{base}{h}">{e(lbl)} →</a>' for h, lbl in OPTICS.get(v["id"], []))
    body = []
    if v["state"] == "sivo" and v["why_grey"]:
        body.append(f'<p class="greywhy">сиво: {e(v["why_grey"])}</p>')
    if v["member"]:
        body.append(f'<p class="mem">{e(v["member"])}</p>')
        line = (f'<span class="big">{e(v["num"])}</span> ' if v["num"] else "") + f'<span class="anc">{e(v["anchor"])}</span>'
        body.append(f'<p class="val">{line}</p>')
    body.append(verdict_html(v))
    for x in v["extra"]:
        body.append(f'<p class="extra">{e(x)}</p>')
    if v.get("trail"):
        body.append(trail_html(v["trail"]))
    if v["grey"]:
        body.append(f'<p class="greym">сиви членове: {e(", ".join(v["grey"]))}</p>')
    meta = e(v["age"]) + (f' · {e(v["source"])}' if v["source"] else "")
    return (f'<article class="tile s-{v["state"]}" id="t{v["id"]}" data-tile="{v["id"]}">'
            f'<header><h3>{e(v["name"])}</h3><span class="st">{e(v["state_bg"])}</span></header>'
            + "".join(body) + f'<p class="meta">{meta}</p>'
            f'<nav class="optics" data-optics="{v["id"]}">{opt}</nav></article>')


# ── редовете над плочките ───────────────────────────────────────────────────
def engine_view(d: dict) -> str:
    er = d.get("engine_room") or {}
    if not er.get("model_ran"):
        parts = [f"моделът още не е минал за тази седмица; последен ход {ddmm(er.get('model_last_run'))}"]
    else:
        parts = [f"режим {er.get('regime')}"]
    # Kill Switch не е на стъклото (решение на Ц., 23.11.2026)
    names = er.get("tiles_without_friday_names") or []
    parts.append("без петъка: " + (", ".join(names) if names else "няма"))
    return " · ".join(parts)


def changed_view(d: dict) -> tuple[list, str, list]:
    w = d.get("what_changed") or {}
    shown = []
    for x in w.get("shown", []):
        m = {"change": x.get("change"), "change_kind": x.get("change_kind")}
        shown.append({"name": member_name(x.get("name", "")), "num": headline(m), "state": x.get("state", ""),
                      "tile": x.get("tile")})
    n = w.get("outside_n", 0)
    outside = [member_name(o.get("name", "")) for o in w.get("outside", [])]
    tail = f"още {n} члена с необичайна промяна останаха отвън" if n else "никой не остана отвън"
    return shown, tail, outside


def why_view(d: dict, changed: list) -> tuple[str, str]:
    w = d.get("why") or {}
    path = w.get("path")
    top = changed[0]["name"] if changed else ""
    if not path:
        return clean(w.get("text") or "черновата за седмицата още я няма"), ""
    m = re.search(r"(\d{4}-\d{2}-\d{2})\.md$", path)
    when = ddmm(m[1]) if m else ""
    lead = f"до {top}: " if top else ""
    txt = (f"{lead}причината е в черновата на новините от {when} ({clean(w.get('text') or '')}); "
           f"редът с нея още не е пренесен в светлините")
    return txt, "file:///" + path.replace("\\", "/").replace(" ", "%20")


def abroad_view(d: dict) -> list:
    out = []
    for it in (d.get("abroad") or {}).get("items", []):
        ch = it.get("change_pct")
        note = clean(it.get("note") or "")
        if it.get("as_of") and it["as_of"] != d["week_end"]:
            note = (note + "; " if note else "") + f"до {ddmm(it['as_of'])}"
        out.append({"name": it.get("name", ""), "num": num(ch, 2, True) + "%" if ch is not None else "няма",
                    "note": note, "z": it.get("z_week")})
    return out


# ── вратите (не са от светлините) ───────────────────────────────────────────
def _git_date(repo: Path, rel: str, before: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cs", f"--before={before}", "--", rel],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def doors(week_end: str) -> list:
    """Пулсът, бюрото и кокпитът: последният изход към края на съботата след петъка."""
    fri = dt.date.fromisoformat(week_end)
    sat = fri + dt.timedelta(days=1)
    res = []
    pulse = sorted(p for p in (DC / "migrations" / "m_pulse" / "out").glob("pulse_*.md")
                   if p.stem[6:] <= sat.isoformat())
    res.append({"name": "Пулсът, дайджестът", "href": "file:///" + str(pulse[-1]).replace("\\", "/") if pulse else "",
                "date": pulse[-1].stem[6:] if pulse else None})
    pages = sorted(p for p in (DC / "migrations" / "m_desk" / "pages").glob("20??-W??.md"))
    pages = [p for p in pages if dt.date.fromisocalendar(int(p.stem[:4]), int(p.stem[6:]), 5) <= fri]
    res.append({"name": "Бюрото, първата страница", "href": "file:///" + str(pages[-1]).replace("\\", "/") if pages else "",
                "date": dt.date.fromisocalendar(int(pages[-1].stem[:4]), int(pages[-1].stem[6:]), 5).isoformat() if pages else None})
    e2 = _git_date(DC, "migrations/e2_dashboard/e2.html", f"{sat.isoformat()}T23:59:59Z")
    res.append({"name": "Вратата на кокпита", "href": "file:///C:/Projects/data-core/migrations/e2_dashboard/e2.html",
                "date": e2})
    # У8 (ИЛЮ7п): възраст над прага на оптиката (optics_catalog, „tol“) дава белега „застоял“
    import optics_catalog as oc
    for x, key in zip(res, ("pulse", "desk", "e2")):
        tol = (oc.U.get(key) or {}).get("tol")
        x["tol"] = tol
        x["age"] = max(0, (fri - dt.date.fromisoformat(x["date"][:10])).days) if x["date"] else None
        x["stale"] = bool(tol is not None and x["age"] is not None and x["age"] > tol)
    return res


# ── страницата ──────────────────────────────────────────────────────────────
CSS = """
:root{--bg:#121417;--card:#1b1e23;--ink:#e7e8ea;--mut:#9aa2ad;--line:#2d3138;--k:#ff6b63;
--kbg:#3a1d1d;--n:#f0b440;--nbg:#3a2e14;--c:#9aa2ad;--cbg:#1b1e23;--g:#7d838c;--gbg:#24272c;--a:#7fb2ff;
--bar:#3a4048;--r1:#5b8def;--r2:#c9a227;--r3:#d0675f;--r4:#4fb08a}
:root[data-theme="light"]{--bg:#f6f5f1;--card:#ffffff;--ink:#1d1f23;--mut:#5d6470;--line:#dcd9d1;
--k:#d23b3a;--kbg:#fbe9e7;--n:#b77a07;--nbg:#fdf3dc;--c:#6b7480;--cbg:#ffffff;--g:#8a8f98;--gbg:#ecebe7;--a:#1f5fae;
--bar:#e3e1db;--r1:#2f6bd6;--r2:#a8840f;--r3:#b8463e;--r4:#2e8a66}
*{box-sizing:border-box}
body{margin:0;overflow-wrap:anywhere;background:var(--bg);color:var(--ink);font:15px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
font-variant-numeric:tabular-nums}
.wrap{max-width:1280px;margin:0 auto;padding:14px 16px 40px}
a{color:var(--a)}
.top{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;margin-bottom:10px}
.top h1{font-size:20px;margin:0}.top .wk{color:var(--mut)}
.top .tools{margin-left:auto;display:flex;gap:12px;align-items:center;font-size:14px}
button.th{font:inherit;font-size:13px;background:var(--card);color:var(--ink);border:1px solid var(--line);
border-radius:6px;padding:3px 9px;cursor:pointer}
.band{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0;font-size:14px}
.band b{font-weight:600}
.lbl{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin:16px 0 6px}
.changed{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.chip{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:6px;padding:6px 9px}
.chip.s-krayno{border-left-color:var(--k)}.chip.s-neobichayno{border-left-color:var(--n)}
.chip .t{font-size:12px;color:var(--mut)}.chip .v{font-size:17px;font-weight:600}
.small{font-size:13px;color:var(--mut)}
details summary{cursor:pointer;color:var(--mut);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.tile{background:var(--cbg);border:1px solid var(--line);border-top:5px solid var(--c);border-radius:8px;
padding:9px 11px;display:flex;flex-direction:column;gap:3px}
.tile header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:4px 8px}
.tile h3{margin:0;font-size:15px}
.tile .st{font-size:12px;font-weight:600;padding:1px 7px;border-radius:10px;border:1px solid var(--line);white-space:nowrap}
.tile p{margin:0}
.tile .mem{font-size:14px;margin-top:3px}
.tile .val .big{font-size:19px;font-weight:650}
.tile .anc{font-size:13px;color:var(--mut)}
.tile .extra,.tile .greym,.tile .greywhy{font-size:13px;color:var(--mut)}
.tile .meta{font-size:12px;color:var(--mut);margin-top:auto;padding-top:4px}
.tile .optics{font-size:12px;display:flex;gap:10px;flex-wrap:wrap}
.tile .optics:empty{display:none}
.s-krayno{border-top-color:var(--k);background:var(--kbg)}.s-krayno .st{color:var(--k);border-color:var(--k)}
.s-neobichayno{border-top-color:var(--n);background:var(--nbg)}.s-neobichayno .st{color:var(--n);border-color:var(--n)}
.s-spokoyno .st{color:var(--c)}
.s-sivo{border-top-color:var(--g);background:repeating-linear-gradient(135deg,var(--gbg) 0 8px,var(--card) 8px 16px);
color:var(--mut)}.s-sivo .st{color:var(--g)}
.abroad{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}
.ab{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:13px;
display:flex;justify-content:space-between;gap:6px}
.ab b{font-weight:600}
.doors{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px}
.doors span{color:var(--mut)}
.door-zastoyal a{color:var(--mut)}.doors .zst{color:var(--k);border:1px solid var(--k);border-radius:3px;padding:0 4px}
.foot{margin-top:18px;font-size:12px;color:var(--mut)}
.verdict{font-size:14px;margin-top:3px}.verdict b{font-weight:650}
.areas{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 8px;align-items:center;font-size:12px;color:var(--mut);margin:3px 0}
.areas .b{height:7px;background:var(--bar);border-radius:4px;overflow:hidden}
.areas .b i{display:block;height:100%;background:var(--c)}
.areas .b.s-krayno i{background:var(--k)}.areas .b.s-neobichayno i{background:var(--n)}
.areas .b.s-sivo i{background:var(--g)}
#t13{grid-column:1/-1}
.trail{margin:6px 0 2px;max-width:760px}
.trail .bars{display:flex;align-items:flex-end;gap:4px;height:84px;border-bottom:1px solid var(--line)}
.trail .bars i{flex:1;min-width:0;border-radius:2px 2px 0 0;background:var(--r1)}
.trail .regs{display:flex;gap:3px;font-size:11px;color:var(--mut);margin-top:3px}
.trail .regs span{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;border-top:3px solid var(--r1);padding-top:2px}
.trail .ends{display:flex;justify-content:space-between;font-size:11px;color:var(--mut)}
.trail .ends b{color:var(--ink);font-size:13px}
.rg1{background:var(--r1)!important;border-color:var(--r1)!important}.rg2{background:var(--r2)!important;border-color:var(--r2)!important}
.rg3{background:var(--r3)!important;border-color:var(--r3)!important}.rg4{background:var(--r4)!important;border-color:var(--r4)!important}
.trail .regs span.rg1,.trail .regs span.rg2,.trail .regs span.rg3,.trail .regs span.rg4{background:none!important}
@media (max-width:700px){.changed{grid-template-columns:repeat(2,minmax(0,1fr))}.abroad{grid-template-columns:repeat(2,minmax(0,1fr))}
.grid{grid-template-columns:minmax(0,1fr)}.top .tools{margin-left:0}}
"""

JS = """
(function(){var r=document.documentElement,b=document.getElementById('th');
function get(){try{return localStorage.getItem('glass-theme')}catch(e){return null}}
function set(v){try{localStorage.setItem('glass-theme',v)}catch(e){}}
var s=get(),h=location.hash.slice(1);if(h==='dark'||h==='light')s=h;if(s)r.setAttribute('data-theme',s);
if(b)b.onclick=function(){var cur=r.getAttribute('data-theme')||'dark';var n=cur==='dark'?'light':'dark';
r.setAttribute('data-theme',n);set(n);};
if(location.protocol==='file:'){var L=document.querySelectorAll('[data-local-only]');
for(var i=0;i<L.length;i++)L[i].removeAttribute('hidden');}})();
"""


def render(d: dict, base: str, dr: list) -> tuple[str, list]:
    """Връща HTML и текстовия изглед (редовете)."""
    e = html.escape
    we = d["week_end"]
    tiles = {t["id"]: tile_view(t, we) for t in d.get("tiles", [])}
    shown, tail, outside = changed_view(d)
    why, why_href = why_view(d, shown)
    ab = abroad_view(d)
    eng = engine_view(d)

    txt = [f"Илюминаторът, седмицата до петък {ddmm(we, True)}",
           f"0. Машинното отделение: {eng}",
           "1. Какво се промени: " + ("; ".join(f"{c['name']} {c['num']}".strip() for c in shown) + f"; {tail}"
                                       if shown else "нито един жив член не се е движил необичайно"),
           f"1а. Защо: {why}"]

    def tline(v):
        parts = [f"{v['name']}: {v['state_bg'].upper()}"]
        if v["state"] == "sivo" and v["why_grey"]:
            parts.append(v["why_grey"])
        if v["member"]:
            parts.append(" ".join(x for x in [v["member"], v["num"]] if x) + (f", {v['anchor']}" if v["anchor"] else ""))
        parts += v["extra"]
        if v["grey"]:
            parts.append("сиви: " + ", ".join(v["grey"]))
        parts.append(v["age"])
        return " · ".join(parts)

    h = [f'<!doctype html><html lang="bg"><head><meta charset="utf-8">'
         f'<meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>Илюминаторът</title><style>{CSS}</style></head><body><div class="wrap">',
         f'<div class="top"><h1>Илюминаторът</h1><span class="wk">седмицата до петък {e(ddmm(we, True))}</span>'
         f'<span class="tools"><a href="{base}{"tekst.html" if base == "" else "staklo/" + we + ".txt"}">като текст</a>'
         f'<a href="{base}staklo/index.html">предишните седмици</a>'
         f'<button class="th" id="th" type="button">тема</button></span></div>',
         f'<div data-zone="lights">',
         f'<div class="band" id="row0"><b>Машинното отделение.</b> {e(eng)}</div>',
         '<div class="lbl">1. Какво се промени от миналия петък</div><div class="changed" id="row1">']
    for c in shown:
        h.append(f'<div class="chip s-{c["state"]}"><div class="t">{e(tiles.get(c["tile"], {}).get("name", ""))}</div>'
                 f'<div>{e(c["name"])}</div><div class="v">{e(c["num"])}</div></div>')
    if not shown:
        h.append('<div class="chip">нито един жив член не се е движил необичайно</div>')
    h.append('</div>')
    h.append(f'<p class="small">Подредени по това колко необичайна е промяната спрямо собствената история на члена; '
             f'най-много два от едно семейство. ')
    if outside:
        h.append(f'<details style="display:inline"><summary>{e(tail)}</summary>{e(", ".join(outside))}</details>')
    else:
        h.append(e(tail))
    h.append('</p>')
    link = f' <a href="{e(why_href)}">черновата</a>' if why_href else ""
    h.append(f'<div class="band" id="row1a"><b>1а. Защо.</b> {e(why)}.{link}</div>')

    for key, title in ROWS:
        ids = [i for i in sorted(tiles) if next(t for t in d["tiles"] if t["id"] == i).get("row") == key]
        n = {"pazari": "2", "ikonomika": "3", "model": "4"}[key]
        h.append(f'<div class="lbl">{n}. {e(title)}</div><div class="grid" id="row{n}">')
        h += [tile_html(tiles[i], base, we) for i in ids]
        h.append('</div>')
        if key == "pazari":
            txt += [f"{n}. " + tline(tiles[i]) if j == 0 else "   " + tline(tiles[i]) for j, i in enumerate(ids)]
            h.append('<div class="lbl">2а. Чужбина, под „Акциите“: десетте местни индекса, '
                     'седмична промяна в местна валута</div><div class="abroad" id="row2a">')
            for a in ab:
                note = f' <span class="small">{e(a["note"])}</span>' if a["note"] else ""
                h.append(f'<div class="ab"><span>{e(a["name"])}{note}</span><b>{e(a["num"])}</b></div>')
            h.append('</div>')
            txt.append("2а. Чужбина: " + "; ".join(f"{a['name']} {a['num']}" + (f" ({a['note']})" if a["note"] else "")
                                                  for a in ab))
        else:
            txt += [f"{n}. " + tline(tiles[i]) if j == 0 else "   " + tline(tiles[i]) for j, i in enumerate(ids)]
    h.append('</div>')

    h.append('<div data-zone="doors"><div class="lbl">Вратите надолу</div><div class="doors">'
             f'<a href="{base}ekran.html">платното и етажите на седмичния екран</a>'
             f'<a href="{base}vrm.html">моделът</a><a href="{base}sectors.html">секторите</a>')
    for x in dr:
        when = f' <span>последен изход {e(ddmm(x["date"]))}</span>' if x["date"] else ' <span>изход няма</span>'
        cls = ''
        if x.get("stale"):
            cls = ' class="door-zastoyal"'
            when = f' <span class="zst">застоял</span> <span>последен изход {e(ddmm(x["date"]))}</span>'
        h.append(f'<span{cls}><a href="{e(x["href"])}">{e(x["name"])}</a>{when}</span>' if x["href"]
                 else f'<span{cls}>{e(x["name"])}{when}</span>')
    h.append('</div><p class="foot">Стъклото подрежда файла със светлините на линийката, без своя сметка; '
             'вратите към Пулса, бюрото и кокпита се отварят само на този компютър.</p></div>')
    h.append(f'</div><script>{JS}</script></body></html>')
    return "\n".join(h), txt


def broken_page(week_end: str, why: str) -> tuple[str, list]:
    e = html.escape
    msg = f"Стъклото за петък {ddmm(week_end, True)} не е сглобено: {why}. Всички плочки са сиви."
    h = (f'<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" '
         f'content="width=device-width,initial-scale=1"><title>Илюминаторът</title><style>{CSS}</style></head>'
         f'<body><div class="wrap"><div class="top"><h1>Илюминаторът</h1></div>'
         f'<div class="tile s-sivo"><header><h3>Файлът със светлините</h3><span class="st">сиво</span></header>'
         f'<p class="greywhy">{e(msg)}</p></div></div></body></html>')
    return h, [msg]


def text_page(lines: list) -> str:
    body = html.escape("\n".join(lines))
    return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Илюминаторът, текст</title><style>'
            ':root{--bg:#121417;--ink:#e7e8ea}'
            'body{margin:0;overflow-wrap:anywhere;background:var(--bg);color:var(--ink)}pre{white-space:pre-wrap;word-break:break-word;'
            'font:14px/1.5 ui-monospace,Consolas,monospace;padding:14px 16px;max-width:1000px;margin:0 auto}'
            '</style></head><body><pre>' + body + '</pre><p style="padding:0 16px"><a href="index.html">'
            'стъклото</a></p></body></html>')


def archive_index(out: Path) -> str:
    weeks = sorted((p.stem for p in (out / "staklo").glob("20??-??-??.html")), reverse=True)
    items = "".join(f'<li><a href="{w}.html">{ddmm(w, True)}</a> · <a href="{w}.txt">текст</a></li>' for w in weeks)
    return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Илюминаторът, седмиците</title><style>'
            ':root{--bg:#121417;--ink:#e7e8ea;--a:#7fb2ff}body{margin:0;overflow-wrap:anywhere;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,'
            'sans-serif;padding:14px 16px}a{color:var(--a)}</style></head><body><h1>Илюминаторът: седмиците</h1>'
            f'<ul>{items}</ul><p><a href="../index.html">стъклото за последната седмица</a></p></body></html>')


def build(week_end: str, lights: Path | None, out: Path) -> int:
    lights = lights or LIGHTS_DIR / f"ilu_lights_{week_end}.json"
    rc = 0
    try:
        d = json.loads(lights.read_text(encoding="utf-8"))
        if d.get("week_end") != week_end:
            raise ValueError(f"файлът е за {d.get('week_end')}, не за {week_end}")
        page, txt = render(d, "../", doors(week_end))
        top, _ = render(d, "", doors(week_end))
        try:  # ИЛЮ5: оптиката зад плочките, за същата седмица и от същия файл
            import build_optics
            build_optics.build(week_end, d, out)
        except Exception as ex:  # noqa: BLE001  стъклото се пише и без оптиката, но ходът е червен
            print(f"оптиката за {week_end} падна: {type(ex).__name__}: {ex}")
            rc = 3
    except FileNotFoundError:
        page, txt = broken_page(week_end, "файлът със светлините за седмицата липсва")
        top, rc = page, 2
    except Exception as ex:  # noqa: BLE001
        page, txt = broken_page(week_end, f"файлът със светлините е счупен ({type(ex).__name__})")
        top, rc = page, 2
    (out / "staklo").mkdir(parents=True, exist_ok=True)
    (out / "staklo" / f"{week_end}.html").write_text(page, encoding="utf-8")
    (out / "staklo" / f"{week_end}.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    (out / "staklo" / "index.html").write_text(archive_index(out), encoding="utf-8")
    newest = max(p.stem for p in (out / "staklo").glob("20??-??-??.html"))
    if week_end == newest:
        (out / "index.html").write_text(top, encoding="utf-8")
        (out / "tekst.html").write_text(text_page(txt), encoding="utf-8")
    print(f"стъклото {week_end}: {len(txt)} реда текст; {'index.html обновен' if week_end == newest else 'само архив'}; rc={rc}")
    return rc


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-end", required=True)
    ap.add_argument("--lights")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    return build(a.week_end, Path(a.lights) if a.lights else None, Path(a.out_dir) if a.out_dir else HERE)


if __name__ == "__main__":
    sys.exit(main())
