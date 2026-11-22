# -*- coding: utf-8 -*-
"""ИЛЮ3 В10 (22.11.2026): седмицата на екрана се извежда от датата (build_screen.closed_week).
Събота и неделя дават току-що затворената седмица; от понеделник до петък (петъкът още не е
затворил) дават предишната; седмица през година носи годината и на двете дати."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_screen as B  # noqa: E402


def _cw(d, monkeypatch):
    monkeypatch.delenv("WEEK_FRIDAY", raising=False)
    return B.closed_week(d)


def test_saturday_sunday_monday_give_the_closed_week(monkeypatch):
    w47 = ("2026-11-16", "2026-11-20", "W47 · 16–20.11.2026")
    assert _cw(date(2026, 11, 21), monkeypatch) == w47      # събота
    assert _cw(date(2026, 11, 22), monkeypatch) == w47      # неделя
    assert _cw(date(2026, 11, 23), monkeypatch) == w47      # понеделник: наваксан ход


def test_friday_before_the_close_is_still_the_previous_week(monkeypatch):
    assert _cw(date(2026, 11, 27), monkeypatch) == ("2026-11-16", "2026-11-20", "W47 · 16–20.11.2026")


def test_week_across_the_new_year(monkeypatch):
    assert _cw(date(2027, 1, 2), monkeypatch) == ("2026-12-28", "2027-01-01",
                                                  "W53 · 28.12.2026–01.01.2027")


def test_week_across_a_month(monkeypatch):
    assert _cw(date(2026, 12, 5), monkeypatch)[2] == "W49 · 30.11–04.12.2026"


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("WEEK_FRIDAY", "2026-11-13")
    assert B.closed_week(date(2026, 11, 28))[2] == "W46 · 09–13.11.2026"
