"""Каталогът на оптиката (ИЛЮ5): уредите зад плочките, как се отварят и откъде им се чете датата.

Тук няма числа за показване. Всеки уред казва:
  name   името за човек
  open   какво се отваря (пълен път до страница или документ), или
  cmd    готовата команда за копиране (уредът иска сесия) и cwd, папката, от която се пуска
  date   откъде се чете датата на данните му (от самия уред, никога сметната тук):
           ("json", файл, [ключове])   стойност в JSON файл (първите 10 знака; „ГГГГ-ММ“ е краят на месеца)
           ("text", файл, регулярен израз) дата в текстов файл
           ("git", хранилище, файл)     датата на последния комит на файла
           ("mtime", файл)              датата на последния запис на файла (за построени страници)
           ("newest", папка, шаблон)    най-новият файл по дата в името
           ("canon_min", [серии])       най-старият последен ден сред входовете в канона
  tol    след колко дни без нови данни уредът е застоял. Числата са от договора за каденцията
         C:\\Projects\\data-core\\migrations\\e2_dashboard\\cadence_contract.yaml (полето „толеранс“),
         където органът е в него; другаде е изрично казано откъде е.
  kind   "page" (страница), "doc" (документ, без застояване), "cmd" (команда), "frozen" (замразен по план)
  data   (по желание) втора дата: на данните в хранилището, когато страницата е построена по-рано

Каталогът е свързване, не уред: нищо в уредите не се пипа.
"""
from __future__ import annotations

from pathlib import Path

P = Path(r"C:\Projects")
DC = P / "data-core"
WS = P / "markets" / "weekly-screen"
CANON = DC / "data" / "canonical"
ARCH = P / "price-archive" / "archive"
NEWS = Path(r"C:\Tsachev Knowledge OS\tsachev-ops\news")
MM = P / "macro" / "MacroModel"
MM_PY = r".venv\Scripts\python.exe"

