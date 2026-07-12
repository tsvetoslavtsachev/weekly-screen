# -*- coding: utf-8 -*-
"""
VRM ЕКРАНЪТ (vrm.html) — пълният екран, който се отваря при клик на VRM картата
в съботния екран (index.html). Мандат 17-MANDATE-VRM-SCREEN.md (ПОДПИСАН 11.07).

Съботен ритуал артефакт — чете data-core деривати. От мандат №28 (12.07.2026, реш. Ц.):
живее в репо weekly-screen на Pages, НЕЛИСТНАТ (noindex, без линк от витрината — Ф-9 духът).

Данни (всичко READ-ONLY):
  - data-core/data/state/vrm_overlay.json      (шапката: режим/KS/alignment; матрицата)
  - _votes_retro_analytics/weekly_13w.csv       (матрицата 8×13 — G2 бит-паритет)
  - _votes_retro_analytics/regime_episodes.csv  (епизодите/възрастта)
Историческите факти (ЕТАЖ 2) са СТАТИЧНИ цитати от ПОДПИСАНИЯ широк тест
(_votes_history_analytics/REPORT-VOTES-HISTORY.md + summary.json, 11.07.2026) —
НЕ се пресмятат наново всяка събота; вградени с provenance.

Дизайнов език = на съботния екран (index.html): палитра --srf/--pg/--up/--dn/--warn,
floor етажи, 1060px wrap, тъмна тема ONLY. Разширения (отбелязани в EXEC): цвят за OVER
(съботният екран няма 4-то състояние) + режимни цветове за епизодната лента.

Гейтове: G1 двоен билд идентичен · G2 матрицата == weekly_13w.csv (assert, бит) ·
G3 node --check + error банер · G4 нула записи в data-core.
Детерминизъм: никакви timestamps; двоен пуск → идентичен файл.
"""
import json, csv, html, statistics, hashlib, os

OVERLAY = r"C:\Projects\data-core\data\state\vrm_overlay.json"
VOTES_DIR = r"C:\Projects\_votes_retro_analytics"
OUT = r"C:\Projects\_weekly_screen\vrm.html"
WINDOW = 13

VOTES = ['RISK_ON_GROWTH','RISK_ON_CYCLICAL','COMMODITY_INFLATION','INFLATION_PROTECTION',
         'DEFENSIVE_EQUITY','DURATION','CREDIT','REAL_ESTATE']
HUMAN = {
    'RISK_ON_GROWTH':      'Растежови акции',
    'RISK_ON_CYCLICAL':    'Циклични акции',
    'COMMODITY_INFLATION': 'Суровини',
    'INFLATION_PROTECTION':'Злато / инфлационна защита',
    'DEFENSIVE_EQUITY':    'Дефанзивни акции',
    'DURATION':            'Дълг (дюрация)',
    'CREDIT':              'Кредит',
    'REAL_ESTATE':         'Имоти',
}
STATE_BG = {'OK':'Съвпада','WATCH':'Гранично','UNDER':'По-слаб','OVER':'По-силен'}
STATE_DEF = {
    'OK':   'Съвпада — класира се както режимът предполага (отклонение до 0.7 място-скор)',
    'WATCH':'Гранично — леко отклонение от очакваната подредба (0.7–1.2), не се наказва в скора',
    'UNDER':'По-слаб от очакваното за режима — класира се по-назад, отколкото режимът предполага (изостава с над 1.2)',
    'OVER': 'По-силен от очакваното за режима — класира се по-напред, отколкото режимът предполага (избързва с над 1.2)',
}
STATE_ORDER = ['OK','WATCH','UNDER','OVER']
REGIME_BG = {'REFLATION':'Рефлация','GROWTH':'Растеж','STAGNATION':'Стагнация',
             'DEFLATION':'Дефлация','CRISIS':'Криза'}
# VERIFIED от overlay_engine.py:84 (REGIME_MATRIX, колони в реда на VOTES).
REGIME_MATRIX = {
    'GROWTH':     [1,    0.5, -1,   -0.5, -1,    0.5,  0.5,  0.5],
    'REFLATION':  [0.5,  1,    1,    0.5, -1,   -1,    0,    0],
    'STAGNATION': [0,   -1,   -0.5,  0,    1,    1,    0.5,  0.5],
    'CRISIS':     [-1,  -1,    0.5,  1,    0.5, -0.5, -0.5, -1],
    'DEFLATION':  [-0.5,-1,   -1,    0.5,  0.5,  1,   -0.5, -0.5],
}
POS_WORD = {1.0:'сред водачите', 0.5:'напред', 0.0:'в средата', -0.5:'леко назад', -1.0:'назад'}
def pos_word(v): return POS_WORD[float(v)]
def num_sign(v):
    v = float(v); return f'+{v:g}' if v > 0 else f'{v:g}'
