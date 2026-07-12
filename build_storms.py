# -*- coding: utf-8 -*-
"""
ИМЕНУВАНИТЕ БУРИ — детерминистичният билд (мандат №26, спец 05-SPEC-NAMED-STORMS.md v1.0).

Чете бурите-YAML от vault-а (chronicle/storms/*.yaml) + СЪЩАТА жива снимка на организма,
която build_screen.py ползва (сателит · regime_episodes · vote_consistency · data-core state —
всичко READ-ONLY, нула нови fetch-ове), преизчислява всяко условие, сваля статуса по §4
(active / weakening / inactive; dwell 2 симетрично; <50% правило), пише storms_state.json
(до другите *_data.json) и append-ва статус-преходите в chronicle/STORMS.md.

Машината само БРОИ и сваля статуса; тя НЕ именува (§1/§6). Имена дава само собственикът.
Нула записи в data-core. Двоен пуск = байт-идентичен (при непроменени входове журналът НЕ расте).

Ритуалната последователност (съботно): build_storms.py → build_screen.py → build_vrm_screen.py.

CLI (по подразбиране = production пътищата; override-ите са САМО за теста в scratchpad):
  --storms-dir PATH   папката с бурите-YAML (default: vault chronicle/storms)
  --out PATH          къде се пише storms_state.json (default: C:\\Projects\\_weekly_screen)
  --journal PATH      журналът за append (default: vault chronicle/STORMS.md)
  --snapshot PATH     мокната merged снимка (JSON) вместо живите източници — само за тест
"""
import json, argparse
from collections import Counter
from pathlib import Path
from datetime import date as _date

VAULT     = Path(r"C:\Tsachev Knowledge OS\tsachev-ops\chronicle")
STORMS_DIR = VAULT / "storms"
JOURNAL    = VAULT / "STORMS.md"
OUT        = Path(r"C:\Projects\_weekly_screen")
HYPE_FILE  = Path(r"C:\Projects\ai-hype-monitor\app\data\v2\euphoria_series.json")  # КАИШКАТА (READ-ONLY)

# фиксиран ред на ключовете за детерминизъм в изхода
_COND_KEYS = ("id", "voice", "label", "field", "test", "core", "link", "lies_when", "holds")

# Рендер-слой: линковете идват от бурите-YAML във vault-а (ЗАМРАЗЕН — не се пипа). Self-екранът
# там е записан като http://localhost:8151/<x>; при рендер го пренаписваме до относителен път
# (маха се само префиксът http://localhost:8151/). Нищо друго в логиката не се променя.
_SELF_PREFIX = "http://localhost:8151/"
def _relativize_link(link):
    if isinstance(link, str) and link.startswith(_SELF_PREFIX):
        return link[len(_SELF_PREFIX):] or "./"
    return link

# ------------------------------------------------------------------ снимка --
def load_hype():
    """КАИШКАТА (AI Hype Monitor) вътрешният разнобой — от ПОСЛЕДНИЯ ред на series, в който И
    z_multiple, И z_promise_delivery са не-null (КАИШКАТА диша със SEC-ритъм — по-бавен от
    съботния). divergence = множител z − промис/деливъри z. READ-ONLY, нула мрежа. Липсващ/
    нечетим файл или нула валидни редове → вдига (условието пада + бележка, билдът НЕ крашва)."""
    data = json.loads(Path(HYPE_FILE).read_text(encoding="utf-8"))
    row = None
    for r in (data.get("series") or []):
        if r.get("z_multiple") is not None and r.get("z_promise_delivery") is not None:
            row = r
    if row is None:
        raise ValueError("euphoria: няма ред със z_multiple и z_promise_delivery")
    zm, zpd = float(row["z_multiple"]), float(row["z_promise_delivery"])
    return {"divergence_sigma": round(zm - zpd, 4), "z_multiple": zm,
            "z_promise_delivery": zpd, "as_of": str(row.get("date"))[:10]}

