"""Проверката на стъклото (ИЛЮ4, гейтове G2 и G6 и броят на числата).

За всяка седмица чете построената страница staklo/<петък>.html, текста staklo/<петък>.txt и
файла със светлините, и проверява:
  G2   всяко число във видимия текст на зоната „светлините“ (и в текста) е във файла:
       като число (до показаните знаци, със знака) или като част от низ от файла (име, котва),
       датите като дата от файла;
  G2в  числата във „вратите“ са датите, които дава build_glass.doors() (те не са от светлините);
  път  във видимия текст няма път до файл;
  G6   няма „прогноз“, „препоръ“, „сигнал“;
  ред  текстът е до 20 реда;
  брой колко числа носи страницата: всички видими числа и отделно без цифрите в имената.

  python verify_glass.py --week-end 2026-11-20 [--out-dir ПАПКА] [--lights ФАЙЛ]
Изход 0: всичко минава; 1: нещо не минава (печата кое, най-много 30 реда).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import build_glass as bg

HERE = Path(__file__).resolve().parent
DATE_RE = re.compile(r"(?<![\d,])(\d{2})\.(\d{2})(?:\.(\d{4}))?(?![\d,])")
NUM_RE = re.compile(r"(?<![\w,.])([+−-]?)(\d+(?:,\d+)?)(?![\d,])")
BANNED = ("прогноз", "препоръ", "сигнал")


class Text(HTMLParser):
    """Видимият текст по зони (data-zone), без script и style."""

    def __init__(self):
        super().__init__()
        self.zone, self.stack, self.skip, self.out = "chrome", [], 0, {"chrome": [], "lights": [], "doors": []}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "div":
            self.stack.append(self.zone)
            if "data-zone" in a:
                self.zone = a["data-zone"]

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        if tag == "div" and self.stack:
            self.zone = self.stack.pop()

    def handle_data(self, data):
        if not self.skip:
            self.out[self.zone].append(data)


def file_facts(d) -> tuple[list, list, set]:
    nums, strs = [], []

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            nums.append(float(x))
        elif isinstance(x, str):
            strs.append(x)
            for m in re.finditer(r"-?\d+(?:\.\d+)?", x):
                nums.append(float(m[0]))
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(k)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", json.dumps(d, ensure_ascii=False)))
    return nums, strs, dates


def names_of(d) -> list:
    out = []
    for t in d.get("tiles", []):
        out.append(t["name"])
        for m in t.get("members", []):
            out += [m.get("name", ""), bg.member_name(m.get("name", ""))]
        ls = (t.get("lupa") or {}).get("strongest") or {}
        if ls.get("name"):
            out.append(bg.clean(ls["name"]))
    out += [a.get("name", "") for a in (d.get("abroad") or {}).get("items", [])]
    return sorted({n for n in out if n}, key=len, reverse=True)


def check_numbers(text: str, d, nums, strs, dates, where: str) -> tuple[list, int, int]:
    bad = []
    blob = " ".join(bg.clean(s) for s in strs)
    stripped = text
    for n in names_of(d):
        stripped = stripped.replace(n, " ")
    n_all = n_data = 0
    for src, count_data in ((text, False), (stripped, True)):
        t = src
        for m in DATE_RE.finditer(t):
            if count_data:
                n_data += 1
                continue
            n_all += 1
            dd, mm, yy = m[1], m[2], m[3]
            ok = any(x[8:10] == dd and x[5:7] == mm and (not yy or x[:4] == yy) for x in dates)
            if not ok:
                bad.append(f"{where}: датата {m[0]} я няма във файла")
        t = DATE_RE.sub(" ", t)
        for m in NUM_RE.finditer(t):
            if count_data:
                n_data += 1
                continue
            n_all += 1
            sign, body = m[1], m[2]
            dec = len(body.split(",")[1]) if "," in body else 0
            val = float(body.replace(",", ".")) * (-1 if sign in ("−", "-") else 1)
            hit = any(round(x, dec) == round(val, dec) or (not sign and round(abs(x), dec) == val) for x in nums)
            if not hit and not sign and re.search(rf"(?<![\d,.]){re.escape(body)}(?![\d,])", blob):
                hit = True
            if not hit:
                bad.append(f"{where}: числото {sign}{body} го няма във файла")
    return bad, n_all, n_data


def verify(week_end: str, out: Path, lights: Path | None) -> int:
    lights = lights or bg.LIGHTS_DIR / f"ilu_lights_{week_end}.json"
    d = json.loads(lights.read_text(encoding="utf-8"))
    nums, strs, dates = file_facts(d)
    page = (out / "staklo" / f"{week_end}.html").read_text(encoding="utf-8")
    txt = (out / "staklo" / f"{week_end}.txt").read_text(encoding="utf-8")
    p = Text()
    p.feed(page)
    zones = {k: " ".join(" ".join(v).split()) for k, v in p.out.items()}
    bad = []
    b1, n_all, n_data = check_numbers(zones["lights"], d, nums, strs, dates, "стъклото")
    b2, t_all, _ = check_numbers(txt, d, nums, strs, dates, "текстът")
    bad += b1 + b2
    # „вратите“: датите им са от build_glass.doors(), не от светлините
    door_dates = {bg.ddmm(x["date"]) for x in bg.doors(week_end) if x["date"]}
    door_found = DATE_RE.findall(zones["doors"])
    for dd, mm, _ in door_found:
        if f"{dd}.{mm}" not in door_dates:
            bad.append(f"вратите: {dd}.{mm} не е от doors()")
    rest = NUM_RE.findall(DATE_RE.sub(" ", zones["doors"]))
    if rest:
        bad.append(f"вратите: числа извън датите {rest}")
    ch_nums = NUM_RE.findall(DATE_RE.sub(" ", zones["chrome"]))
    ch_dates = DATE_RE.findall(zones["chrome"])
    for dd, mm, yy in ch_dates:
        if f"{yy}-{mm}-{dd}" != week_end:
            bad.append(f"шапката: датата {dd}.{mm}.{yy} не е петъкът")
    if ch_nums:
        bad.append(f"шапката: числа {ch_nums}")
    allvis = " ".join(zones.values()) + " " + txt
    if re.search(r"[A-Za-z]:\\|[A-Za-z]:/|\\Projects|/Projects|\.json|\.py\b", allvis):
        bad.append("пътища: във видимия текст има път до файл")
    for w in BANNED:
        if w in allvis.lower():
            bad.append(f"G6: думата „{w}…“ е на страницата")
    lines = [x for x in txt.splitlines() if x.strip()]
    if len(lines) > 20:
        bad.append(f"текстът е {len(lines)} реда, над 20")
    total = n_all + len(door_found) + len(ch_dates)
    total_data = n_data + len(door_found) + len(ch_dates)
    print(f"{week_end}: числа на стъклото {total} (без цифрите в имената {total_data}); "
          f"в зоната на светлините {n_all}, проверени срещу файла; вратите {len(door_found)}; "
          f"текстът {len(lines)} реда, {t_all} числа")
    for b in bad[:30]:
        print("  НЕ:", b)
    print("  минава" if not bad else f"  не минава: {len(bad)}")
    return 0 if not bad else 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-end", required=True)
    ap.add_argument("--out-dir")
    ap.add_argument("--lights")
    a = ap.parse_args()
    return verify(a.week_end, Path(a.out_dir) if a.out_dir else HERE, Path(a.lights) if a.lights else None)


if __name__ == "__main__":
    sys.exit(main())