def dfmt(iso):
    y,m,d = iso.split('-'); return f"{d}.{m}.{y}"
def dshort(iso):
    y,m,d = iso.split('-'); return f"{d}.{m}"
def esc(s): return html.escape(str(s), quote=True)

# ---------------------------------------------------------------- load (READ-ONLY)
with open(OVERLAY, encoding='utf-8') as f:
    data = json.load(f)
last = data[-1]

with open(os.path.join(VOTES_DIR,'weekly_13w.csv'), newline='', encoding='utf-8') as f:
    csv_rows = list(csv.DictReader(f))
assert len(csv_rows) == WINDOW, "weekly_13w.csv трябва да носи 13 седмици"

# G2 (бит-паритет): матрицата в екрана = CSV-то = overlay-ът. Assert по клетка.
w13 = data[-WINDOW:]
for i, (cr, od) in enumerate(zip(csv_rows, w13)):
    assert cr['as_of'] == od['as_of'], f"G2: as_of разминаване ред {i}"
    assert cr['regime'] == od['regime'], f"G2: regime разминаване {cr['as_of']}"
    assert int(cr['alignment_score']) == od['alignment_score'], f"G2: score разминаване {cr['as_of']}"
    for v in VOTES:
        assert cr[v] == od['alignment_flags'][v], f"G2: {v} разминаване {cr['as_of']}"

with open(os.path.join(VOTES_DIR,'regime_episodes.csv'), newline='', encoding='utf-8') as f:
    episodes = [dict(regime=r['regime'], start=r['start'], end=r['end'], weeks=int(r['weeks']))
                for r in csv.DictReader(f)]
# паритет: епизодите от CSV = реконструираните от overlay
_eps = []
_cur = None
for d in data:
    if _cur is None or d['regime'] != _cur['regime']:
        if _cur: _eps.append(_cur)
        _cur = dict(regime=d['regime'], start=d['as_of'], end=d['as_of'], weeks=1)
    else:
        _cur['end'] = d['as_of']; _cur['weeks'] += 1
_eps.append(_cur)
assert _eps == episodes, "G2: епизодите CSV != overlay"

current_ep = episodes[-1]
prev_ep = episodes[-2]
CUR_REG = current_ep['regime']
med_cur = statistics.median([e['weeks'] for e in episodes if e['regime'] == CUR_REG])
max_cur = max(e['weeks'] for e in episodes if e['regime'] == CUR_REG)
scores = [int(r['alignment_score']) for r in csv_rows]
# alignment през ЦЕЛИЯ текущ епизод (за човешкото изречение) — от overlay, детерминистично
ep_scores = [d['alignment_score'] for d in data if d['as_of'] >= current_ep['start']]
EP_MIN, EP_MAX = min(ep_scores), max(ep_scores)

ks = last['kill_switch']
c4 = last['cumulative_4w']
KS_ACTIVE = bool(ks.get('active'))
KS_TXT = 'АКТИВЕН' if KS_ACTIVE else 'НЕАКТИВЕН'
W_START, W_END = csv_rows[0]['as_of'], csv_rows[-1]['as_of']

# ---------------------------------------------------------------- гласовете (13w метрики,
# същите детерминистични правила като VOTES-RETRO — езиковата версия след бележките на Ц.)
def flips(seq): return sum(1 for i in range(1, len(seq)) if seq[i] != seq[i-1])
def end_streak(seq):
    n = 1
    for i in range(len(seq)-1, 0, -1):
        if seq[i] == seq[i-1]: n += 1
        else: break
    return n

