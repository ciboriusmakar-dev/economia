"""Отчёты по результату запуска модели: сначала «Главное» простым языком, потом график, таблицы,
предупреждения и в конце — технические подробности. Форматы: HTML (с графиками), Markdown, JSON."""
from __future__ import annotations
import json, html, math
from pathlib import Path
from economia_spec_common import fnum

STATUS_RU = {
    'COMPLETED': ('Расчёт выполнен', 'ok'),
    'COMPLETED_WITH_WARNINGS': ('Расчёт выполнен, есть предупреждения', 'warn'),
    'FAILED_VALIDATION': ('Расчёт выполнен, но проверка не пройдена', 'bad'),
    'REJECTED_INPUT': ('Данные не приняты', 'bad'),
    'FAILED': ('Расчёт не удался', 'bad'),
}
MODE_RU = {'real': 'Реальные данные', 'simulation': 'Учебные / сценарные данные (не официальная статистика)'}
PALETTE = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)']
DASHES = ['', '7 4', '2 3', '10 3 2 3', '', '']


def _name(model_id):
    try:
        from economia_modules import MODEL_NAMES
        return MODEL_NAMES.get(model_id, model_id)
    except Exception:
        return model_id


def _cell(v):
    if v is None: return '—'
    if isinstance(v, bool): return 'да' if v else 'нет'
    if isinstance(v, int): return str(v)
    if isinstance(v, float):
        if not math.isfinite(v): return '—'
        a = abs(v)
        return fnum(v, 0 if a >= 1000 else 1 if a >= 100 else 2 if a >= 0.01 or a == 0 else 4)
    return str(v)


def _col_fmt(rows, j):
    """Одинаковое число знаков во всей колонке: по самому большому по модулю значению."""
    vals = [row[j] for row in rows if isinstance(row[j], float) and math.isfinite(row[j])]
    if not vals: return None
    mx = max(abs(v) for v in vals)
    return 0 if mx >= 1000 else 1 if mx >= 100 else 2 if mx >= 0.01 else 4


def _text_cols(t):
    return {j for j in range(len(t['columns'])) if all(not isinstance(row[j], (int, float)) or isinstance(row[j], bool) for row in t['rows'])}


def _cells(t):
    """Строки таблицы в виде готовых строк с единым форматом чисел по колонкам."""
    decs = [_col_fmt(t['rows'], j) for j in range(len(t['columns']))]
    return [[(fnum(v, decs[j]) if isinstance(v, float) and decs[j] is not None and math.isfinite(v) else _cell(v)) for j, v in enumerate(row)] for row in t['rows']]


def _ticks(lo, hi, k=5):
    if hi == lo: hi = lo + 1
    step = (hi - lo) / (k - 1)
    return [lo + i * step for i in range(k)]


def _dash(k, s):
    d = '7 4' if s.get('dash') else DASHES[k % len(DASHES)]
    return f' stroke-dasharray="{d}"' if d else ''


