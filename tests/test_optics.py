"""Оптиката (ИЛЮ5): от плочка до име или серия за три хода; застоялият уред не изглежда жив.

Ползват истинския файл със светлините за 20.11.2026 и живите уреди (не измислени числа);
повредите са върху копие в tmp.
"""
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_glass as bg  # noqa: E402
import build_optics as bo  # noqa: E402
import verify_optics as vo  # noqa: E402

WEEK = "2026-11-20"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    p = bg.LIGHTS_DIR / f"ilu_lights_{WEEK}.json"
    if not p.exists():
        pytest.skip(f"няма {p.name}")
    out = tmp_path_factory.mktemp("opt")
    assert bg.build(WEEK, p, out) == 0
    return out, json.loads(p.read_text(encoding="utf-8"))


def test_every_tile_has_a_door_on_the_glass(built):
    out, d = built
    html = (out / "staklo" / f"{WEEK}.html").read_text(encoding="utf-8")
    doors = re.findall(r'href="\.\./optika/2026-11-20/t(\d+)\.html" data-optics-door', html)
    assert sorted(map(int, doors)) == [t["id"] for t in d["tiles"]]


def test_g1_every_member_reaches_a_street_in_three(built):
    out, d = built
    vo._cache.clear()
    bad, rows = vo.g1(out, WEEK, d)
    assert bad == []
    assert all(r[3] is not None and r[3] <= 3 for r in rows if isinstance(r[0], int))


def test_g2_the_five_from_the_trial(built):
    out, _ = built
    vo._cache.clear()
    bad, rows = vo.g2(out, WEEK)
    assert bad == []
    assert max(h for _, ps in rows for _, h, _ in ps) <= 3


def test_g4_numbers_come_from_files(built):
    out, d = built
    vo._cache.clear()
    bad, cnt = vo.g4(out, WEEK, d)
    assert bad == [] and cnt["lights"] > 0 and cnt["src"] > 0


def test_g4_catches_a_changed_number(built, tmp_path):
    out, d = built
    import shutil
    shutil.copytree(out / "staklo", tmp_path / "staklo")
    shutil.copytree(out / "optika", tmp_path / "optika")
    p = tmp_path / "optika" / WEEK / "ul-arch-px_spy_daily.html"
    txt = p.read_text(encoding="utf-8")
    # последното наблюдение в таблицата става число, което го няма в архива
    new = re.sub(r'(<tr><td class="n">20\.11\.2026</td><td class="n">)[^<]+', r"\g<1>123456789", txt, count=1)
    assert new != txt
    p.write_text(new, encoding="utf-8")
    vo._cache.clear()
    bad, _ = vo.g4(tmp_path, WEEK, d)
    assert any("123456789" in b for b in bad)


def test_g1_catches_a_missing_street(built, tmp_path):
    out, d = built
    import shutil
    shutil.copytree(out / "staklo", tmp_path / "staklo")
    shutil.copytree(out / "optika", tmp_path / "optika")
    (tmp_path / "optika" / WEEK / "ul-arch-px_spy_daily.html").unlink()
    vo._cache.clear()
    bad, _ = vo.g1(tmp_path, WEEK, d)
    assert any("px_spy_daily" in b for b in bad)


def test_g3_stale_instrument_never_looks_alive(built):
    _, d = built
    bad, rows = vo.g3(WEEK, d, "barometar")
    assert bad == [], rows


def test_stale_card_says_so():
    v = {"key": "x", "name": "уред", "kind": "page", "status": "zastoyal", "date": "2026-10-01", "age": 50,
         "tol": 10, "tol_src": "", "href": "file:///C:/x.html", "cmd": None, "cwd": None, "script": None,
         "data_date": None, "how": ""}
    h = bo.ured_html(v)
    assert "u-zastoyal" in h and "застоял" in h and "жив" not in h and "50 д." in h and "праг 10 д." in h


def test_date_formats_from_instruments():
    assert bo.norm_date("2026-11-21 11:46 UTC") == "2026-11-21"
    assert bo.norm_date("29.06.2026 16:37") == "2026-06-29"
    assert bo.norm_date("2026-10") == "2026-10-31"
    assert bo.norm_date("W47 · 16-20.11.2026") == "2026-11-20"