def friendly(counts, fl, st, lastst):
    N = WINDOW
    if counts['OK'] == N:
        return 'firm', f'Постоянно съвпада ({N} от {N})', f'съвпада в {N} от {N} седмици'
    if counts['UNDER'] >= 0.8*N:
        return 'against', f'Постоянно се разминава ({st} поредни)', f'по-слаб в {counts["UNDER"]} от {N} седмици'
    if counts['OVER'] >= 0.8*N:
        return 'against', f'Постоянно се разминава ({st} поредни)', f'по-силен в {counts["OVER"]} от {N} седмици'
    if lastst == 'OK' and st >= 8:
        return 'neutral', f'Скоро застана зад режима (последните {st})', f'съвпада в {counts["OK"]} от {N} седмици'
    if counts['WATCH'] >= 0.6*N and lastst == 'WATCH':
        return 'swing', f'Устойчиво гранично (последните {st})', f'гранично в {counts["WATCH"]} от {N} седмици'
    if counts['OK'] >= 0.4*N and counts['UNDER'] >= 0.4*N:
        return 'swing', 'Разделен (половината време)', f'съвпада в {counts["OK"]}, по-слаб в {counts["UNDER"]} от {N} седмици'
    if counts['OK'] >= 0.6*N and fl >= 3:
        return 'swing', 'Често сменя страната си', f'съвпада в {counts["OK"]} от {N} седмици'
    if counts['OK'] >= 0.6*N:
        return 'firm', f'Предимно съвпада ({counts["OK"]} от {N})', f'съвпада в {counts["OK"]} от {N} седмици'
    return 'neutral', 'Без устойчива посока', f'съвпада в {counts["OK"]} от {N} седмици'

rows = []
for k, v in enumerate(VOTES):
    seq = [cr[v] for cr in csv_rows]
    counts = {s: seq.count(s) for s in STATE_ORDER}
    fl, st = flips(seq), end_streak(seq)
    bcls, blabel, bsub = friendly(counts, fl, st, seq[-1])
    exp = REGIME_MATRIX[CUR_REG][k]
    interp = f'Очаквано място при {REGIME_BG[CUR_REG]}: {pos_word(exp)} ({num_sign(exp)})'
    extra = ''
    if v == 'INFLATION_PROTECTION' and counts['UNDER'] >= 0.8*WINDOW:
        extra = ('Устойчиво по-слабото злато пасва на растежов учебник '
                 '(растежът го очаква леко назад, −0.5) — не на стагнационен (0).')
    if v == 'DURATION' and counts['OK'] == WINDOW:
        extra = ('Стои назад точно както рефлацията иска; стагнацията би го искала '
                 'сред водачите (+1) → анти-стагнационен глас.')
    rows.append(dict(key=v, name=HUMAN[v], seq=seq, counts=counts, streak=st,
                     bcls=bcls, blabel=blabel, bsub=bsub, interp=interp, extra=extra))

# ---------------------------------------------------------------- ЕТАЖ 2: СТАТИЧНИТЕ факти
# от подписания широк тест. Цитати, НЕ пресмятания. Provenance: REPORT-VOTES-HISTORY.md +
# summary.json (11.07.2026; пре-регистрация 16-PREREG-VOTES-HISTORY.md, подписана 10.07;
# данни 979 седмици 05.10.2007–03.07.2026, ex-warmup 875; BH-FDR q=0.10).
HISTORY_FACTS = [
    dict(
        title='Шареното гласуване е ЕХО на смяната, не предвестник',
        verdict=('Н1 ПАДНА', 'dn'),
        body=('Хазардът при шарена коалиция е <b>0.340</b> — ПОД базовия 0.407 (при спокойна: 0.451). '
              'Механиката: гласовете се пре-сортират <b>след</b> смяната (среден churn 5.25 в първите '
              '4 седмици на епизод срещу 3.55 по-късно) — а точно тогава следващата смяна е далеч. '
              'SPY forward също не различава шарено от спокойно (наклоните положителни, незначими).'),
        meta='N=875 ex-warmup седмици · H1a p=0.043 — значим, но в АНТИ-хипотезна посока · H1b ns · двата фалсификатора сработиха'),
    dict(
        title='Старите режими са дълголетниците — възрастта сама не тревожи',
        verdict=('Н2 ПАДНА', 'dn'),
        body=('Хазард при възраст над медианата: <b>0.364</b> — ПОД базовия 0.407 (разлика −0.079, '
              'незначима, p=0.354). Режимите, надживели медианата за типа си, клонят да са дълголетниците '
              '(Рефлация 82с; Стагнация 74с) — веднъж „стари", те продължават, не се чупят. '
              f'Живото: текущият епизод е {current_ep["weeks"]}-а седмица срещу медиана {med_cur:.0f}с — '
              'само по себе си това НЕ е сигнал за крехкост.'),
        meta='N=875 седмици / 57 епизода · p=0.354 (ns) · фалсификаторът сработи'),
    dict(
        title='Устойчивият дисидент сочи следващия режим',
        verdict=('Н3 ИЗДЪРЖА (условно)', 'up'),
        body=('При <b>23 от 30 смени (76.7%)</b> поне един устойчив дисидент (8+ поредни седмици в едно '
              'разминаващо се състояние) е сочел към следващия режим по учебника си; на ниво наблюдение '
              '31/61 = 50.8% срещу случайни 35.5% (~1.43×). Крехко: на строгите еднозначни прочити '
              '18/41 = 43.9%. <b>Живото:</b> златото е точно такъв дисидент — по-слабо 11 поредни '
              'седмици, растежов учебник; исторически същият сетъп (злато UNDER в Рефлация) е уцелвал '
              'при смени №14 и №17 → Растеж.'),
        meta='N=61 наблюдения / 30 смени · p=0.014 · FDR PASS (q=0.10) · мощност ниска-умерена · наблюдение, не закон'),
    dict(
        title='Best-fit контекстът — информация, не мнозинство',
        verdict=('Н4 СМЕСЕНА', 'warn'),
        body=('Когато вътрешната подредба пасва по-добре на друг режим 4+ поредни седмици, следващата '
              'смяна отива там в <b>15 от 35 случая (42.9%)</b> срещу случайни 27.6% — <b>1.55× над '
              'случайността</b>, но ПОД 50%: греши по-често, отколкото уцелва. Системно надкалква '
              'Криза/Дефлация в дългите опашки на Стагнация/Рефлация.'),
        meta='N=35 пламвания · p=0.025 · FDR PASS · пада по строгия 50% фалсификатор · отклонен към Криза'),
]
# На лицето — без файлови пътища (Ц., 11.07); машинният детайл живее в REPORT/EXEC.
HISTORY_PROV = ('Четирите факта са статични цитати от пре-регистрирания широк тест върху цялата '
                'история, подписан на 10.07 — не се пресмятат наново при съботния билд.')