U: dict[str, dict] = {
    # ── пазарите ──
    "kompas": {"name": "Regime Compass (кривата и режимите)", "kind": "page",
               "open": P / "markets/regime-compass/dist/public/index.html",
               "date": ("mtime", P / "markets/regime-compass/dist/public/index.html"),
               "data": ("text", P / "markets/regime-compass/client/src/data/wired.ts", r'asOf"?\s*:\s*"(\d{4}-\d{2}-\d{2})'),
               "tol": 10, "tol_src": "седмичен инджест в събота (saturday-ingest.yml), толерансът като на табла 7/10"},
    "funding": {"name": "Радарът за финансирането на хазната", "kind": "page",
                "open": P / "macro/treasury-funding-radar/docs/index.html",
                "date": ("json", P / "macro/treasury-funding-radar/data/lamps.json", ["generated_at"]),
                "tol": 4, "tol_src": "договорът: funding-radar 1/4"},
    "barometar": {"name": "Барометърът (тълпата)", "kind": "page",
                  "open": P / "markets/etf-rotationradar/docs/index.html",
                  "date": ("json", P / "markets/etf-rotationradar/docs/barometer_feed.json", ["as_of"]),
                  "tol": 10, "tol_src": "договорът: barometer 7/10"},
    "etf_radar": {"name": "ETF радарът (131 фонда)", "kind": "page",
                  "open": P / "markets/etf-rotationradar/docs/index.html",
                  "date": ("json", P / "markets/etf-rotationradar/docs/data.json", ["as_of"]),
                  "tol": 10, "tol_src": "договорът: etf-rotation 7/10"},
    "cot": {"name": "Позициите на фондовете (COT монитор)", "kind": "page",
            "open": P / "markets/cot-monitor/index.html",
            "date": ("json", P / "markets/cot-monitor/data/ai_context.json", ["latest_cot_date"]),
            "tol": 17, "tol_src": "договорът: cot-monitor 7/17",
            "how": "раздел „Секторна картина“: групите Валути, Енергоносители, Метали, Агрокултури"},
    "dollar_corr": {"name": "dollar-correlation в регистъра", "kind": "page",
                    "open": P / "markets/signals-registry/status.md",
                    "date": ("json", P / "markets/signals-registry/registry/current.json",
                             ["signals", "dollar-correlation", "signal", "as_of"]),
                    "tol": 10, "tol_src": "регистърът: общият праг за остаряване 10 дни (registry/status.json)"},
    "rot_radar": {"name": "Ротационният радар (S&P 500)", "kind": "page",
                  "open": P / "markets/SP500-rotationradar/docs/index.html",
                  "date": ("json", P / "markets/SP500-rotationradar/docs/data.json", ["metadata", "as_of"]),
                  "tol": 10, "tol_src": "договорът: rotation-twins 7/10"},
    "klasacia": {"name": "Класацията (S&P 500, 502 имена)", "kind": "page",
                 "open": P / "markets/SP500-momentumrank/index.html",
                 "date": ("json", P / "markets/SP500-momentumrank/data_meta.json", ["updated"]),
                 "tol": 10, "tol_src": "договорът: momentum-twins 7/10"},
    "sector_mon": {"name": "Секторният монитор", "kind": "page",
                   "open": P / "markets/sector-monitor/dist/public/index.html",
                   "date": ("mtime", P / "markets/sector-monitor/dist/public/index.html"),
                   "data": ("json", P / "markets/sector-monitor/client/public/data/canon.json", ["meta", "asOf"]),
                   "tol": 45, "tol_src": "месечна кохорта, толерансът като на месечните органи 30/45"},
    "oil": {"name": "Петролният канон (collectors)", "kind": "page",
            "open": P / "collectors/docs/index.html",
            "date": ("json", P / "collectors/docs/state.json", ["generated_at"]),
            "tol": 4, "tol_src": "договорът: oil 1/4 (ДРАФТ)"},
    "platno": {"name": "Платното с 31 актива (етаж 3 на стария екран)", "kind": "page",
               "open": WS / "ekran.html", "anchor": "etazh3",
               "date": ("json", WS / "screen_data.json", ["week"]),
               "tol": 8, "tol_src": "седмичният екран, строи се в съботата"},
    "talpata": {"name": "Барометърът на стария екран („Тълпата“)", "kind": "page",
                "open": WS / "ekran.html", "anchor": "talpata",
                "date": ("json", WS / "screen_data.json", ["week"]),
                "tol": 8, "tol_src": "седмичният екран, строи се в съботата"},
    "sectors_page": {"name": "Страницата на секторите (седмичният екран)", "kind": "page",
                     "open": WS / "sectors.html", "date": ("git", WS, "sectors.html"),
                     "tol": 8, "tol_src": "седмичният екран, строи се в съботата"},
    "breadth": {"name": "Ширината по групи (станцията m_breadth)", "kind": "page",
                "open": DC / "migrations/m_breadth/breadth.json",
                "date": ("json", DC / "migrations/m_breadth/breadth.json", ["group_frontier"]),
                "tol": 14, "tol_src": "договорът: M-BREADTH 7/14"},
    "conc": {"name": "Концентрацията по страни (станцията m_conc)", "kind": "page",
             "open": DC / "migrations/m_conc/conc.json",
             "date": ("json", DC / "migrations/m_conc/conc.json", ["store_frontier"]),
             "tol": 14, "tol_src": "станция като M-BREADTH 7/14 (m_conc не е в договора)"},
    "valuation": {"name": "Оценъчният уред: консенсусът (месечна снимка)", "kind": "page",
                  "open": P / "companies/valuation-organ/consensus/normalized",
                  "date": ("newest_mtime", P / "companies/valuation-organ/consensus/normalized", "20??-??-wide.json"),
                  "tol": 45, "tol_src": "месечно качване, толерансът като на месечните органи 30/45"},
    "ai_hype": {"name": "Мониторът на балона в ИИ", "kind": "frozen",
                "open": P / "markets/ai-hype-monitor/docs/index.html",
                "date": ("json", P / "markets/ai-hype-monitor/app/data/hype_index.json", ["history", -1, "date"]),
                "tol": None, "tol_src": "договорът: ai-hype, замръзнал по план"},
    "stoxx_rot": {"name": "Ротационният радар (STOXX 600)", "kind": "page",
                  "open": P / "markets/STOXX600-rotationradar/docs/index.html",
                  "date": ("json", P / "markets/STOXX600-rotationradar/docs/data.json", ["metadata", "as_of"]),
                  "tol": 10, "tol_src": "двойката като американската, 7/10"},
    "stoxx_rank": {"name": "Класацията (STOXX 600)", "kind": "page",
                   "open": P / "markets/stoxx600-momentumrank/index.html",
                   "date": ("json", P / "markets/stoxx600-momentumrank/data_meta.json", ["updated"]),
                   "tol": 10, "tol_src": "двойката като американската, 7/10"},
    "m_path": {"name": "Пътят от фючърсите (станцията m_path)", "kind": "page",
               "open": DC / "data/policy_path/policy_path_futures.json",
               "date": ("json", DC / "data/policy_path/policy_path_futures.json", ["rows", -1, "date"]),
               "tol": 4, "tol_src": "дневна станция, толерансът като на дневните органи 1/4"},
    # ── икономиката ──
    "us_dash": {"name": "Таблото на САЩ (уеб таблото, чете живо от GitHub)", "kind": "page",
                "open": P / "macro/macro-web-dashboard/index.html",
                "date": ("json", P / "macro/us-macro-dashboard/output/api/macro_state.json", ["as_of_date"]),
                "tol": 10, "tol_src": "договорът: macro-regime.us 7/10"},
    "eu_dash": {"name": "Таблото на еврозоната (уеб таблото, чете живо от GitHub)", "kind": "page",
                "open": P / "macro/macro-web-dashboard/index.html",
                "date": ("json", P / "macro/eu-macro-dashboard/output/api/macro_state.json", ["as_of_date"]),
                "tol": 10, "tol_src": "договорът: macro-regime.eu 7/10"},
    "cn_dash": {"name": "Таблото на Китай", "kind": "page",
                "open": P / "macro/china-macro-dashboard/output/index.html",
                "date": ("mtime", P / "macro/china-macro-dashboard/output/index.html"),
                "data": ("json", P / "macro/china-macro-dashboard/output/api/macro_state.json", ["as_of_date"]),
                "tol": 10, "tol_src": "договорът: macro-regime.cn 7/10"},
    "jp_dash": {"name": "Таблото на Япония (със слоя за йената)", "kind": "page",
                "open": P / "macro/jp-macro-dashboard/output/index.html",
                "date": ("mtime", P / "macro/jp-macro-dashboard/output/index.html"),
                "data": ("json", P / "macro/jp-macro-dashboard/output/api/macro_state.json", ["as_of_date"]),
                "tol": 10, "tol_src": "като другите табла, 7/10"},
    # ── моделът и машинното отделение ──
    "vrm_page": {"name": "Страницата на модела (vrm.html)", "kind": "page",
                 "open": WS / "vrm.html", "date": ("git", WS, "vrm.html"),
                 "tol": 8, "tol_src": "седмичният екран, строи се в съботата"},
    "e2": {"name": "Вратата на кокпита (свежестта на уредите)", "kind": "page",
           "open": DC / "migrations/e2_dashboard/e2.html", "date": ("git", DC, "migrations/e2_dashboard/e2.html"),
           "tol": 8, "tol_src": "строи се със седмичния ход"},
    "pulse": {"name": "Пулсът, дайджестът", "kind": "page",
              "open_newest": (DC / "migrations/m_pulse/out", "pulse_20??-??-??.md"),
              "date": ("newest", DC / "migrations/m_pulse/out", "pulse_20??-??-??.md"),
              "tol": 8, "tol_src": "по листа, т. 5: ръчен; седмица като стъклото"},
    "desk": {"name": "Бюрото, първата страница", "kind": "page",
             "open_newest": (DC / "migrations/m_desk/out", "desk_20??-??-??"),
             "date": ("newest", DC / "migrations/m_desk/out", "desk_20??-??-??"),
             "tol": 8, "tol_src": "по листа, т. 5: ръчна; седмица като стъклото"},
    # ── радарът и инфрачервеното ──
    "news": {"name": "Радарът за новините (последният брой)", "kind": "page",
             "open_newest": (NEWS, "20??-??-??.md"),
             "date": ("newest_front", NEWS, "20??-??-??.md", "week_ending"),
             "tol": 8, "tol_src": "седмичен брой (файловете 24.10 до 21.11 са през седмица)"},
    "s9_tech": {"name": "Актив срещу двигателите: технологиите (QQQ, XLK, SMH, SPY)", "kind": "cmd",
                "cmd": r"python -X utf8 migrations\drill\s9_tech.py", "cwd": DC,
                "script": DC / "migrations/drill/s9_tech.py",
                "date": ("canon_min", ["mkt_real_10y", "mkt_breakeven_10y", "mkt_hy_oas", "mkt_baa_10y_spread"]),
                "tol": 4, "tol_src": "входовете са дневни серии в канона; толерансът като на дневните органи 1/4"},
    "s9_gold": {"name": "Актив срещу двигателите: златото", "kind": "cmd",
                "cmd": r"python -X utf8 migrations\drill\s9_gold.py", "cwd": DC,
                "script": DC / "migrations/drill/s9_gold.py",
                "date": ("canon_min", ["mkt_real_10y", "mkt_gold_usd"]),
                "tol": 4, "tol_src": "входовете са дневни серии в канона; толерансът като на дневните органи 1/4"},
    "fragility": {"name": "Моделът за крехкостта: Мински за САЩ", "kind": "cmd",
                  "cmd": MM_PY + " -m fragility.minsky --area US", "cwd": MM,
                  "script": MM / "fragility/minsky.py",
                  "date": ("json", P / "markets/signals-registry/registry/current.json",
                           ["signals", "macro-fragility-us", "signal", "as_of"]),
                  "tol": 200, "tol_src": "регистърът: stale_after_days 200 за тримесечните данни (manifest.yaml)"},
    "macromodel": {"name": "MacroModel: базата и шоковете с профила", "kind": "cmd",
                   "cmd": MM_PY + " -m projections.live --profile", "cwd": MM,
                   "script": MM / "projections/live.py",
                   "date": ("git", MM, "."),
                   "tol": None, "tol_src": "по поискване: датата е последната промяна на уреда"},
    "raft": {"name": "Рафтът за спад в акциите", "kind": "doc",
             "open": P / "_orchestration/iluminator/ILU0-RAFT-SPAD-V-AKCIITE.md",
             "date": ("git", P, "_orchestration/iluminator/ILU0-RAFT-SPAD-V-AKCIITE.md"),
             "tol": None, "tol_src": "документ"},
    "revizii": {"name": "Извънредното изваждане: преди и след (рафтът, т. 8)", "kind": "cmd",
                "cmd": r"python C:\Projects\_orchestration\iluminator\work\revizii_predi_sled.py",
                "cwd": P / "_orchestration/iluminator/work",
                "script": P / "_orchestration/iluminator/work/revizii_predi_sled.py",
                "date": ("newest_mtime", P / "companies/valuation-organ/consensus/normalized", "20??-??-wide.json"),
                "tol": 45, "tol_src": "сравнява срещу месечната снимка; 30/45",
                "how": "чете файловете от Koyfin в папката от т. 8 на рафта; пътят е вписан в скрипта"},
}

