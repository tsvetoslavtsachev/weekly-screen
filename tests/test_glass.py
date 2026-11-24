"""Стъклото (ИЛЮ4): строи се от файла със светлините, всяко число е във файла, сивото е сиво.

Тестовете ползват истинските файлове на линийката за 13.11 и 20.11.2026 (живи изходи, не
измислени числа); мутациите са върху копие в tmp_path.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_glass as bg  # noqa: E402
import verify_glass as vg  # noqa: E402

WEEKS = ["2026-11-13", "2026-11-20"]


def lights(week):
    p = bg.LIGHTS_DIR / f"ilu_lights_{week}.json"
    if not p.exists():
        pytest.skip(f"няма {p.name}")
    return p


@pytest.mark.parametrize("week", WEEKS)
def test_builds_and_every_number_is_in_the_file(week, tmp_path):
    assert bg.build(week, lights(week), tmp_path) == 0
    assert vg.verify(week, tmp_path, lights(week)) == 0
    txt = (tmp_path / "staklo" / f"{week}.txt").read_text(encoding="utf-8").splitlines()
    assert len(txt) <= 20


def test_older_week_does_not_overwrite_index(tmp_path):
    bg.build("2026-11-20", lights("2026-11-20"), tmp_path)
    top = (tmp_path / "index.html").read_text(encoding="utf-8")
    bg.build("2026-11-13", lights("2026-11-13"), tmp_path)
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == top
    assert (tmp_path / "staklo" / "2026-11-13.html").exists()
    idx = (tmp_path / "staklo" / "index.html").read_text(encoding="utf-8")
    assert "2026-11-13.html" in idx and "2026-11-20.html" in idx


def test_g2_tampered_number_is_caught(tmp_path):
    bg.build("2026-11-20", lights("2026-11-20"), tmp_path)
    p = tmp_path / "staklo" / "2026-11-20.html"
    s = p.read_text(encoding="utf-8")
    s2, n = re.subn(r"−8,56%", "−8,57%", s, count=1)
    assert n == 1
    p.write_text(s2, encoding="utf-8")
    assert vg.verify("2026-11-20", tmp_path, lights("2026-11-20")) == 1


def test_g3_stale_tile_is_grey_on_the_page(tmp_path):
    d = json.loads(lights("2026-11-20").read_text(encoding="utf-8"))
    d2 = copy.deepcopy(d)
    t = next(x for x in d2["tiles"] if x["id"] == 5)
    t["state"], t["state_bg"], t["strongest"] = "sivo", "сиво", None
    t["color_why"] = "живи са 0 от 6, под половината"
    f = tmp_path / "l.json"
    f.write_text(json.dumps(d2, ensure_ascii=False), encoding="utf-8")
    bg.build("2026-11-20", f, tmp_path)
    s = (tmp_path / "staklo" / "2026-11-20.html").read_text(encoding="utf-8")
    tile = re.search(r'<article class="tile s-(\w+)" id="t5".*?</article>', s, re.S)
    assert tile[1] == "sivo"
    assert "сиво: живи са 0 от 6, под половината" in tile[0]


def test_missing_lights_file_says_so_on_the_page(tmp_path):
    rc = bg.build("2026-11-27", tmp_path / "nyama.json", tmp_path)
    assert rc == 2
    s = (tmp_path / "staklo" / "2026-11-27.html").read_text(encoding="utf-8")
    assert "липсва" in s and "s-sivo" in s


def test_c_23_11_no_lens_word_no_kill_switch_trail_and_areas(tmp_path):
    """Ц., 23.11.2026: без думата „леща“, без Kill Switch, ходът на VRM и уредите на таблата, тъмно."""
    bg.build("2026-11-20", lights("2026-11-20"), tmp_path)
    s = (tmp_path / "staklo" / "2026-11-20.html").read_text(encoding="utf-8")
    t = (tmp_path / "staklo" / "2026-11-20.txt").read_text(encoding="utf-8")
    for x in (s, t):
        assert "лещ" not in x.lower() and "kill switch" not in x.lower()
    tile13 = re.search(r'id="t13".*?</article>', s, re.S)[0]
    assert tile13.count('<i class="rg') == len(json.loads(lights("2026-11-20").read_text(encoding="utf-8"))
                                               ["tiles"][12]["trail"])
    tile11 = re.search(r'id="t11".*?</article>', s, re.S)[0]
    assert 'class="areas"' in tile11 and "таблото: <b>" in tile11
    assert re.search(r":root\{--bg:#121417", s)


@pytest.mark.parametrize("week", WEEKS)
def test_g6_and_no_paths(week, tmp_path):
    bg.build(week, lights(week), tmp_path)
    s = (tmp_path / "staklo" / f"{week}.html").read_text(encoding="utf-8")
    p = vg.Text()
    p.feed(s)
    vis = " ".join(" ".join(v) for v in p.out.values()).lower()
    for w in vg.BANNED:
        assert w not in vis
    assert not re.search(r"[a-z]:\\|[a-z]:/", vis)


def test_u8_stale_door_is_marked_like_optics(tmp_path, monkeypatch):
    """ИЛЮ7п, У8: вратата към уред над прага на оптиката носи белега „застоял“ (бюрото, 06.11)."""
    import optics_catalog as oc
    bg.build("2026-11-20", lights("2026-11-20"), tmp_path)
    page = (tmp_path / "staklo" / "2026-11-20.html").read_text(encoding="utf-8")
    spans = re.findall(r'<span( class="door-zastoyal")?><a href="[^"]*">([^<]*)</a>(.*?)</span>\s*(?=<span|</div>)', page, re.S)
    by = {name: (bool(cls), rest) for cls, name, rest in spans}
    desk = by["Бюрото, първата страница"]
    assert desk[0] and "застоял" in desk[1], desk
    assert not by["Пулсът, дайджестът"][0]
    # мутация: прагът на бюрото над възрастта му -> белегът изчезва
    monkeypatch.setitem(oc.U["desk"], "tol", 400)
    bg.build("2026-11-20", lights("2026-11-20"), tmp_path / "m")
    page = (tmp_path / "m" / "staklo" / "2026-11-20.html").read_text(encoding="utf-8")
    assert 'class="door-zastoyal"' not in page


def test_zh1_cap_60_numbers_is_a_check(tmp_path, capsys):
    """ИЛЮ7п, Ж1: таванът от 60 числа на първата страница (Ц., 22.11.2026) е проверка, не броене.
    Мутация: повтаряме едно вярно число от файла в зоната на светлините, докато станат 61."""
    week = "2026-11-20"
    bg.build(week, lights(week), tmp_path)
    assert vg.verify(week, tmp_path, lights(week)) == 0
    n = int(re.search(r"без цифрите в имената (\d+)", capsys.readouterr().out).group(1))
    assert n <= 60
    p = tmp_path / "staklo" / f"{week}.html"
    s = p.read_text(encoding="utf-8")
    extra = " −8,56%" * (61 - n)
    s2, k = re.subn(r"−8,56%", "−8,56%" + extra, s, count=1)
    assert k == 1
    p.write_text(s2, encoding="utf-8")
    assert vg.verify(week, tmp_path, lights(week)) == 1
    out = capsys.readouterr().out
    assert "без цифрите в имената 61" in out and re.search(r"НЕ: .*61.*60", out), out