# ---------------------------------------------------------------- HTML фрагменти
# Шапка chips (всичко от build данни)
age_ord = f"{current_ep['weeks']}-а" if str(current_ep['weeks'])[-1] not in ('1',) else f"{current_ep['weeks']}-ва"
CHIPS = (
 f'<span class="chip"><b>ВЪЗРАСТ</b>{age_ord} седмица <span class="small">медианата за '
 f'{esc(REGIME_BG[CUR_REG].lower())} е {med_cur:.0f}с · макс {max_cur}с</span></span>'
 f'<span class="chip"><b>ПОСЛЕДНА СМЯНА</b>{esc(dfmt(current_ep["start"]))} '
 f'<span class="small">{esc(REGIME_BG[prev_ep["regime"]])} → {esc(REGIME_BG[CUR_REG])}</span></span>'
 f'<span class="chip"><b>KILL SWITCH</b><span class="{ "b dn" if KS_ACTIVE else "b up" }">{KS_TXT}</span> '
 f'<span class="small">margin {c4["margin_pct"]:+.2f}% (SPY 4с {c4["spy_pct"]:+.2f}% срещу праг {c4["threshold_pct"]:.1f}%)</span></span>'
 f'<span class="chip"><b>ALIGNMENT</b>{last["alignment_score"]}/8 '
 f'<span class="small">= 8 − броя разминаващи се („Гранично" не се наказва)</span></span>'
 f'<span class="chip"><b>GMS</b>{last["gms"]["score"]}/{last["gms"]["max"]} {esc(last["gms"]["tier"])}</span>'
)

# ЕТАЖ 1: матрицата
def state_cell(s):
    return f'<td class="st st-{s}" title="{esc(STATE_DEF[s])}">{esc(STATE_BG[s])}</td>'

def compbar(counts):
    segs = []
    for s in STATE_ORDER:
        n = counts[s]
        if n:
            segs.append(f'<span class="seg seg-{s}" style="flex:{n} 1 0" '
                        f'title="{esc(STATE_BG[s])}: {n}/{WINDOW}"></span>')
    return f'<div class="comp">{"".join(segs)}</div>'

mrows = []
for r in rows:
    cells = ''.join(state_cell(s) for s in r['seq'])
    interp_html = esc(r['interp'])
    if r['extra']:
        interp_html += '<br>' + esc(r['extra'])
    badge = (f'<div class="cb"><span class="badge {r["bcls"]}">{esc(r["blabel"])}</span>'
             f'{compbar(r["counts"])}<span class="small">{esc(r["bsub"])}</span></div>')
    mrows.append(f'<tr><th class="vid"><span class="vn">{esc(r["name"])}</span>'
                 f'<span class="vi">{interp_html}</span>{badge}</th>{cells}</tr>')