# Плочката: първата оптика и радарът (листът, т. 3, и поправките в брифа)
TILES: dict[int, dict] = {
    1: {"first": ["kompas"], "radar": ["s9_tech", "s9_gold"]},
    2: {"first": ["funding"], "radar": []},
    3: {"first": ["barometar", "talpata"], "radar": ["raft", "fragility"]},
    4: {"first": ["cot"], "radar": ["dollar_corr"]},
    5: {"first": ["raft"], "radar": ["s9_tech"]},
    6: {"first": ["rot_radar", "klasacia"], "radar": ["sector_mon"]},
    7: {"first": ["oil", "cot"], "radar": ["s9_gold"]},
    8: {"first": ["us_dash"], "radar": ["macromodel", "fragility"]},
    9: {"first": ["eu_dash"], "radar": ["stoxx_rot", "stoxx_rank", "conc"]},
    10: {"first": ["cn_dash"], "radar": []},
    11: {"first": ["jp_dash"], "radar": []},
    12: {"first": ["kompas", "m_path"], "radar": []},
    13: {"first": ["vrm_page"], "radar": ["e2", "pulse", "desk"]},
}
# Общото за всяка плочка: радарът и инфрачервеното се викат от едно място (брифът, т. 5)
COMMON_RADAR = ["news", "fragility"]

