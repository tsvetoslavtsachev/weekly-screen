"""Проверката на оптиката (ИЛЮ5): гейтовете G1 до G4 и G6 от брифа.

  G1   за всяка от тринадесетте плочки скриптът минава пътя от стъклото до име или серия:
       ход 1 континентът, ход 2 членът, ход 3 улицата; всеки член стига до улица за най-много три
       хода и всяка връзка води някъде (файлът съществува, котвата е в него, командата има папка
       и скрипт);
  G2   петте неща, които Ц. посочи на пробата (ILU0-OTCHET.md), се стигат от плочката „Акциите“
       за най-много три хода; печата пътя;
  G3   мутация върху един уред: копие на файла му с дата 30 дни преди петъка; оптиката, построена
       с копието, показва уреда като „застоял“ на всяка страница и никъде като „жив“;
  G4   числата: зоната „светлините“ срещу файла със светлините, зоната „src“ срещу файла на уреда
       в data-src, зоната „ured“: датата е тази, която уредът дава сега, а възрастта е петъкът
       минус нея;
  G6   няма „прогноз“, „препоръ“, „сигнал“ във видимия текст.

  python verify_optics.py --week-end 2026-11-20 [--out-dir ПАПКА] [--lights ФАЙЛ] [--mutate КЛЮЧ]
Изход 0: всичко минава; 1: нещо не минава. Печата до 30 реда.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import sys
import tempfile
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import build_glass as bg
import build_optics as bo
import optics_catalog as oc
import verify_glass as vg

HERE = Path(__file__).resolve().parent


class Page(HTMLParser):
    """Връзките, котвите, картите на уредите, улиците и видимият текст по зони."""

    def __init__(self):
        super().__init__()
        self.links, self.ids, self.ureds, self.streets = [], set(), [], 0
        self.zone, self.stack, self.skip = "chrome", [], 0
        self.text: dict[str, list] = {}
        self.cur_ured = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if "id" in a:
            self.ids.add(a["id"])
        if "data-street" in a:
            self.streets += 1
        if tag == "a" and a.get("href"):
            self.links.append((a["href"], a.get("data-hop", ""), a.get("data-optics-door")))
        if tag == "div":
            src = a.get("data-src")
            self.stack.append((self.zone, self.cur_ured))
            if "data-zone" in a:
                self.zone = a["data-zone"] + (f"|{src}" if src else "")
            if "data-ured" in a:
                self.cur_ured = dict(a)
                self.ureds.append(self.cur_ured)
                self.cur_ured["_text"] = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        if tag == "div" and self.stack:
            self.zone, self.cur_ured = self.stack.pop()

    def handle_data(self, data):
        if self.skip:
            return
        self.text.setdefault(self.zone, []).append(data)
        if self.cur_ured is not None:
            self.cur_ured["_text"].append(data)


_cache: dict[Path, Page] = {}


def parse(p: Path) -> Page:
    if p not in _cache:
        x = Page()
        x.feed(p.read_text(encoding="utf-8"))
        _cache[p] = x
    return _cache[p]


def resolve(href: str, here: Path) -> tuple[Path | None, str]:
    """(файл, котва) за връзка; None за външна (http)."""
    if href.startswith("http"):
        return None, ""
    path, _, anchor = href.partition("#")
    if path.startswith("file:///"):
        return Path(unquote(path[8:])), anchor
    if not path:
        return here, anchor
    return (here.parent / path).resolve(), anchor


def check_link(href: str, here: Path) -> str | None:
    f, anchor = resolve(href, here)
    if f is None:
        return None
    if not f.exists():
        return f"{here.name}: връзката {href} не води до файл"
    if anchor and f.suffix == ".html" and anchor not in parse(f).ids:
        return f"{here.name}: котвата #{anchor} я няма в {f.name}"
    return None


# ── G1 ──────────────────────────────────────────────────────────────────────
def g1(out: Path, we: str, d: dict) -> tuple[list, list]:
    bad, rows = [], []
    glass = out / "staklo" / f"{we}.html"
    gp = parse(glass)
    doors = {}
    for href, _, door in gp.links:
        if door:
            m = re.search(r"/t(\d+)\.html$", href)
            doors[int(m[1])] = resolve(href, glass)[0]
    seen_links = 0
    for t in d["tiles"]:
        tid = t["id"]
        cont = doors.get(tid)
        if not cont or not cont.exists():
            bad.append(f"плочка {tid}: няма врата към оптиката")
            continue
        cp = parse(cont)
        members = [(h, cont) for h, hop, _ in cp.links if hop == "2" and re.match(rf"t{tid}-", h)]
        hops = []
        for href, here in members:
            mp_path = resolve(href, here)[0]
            if not mp_path.exists():
                bad.append(f"плочка {tid}: членът {href} липсва")
                continue
            mp = parse(mp_path)
            if mp.streets:
                hops.append(2)
                continue
            st = [resolve(h, mp_path)[0] for h, hop, _ in mp.links if hop == "3"]
            ok = [p for p in st if p.exists() and parse(p).streets]
            if ok:
                hops.append(3)
            else:
                bad.append(f"плочка {tid}: от члена {href} няма улица до третия ход")
        if len(members) != len(t["members"]):
            bad.append(f"плочка {tid}: членове в оптиката {len(members)}, във файла {len(t['members'])}")
        # всяка връзка на всяка страница от плочката надолу води някъде
        q, seen = deque([cont]), {cont}
        while q:
            p = q.popleft()
            pg = parse(p)
            for href, hop, _ in pg.links:
                seen_links += 1
                err = check_link(href, p)
                if err:
                    bad.append(err)
                    continue
                f, _ = resolve(href, p)
                if f and f.suffix == ".html" and f.parent == cont.parent and f not in seen:
                    seen.add(f)
                    q.append(f)
            for u in pg.ureds:
                if u.get("data-cwd") and not Path(u["data-cwd"]).exists():
                    bad.append(f"{p.name}: папката на {u['data-ured']} липсва")
                if u.get("data-script") and not Path(u["data-script"]).exists():
                    bad.append(f"{p.name}: скриптът на {u['data-ured']} липсва")
        rows.append((tid, t["name"], len(members), max(hops) if hops else None, len(seen)))
    return bad, rows + [("връзки", seen_links)]


# ── G2 ──────────────────────────────────────────────────────────────────────
G2_TARGETS = [
    ("1. Плочката „Акциите“ (SPY до серията)", ["ul-arch-px_spy_daily.html"]),
    ("2. Сектори и имена; защо; чужбина", ["imena-Technology.html", "ured:news", "ul-arch-px_stoxx_daily.html"]),
    ("3. Радарът за технологиите и какво имаме", ["ured:s9_tech", "ured:raft"]),
    ("4. Позиционирането и ревизиите", ["ured:cot", "ured:valuation", "ured:revizii"]),
    ("5. Дефанзивни срещу рискови, активите, междупазарните", ["ul-baro-XLY-XLP.html", "t7.html", "t4.html"]),
    ("6. Подобен синхрон и тихият кредит (вън от петте)", ["t3.html", "ured:fragility"]),
    ("7. Канарчетата (вън от петте)", ["ul-arch-px_kre_daily.html"]),
]


def g2(out: Path, we: str) -> tuple[list, list]:
    """Обхождане в ширина от плочката „Акциите“ (ход 1 е континентът t5)."""
    folder = out / "optika" / we
    start = folder / "t5.html"
    dist, prev = {start.name: 1}, {start.name: None}
    q = deque([start])
    while q:
        p = q.popleft()
        h = dist[p.name]
        pg = parse(p)
        for u in pg.ureds:
            key = "ured:" + u["data-ured"]
            cost = h if u.get("data-cwd") else h + 1  # командата е на страницата; страницата на уреда е още един ход
            if key not in dist or dist[key] > cost:
                dist[key], prev[key] = cost, p.name
        for href, _, _ in pg.links:
            f, _ = resolve(href, p)
            if f and f.parent == folder and f.suffix == ".html" and f.exists() and f.name not in dist:
                dist[f.name], prev[f.name] = h + 1, p.name
                q.append(f)
    bad, rows = [], []
    for label, targets in G2_TARGETS:
        parts = []
        for tg in targets:
            if tg not in dist:
                bad.append(f"G2 {label}: {tg} не се стига")
                continue
            path, x = [], tg
            while x:
                path.append(x)
                x = prev.get(x)
            parts.append((tg, dist[tg], " › ".join(["стъклото"] + list(reversed(path)))))
            if dist[tg] > 3:
                bad.append(f"G2 {label}: {tg} е на {dist[tg]} хода")
        rows.append((label, parts))
    return bad, rows


# ── G4 и G6 ─────────────────────────────────────────────────────────────────
_facts: dict[str, tuple] = {}


def src_facts(src: str) -> tuple:
    if src in _facts:
        return _facts[src]
    p = Path(src)
    if p.is_dir():
        objs = []
        for f in sorted(p.glob("*.jsonl"))[-11:]:
            objs += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        res = vg.file_facts(objs)
    elif p.suffix == ".json":
        res = vg.file_facts(json.loads(p.read_text(encoding="utf-8")))
    else:  # .csv, .md: числата и датите в текста
        txt = p.read_text(encoding="utf-8")
        res = vg.file_facts([txt])
    res = Facts(*res)
    _facts[src] = res
    return res


class Facts:
    """Числата и датите на файл, подредени за бързо търсене. Правилото е това на verify_glass:
    числото е във файла до показаните знаци (със знака, или без знак по модул), или е част от низ
    от файла; датата ДД.ММ(.ГГГГ) е дата от файла."""

    def __init__(self, nums, strs, dates):
        self.r = {k: {round(x, k) for x in nums} for k in range(6)}
        self.ra = {k: {round(abs(x), k) for x in nums} for k in range(6)}
        self.blob = " ".join(bg.clean(x) for x in strs if not re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", x))
        self.d3 = {(x[8:10], x[5:7], x[:4]) for x in dates}
        self.d2 = {(x[8:10], x[5:7]) for x in dates}


def fast_check(text: str, f: Facts, where: str) -> tuple[list, int]:
    bad, n = [], 0
    for m in vg.DATE_RE.finditer(text):
        n += 1
        if not ((m[1], m[2], m[3]) in f.d3 if m[3] else (m[1], m[2]) in f.d2):
            bad.append(f"{where}: датата {m[0]} я няма във файла")
    for m in vg.NUM_RE.finditer(vg.DATE_RE.sub(" ", text)):
        n += 1
        sign, body = m[1], m[2]
        dec = len(body.split(",")[1]) if "," in body else 0
        val = float(body.replace(",", ".")) * (-1 if sign in ("−", "-") else 1)
        hit = dec < 6 and (round(val, dec) in f.r[dec] or (not sign and val in f.ra[dec]))
        if not hit and not sign and re.search(rf"(?<![\d,.]){re.escape(body)}(?![\d,])", f.blob):
            hit = True
        if not hit:
            bad.append(f"{where}: числото {sign}{body} го няма във файла")
    return bad, n


AGE_RE = re.compile(r"данни към (\d{2})\.(\d{2})\.(\d{4}) · (\d+) д\.")


def g4(out: Path, we: str, d: dict, cat: dict | None = None) -> tuple[list, dict]:
    folder = out / "optika" / we
    lf = Facts(*vg.file_facts(d))
    bad, cnt = [], {"lights": 0, "src": 0, "ured": 0, "pages": 0}
    fri = dt.date.fromisoformat(we)
    before = f"{(fri + dt.timedelta(days=1)).isoformat()}T23:59:59"
    now_dates: dict[str, str | None] = {}
    for p in sorted(folder.glob("*.html")):
        pg = parse(p)
        cnt["pages"] += 1
        for zone, parts in pg.text.items():
            text = " ".join(" ".join(parts).split())
            low = text.lower()
            for w in vg.BANNED:
                if w in low:
                    bad.append(f"G6 {p.name}: думата „{w}“")
            if zone == "lights":
                b, n = fast_check(text, lf, p.name)
                bad += b
                cnt["lights"] += n
            elif zone.startswith("src|"):
                b, n = fast_check(text, src_facts(zone[4:]), f"{p.name} ({Path(zone[4:]).name})")
                bad += b
                cnt["src"] += n
        for u in pg.ureds:
            key, shown = u["data-ured"], " ".join("".join(u["_text"]).split())
            if key not in now_dates:
                now_dates[key] = bo.read_date((cat or oc.U)[key].get("date"), before)
            if (u.get("data-date") or None) != now_dates[key]:
                bad.append(f"G4 {p.name}: {key} носи дата {u.get('data-date')}, уредът дава {now_dates[key]}")
            m = AGE_RE.search(shown)
            if m:
                cnt["ured"] += 1
                iso = f"{m[3]}-{m[2]}-{m[1]}"
                if iso != u.get("data-date"):
                    bad.append(f"G4 {p.name}: {key} показва {iso}, а данните му са {u.get('data-date')}")
                if int(m[4]) != max(0, (fri - dt.date.fromisoformat(iso)).days):
                    bad.append(f"G4 {p.name}: {key}: възрастта {m[4]} д. не е петъкът минус датата")
    return bad, cnt


# ── G3 ──────────────────────────────────────────────────────────────────────
def g3(we: str, d: dict, key: str) -> tuple[list, list]:
    """Мутация върху копие на файла на уреда: датата 30 дни преди петъка."""
    bad, rows = [], []
    u = oc.U[key]
    spec = u["date"]
    if spec[0] != "json":
        return [f"G3: уредът {key} не е с дата в JSON; избери друг"], rows
    old = (dt.date.fromisoformat(we) - dt.timedelta(days=30)).isoformat()
    before = bo.ured_view(key, we)
    rows.append(f"преди мутацията: {key} е „{bo.STATUS_BG[before['status']]}“, данни към {before['date']}")
    if before["status"] != "zhiv":
        bad.append(f"G3: {key} трябва да е жив преди мутацията, а е {before['status']}")
    with tempfile.TemporaryDirectory() as tmp:
        data = json.loads(Path(spec[1]).read_text(encoding="utf-8"))
        node = data
        for k in spec[2][:-1]:
            node = node[k]
        node[spec[2][-1]] = old
        mf = Path(tmp) / Path(spec[1]).name
        mf.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        cat = copy.deepcopy(oc.U)
        cat[key]["date"] = ("json", mf, spec[2])
        out = Path(tmp) / "out"
        bo.build(we, d, out, cat)
        n_cards, n_bad = 0, 0
        for p in sorted((out / "optika" / we).glob("*.html")):
            pg = Page()
            pg.feed(p.read_text(encoding="utf-8"))
            for c in pg.ureds:
                if c["data-ured"] != key:
                    continue
                n_cards += 1
                txt = "".join(c["_text"])
                if "u-zastoyal" not in c.get("class", "") or "застоял" not in txt or "жив" in txt:
                    n_bad += 1
        rows.append(f"след мутацията (данни към {old}): {n_cards} карти на {key}, „застоял“ на всички: "
                    f"{'да' if n_cards and not n_bad else 'не'}")
        if not n_cards or n_bad:
            bad.append(f"G3: {n_bad} от {n_cards} карти на {key} не показват „застоял“")
    return bad, rows


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-end", required=True)
    ap.add_argument("--out-dir")
    ap.add_argument("--lights")
    ap.add_argument("--mutate", default="barometar")
    ap.add_argument("--paths", action="store_true", help="печата пътищата на G2")
    a = ap.parse_args()
    out = Path(a.out_dir) if a.out_dir else HERE
    lights = Path(a.lights) if a.lights else bg.LIGHTS_DIR / f"ilu_lights_{a.week_end}.json"
    d = json.loads(lights.read_text(encoding="utf-8"))
    b1, r1 = g1(out, a.week_end, d)
    b2, r2 = g2(out, a.week_end)
    b4, c4 = g4(out, a.week_end, d)
    b3, r3 = g3(a.week_end, d, a.mutate)
    bad = b1 + b2 + b3 + b4
    lines = [f"G1: {sum(1 for r in r1 if isinstance(r[0], int) and r[3] and r[3] <= 3)} от 13 плочки стигат улица "
             f"за <=3 хода; {r1[-1][1]} връзки проверени; " + ", ".join(f"{r[0]}:{r[2]}чл/{r[3]}х" for r in r1 if isinstance(r[0], int))]
    if a.paths:
        for label, parts in r2:
            lines.append(f"G2 {label}: " + "; ".join(f"{tg} за {h} хода" for tg, h, _ in parts))
    else:
        lines.append(f"G2: {len(r2)} пътя от пробата, най-дълъг {max(h for _, ps in r2 for _, h, _ in ps)} хода")
    lines += [f"G3: {x}" for x in r3]
    lines.append(f"G4: {c4['pages']} страници; числа от светлините {c4['lights']}, от уредите {c4['src']}, "
                 f"дати на уреди {c4['ured']}")
    lines += [f"  НЕ: {x}" for x in bad[:30 - len(lines) - 1]]
    lines.append("  минава" if not bad else f"  не минава ({len(bad)})")
    print("\n".join(lines[:30]))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