MATRIX_ROWS = ''.join(mrows)
# Съгласуваността живее ПРИ матрицата, на СЪЩАТА времева ос (Ц., 11.07): тънък ред под
# 13-те колони — броят съвпадащи гласа per седмица (alignment_score, от build данните).
ALIGN_ROW = ('<tr class="alrow"><th class="vid alid">съвпадат с режима '
             '<span class="small">(от 8; „Гранично" не се брои за разминаване)</span></th>'
             + ''.join(f'<td class="al" title="{esc(dfmt(cr["as_of"]))}: {s} от 8 гласа съвпадат">{s}</td>'
                       for cr, s in zip(csv_rows, scores)) + '</tr>')
ALIGN_SENT = (f'Днес <b>{scores[-1]} от 8</b> гласа съвпадат с режима; '
              f'през целия епизод — между {EP_MIN} и {EP_MAX}.')
MATRIX_HEAD = ''.join(f'<th class="wk">{esc(dshort(cr["as_of"]))}</th>' for cr in csv_rows)
MATRIX_COLS = '<col class="cid">' + '<col class="cwk">'*WINDOW
STATE_LEG = ''.join(f'<span class="lg lg-{s}" title="{esc(STATE_DEF[s])}">{esc(STATE_BG[s])} <em>({s})</em></span>'
                    for s in STATE_ORDER)

# ЕТАЖ 2: картите
cards = []
for fdict in HISTORY_FACTS:
    vt, vc = fdict['verdict']
    cards.append(f'<div class="scard"><h3>{esc(fdict["title"])} '
                 f'<span class="b {vc}" style="font-size:11.5px">{esc(vt)}</span></h3>'
                 f'<p class="hb">{fdict["body"]}</p>'
                 f'<div class="meta">{esc(fdict["meta"])}</div></div>')
HISTORY_CARDS = ''.join(cards)

# ЕТАЖ 3: САМО историята на режимите (Ц., 11.07: спарклинията ПАДА — беше на друга времева
# ос и в диапазон 5-7 е почти права). Лентата — четима за човек: име + седмици + годишни маркери.
from datetime import date as _date
recent = episodes[-10:]
rib = []
for e in recent:
    rib.append(f'<div class="ribseg reg-{e["regime"]}" style="flex:{e["weeks"]} 1 0" '
               f'title="{esc(REGIME_BG[e["regime"]])} · {esc(dfmt(e["start"]))}–{esc(dfmt(e["end"]))} · {e["weeks"]} седмици">'
               f'<span>{esc(REGIME_BG[e["regime"]])}</span><span class="rw">{e["weeks"]}с</span></div>')
RIBBON = ''.join(rib)
# годишни маркери по оста (позиция = дни от началото на видимия прозорец)
_span_a = _date.fromisoformat(recent[0]['start'])
_span_b = _date.fromisoformat(recent[-1]['end'])
_total = (_span_b - _span_a).days
ymarks = [f'<span class="ymark" style="left:0%"><i></i>{_span_a.year}</span>']
for y in range(_span_a.year + 1, _span_b.year + 1):
    pct = 100.0 * (_date(y, 1, 1) - _span_a).days / _total
    ymarks.append(f'<span class="ymark" style="left:{pct:.2f}%"><i></i>{y}</span>')
YAXIS = ''.join(ymarks)

# ПРОИЗХОДЪТ — като за човек (Ц., 11.07): без пътища/хешове/as_of на лицето.
# Машинният детайл живее в REPORT/EXEC файловете.
_years = (_date.fromisoformat(last['as_of']) - _date.fromisoformat(data[0]['as_of'])).days / 365.25
PROV = (f'Числата идват от седмичния запис на VRM — {_years:.1f} години история, същият двигател, '
        f'който смята режима. Историческите факти са от теста, подписан на 10.07. '
        f'Нищо тук не е писано на ръка.')