CANARIES = {"px_kre_daily", "px_kbe_daily", "px_iai_daily", "px_kie_daily", "px_igv_daily", "px_xhb_daily",
            "px_itb_daily", "px_iyt_daily", "px_pff_daily", "px_cwb_daily", "px_srln_daily", "px_angl_daily"}
# Секторът в класацията за всеки секторен фонд (имената на улицата). SMH и канарчетата нямат сектор там.
SECTOR_OF = {"px_xlk_daily": "Technology", "px_xlf_daily": "Financial Services", "px_xlv_daily": "Healthcare",
             "px_xle_daily": "Energy", "px_xli_daily": "Industrials", "px_xly_daily": "Consumer Cyclical",
             "px_xlp_daily": "Consumer Defensive", "px_xlu_daily": "Utilities", "px_xlb_daily": "Basic Materials",
             "px_xlre_daily": "Real Estate", "px_xlc_daily": "Communication Services"}


def member_instruments(tile_id: int, m: dict) -> list[str]:
    """Уредите зад члена (вторият ход, листът т. 3)."""
    s, src = m.get("series", ""), m.get("source", "")
    if tile_id == 1:
        return ["kompas", "s9_tech"]
    if tile_id == 2:
        return ["funding"]
    if tile_id == 3:
        if s in CANARIES:
            return ["etf_radar", "rot_radar"]
        if s == "IG_OAS":
            return ["us_dash", "barometar"]
        return ["barometar", "talpata"]
    if tile_id == 4:
        return ["cot", "dollar_corr"]
    if tile_id == 5:
        return ["breadth"] if "breadth" in src else ["etf_radar", "platno"]
    if tile_id == 6:
        return ["etf_radar", "rot_radar"] if s in CANARIES else ["rot_radar", "klasacia", "sectors_page"]
    if tile_id == 7:
        if s.startswith("oil_") or s == "ttf_front":
            return ["oil", "cot"]
        if s in ("mkt_gold_usd", "px_slv_daily"):
            return ["cot", "s9_gold"]
        return ["cot", "etf_radar"]
    if tile_id in (8, 9, 10, 11):
        return {8: ["us_dash"], 9: ["eu_dash"], 10: ["cn_dash"], 11: ["jp_dash"]}[tile_id]
    if tile_id == 12:
        if s.startswith("policy_path"):
            return ["m_path", "kompas"]
        return {"FED_FUNDS": ["us_dash"], "ECB_DFR": ["eu_dash"], "CN_LPR_1Y": ["cn_dash"]}.get(s, ["jp_dash"])
    if tile_id == 13:
        return ["vrm_page", "e2"]
    return []