def build_snapshot():
    """Merged снимка от СЪЩИТЕ източници като build_screen.py (защитено; липсващ орган →
    полето просто липсва → условието му пада honestly, билдът не крашва). as_of = най-свежата
    входна дата (детерминистичният седмичен ключ)."""
    import build_screen as bs
    snap = {"regime": {}, "lenses": {}, "core": {}, "votes": {}}
    errs = []
    dates = []
    try:
        age = bs.load_age()
        snap["regime"] = {"current": age["regime"], "age_weeks": age["age"],
                          "median_weeks": age["median"], "max_weeks": age["max"]}
        if age.get("asof"): dates.append(str(age["asof"])[:10])
    except Exception as e:
        errs.append(f"regime: {e}")
    try:
        sat = bs.load_satellite(); rg = sat.get("regimes", {})
        def _lbl(k): return (rg.get(k) or {}).get("regime_label_bg")
        us, eu, cn = _lbl("us_macro"), _lbl("eu_macro"), _lbl("cn_macro")
        nonrefl = sum(1 for x in (us, eu, cn) if x and "рефлац" not in x.lower())
        snap["lenses"] = {"us": us, "eu": eu, "cn": cn, "non_reflation_count": nonrefl}
        for k in ("us_macro", "eu_macro", "cn_macro"):
            a = (rg.get(k) or {}).get("as_of")
            if a: dates.append(str(a)[:10])
        vrm = rg.get("vrm") or {}
        if vrm.get("alignment_total") is not None:
            snap["core"]["alignment_total"] = vrm["alignment_total"]
    except Exception as e:
        errs.append(f"lenses: {e}")
    try:
        core = bs.load_core(); g = core.get("gms") or {}
        snap["core"].update({"ks_margin_pct": core["margin"], "ks_active": core["ks_active"],
                             "gms_score": g.get("score"), "gms_max": g.get("max"),
                             "gms_tier": g.get("tier"), "alignment_score": core["align"],
                             "s11_net_confirm": core["s11_net"]})
        if core.get("ks_asof"): dates.append(str(core["ks_asof"])[:10])
    except Exception as e:
        errs.append(f"core: {e}")
    try:
        votes = bs.load_votes(); c = Counter(v["class"] for v in votes)
        snap["votes"] = {"firm_count": c.get("твърд поддръжник", 0),
                         "against_count": c.get("твърдо против", 0),
                         "swing_count": c.get("люлее се", 0),
                         "mixed_count": c.get("смесен", 0)}
    except Exception as e:
        errs.append(f"votes: {e}")
    try:
        snap["hype"] = load_hype()          # КАИШКАТА: SEC-ритъм; as_of е СВОЙ, НЕ храни глобалния as_of
    except Exception as e:
        errs.append(f"hype: {e}")
    snap["as_of"] = max(dates) if dates else None
    if errs: snap["_errors"] = errs
    return snap

# ------------------------------------------------------------------ оценка --
def _num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def resolve_field(snapshot, path):
    """Резолвва dot-path в снимката. Връща (стойност, резолвнато?)."""
    cur = snapshot
    for seg in str(path).split("."):
        if isinstance(cur, dict):
            if seg not in cur: return (None, False)
            cur = cur[seg]
        elif isinstance(cur, list):
            try: cur = cur[int(seg)]
            except (ValueError, IndexError): return (None, False)
        else:
            return (None, False)
    return (cur, True)