# ---------------------------------------------------------------- HTML (mockup дизайн език)
TPL = r"""<!doctype html><html lang="bg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>VRM ЕКРАНЪТ · режимното ядро</title>
<!-- Съботен ритуал артефакт: чете data-core деривати. Мандат №28: на Pages, нелистнат (noindex). -->
<script>
/* РАНЕН диагностичен банер (канонът от VISUAL-DESIGN-RESEARCH §4). */
(function(){
  function show(msg){
    var b=document.getElementById('errbanner');
    if(!b){b=document.createElement('div');b.id='errbanner';document.documentElement.appendChild(b);}
    b.textContent='⚠ Грешка при рендиране: '+msg;b.style.display='block';
  }
  window.addEventListener('error',function(e){
    show((e.message||'скрипт')+' ['+(e.filename||'')+':'+(e.lineno||'?')+':'+(e.colno||'?')+']');
  });
  window.addEventListener('unhandledrejection',function(e){show('promise: '+(e.reason&&e.reason.message||e.reason));});
})();
</script>
<style>
:root{--srf:#1a1a19;--pg:#0d0d0d;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;
--ax:#383835;--up:#0ca30c;--dn:#d03b3b;--warn:#fab219;--ring:rgba(255,255,255,.1);
/* разширения за VRM екрана (мокъпът няма 4-то състояние/режимни цветове): */
--ovr:#5b9bd9;
--okbg:#16301f;--okfg:#6ec98b;--wabg:#332b12;--wafg:#f2c65a;
--unbg:#361c1b;--unfg:#e88a89;--ovbg:#152638;--ovfg:#7fb2ec;
--reg-REFLATION:#39b8a8;--reg-GROWTH:#7089f7;--reg-STAGNATION:#d9ad52;
--reg-DEFLATION:#9a8cc4;--reg-CRISIS:#d46b69}
*{box-sizing:border-box}body{margin:0;background:var(--pg);color:var(--ink);
font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding:20px;
font-variant-numeric:lining-nums tabular-nums}
#errbanner{display:none;position:sticky;top:0;z-index:99;background:#c0392b;color:#fff;
font:600 13px/1.4 system-ui;padding:10px 16px}
.wrap{max-width:1060px;margin:0 auto}
h1{font-size:19px;margin:0 0 2px}
.sub{color:var(--ink2);font-size:13px;margin-bottom:16px}
.tag{border:1px solid var(--ring);color:var(--mut);border-radius:9px;padding:1px 8px;font-size:11.5px;margin-left:6px}
.tag.obs{color:var(--reg-REFLATION);border-color:var(--reg-REFLATION)}
.floor{background:var(--srf);border:1px solid var(--ring);border-radius:12px;padding:14px 16px;margin-bottom:14px}
.fh{display:flex;align-items:baseline;gap:10px;margin-bottom:10px}
.fh .n{color:var(--mut);font-size:11px;letter-spacing:1px}
.fh .t{font-weight:700;font-size:15px}
.fh .d{color:var(--mut);font-size:12px;margin-left:auto;cursor:help}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--ring);border-radius:9px;padding:6px 12px;font-size:13px}
.chip b{display:block;font-size:11px;color:var(--mut);font-weight:600;letter-spacing:.4px}
.small{color:var(--mut);font-size:11.5px}
.b{font-weight:650}.b.up{color:var(--up)}.b.dn{color:var(--dn)}.b.warn{color:var(--warn)}
.hero{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:10px}
.hero .rg{font-size:30px;font-weight:800;letter-spacing:.5px;color:var(--reg-REFLATION)}
.hero .rgsub{color:var(--mut);font-size:12px}
.badge{border-radius:8px;padding:0 7px;font-size:11.5px;border:1px solid var(--ring);color:var(--ink2);white-space:nowrap}
.badge.firm{color:var(--okfg);border-color:var(--okfg)}
.badge.against{color:var(--unfg);border-color:var(--unfg)}
.badge.swing{color:var(--warn);border-color:var(--warn)}
.badge.neutral{color:var(--ink2);border-color:var(--ring)}
.mnote{font-size:11.5px;color:var(--mut);margin:0 0 12px}
.mscroll{overflow-x:auto;padding-bottom:2px}
table.mtx{border-collapse:separate;border-spacing:0;width:100%;min-width:960px;table-layout:fixed}
table.mtx th,table.mtx td{padding:0}
col.cid{width:256px}
.wk{font-size:10.5px;color:var(--mut);font-weight:600;text-align:center;padding:0 0 8px!important;white-space:nowrap}
.corner{position:sticky;left:0;background:var(--srf);z-index:3}
.vid{text-align:left;vertical-align:top;padding:5px 14px 14px 0!important;
position:sticky;left:0;background:var(--srf);z-index:2}
.vid .vn{display:block;font-size:13.5px;font-weight:700;margin-bottom:3px;line-height:1.2}
.vid .vi{display:block;font-size:10.5px;color:var(--mut);line-height:1.45;margin:0 0 7px;white-space:normal;font-weight:400}
.cb{display:flex;flex-direction:column;gap:4px;align-items:flex-start}
td.st{text-align:center;font-size:10px;font-weight:700;height:32px;border:2px solid var(--srf);
border-radius:6px;white-space:nowrap;overflow:hidden}
.st-OK{background:var(--okbg);color:var(--okfg)}
.st-WATCH{background:var(--wabg);color:var(--wafg)}
.st-UNDER{background:var(--unbg);color:var(--unfg)}
.st-OVER{background:var(--ovbg);color:var(--ovfg)}
.comp{display:flex;height:7px;border-radius:4px;overflow:hidden;background:#0f0f0e;align-self:stretch}
.seg-OK{background:var(--okfg)}.seg-WATCH{background:var(--wafg)}
.seg-UNDER{background:var(--unfg)}.seg-OVER{background:var(--ovfg)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;font-size:12px;color:var(--ink2)}
.lg{display:inline-flex;align-items:center;gap:6px}.lg em{color:var(--mut);font-style:normal;font-size:11px}
.lg::before{content:"";width:11px;height:11px;border-radius:3px}
.lg-OK::before{background:var(--okfg)}.lg-WATCH::before{background:var(--wafg)}
.lg-UNDER::before{background:var(--unfg)}.lg-OVER::before{background:var(--ovfg)}
.howto{margin:10px 0 0;padding-left:18px;font-size:12.5px;color:var(--ink2);line-height:1.6}
.howto li{margin:3px 0}.howto b{color:var(--ink)}
.cards2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.scard{border:1px solid var(--ring);border-radius:10px;padding:10px 12px;background:#151514}
.scard h3{margin:0 0 6px;font-size:13.5px}
.scard .hb{margin:0;font-size:12.5px;color:var(--ink2);line-height:1.55}
.scard .hb b{color:var(--ink)}
.scard .meta{color:var(--mut);font-size:11px;margin-top:8px}
.hprov{color:var(--mut);font-size:11.5px;margin-top:10px}
.ribcap{font-size:11px;color:var(--mut);margin:0 0 6px;display:flex;justify-content:space-between}
.ribbon{display:flex;gap:2px;height:36px;margin-bottom:12px}
.ribseg{border-radius:5px;display:flex;flex-direction:column;align-items:center;justify-content:center;
color:#0d0d0d;font-size:10px;font-weight:700;overflow:hidden;min-width:14px;padding:0 2px;text-align:center}
.ribseg .rw{font-weight:600;opacity:.75;font-size:9px}
.reg-REFLATION{background:var(--reg-REFLATION)}.reg-GROWTH{background:var(--reg-GROWTH)}
.reg-STAGNATION{background:var(--reg-STAGNATION)}.reg-DEFLATION{background:var(--reg-DEFLATION)}
.reg-CRISIS{background:var(--reg-CRISIS)}
.yaxis{position:relative;height:18px;margin-top:4px}
.ymark{position:absolute;transform:translateX(-50%);font-size:10px;color:var(--mut);text-align:center}
.ymark i{display:block;width:1px;height:6px;background:var(--ax);margin:0 auto 1px}
tr.alrow th,tr.alrow td{border-top:6px solid var(--srf)}
.alid{font-size:11.5px!important;color:var(--ink2);font-weight:600;padding-top:9px!important}
.alid .small{display:block;font-weight:400}
td.al{text-align:center;font-size:12px;font-weight:700;color:var(--ink2);height:24px;
background:#151514;border:2px solid var(--srf);border-radius:6px}
.alsent{font-size:13px;color:var(--ink2);margin:10px 0 0}
.alsent b{color:var(--ink)}
.foot{color:var(--mut);font-size:11.5px;margin-top:6px}
.prov{color:var(--ink2);font-size:13px;line-height:1.6;margin:0}
a.back{color:var(--warn);font-size:12px;text-decoration:none}
</style></head><body><div class="wrap">

<h1>VRM ЕКРАНЪТ — режимното ядро<span class="tag">[ВЪТРЕШЕН ПОГЛЕД]</span><span class="tag obs">наблюдение, не сигнал</span></h1>
<div class="sub">пълният екран зад VRM картата на съботния екран · <a class="back" href="index.html">← обратно към екрана</a></div>

<div class="floor">
<div class="hero"><span class="rg">__REGIME__</span><span class="rgsub">режимът по VRM · до __ASOF__ (седмичен overlay)</span></div>
<div class="chips">__CHIPS__</div>
</div>

<div class="floor">
<div class="fh"><span class="n">ЕТАЖ 1</span><span class="t">Гласовете под режима — 8 кошници × 13 седмици</span>
<span class="d" title="Всяка кошница се класира по 3-месечна доходност; състоянието сравнява реалното ѝ място с мястото, което режимът предполага (матрицата на VRM).">ⓘ</span></div>
<p class="mnote">Тълкуващият ред под всяко име = по матрицата на VRM (очакваното място при текущия режим) · нула нови дефиниции.</p>
<div class="mscroll">
<table class="mtx"><colgroup>__MATRIX_COLS__</colgroup>
<thead><tr><th class="corner"></th>__MATRIX_HEAD__</tr></thead>
<tbody>__MATRIX_ROWS____ALIGN_ROW__</tbody></table>
</div>
<p class="alsent">__ALIGN_SENT__</p>
<div class="legend">__STATE_LEG__</div>
<ul class="howto">
<li>Осемте кошници се <b>класират една срещу друга по 3-месечна доходност</b>; състоянието на всяка сравнява реалното ѝ място с мястото, което текущият режим предполага (матрицата на VRM).</li>
<li>„По-слаб от очакваното&quot; <b>НЕ сочи автоматично друг режим</b> — един глас не стига; за такъв прочит е нужна цялата подредба на осемте.</li>
<li><b>[ВЪТРЕШЕН ПОГЛЕД]</b> Наблюдение, не сигнал.</li>
</ul>
</div>

<div class="floor">
<div class="fh"><span class="n">ЕТАЖ 2</span><span class="t">Какво казва историята — четирите факта от широкия тест</span>
<span class="d" title="Пре-регистриран тест върху цялата история (979 седмици, ex-warmup 875). Статични цитати с N/FDR — не се пресмятат наново.">ⓘ</span></div>
<div class="cards2">__HISTORY_CARDS__</div>
<div class="hprov">__HISTORY_PROV__</div>
</div>

<div class="floor">
<div class="fh"><span class="n">ЕТАЖ 3</span><span class="t">Историята на режимите</span>
<span class="d" title="Последните 10 режимни епизода: име + продължителност в седмици, ширината пропорционална на седмиците; годините отдолу.">ⓘ</span></div>
<div class="ribcap"><span>Последните 10 режимни епизода — име · продължителност (седмици)</span></div>
<div class="ribbon">__RIBBON__</div>
<div class="yaxis">__YAXIS__</div>
</div>

<div class="floor">
<div class="fh"><span class="n">·</span><span class="t">Произход на числата</span></div>
<p class="prov">__PROV__</p>
</div>

<div class="foot">Програма КОКПИТ · билд: build_vrm_screen.py (детерминистичен) · диригентът го пуска всяка събота след build_screen.py · ЛОКАЛЕН артефакт, никога на Pages</div>
</div>
</body></html>
"""