def render_chart_svg(chart):
    """Простые графики без внешних библиотек: линии (с пунктиром и коридором) и горизонтальные столбики."""
    if not chart: return ''
    if chart.get('type') == 'bar':
        labels, vals = chart['labels'], chart['values']
        pairs = [(l, v) for l, v in zip(labels, vals) if v is not None]
        if not pairs: return ''
        dec = _col_fmt([[v] for _, v in pairs], 0) or 2
        W, row, L, R, T = 720, 30, 230, 80, 14; H = T + row * len(pairs) + 24
        lo = min(0, min(v for _, v in pairs)); hi = max(0, max(v for _, v in pairs)); span = (hi - lo) or 1.0
        lo = lo - 0.16 * span if lo < 0 else lo; hi = hi + 0.16 * span if hi > 0 else hi   # запас под подписи значений
        X = lambda v: L + (v - lo) / (hi - lo) * (W - L - R) if hi != lo else L
        out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{html.escape(chart.get("title", ""))}">']
        out.append(f'<line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{T - 4}" y2="{H - 20}" class="axis"/>')
        for i, (l, v) in enumerate(pairs):
            y = T + i * row; x0, x1 = sorted((X(0), X(v)))
            cls = 'barpos' if v >= 0 else 'barneg'
            out.append(f'<text x="{L - 8}" y="{y + 18}" text-anchor="end">{html.escape(str(l) if len(str(l)) <= 36 else str(l)[:35] + '…')}</text>')
            out.append(f'<rect x="{x0:.1f}" y="{y + 5}" width="{max(x1 - x0, 1):.1f}" height="18" rx="2" class="{cls}"><title>{html.escape(str(l))}: {fnum(float(v), dec)}</title></rect>')
            tx = x1 + 6 if v >= 0 else x0 - 6; anc = 'start' if v >= 0 else 'end'
            out.append(f'<text x="{tx:.1f}" y="{y + 18}" text-anchor="{anc}">{fnum(float(v), dec)}</text>')
        out.append('</svg>'); return ''.join(out)
    # line
    xs = chart['x']; series = chart['series']; n = len(xs); band = chart.get('band')
    allv = [v for s in series for v in s['values'] if v is not None] + ([v for k in ('lo', 'hi') for v in band[k] if v is not None] if band else [])
    if not allv or n < 2: return ''
    lo, hi = min(allv), max(allv)
    if lo >= 0 and lo <= 0.6 * hi: lo = 0
    else: pad = (hi - lo) * 0.06 or 1; lo -= pad
    hi += (hi - lo) * 0.04
    W, H, L, R, T, B = 720, 300, 64, 24, 14, 44
    X = lambda i: L + i / (n - 1) * (W - L - R); Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    o = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{html.escape(chart.get("title", ""))}">']
    for t in _ticks(lo, hi):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/><text x="{L - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{_cell(float(t))}</text>')
    if lo < 0 < hi: o.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="axis"/>')
    step = max(1, math.ceil(n / 8))
    for i in range(0, n, step): o.append(f'<text x="{X(i):.1f}" y="{H - 22}" text-anchor="middle">{html.escape(str(xs[i]))}</text>')
    if band:
        pts = [(i, band['lo'][i], band['hi'][i]) for i in range(n) if band['lo'][i] is not None and band['hi'][i] is not None]
        if len(pts) >= 2:
            up = ' '.join(f'{X(i):.1f},{Y(h):.1f}' for i, _, h in pts); dn = ' '.join(f'{X(i):.1f},{Y(l):.1f}' for i, l, _ in reversed(pts))
            o.append(f'<polygon points="{up} {dn}" class="band"/>')
    for k, s in enumerate(series):
        col = PALETTE[k % len(PALETTE)]; dash = _dash(k, s)
        seg = []
        for i, v in enumerate(s['values'] + [None]):
            if v is not None: seg.append((i, v))
            elif seg:
                o.append(f'<polyline fill="none" stroke="{col}" stroke-width="2.4"{dash} points="{" ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in seg)}"/>')
                if n <= 40: o += [f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="2.6" fill="{col}"><title>{html.escape(s["name"])}, {html.escape(str(xs[i]))}: {_cell(float(v))}</title></circle>' for i, v in seg]
                seg = []
    o.append('</svg>')
    leg = ''.join(f'<span><svg width="28" height="8"><line x1="0" x2="28" y1="4" y2="4" stroke="{PALETTE[k % len(PALETTE)]}" stroke-width="2.4"{_dash(k, s)}/></svg>{html.escape(s["name"])}</span>' for k, s in enumerate(series))
    if band: leg += '<span><svg width="28" height="10"><rect width="28" height="10" class="band"/></svg>Коридор 80 %</span>'
    return ''.join(o) + f'<div class="leg">{leg}</div>'


def _split(result):
    out = result.get('outputs') or {}
    return out, out.get('summary_ru') or [], out.get('tables') or {}, out.get('chart')


def to_markdown(result):
    out, summ, tables, _ = _split(result)
    status, _ = STATUS_RU.get(result.get('status'), (result.get('status', '?'), 'warn'))
    L = [f"# {_name(result.get('model_id', '?'))} ({result.get('model_id', '?')})", '', f"**{status}.** {MODE_RU.get(result.get('mode'), result.get('mode', ''))}.", '']
    if summ:
        L += ['## Главное', ''] + [f'- {x}' for x in summ] + ['']
    for t in tables.values():
        L += [f"## {t.get('title') or 'Таблица'}", '', '| ' + ' | '.join(t['columns']) + ' |', '|' + '---|' * len(t['columns'])]
        L += ['| ' + ' | '.join(row) + ' |' for row in _cells(t)] + ['']
    L += ['## На что обратить внимание', '']
    L += [f'- {x}' for x in result.get('warnings', [])] or ['- Особых замечаний нет.']
    if result.get('errors'): L += ['', '## Ошибки', ''] + [f'- {x}' for x in result['errors']]
    tech = {k: v for k, v in out.items() if k not in ('summary_ru', 'tables', 'chart')} if summ else out
    L += ['', '## Технические подробности', '',
          f"Версия модели {result.get('model_version', '?')}; SHA-256 входа `{result.get('inputs_hash', '?')}`; {result.get('started_at', '?')} — {result.get('completed_at', '?')}.", '',
          '```json', json.dumps({'outputs': tech, 'diagnostics': result.get('diagnostics', {})}, ensure_ascii=False, indent=2, default=str), '```', '',
          '> Статус «Расчёт выполнен» значит только, что вычисление прошло без ошибок. Это не эмпирическое подтверждение модели.']
    return '\n'.join(L) + '\n'


CSS = '''
:root{--bg:#f4f5f2;--panel:#fff;--ink:#1d2421;--mute:#5f6b66;--line:#d9ddd8;--accent:#2f6f5e;--c1:#2f7d4f;--c2:#b5532f;--c3:#3b6ea5;--c4:#8a6bb0;--c5:#a07d1f;--c6:#5f6b66;--ok:#2f7d4f;--warn:#a07d1f;--bad:#b5532f;--chip:#e8ece8}
@media (prefers-color-scheme:dark){:root{--bg:#121a17;--panel:#1b2622;--ink:#e6ece8;--mute:#9aa8a1;--line:#2e3b36;--accent:#6fbfa5;--c1:#5fc08a;--c2:#e08a63;--c3:#7fb0e0;--c4:#b99ae0;--c5:#d6b24a;--c6:#9aa8a1;--ok:#5fc08a;--warn:#d6b24a;--bad:#e08a63;--chip:#25322d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,Segoe UI,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:20px 16px 40px}h1{font-size:24px;margin:0}.id{color:var(--mute);font-size:14px;margin:2px 0 12px}
.badge{display:inline-block;padding:3px 12px;border-radius:999px;font-weight:600;font-size:14px;border:1px solid currentColor}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.mode{color:var(--mute);font-size:14px;margin:8px 0 16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0;overflow-x:auto}
.card h2{font-size:17px;margin:0 0 8px}.main li{margin:7px 0}.main{padding-left:20px;margin:0;font-size:17px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th:first-child,td:first-child,th.l,td.l{text-align:left}th{color:var(--mute);font-weight:600}
.note li{margin:5px 0}.note{padding-left:20px;margin:0}
svg text{fill:var(--ink);font-size:12px}svg .grid{stroke:var(--line);stroke-dasharray:3 4}svg .axis{stroke:var(--mute)}svg .band{fill:var(--c3);opacity:.18}svg .barpos{fill:var(--c1)}svg .barneg{fill:var(--c2)}
.leg{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;margin-top:6px}.leg span{display:flex;gap:6px;align-items:center}
details summary{cursor:pointer;color:var(--mute)}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;background:var(--chip);padding:10px;border-radius:8px}
.foot{color:var(--mute);font-size:13px;margin-top:16px}
'''


JS = '''<script>(function(){var K='economia_mode',m='user';try{m=localStorage.getItem(K)||'user'}catch(e){}
function ap(){document.querySelectorAll('.mb').forEach(function(b){var on=b.dataset.m===m;b.style.cssText='border:1px solid var(--line);border-radius:8px;padding:4px 10px;cursor:pointer;font:inherit;background:'+(on?'var(--c1)':'var(--chip)')+';color:'+(on?'#fff':'var(--ink)')});
document.querySelectorAll('details').forEach(function(d){d.open=(m==='pro')});document.querySelectorAll('.pro').forEach(function(x){x.style.display=m==='pro'?'':'none'})}
document.querySelectorAll('.mb').forEach(function(b){b.onclick=function(){m=b.dataset.m;try{localStorage.setItem(K,m)}catch(e){}ap()}});ap()})();</script>'''


def to_html(result):
    out, summ, tables, chart = _split(result)
    status, cls = STATUS_RU.get(result.get('status'), (result.get('status', '?'), 'warn'))
    e = html.escape
    parts = [f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(_name(result.get("model_id", "?")))} — отчёт ECONOMIA</title><style>{CSS}</style></head><body><div class="wrap">',
             f'<div class="modebar" style="display:flex;gap:6px;align-items:center;margin:0 0 10px;font-size:13px"><span style="color:var(--mute)">Режим:</span><button type="button" data-m="user" class="mb">Пользователь</button><button type="button" data-m="pro" class="mb">Профессионал</button></div><h1>{e(_name(result.get("model_id", "?")))}</h1><div class="id">Модуль {e(result.get("model_id", "?"))}</div>',
             f'<span class="badge {cls}">{e(status)}</span><div class="mode">{e(MODE_RU.get(result.get("mode"), str(result.get("mode", ""))))}</div>']
    dg = result.get('diagnostics', {})
    parts.append('<div class="pro card" style="display:none"><h2>Для профессионала</h2><p class="foot" style="margin:0">Версия модели ' + e(str(result.get('model_version', '?'))) + '; набор ' + e(str(dg.get('dataset_id', '—'))) + '; происхождение ' + e(str(dg.get('dataset_origin', '—'))) + '; записей ' + e(str(dg.get('input_record_count', '—'))) + '; SHA-256 входа ' + e(str(result.get('inputs_hash', '?'))) + '. Полные параметры и диагностика раскрыты внизу страницы.</p></div>')
    if summ: parts.append('<div class="card"><h2>Главное</h2><ul class="main">' + ''.join(f'<li>{e(x)}</li>' for x in summ) + '</ul></div>')
    else: parts.append('<div class="card"><h2>Главное</h2><p>Для этого режима расчёта краткое резюме не подготовлено — см. технические подробности ниже.</p></div>')
    svg = render_chart_svg(chart)
    if svg: parts.append(f'<div class="card"><h2>{e(chart.get("title", "График"))}</h2>{svg}</div>')
    for t in tables.values():
        tc = _text_cols(t)
        parts.append(f'<div class="card"><h2>{e(t.get("title") or "Таблица")}</h2><table><thead><tr>' + ''.join(f'<th{" class=l" if j in tc else ""}>{e(c)}</th>' for j, c in enumerate(t['columns'])) + '</tr></thead><tbody>' +
                     ''.join('<tr>' + ''.join(f'<td{" class=l" if j in tc else ""}>{e(c)}</td>' for j, c in enumerate(row)) + '</tr>' for row in _cells(t)) + '</tbody></table></div>')
    warns = result.get('warnings', []); errs = result.get('errors', [])
    parts.append('<div class="card"><h2>На что обратить внимание</h2><ul class="note">' + (''.join(f'<li>{e(x)}</li>' for x in warns) or '<li>Особых замечаний нет.</li>') + '</ul></div>')
    if errs: parts.append('<div class="card"><h2>Ошибки</h2><ul class="note bad">' + ''.join(f'<li>{e(x)}</li>' for x in errs) + '</ul></div>')
    tech = {k: v for k, v in out.items() if k not in ('summary_ru', 'tables', 'chart')} if summ else out
    parts.append('<div class="card"><details><summary>Технические подробности</summary><p class="foot">Версия модели ' + e(str(result.get('model_version', '?'))) + '; SHA-256 входа ' + e(str(result.get('inputs_hash', '?'))) + '</p><pre>' +
                 e(json.dumps({'outputs': tech, 'diagnostics': result.get('diagnostics', {})}, ensure_ascii=False, indent=2, default=str)) + '</pre></details></div>')
    parts.append('<div class="foot">«Расчёт выполнен» значит, что вычисление прошло без ошибок. Это не эмпирическое подтверждение модели и не гарантия точности. Сценарии и прогнозы — допущения, а не предсказания.</div></div>'+JS+'</body></html>')
    return ''.join(parts)


def write_report(result, path):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    ext = p.suffix.lower()
    if ext == '.json': p.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    elif ext in {'.md', '.markdown'}: p.write_text(to_markdown(result), encoding='utf-8')
    elif ext == '.html': p.write_text(to_html(result), encoding='utf-8')
    else: raise ValueError('Поддерживаются форматы JSON, Markdown и HTML')
    return p