def eval_test(value, test):
    """Операторите на §4: >= <= != == > < срещу число · == <ЕТИКЕТ> категорийно · true/false."""
    t = str(test).strip()
    op, rhs = None, t
    for cand in (">=", "<=", "!=", "==", ">", "<", "="):
        if t.startswith(cand):
            op, rhs = cand, t[len(cand):].strip(); break
    if op is None: op = "=="          # гол токен → равенство
    if op == "=": op = "=="
    low = rhs.lower()
    if low in ("true", "false"):
        want = (low == "true")
        if op == "==": return bool(value) is want
        if op == "!=": return bool(value) is not want
        return False
    vnum, rnum = _num(value), _num(rhs)
    if op in (">=", "<=", ">", "<"):
        if vnum is None or rnum is None: return False
        return {">=": vnum >= rnum, "<=": vnum <= rnum, ">": vnum > rnum, "<": vnum < rnum}[op]
    if op == "==":
        if vnum is not None and rnum is not None: return vnum == rnum
        return str(value).strip() == rhs
    if op == "!=":
        if vnum is not None and rnum is not None: return vnum != rnum
        return str(value).strip() != rhs
    return False

def _age_days(born, asof):
    try:
        b = _date(*(int(x) for x in str(born)[:10].split("-")))
        a = _date(*(int(x) for x in str(asof)[:10].split("-")))
        # буря, родена СЛЕД датата на снимката (кръщене между съботи), е на 0 дни
        # към тази снимка — не „минус N". Презентационно; статусът не ползва age.
        return max(0, (a - b).days)
    except Exception:
        return None

# ------------------------------------------------------------------ статус --
def evaluate_storm(y, snapshot, prior, cur_asof):
    """Чисто преизчисляване: (предната записана буря, живата снимка, cur_asof) → нов запис +
    (по избор) статус-преход. Dwell-стрийкът напредва САМО когато cur_asof надмине записаната
    дата — така повторен пуск същия ден е идемпотентен (§4, гейт 1)."""
    conds = []
    core_ids, core_down = [], {}
    for c in (y.get("conditions") or []):
        cid = c.get("id")
        val, resolved = resolve_field(snapshot, c.get("field"))
        holds = bool(resolved and eval_test(val, c.get("test")))
        rec = {"id": cid, "voice": c.get("voice"), "label": c.get("label"),
               "field": c.get("field"), "test": c.get("test"), "core": bool(c.get("core")),
               "link": _relativize_link(c.get("link")), "lies_when": c.get("lies_when"), "holds": holds}
        conds.append({k: rec.get(k) for k in _COND_KEYS})
        if rec["core"]:
            core_ids.append(cid); core_down[cid] = not holds

    # базата за dwell/преход (идемпотентно спрямо cur_asof)
    if prior is None:
        base_streak = {cid: 0 for cid in core_ids}
        base_status = None                                   # раждането е на собственика — без журнал
    elif prior.get("as_of") == cur_asof:
        base_streak = prior.get("baseline_down_streak") or {cid: 0 for cid in core_ids}
        base_status = prior.get("baseline_status")
    else:
        base_streak = prior.get("down_streak") or {cid: 0 for cid in core_ids}
        base_status = prior.get("status")

    new_streak = {cid: (int(base_streak.get(cid, 0)) + 1 if core_down[cid] else 0) for cid in core_ids}

    n_total = len(conds); n_hold = sum(1 for c in conds if c["holds"])
    frac = (n_hold / n_total) if n_total else 0.0
    any_dwell2 = any(new_streak[cid] >= 2 for cid in core_ids)
    any_down1  = any(new_streak[cid] == 1 for cid in core_ids)
    if (n_total and frac < 0.5) or any_dwell2:
        status = "inactive"
    elif any_down1:
        status = "weakening"
    else:
        status = "active"

    slug = y.get("slug") or y.get("_slug")
    name = y.get("name") or slug
    rec = {"slug": slug, "name": name, "says": y.get("says"), "born": y.get("born"),
           "status": status, "as_of": cur_asof,
           "age_days": _age_days(y.get("born"), cur_asof),
           "n_hold": n_hold, "n_total": n_total,
           "conditions": conds, "falsifier": y.get("falsifier"),
           "down_streak": new_streak, "baseline_down_streak": base_streak,
           "baseline_status": base_status}

    transition = None
    if base_status is not None and status != base_status:
        down = [c["label"] or c["id"] for c in conds if c["core"] and not c["holds"]]
        if down:
            driver = ", ".join(down)
        elif n_total and frac < 0.5:
            driver = f"<50% условия ({n_hold}/{n_total})"
        else:
            driver = "—"
        transition = {"as_of": cur_asof, "name": name,
                      "line": f"{cur_asof} · {name} · {base_status} → {status} · {driver}"}
    return rec, transition

