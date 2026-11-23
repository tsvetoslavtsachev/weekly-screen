"""Оптиката на илюминатора (ИЛЮ5): от светнала плочка до име или серия за най-много три хода.

  ход 1, континентът   optika/<петък>/t<N>.html          членовете на плочката: числото, котвата,
                                                          мястото спрямо нормалното, възрастта, графика
  ход 2, страната      optika/<петък>/t<N>-<член>.html   уредът зад члена (по листа) и пътищата надолу
  ход 3, улицата       optika/<петък>/ul-<серия>.html    серията с историята ѝ от самия уред
                       optika/<петък>/imena-<сектор>.html имената в сектора от класацията

Радарът и инфрачервеното (актив срещу двигателите, новините, крехкостта) са на всеки континент.
Където уредът иска сесия, страницата дава готовата команда с бутон за копиране.

Числата идват само от две места (G4): от файла със светлините (зона data-zone="lights") и от
самия уред, чийто файл е посочен в data-src (зона data-zone="src"). Тук не се смята нищо: само
се подрежда, закръгля до показаните знаци и се чертае. Изключението е възрастта на уреда, разлика
от две дати (петъкът и датата, прочетена от уреда), в зона data-zone="ured" с data-date.

Уред, който е застоял или замразен, стои на шарка с думата „застоял“ или „замразен“ и възрастта
си (брифът, т. 6); никога не изглежда жив.

  python build_optics.py --week-end 2026-11-20 [--lights ФАЙЛ] [--out-dir ПАПКА]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import build_glass as bg
import optics_catalog as oc

HERE = Path(__file__).resolve().parent
e = html.escape


# ── датите на уредите ───────────────────────────────────────────────────────
def norm_date(v) -> str | None:
    s = str(v or "")
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        return m[0]
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        return f"{m[3]}-{m[2]}-{m[1]}"
    m = re.search(r"(\d{4})-(\d{2})(?!\d)", s)
    if m:  # „ГГГГ-ММ“ е краят на месеца (правилото на договора за каденцията)
        y, mo = int(m[1]), int(m[2])
        nxt = dt.date(y + (mo == 12), mo % 12 + 1, 1)
        return (nxt - dt.timedelta(days=1)).isoformat()
    return None


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _dig(d, keys):
    for k in keys:
        d = d[k]
    return d


def _git(repo: Path, rel: str, before: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cs", f"--before={before}", "--", rel],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _newest(folder: Path, pattern: str) -> Path | None:
    xs = sorted(Path(folder).glob(pattern))
    return xs[-1] if xs else None


def read_date(spec, before: str) -> str | None:
    """Датата на данните, прочетена от уреда (никога сметната)."""
    if not spec:
        return None
    kind = spec[0]
    try:
        if kind == "json":
            return norm_date(_dig(_load(spec[1]), spec[2]))
        if kind == "text":
            m = re.search(spec[2], Path(spec[1]).read_text(encoding="utf-8"))
            return m[1] if m else None
        if kind == "git":
            return _git(spec[1], spec[2], before)
        if kind == "mtime":
            return dt.date.fromtimestamp(os.path.getmtime(spec[1])).isoformat()
        if kind == "newest":
            p = _newest(spec[1], spec[2])
            return norm_date(p.name) if p else None
        if kind == "newest_mtime":
            p = _newest(spec[1], spec[2])
            return dt.date.fromtimestamp(os.path.getmtime(p)).isoformat() if p else None
        if kind == "newest_front":
            p = _newest(spec[1], spec[2])
            if not p:
                return None
            m = re.search(rf"^{spec[3]}:\s*(\S+)", p.read_text(encoding="utf-8"), re.M)
            return norm_date(m[1]) if m else None
        if kind == "canon_min":
            ds = []
            for sid in spec[1]:
                rows = _load(oc.CANON / f"{sid}.json")
                ds.append(max(r["as_of"] for r in rows if r.get("value") is not None))
            return min(ds) if ds else None
    except Exception:  # noqa: BLE001
        return None
    return None


def file_url(p: Path, anchor: str = "") -> str:
    return "file:///" + quote(str(p).replace("\\", "/"), safe="/:") + (f"#{anchor}" if anchor else "")


def ured_view(key: str, week_end: str, cat: dict | None = None) -> dict:
    u = (cat or oc.U)[key]
    fri = dt.date.fromisoformat(week_end)
    before = f"{(fri + dt.timedelta(days=1)).isoformat()}T23:59:59"
    date = read_date(u.get("date"), before)
    data_date = read_date(u.get("data"), before) if u.get("data") else None
    age = max(0, (fri - dt.date.fromisoformat(date)).days) if date else None
    kind, tol = u.get("kind", "page"), u.get("tol")
    if kind == "frozen":
        status = "zamrazen"
    elif date is None:
        status = "bez"
    elif tol is not None and age > tol:
        status = "zastoyal"
    elif kind == "doc":
        status = "doc"
    elif tol is None:
        status = "poiskane"
    else:
        status = "zhiv"
    href = ""
    if u.get("open"):
        href = file_url(u["open"], u.get("anchor", ""))
    elif u.get("open_newest"):
        p = _newest(*u["open_newest"])
        href = file_url(p) if p else ""
    return {"key": key, "name": u["name"], "kind": kind, "status": status, "date": date, "age": age,
            "tol": tol, "tol_src": u.get("tol_src", ""), "href": href, "cmd": u.get("cmd"), "cwd": u.get("cwd"),
            "script": u.get("script"), "data_date": data_date, "how": u.get("how", "")}


def full_cmd(v: dict) -> str:
    """Командата за копиране с папката си, за PowerShell (Ж1: пътят стои само в командата)."""
    cwd = str(v["cwd"])
    cwd = f'"{cwd}"' if " " in cwd else cwd
    return f"cd {cwd}; {v['cmd']}"


STATUS_BG = {"zhiv": "жив", "zastoyal": "застоял", "zamrazen": "замразен", "bez": "без дата",
             "doc": "документ", "poiskane": "по поискване"}


def ured_html(v: dict) -> str:
    st = STATUS_BG[v["status"]]
    when = (f'данни към {bg.ddmm(v["date"], True)} · {v["age"]} д.' if v["date"] else "датата не се чете")
    if v["kind"] == "doc":
        when = f'от {bg.ddmm(v["date"], True)}' if v["date"] else "без дата"
    if v["status"] == "zastoyal":
        when += f' (праг {v["tol"]} д.)'
    parts = [f'<span class="ust">{e(st)}</span>']
    if v["href"]:
        parts.append(f'<a href="{e(v["href"])}" data-hop="ured">{e(v["name"])} →</a>')
    else:
        parts.append(f'<b>{e(v["name"])}</b>')
    parts.append(f'<span class="uwhen">{e(when)}</span>')
    if v["data_date"] and v["data_date"] != v["date"]:
        parts.append(f'<span class="unote">страницата е построена на {e(bg.ddmm(v["date"], True))}, '
                     f'данните в хранилището са към {e(bg.ddmm(v["data_date"], True))}</span>')
    if v["how"]:
        parts.append(f'<span class="unote">{e(v["how"])}</span>')
    if v["cmd"]:
        full = full_cmd(v)
        parts.append(f'<span class="cmdl"><code class="cmd">{e(full)}</code>'
                     f'<button class="copy" type="button" data-cmd="{e(full)}">копирай</button></span>')
    return (f'<div class="ured u-{v["status"]}" data-zone="ured" data-ured="{e(v["key"])}" '
            f'data-date="{e(v["date"] or "")}" data-age="{"" if v["age"] is None else v["age"]}" '
            f'data-data-date="{e(v["data_date"] or "")}"'
            + (f' data-cwd="{e(str(v["cwd"]))}" data-script="{e(str(v["script"]))}"' if v["cmd"] else "")
            + ">" + " ".join(parts) + "</div>")


# ── улиците: историята на серията от самия уред ─────────────────────────────
def _cut(pts: list, week_end: str) -> list:
    return [(d, v) for d, v in pts if d <= week_end and isinstance(v, (int, float)) and not isinstance(v, bool)]


def hist_canon(sid):
    p = oc.CANON / f"{sid}.json"
    return p, [(r["as_of"], r.get("value")) for r in _load(p)]


def hist_arch(sid):
    folder = oc.ARCH / sid
    files = sorted(folder.glob("*.jsonl"))[-11:]
    pts = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                pts.append((r["as_of"], r.get("close")))
    return folder, pts


def _sdata_path(region):
    return oc.P / f"macro/{region}-macro-dashboard/output/api/series_data.json"


def hist_sdata(region, sid):
    p = _sdata_path(region)
    c = _load(p)["series"][sid]["chart"]
    return p, list(zip(c["dates"], c["values"]))


BARO = oc.P / "markets/etf-rotationradar/docs/barometer_feed.json"


def hist_baro(ind):
    x = [s for s in _load(BARO)["snapshot"] if s["indicator"] == ind][0]
    return BARO, [(h["date"], h["value"]) for h in x.get("history", [])]


def hist_breadth(col):
    p = oc.DC / "migrations/m_breadth/breadth_history.csv"
    with open(p, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["group"] == "sp500_universe"]
    return p, [(r["friday"], float(r[col])) for r in rows if r.get(col) not in (None, "")]


def hist_ttf():
    p = oc.P / "_orchestration/stag/work/cache/ttf_front.json"
    return p, [(d, v) for d, v in _load(p)["obs"]]


def hist_path(k, part="points"):
    p = oc.DC / "data/policy_path/policy_path_futures.json"
    return p, [(r["date"], ((r.get(part) or {}).get(k) or {}).get("value")) for r in _load(p)["rows"]]


def hist_lpr(sid):
    p = oc.P / "macro/china-macro-dashboard/data/cache_akshare.json"
    return p, sorted(_load(p)[sid]["data"].items())


def hist_vrm(k):
    p = oc.DC / "data/state/vrm_overlay.json"
    return p, [(r["as_of"], r.get(k)) for r in _load(p)]


def street_of(spec) -> dict:
    """spec → {slug, title, src, pts | rows}. Нищо не се смята; само се чете."""
    kind = spec[0]
    if kind == "canon":
        src, pts = hist_canon(spec[1])
    elif kind == "arch":
        src, pts = hist_arch(spec[1])
    elif kind == "sdata":
        src, pts = hist_sdata(spec[1], spec[2])
    elif kind == "baro":
        src, pts = hist_baro(spec[1])
    elif kind == "breadth":
        src, pts = hist_breadth(spec[1])
    elif kind == "ttf":
        src, pts = hist_ttf()
    elif kind == "path":
        src, pts = hist_path(spec[1], spec[2] if len(spec) > 2 else "points")
    elif kind == "lpr":
        src, pts = hist_lpr(spec[1])
    elif kind == "vrm":
        src, pts = hist_vrm(spec[1])
    else:
        raise ValueError(kind)
    slug = "ul-" + re.sub(r"[^A-Za-z0-9_.-]", "-", "-".join(str(x) for x in spec)) + ".html"
    return {"slug": slug, "src": src, "pts": pts, "spec": spec}


def member_specs(tile_id: int, m: dict) -> list:
    s, src = m.get("series", ""), m.get("source", "")
    if s.startswith("px_"):
        return [("arch", s)]
    if "canonical" in src:
        return [("canon", s)]
    if "series_data.json" in src:
        return [("sdata", "us" if "us-macro" in src else "eu" if "eu-macro" in src else "china", s)]
    if s.startswith("barometer."):
        return [("baro", s.split(".", 1)[1])]
    if s.startswith("m_breadth."):
        return [("breadth", s.split(".", 1)[1])]
    if s == "ttf_front":
        return [("ttf",)]
    if s.startswith("policy_path_futures.points."):
        return [("path", s.rsplit(".", 1)[1])]
    if s.startswith("policy_path_futures.sofr."):
        return [("path", s.rsplit(".", 1)[1], "sofr")]
    if s == "CN_LPR_1Y":
        return [("lpr", s)]
    if s == "vrm_overlay.alignment_score":
        return [("vrm", "alignment_score")]
    return []


# ── формат и графиката ──────────────────────────────────────────────────────
def fmt(v: float) -> str:
    a = abs(v)
    d = 0 if a >= 1000 else 2 if a >= 1 else 4
    return bg.num(v, d)


def svg_chart(pts: list, h: int = 120, small: bool = False) -> str:
    if len(pts) < 2:
        return ""
    step = max(1, len(pts) // 600)
    p = pts[::step]
    if p[-1] != pts[-1]:
        p.append(pts[-1])
    vs = [v for _, v in p]
    lo, hi = min(vs), max(vs)
    rng = (hi - lo) or 1.0
    w = 600
    xy = " ".join(f"{i * (w - 1) / (len(p) - 1):.1f},{(h - 4) - (v - lo) / rng * (h - 8):.1f}" for i, (_, v) in enumerate(p))
    lbl = "" if small else (
        f'<div class="clbl"><span>{e(bg.ddmm(p[0][0], True))}</span>'
        f'<span>най-ниско {e(fmt(lo))} · най-високо {e(fmt(hi))}</span><span>{e(bg.ddmm(p[-1][0], True))}</span></div>')
    return (f'<div class="chart{" sm" if small else ""}"><svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'role="img" aria-label="историята на серията"><polyline points="{xy}" /></svg>{lbl}</div>')


def last_year(pts: list, week_end: str) -> list:
    start = (dt.date.fromisoformat(week_end) - dt.timedelta(days=365)).isoformat()
    return [(d, v) for d, v in pts if d >= start]


CSS_EXTRA = """
.crumbs{font-size:13px;color:var(--mut);display:flex;flex-wrap:wrap;gap:4px 12px;margin-bottom:6px}
.head{background:var(--card);border:1px solid var(--line);border-top:5px solid var(--c);border-radius:8px;padding:9px 12px}
.head.s-krayno{border-top-color:var(--k)}.head.s-neobichayno{border-top-color:var(--n)}.head.s-sivo{border-top-color:var(--g)}
.head h1{font-size:20px;margin:0 0 3px}
.ured{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--r4);border-radius:6px;padding:6px 10px;margin:5px 0;
display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;font-size:14px}
.ured .ust{font-size:12px;font-weight:650;border:1px solid var(--line);border-radius:10px;padding:0 7px}
.ured .uwhen,.ured .unote{font-size:12px;color:var(--mut)}
.u-zastoyal,.u-zamrazen,.u-bez{border-left-color:var(--g);color:var(--mut);
background:repeating-linear-gradient(135deg,var(--gbg) 0 8px,var(--card) 8px 16px)}
.u-zastoyal .ust,.u-zamrazen .ust,.u-bez .ust{color:var(--k);border-color:var(--k)}
.u-zastoyal a,.u-zamrazen a{color:var(--mut)}
.u-doc,.u-poiskane{border-left-color:var(--c)}
.cmdl{display:flex;gap:6px;align-items:center;flex-wrap:wrap;width:100%}
code.cmd{font-size:12px;background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:2px 6px;overflow-wrap:anywhere}
button.copy{font:inherit;font-size:12px;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:5px;padding:1px 8px;cursor:pointer}
table.mem{width:100%;border-collapse:collapse;font-size:14px}
table.mem th{font-size:12px;color:var(--mut);text-align:left;font-weight:500;border-bottom:1px solid var(--line);padding:4px 6px}
table.mem td{border-bottom:1px solid var(--line);padding:5px 6px;vertical-align:middle}
table.mem td.n{white-space:nowrap}
tr.s-krayno td:first-child{border-left:4px solid var(--k)}tr.s-neobichayno td:first-child{border-left:4px solid var(--n)}
tr.s-sivo{color:var(--mut)}tr.s-sivo td:first-child{border-left:4px solid var(--g)}
tr.s-krayno,tr.s-neobichayno{background:none}
.chart svg{width:100%;height:120px;display:block}.chart polyline{fill:none;stroke:var(--a);stroke-width:1.5;vector-effect:non-scaling-stroke}
.chart.sm svg{height:34px;min-width:110px}
.clbl{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:var(--mut)}
.steps{margin:0;padding-left:22px}.steps li{margin:6px 0}
.steps li>p{margin:2px 0}
.lnk{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:14px}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 12px;font-size:14px}
.kv span:nth-child(odd){color:var(--mut)}
.street{font-size:13px;color:var(--mut)}
@media (max-width:700px){table.mem .hide{display:none}}
"""

JS_COPY = """
document.querySelectorAll('button.copy').forEach(function(b){b.onclick=function(){var t=b.getAttribute('data-cmd');
function ok(){b.textContent='копирано';setTimeout(function(){b.textContent='копирай'},1500)}
if(navigator.clipboard){navigator.clipboard.writeText(t).then(ok,function(){})}else{var a=document.createElement('textarea');
a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy');ok()}catch(x){}a.remove()}}});
"""


def page(title: str, week_end: str, body: str, crumbs: list) -> str:
    cr = " › ".join(f'<a href="{e(h)}">{e(t)}</a>' if h else e(t) for h, t in crumbs)
    return ("<!doctype html><html lang=\"bg\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{e(title)} · оптиката</title><link rel=\"stylesheet\" href=\"../optika.css\"></head><body><div class=\"wrap\">"
            f'<div class="top"><div class="crumbs" data-zone="chrome">{cr}</div>'
            f'<div class="tools"><button class="th" id="th" type="button">тема</button></div></div>'
            f"{body}"
            f'<p class="foot">Оптиката за седмицата до петък {e(bg.ddmm(week_end, True))}. Числата са от файла със '
            f"светлините или от уреда, посочен до тях; тук нищо не се смята.</p>"
            f"</div><script>{bg.JS}{JS_COPY}</script></body></html>")


# ── страниците ──────────────────────────────────────────────────────────────
def mslug(tile_id: int, m: dict) -> str:
    return f"t{tile_id}-" + re.sub(r"[^A-Za-z0-9_.-]", "-", m.get("series") or m.get("name", "x")) + ".html"


def member_cells(m: dict) -> tuple[str, str, str]:
    num = bg.headline(m)
    val = m.get("value")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        valt = bg.num(val, 2)
    else:
        valt = bg.clean(str(val)) if val is not None else ""
    age = (f'{bg.ddmm(m.get("as_of"), True)} · {m.get("age_days")} д.' if m.get("as_of") else "без дата")
    return num, valt, age


class Ctx:
    def __init__(self, d: dict, week_end: str, cat: dict | None):
        self.d, self.we, self.cat = d, week_end, cat
        self.uredi: dict[str, dict] = {}
        self.streets: dict[str, dict] = {}
        self.pages: dict[str, str] = {}

    def u(self, key: str) -> str:
        if key not in self.uredi:
            self.uredi[key] = ured_view(key, self.we, self.cat)
        return ured_html(self.uredi[key])

    def street(self, spec, title: str) -> str | None:
        try:
            s = street_of(spec)
        except Exception:  # noqa: BLE001
            return None
        s["title"] = title
        self.streets.setdefault(s["slug"], s)
        return s["slug"]

    def tile(self, tid: int) -> dict:
        return next(t for t in self.d["tiles"] if t["id"] == tid)


def continent(ctx: Ctx, t: dict) -> str:
    tid, we = t["id"], ctx.we
    v = bg.tile_view(t, we)
    cfg = oc.TILES[tid]
    out = [f'<div class="head s-{t["state"]}" data-zone="lights"><h1>{e(t["name"])}</h1>'
           f'<p><b>{e(v["state_bg"])}</b> · {e(bg.clean(t.get("color_why") or ""))}</p>'
           f'<p class="small">{e(v["age"])}</p>'
           + "".join(f'<p class="small">{e(x)}</p>' for x in v["extra"]) + "</div>"]
    if tid == 5:
        out.append(raft_html(ctx))
    out.append('<div class="lbl">Първата оптика</div>' + "".join(ctx.u(k) for k in cfg["first"]))
    if tid == 3:
        out.append(ratios_html(ctx))
    # членовете
    rows = []
    for m in t.get("members", []):
        num, valt, age = member_cells(m)
        specs = member_specs(tid, m)
        chart = ""
        if specs:
            try:
                s = street_of(specs[0])
                chart = svg_chart(last_year(_cut(s["pts"], we), we), small=True)
            except Exception:  # noqa: BLE001
                chart = ""
        rows.append(f'<tr class="s-{m.get("state", "sivo")}"><td><a href="{mslug(tid, m)}" data-hop="2">'
                    f'{e(bg.member_name(m.get("name", "")))}</a></td>'
                    f'<td class="n"><b>{e(num)}</b></td><td class="n">{e(valt)}</td>'
                    f'<td>{e(bg.anchor(m))}</td><td class="n">{e(bg.STATE_BG.get(m.get("state"), ""))}</td>'
                    f'<td class="n hide">{e(age)}</td><td class="hide">{chart}</td></tr>')
    out.append('<div class="lbl">Членовете (ход 2: щракни името)</div><div data-zone="lights"><table class="mem">'
               "<tr><th>член</th><th>за седмицата</th><th>ниво</th><th>спрямо нормалното</th><th>състояние</th>"
               '<th class="hide">данни към</th><th class="hide">година назад</th></tr>' + "".join(rows) + "</table></div>")
    if t.get("grey_members"):
        out.append(f'<p class="small" data-zone="lights">сиви членове: '
                   f'{e(", ".join(bg.member_name(g.get("name", "")) for g in t["grey_members"]))}</p>')
    radar = list(dict.fromkeys(cfg["radar"] + oc.COMMON_RADAR))
    out.append('<div class="lbl">Радарът и инфрачервеното</div>' + "".join(ctx.u(k) for k in radar))
    return page(t["name"], we, "".join(out), [("../../staklo/" + we + ".html", "стъклото"), ("", t["name"])])


def ratios_html(ctx: Ctx) -> str:
    """Петте съотношения на барометъра (поправките в брифа): числата са от барометъра."""
    feed = _load(BARO)
    rows = []
    for ind in ("XLE/SPY", "GLD/TLT", "XLY/XLP", "IWM/SPY", "VUG/VTV"):
        x = next((s for s in feed["snapshot"] if s["indicator"] == ind), None)
        if not x:
            continue
        slug = ctx.street(("baro", ind), f"{ind} (барометърът)")
        z = x.get("z")
        rows.append(f'<tr><td><a href="{slug}" data-hop="street">{e(ind)}</a></td><td class="n">{e(fmt(x["value"]))}</td>'
                    f'<td class="n">{"z " + e(bg.num(z, 2, True)) if isinstance(z, (int, float)) else ""}</td>'
                    f'<td>{e(bg.FLAG_BG.get(str(x.get("zone")), str(x.get("zone"))))}</td>'
                    f'<td class="n">{e(bg.ddmm(x.get("value_date"), True))}</td></tr>')
    return ('<div class="lbl">Дефанзивни срещу рискови: петте съотношения на барометъра</div>'
            f'<div data-zone="src" data-src="{e(str(BARO))}"><table class="mem"><tr><th>съотношение</th><th>ниво</th>'
            "<th>спрямо нормалното</th><th>зона</th><th>към</th></tr>" + "".join(rows) + "</table></div>")


def raft_html(ctx: Ctx) -> str:
    """Рафтът при спад в акциите, в реда от т. 4 на листа, със стъпката за икономиката."""
    d, we = ctx.d, ctx.we
    t6, t3 = ctx.tile(6), ctx.tile(3)
    sect = [m for m in t6["members"] if m["series"] not in oc.CANARIES]
    can = [(6, m) for m in t6["members"] if m["series"] in oc.CANARIES] + \
          [(3, m) for m in t3["members"] if m["series"] in oc.CANARIES]

    def mlinks(pairs):
        return ('<div class="lnk" data-zone="lights">' + "".join(
            f'<a href="{mslug(tid, m)}" data-hop="2">{e(bg.member_name(m["name"]))}</a>'
            f'<span class="small">{e(bg.headline(m))} {e(bg.STATE_BG.get(m.get("state"), ""))}</span>'
            for tid, m in pairs) + "</div>")

    why = d.get("why") or {}
    econ = []
    for tid in (8, 9, 10, 11):
        tv = bg.tile_view(ctx.tile(tid), we)
        lab = tv.get("verdict", ("", ""))[0] if tv.get("verdict") else ""
        econ.append(f'<a href="t{tid}.html" data-hop="2">{e(tv["name"])}</a>'
                    f'<span class="small">{e(tv["state_bg"])}{" · " + e(lab) if lab else ""}</span>')
    steps = [
        ("сектори и имена", mlinks([(6, m) for m in sect]) +
         '<p class="small">от члена на сектора: уредът и имената в сектора от класацията</p>'),
        ("защо", f'<p class="small" data-zone="lights">{e(bg.clean(why.get("text") or ""))}</p>' + ctx.u("news")),
        ("чужбина", '<div class="lnk"><a href="chuzhbina.html" data-hop="2">десетте местни индекса в местна валута</a></div>'),
        ("радарът и какво още имаме", ctx.u("s9_tech") + ctx.u("raft") + ctx.u("breadth") + ctx.u("conc")
         + ctx.u("sector_mon") + ctx.u("ai_hype")),
        ("ревизиите и позиционирането", ctx.u("valuation") + ctx.u("revizii") + ctx.u("cot")
         + '<p class="small">позиционирането и ливъриджът: по думите на Ц. на 21.11 „няма как да го имаме“; остава COT</p>'),
        ("дефанзивни срещу рискови, други активи, междупазарни връзки", ratios_html(ctx)
         + '<div class="lnk"><a href="t7.html" data-hop="2">суровините</a><a href="t4.html" data-hop="2">доларът</a>'
           '<a href="t1.html" data-hop="2">цената на парите</a></div>' + ctx.u("talpata")),
        ("кога е имало подобно и вярва ли кредитът",
         '<div class="lnk"><a href="t3.html" data-hop="2">кредит и нерви</a></div>' + ctx.u("fragility")),
        ("какво казва икономиката", '<div class="lnk" data-zone="lights">' + "".join(econ) + "</div>"),
        ("канарчетата на кризата", mlinks(can)),
        ("чак накрая останалите плочки", f'<div class="lnk"><a href="../../staklo/{we}.html">стъклото</a></div>'),
    ]
    lis = "".join(f'<li><b>{e(h)}</b>{b}</li>' for h, b in steps)
    return '<div class="lbl">Рафтът: редът, в който Ц. пита при спад</div><ol class="steps">' + lis + "</ol>"


def country(ctx: Ctx, t: dict, m: dict) -> str:
    tid, we = t["id"], ctx.we
    num, valt, age = member_cells(m)
    kv = [("за седмицата", num), ("ниво", valt), ("предишно", bg.num(m["prev"], 2) if isinstance(m.get("prev"), (int, float)) else ""),
          ("спрямо нормалното", bg.anchor(m)), ("състояние", bg.STATE_BG.get(m.get("state"), "")),
          ("данни към", age), ("защо свети", bg.clean(m.get("why") or ""))]
    out = [f'<div class="head s-{m.get("state", "sivo")}" data-zone="lights"><h1>{e(bg.member_name(m.get("name", "")))}</h1>'
           '<div class="kv">' + "".join(f"<span>{e(k)}</span><span>{e(v)}</span>" for k, v in kv if v) + "</div></div>"]
    out.append('<div class="lbl">Уредът зад члена</div>' + "".join(ctx.u(k) for k in oc.member_instruments(tid, m)))
    streets = []
    for spec in member_specs(tid, m):
        slug = ctx.street(spec, bg.member_name(m.get("name", "")))
        if slug:
            streets.append(f'<a href="{slug}" data-hop="3">серията {e(m.get("series", ""))} с историята ѝ</a>')
    if tid == 6 and m["series"] in oc.SECTOR_OF:
        sec = oc.SECTOR_OF[m["series"]]
        ctx.pages.setdefault(f"imena-{sec.replace(' ', '-')}.html", "")
        streets.append(f'<a href="imena-{e(sec.replace(" ", "-"))}.html" data-hop="3">имената в сектора ({e(sec)})</a>')
    sec_html = ""
    if str(m.get("series", "")).startswith("lens_"):
        sec_html = lens_html(ctx, t, m)
    elif m.get("series", "").startswith("lamp_"):
        sec_html = lamp_html(m)
    elif m.get("series", "").startswith("jp.yen_layer."):
        sec_html = yen_html(m)
    elif m.get("series") == "vrm_overlay.regime":
        sec_html = regime_html(ctx)
    if streets:
        out.append('<div class="lbl">Улицата (ход 3)</div><div class="lnk">' + "".join(streets) + "</div>")
    out.append(sec_html)
    return page(bg.member_name(m.get("name", "")), we, "".join(out),
                [("../../staklo/" + we + ".html", "стъклото"), (f"t{tid}.html", t["name"]), ("", bg.member_name(m.get("name", "")))])


REGION = {8: "us", 9: "eu", 10: "china"}
JP_HEAD = {"inflation": "Инфлация", "growth": "Растеж", "labor": "Пазар на труда", "credit": "Кредит и финанси",
           "external": "Външен сектор", "property": "Имоти"}


def lens_html(ctx: Ctx, t: dict, m: dict) -> str:
    lens = m["series"][5:]
    tid = t["id"]
    if tid in REGION:
        rows = []
        for s in (t.get("lupa") or {}).get("series", []):
            if s.get("lens") != lens:
                continue
            slug = ctx.street(("sdata", REGION[tid], s["series"]), s.get("name") or s["series"])
            zo = s.get("z_own")
            nm = e(bg.clean(s.get("name") or s["series"]))
            link = f'<a href="{slug}" data-hop="3">{nm}</a>' if slug else nm
            rows.append(f'<tr class="s-{s.get("state", "sivo")}"><td>{link}</td>'
                        f'<td class="n">{e(fmt(s["value"])) if isinstance(s.get("value"), (int, float)) else ""}</td>'
                        f'<td class="n">{"z " + e(bg.num(zo, 2, True)) if isinstance(zo, (int, float)) else ""}</td>'
                        f'<td class="n">{e(bg.STATE_BG.get(s.get("state"), ""))}</td>'
                        f'<td class="n">{e(bg.ddmm(s.get("as_of"), True))}</td></tr>')
        return ('<div class="lbl">Сериите под лупата в тази област (ход 3: щракни серията)</div>'
                '<div data-zone="lights"><table class="mem"><tr><th>серия</th><th>ниво</th><th>спрямо нормалното</th>'
                "<th>състояние</th><th>към</th></tr>" + "".join(rows) + "</table></div>")
    # Япония: таблото няма файл със сериите; имената и стойностите са от брифинга на таблото
    out = oc.P / "macro/jp-macro-dashboard/output"
    sat = (dt.date.fromisoformat(ctx.we) + dt.timedelta(days=1)).isoformat()
    files = sorted(p for p in out.glob("briefing_context_20??-??-??.md") if p.stem[-10:] <= sat)
    if not files:
        return '<p class="small">брифингът на таблото липсва</p>'
    f = files[-1]
    txt = f.read_text(encoding="utf-8")
    sec = re.search(rf"^## {re.escape(JP_HEAD.get(lens, lens))}\s*$(.*?)(?=^## |\Z)", txt, re.M | re.S)
    rows = []
    if sec:
        for line in sec[1].splitlines():
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(c) == 4 and re.match(r"\d{4}-\d{2}-\d{2}", c[3]):
                rows.append(f'<tr data-street="1"><td>{e(c[0])}</td><td class="n">{e(c[1].replace(".", ","))}</td>'
                            f'<td class="n">{e(c[2].replace(".", ","))}</td><td class="n">{e(bg.ddmm(c[3], True))}</td></tr>')
    return ('<div class="lbl">Сериите в тази област (имената са тук; историята е само в таблото)</div>'
            f'<div data-zone="src" data-src="{e(str(f))}" data-street="names"><table class="mem"><tr><th>серия</th><th>стойност</th>'
            "<th>оценка от 100</th><th>към</th></tr>" + "".join(rows) + "</table></div>"
            '<p class="small">Таблото на Япония няма файл със сериите; затова историята на серия се гледа в самото табло.</p>')


def lamp_html(m: dict) -> str:
    p = oc.P / "macro/treasury-funding-radar/data/lamps.json"
    lid = int(m["series"][5:])
    lamp = next((x for x in _load(p)["lamps"] if x["id"] == lid), None)
    if not lamp:
        return ""
    kv = [("лампа", lamp["name"]), ("цвят", bg.FLAG_BG.get(lamp.get("status"), str(lamp.get("status")))),
          ("стойност", fmt(lamp["value"]) if isinstance(lamp.get("value"), (int, float)) else ""),
          ("към", bg.ddmm(lamp.get("as_of"), True))]
    pc = lamp.get("percentile") or {}
    if isinstance(pc.get("percentile"), (int, float)):
        kv.append(("персентил", f'{bg.num(pc["percentile"], 1)} ({pc.get("window", "")}, {pc.get("n", "")} точки)'))
    for k, v in (lamp.get("detail") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            kv.append((k, fmt(v)))
    return ('<div class="lbl">Улицата (ход 3): лампата в радара</div>'
            f'<div data-zone="src" data-src="{e(str(p))}" data-street="lamp"><div class="kv">'
            + "".join(f"<span>{e(k)}</span><span>{e(v)}</span>" for k, v in kv if v) + "</div></div>"
            '<p class="small">Радарът пази само последната стойност на лампата; историята ѝ е в самия радар.</p>')


def yen_html(m: dict) -> str:
    p = oc.P / "macro/jp-macro-dashboard/output/api/macro_state.json"
    rates = (_load(p).get("yen_layer") or {}).get("rates") or {}
    rows = [(k, x) for k, x in rates.items() if isinstance(x, dict) and isinstance(x.get("value"), (int, float))]
    return ('<div class="lbl">Улицата (ход 3): лихвите в слоя за йената</div>'
            f'<div data-zone="src" data-src="{e(str(p))}" data-street="yen"><table class="mem"><tr><th>серия</th><th>стойност</th><th>към</th></tr>'
            + "".join(f'<tr><td>{e(k)}</td><td class="n">{e(fmt(x["value"]))}</td><td class="n">{e(bg.ddmm(x.get("as_of"), True))}</td></tr>'
                      for k, x in rows) + "</table></div>"
            '<p class="small">Слоят пази последните стойности; историята е в таблото на Япония.</p>')


def regime_html(ctx: Ctx) -> str:
    p = oc.DC / "data/state/vrm_overlay.json"
    rows = [r for r in _load(p) if r.get("as_of", "") <= ctx.we][-13:]
    return ('<div class="lbl">Улицата (ход 3): режимът по седмици</div>'
            f'<div data-zone="src" data-src="{e(str(p))}" data-street="regime"><table class="mem"><tr><th>седмица</th><th>режим</th><th>гласове от 8</th></tr>'
            + "".join(f'<tr><td class="n">{e(bg.ddmm(r["as_of"], True))}</td><td>{e(str(r.get("regime")))}</td>'
                      f'<td class="n">{e(str(r.get("alignment_score")))}</td></tr>' for r in reversed(rows))
            + "</table></div>")


def street_page(ctx: Ctx, s: dict) -> str:
    we = ctx.we
    pts = _cut(s["pts"], we)
    ten = [(d, v) for d, v in pts if d >= (dt.date.fromisoformat(we) - dt.timedelta(days=3653)).isoformat()]
    tail = pts[-13:]
    rows = "".join(f'<tr><td class="n">{e(bg.ddmm(d, True))}</td><td class="n">{e(fmt(v))}</td></tr>' for d, v in reversed(tail))
    sid = str(s["spec"][1] if s["spec"][0] in ("path", "canon", "arch", "baro", "breadth", "lpr", "vrm")
              else s["spec"][-1])
    # Ж1: уредът с името си за човек, както на стъклото; пътят е само в data-src
    body = (f'<div class="head" data-zone="chrome"><h1>{e(s["title"])}</h1><p class="small">серията {e(sid)} · '
            f'уредът: {e(bg.source_name(str(s["src"]), sid))}</p></div>'
            f'<div data-zone="src" data-src="{e(str(s["src"]))}" data-street="series">'
            '<div class="lbl">Историята до петъка (до десет години)</div>' + svg_chart(ten)
            + '<div class="lbl">Последните наблюдения</div><table class="mem"><tr><th>дата</th><th>стойност</th></tr>'
            + rows + "</table></div>")
    return page(s["title"], we, body, [("../../staklo/" + we + ".html", "стъклото"), ("", s["title"])])


def names_page(ctx: Ctx, sec: str) -> str:
    p = oc.P / "markets/SP500-momentumrank/data.json"
    meta = _load(oc.P / "markets/SP500-momentumrank/data_meta.json")
    xs = sorted((x for x in _load(p) if x.get("sector") == sec), key=lambda x: -(x.get("weight") or 0))[:25]
    rows = "".join(
        f'<tr><td><b>{e(x.get("symbol", ""))}</b> {e(x.get("name", ""))}</td>'
        f'<td class="n">{e(bg.num(x["weight"], 2)) if isinstance(x.get("weight"), (int, float)) else ""}</td>'
        f'<td class="n">{e(bg.num(x["return1m"], 2, True)) if isinstance(x.get("return1m"), (int, float)) else ""}</td>'
        f'<td class="n">{e(bg.num(x["dayChange"], 2, True)) if isinstance(x.get("dayChange"), (int, float)) else ""}</td>'
        f'<td class="n">{e(str(x.get("rank", "")))}</td></tr>' for x in xs)
    body = (f'<div class="head" data-zone="chrome"><h1>Имената в сектора: {e(sec)}</h1>'
            f'<p class="small">класацията на S&amp;P 500, обновена {e(str(meta.get("updated", "")))}; '
            "първите 25 по тегло. Класацията пази само днешния ден, затова е към датата си, не към петъка.</p></div>"
            + ctx.u("klasacia")
            + f'<div data-zone="src" data-src="{e(str(p))}" data-street="names"><table class="mem"><tr><th>име</th><th>тегло</th>'
              "<th>за месец</th><th>за деня</th><th>място</th></tr>" + rows + "</table></div>")
    return page(f"Имената: {sec}", ctx.we, body, [("../../staklo/" + ctx.we + ".html", "стъклото"),
                                                   ("t6.html", "Секторите"), ("", sec)])


def abroad_page(ctx: Ctx) -> str:
    ab = ctx.d.get("abroad") or {}
    rows = []
    for a in ab.get("items", []):
        slug = ctx.street(("arch", a["series"]), a["name"]) if a.get("series", "").startswith("px_") else None
        nm = f'<a href="{slug}" data-hop="3">{e(a["name"])}</a>' if slug else e(a["name"])
        ch, z = a.get("change_pct"), a.get("z_week")
        rows.append(f'<tr><td>{nm}</td><td class="n"><b>{e(bg.num(ch, 2, True) + "%") if isinstance(ch, (int, float)) else ""}</b></td>'
                    f'<td class="n">{"z " + e(bg.num(z, 2, True)) if isinstance(z, (int, float)) else ""}</td>'
                    f'<td class="n">{e(bg.ddmm(a.get("as_of"), True))}</td></tr>')
    body = (f'<div class="head" data-zone="chrome"><h1>Чужбината</h1><p class="small">{e(bg.clean(ab.get("title", "")))}</p></div>'
            '<div data-zone="lights"><table class="mem"><tr><th>индекс</th><th>за седмицата</th><th>спрямо нормалното</th>'
            "<th>към</th></tr>" + "".join(rows) + "</table></div>"
            + ctx.u("stoxx_rot") + ctx.u("stoxx_rank") + ctx.u("conc"))
    return page("Чужбината", ctx.we, body, [("../../staklo/" + ctx.we + ".html", "стъклото"), ("t5.html", "Акциите"), ("", "Чужбината")])


def build(week_end: str, d: dict, out: Path, cat: dict | None = None) -> dict:
    """Пише optika/<петък>/ и връща {страница: html} (за тестовете)."""
    ctx = Ctx(d, week_end, cat)
    pages: dict[str, str] = {}
    for t in d.get("tiles", []):
        pages[f"t{t['id']}.html"] = continent(ctx, t)
        for m in t.get("members", []):
            pages[mslug(t["id"], m)] = country(ctx, t, m)
    pages["chuzhbina.html"] = abroad_page(ctx)
    for name in list(ctx.pages):
        if name.startswith("imena-"):
            sec = next(s for s in oc.SECTOR_OF.values() if s.replace(" ", "-") == name[6:-5])
            pages[name] = names_page(ctx, sec)
    for slug, s in list(ctx.streets.items()):
        pages[slug] = street_page(ctx, s)
    folder = out / "optika" / week_end
    folder.mkdir(parents=True, exist_ok=True)
    (out / "optika" / "optika.css").write_text(bg.CSS + CSS_EXTRA, encoding="utf-8")
    for name, txt in pages.items():
        (folder / name).write_text(txt, encoding="utf-8")
    return pages


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-end", required=True)
    ap.add_argument("--lights")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    lights = Path(a.lights) if a.lights else bg.LIGHTS_DIR / f"ilu_lights_{a.week_end}.json"
    d = json.loads(lights.read_text(encoding="utf-8"))
    pages = build(a.week_end, d, Path(a.out_dir) if a.out_dir else HERE)
    print(f"оптиката {a.week_end}: {len(pages)} страници")
    return 0


if __name__ == "__main__":
    sys.exit(main())