out = (TPL
  .replace('__REGIME__', esc(REGIME_BG[CUR_REG]))
  .replace('__ASOF__', esc(dfmt(last['as_of'])))
  .replace('__CHIPS__', CHIPS)
  .replace('__MATRIX_COLS__', MATRIX_COLS)
  .replace('__MATRIX_HEAD__', MATRIX_HEAD)
  .replace('__MATRIX_ROWS__', MATRIX_ROWS)
  .replace('__ALIGN_ROW__', ALIGN_ROW)
  .replace('__ALIGN_SENT__', ALIGN_SENT)
  .replace('__STATE_LEG__', STATE_LEG)
  .replace('__HISTORY_CARDS__', HISTORY_CARDS)
  .replace('__HISTORY_PROV__', esc(HISTORY_PROV))
  .replace('__RIBBON__', RIBBON)
  .replace('__YAXIS__', YAXIS)
  .replace('__PROV__', PROV))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(out)

print("HTML bytes:", len(out))
print("sha256:", hashlib.sha256(out.encode('utf-8')).hexdigest()[:16])
print("G2 матрица==CSV==overlay: PASS (assert)")
print("режим:", REGIME_BG[CUR_REG], current_ep['weeks'], "с; медиана", med_cur, "; KS", KS_TXT,
      f"margin {c4['margin_pct']:+.2f}%; alignment {last['alignment_score']}/8")
print("OK ->", OUT)