# ------------------------------------------------------------------ i/o --
def load_yamls(storms_dir):
    import yaml
    out = []
    for f in sorted(Path(storms_dir).glob("*.yaml"), key=lambda p: p.name):
        if f.name.startswith("_"): continue
        y = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        y["_slug"] = f.stem
        out.append(y)
    return out

def append_journal(journal_path, transitions):
    """Append-only + идемпотентен: ред, чийто подпис (дата · буря · стар → нов) вече е в
    журнала, не се дублира. Няма нови редове → файлът НЕ се пипа (байт-идентичен пуск)."""
    jp = Path(journal_path)
    text = jp.read_text(encoding="utf-8") if jp.exists() else "# ЖУРНАЛЪТ НА ИМЕНУВАНИТЕ БУРИ\n\n## Записи\n\n— журналът започва празен —\n"
    added = []
    for t in transitions:
        sig = t["line"].rsplit(" · ", 1)[0]           # „дата · буря · стар → нов" (без бележката)
        if sig not in text:
            added.append("- " + t["line"])
    if not added:
        return []
    text = text.rstrip("\n") + "\n" + "\n".join(added) + "\n"
    jp.write_text(text, encoding="utf-8")
    return added

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storms-dir", default=str(STORMS_DIR))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--journal", default=str(JOURNAL))
    ap.add_argument("--snapshot", default=None)
    a = ap.parse_args()

    out_dir = Path(a.out); state_path = out_dir / "storms_state.json"
    prior_all = {}
    if state_path.exists():
        try:
            prev = json.loads(state_path.read_text(encoding="utf-8"))
            prior_all = {s["slug"]: s for s in prev.get("storms", [])}
        except Exception:
            prior_all = {}

    yamls = load_yamls(a.storms_dir)

    if a.snapshot:
        snapshot = json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
    elif yamls:
        snapshot = build_snapshot()
    else:
        snapshot = build_snapshot()          # празно → и празната карта носи честна as-of
    cur_asof = snapshot.get("as_of")

    storms, transitions = [], []
    for y in yamls:
        slug = y.get("slug") or y.get("_slug")
        rec, tr = evaluate_storm(y, snapshot, prior_all.get(slug), cur_asof)
        storms.append(rec)
        if tr: transitions.append(tr)
    storms.sort(key=lambda s: s["slug"] or "")

    added = append_journal(a.journal, transitions)

    payload = {"as_of": cur_asof, "n_storms": len(storms), "storms": storms}
    if snapshot.get("_errors"): payload["snapshot_errors"] = snapshot["_errors"]
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                          encoding="utf-8")

    def _safe_print(msg):
        # cp1252 Windows конзола гърми на кирилица; JSON-ът вече е записан — принтът
        # не бива да сваля ритуала (exit 1 след коректен запис). UTF-8 конзола = чист.
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("ascii", errors="replace").decode("ascii"))

    print("STORMS as_of", cur_asof, "| n_storms", len(storms))
    for s in storms:
        _safe_print(f"  · {s['slug']}: {s['status']} ({s['n_hold']}/{s['n_total']} условия · възраст {s['age_days']}д)")
    if added:
        for l in added: _safe_print("JOURNAL+ " + str(l))
    else:
        print("JOURNAL unchanged")
    if snapshot.get("_errors"): print("SNAPSHOT ERRORS:", snapshot["_errors"])
    print("OK ->", state_path)

if __name__ == "__main__":
    main()
