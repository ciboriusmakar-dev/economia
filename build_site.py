#!/usr/bin/env python3
"""Собирает статичный сайт из raw/ и манифеста: панели M01 и отчёты M02, M03, M07, M09 на РЕАЛЬНЫХ данных.
  python build_site.py [--raw raw] [--manifest data/manifest.json] [--out site]
Всё считается по файлам в raw/; если какого-то набора нет, зависящие от него страницы пропускаются и на главной это написано."""
import argparse, html, json, os, shutil, subprocess, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(*args):
    r = subprocess.run([PY, *args], cwd=HERE, capture_output=True, text=True)
    if r.returncode: print('ОШИБКА:', ' '.join(args), r.stderr[-400:], file=sys.stderr)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--raw', default='raw'); ap.add_argument('--manifest', default='data/manifest.json')
    ap.add_argument('--out', default='site'); ap.add_argument('--config', default='site_config/datasets.json')
    a = ap.parse_args(); raw, out = os.path.abspath(a.raw), os.path.abspath(a.out)
    man = json.load(open(a.manifest, encoding='utf-8')) if os.path.exists(a.manifest) else {'datasets': {}}
    cfg = json.load(open(a.config, encoding='utf-8'))
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out + '/reports'); os.makedirs(out + '/panels')
    pages, notes = [], []
    have = lambda i: os.path.exists(os.path.join(raw, i + '.tsv.gz'))
    # M01: энергобалансы
    if have('nrg_bal_c'):
        tmp = os.path.join(out, '_tmp'); os.makedirs(tmp)
        for name, extra, title in (('M01_energy_DE_FR', ['--countries', 'DE,FR', '--from', '2008'], 'M01 · Германия и Франция, 2008–2024'),
                                   ('M01_energy_EU', ['--from', '1990'], 'M01 · все страны, 1990–2024')):
            csvp = os.path.join(tmp, name + '.csv')
            if run('m01_from_eurostat_energy.py', os.path.join(raw, 'nrg_bal_c.tsv.gz'), '--out', csvp, '--exclude', ','.join(cfg.get('exclude_countries', [])), *extra) and \
               run('m01_dashboard.py', csvp, '--out', os.path.join(out, 'panels', name + '.html')):
                pages.append(('panels/' + name + '.html', title, 'Товарный баланс: производство, импорт, экспорт, потребление (ТДж)'))
        shutil.rmtree(tmp)
    else:
        notes.append('Панели M01 не построены: нет набора nrg_bal_c.')
    # M02, M03, M07, M09
    need = ['nama_10_gdp', 'une_rt_m', 'sts_inpr_m', 'prc_hicp_midx', 'sts_trtu_m']
    miss = [i for i in need if not have(i)]
    if miss:
        notes.append('Отчёты по модулям не построены: нет наборов ' + ', '.join(miss) + '.')
    elif run('run_real_pipeline.py', '--raw', raw, '--out', out + '/reports'):
        titles = {'M07_DE_GDP_real': ('M07 · ВВП Германии', 'Реальный и номинальный рост, дефлятор'), 'M09_DE_unemployment': ('M09 · Безработица', 'Прогноз по базовым методам с проверкой'),
                  'M09_DE_industrial_production': ('M09 · Промышленное производство', 'Прогноз по базовым методам с проверкой'),
                  'M03_DE_HICP': ('M03 · Потребительские цены', 'Индексы и инфляция по группам'), 'M02_DE_retail': ('M02 · Розничная торговля', 'Динамика, сезонность, связь с ценой')}
        titles.update({'M07_WB_DEU_GDP': ('M07 · ВВП Германии (Всемирный банк)', 'Реальный и номинальный рост в долл. США'), 'M07_WB_FRA_GDP': ('M07 · ВВП Франции (Всемирный банк)', 'Реальный и номинальный рост в долл. США')})
        for k, (t, d) in titles.items():
            if os.path.exists(f'{out}/reports/{k}.html'): pages.append((f'reports/{k}.html', t, d))
        for f in os.listdir(out + '/reports'):
            if not f.endswith('.html'): os.remove(os.path.join(out, 'reports', f)) if f.endswith('.md') else None
    if not miss:
        if run('independent_check.py', '--raw', raw, '--out', out + '/check.html'):
            pages.append(('check.html', 'Независимая сверка', 'Расчёты ECONOMIA против процентов, опубликованных самим Eurostat'))
        else:
            notes.append('Независимая сверка не прошла или не выполнена: смотрите журнал сборки.')
    e = html.escape
    srcs, dsets = cfg.get('sources', {}), {d['id']: d for d in cfg['datasets']}
    page_ds = lambda u: (['nama_10_gdp', 'sts_inpr_m', 'prc_hicp_midx'] if u == 'check.html' else ['nrg_bal_c'] if u.startswith('panels/') else
                         ['nama_10_gdp'] if 'M07_DE_GDP' in u else ['wdi_NY.GDP.MKTP.KD', 'wdi_NY.GDP.MKTP.CD'] if 'M07_WB' in u else
                         ['une_rt_m'] if 'unemployment' in u else ['sts_inpr_m'] if 'industrial' in u else ['prc_hicp_midx'] if 'M03' in u else ['sts_trtu_m', 'prc_hicp_midx'])
    def attr(i):
        d = dsets[i]; m = man.get('datasets', {}).get(i, {}); date = str(m.get('retrieved_utc', ''))[:10] or '—'
        return srcs[d['source']]['attribution'].format(title=d['title'], id=i, indicator=d.get('indicator', ''), date=date)
    for u, _, _ in pages:
        p = os.path.join(out, u); h = open(p, encoding='utf-8').read()
        foot = '<div style="max-width:1100px;margin:14px auto;padding:0 16px;font:13px/1.5 system-ui,Arial,sans-serif;color:#5f6b66">' + '<br>'.join(e(attr(i)) for i in page_ds(u)) + ' · <a href="' + ('../' if '/' in u else '') + 'licences.html">лицензии</a> · <a href="' + ('../' if '/' in u else '') + 'index.html">на главную</a></div>'
        open(p, 'w', encoding='utf-8').write(h.replace('</body>', foot + '</body>', 1))
    lic = ''.join(f'<h2>{e(v["name"])}</h2><p>{e(v["licence"])}</p><p><a href="{e(v["terms_url"])}">Официальные условия</a></p>' for v in srcs.values())
    lic += '<h2>Как указан источник на страницах</h2><ul>' + ''.join(f'<li>{e(attr(i))}</li>' for i in dsets) + '</ul>'
    lic += f'<p class="m">Условия проверены {e(cfg.get("licence_checked", "—"))} по официальным страницам; перед коммерческим использованием проверьте их снова. Исключены страны вне ЕС, ЕАСТ и кандидатов в ЕС (Великобритания): их данные Eurostat разрешает использовать только некоммерческим способом. Данные обработаны ECONOMIA (пересчёт показателей, отбор стран и лет); это не официальная статистика Eurostat или Всемирного банка.</p>'
    open(out + '/licences.html', 'w', encoding='utf-8').write('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Лицензии · ECONOMIA</title><style>body{margin:0;font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;background:#f4f5f2;color:#1d2421}.w{max-width:860px;margin:0 auto;padding:16px}h2{font-size:17px}.m{color:#5f6b66;font-size:13px}@media(prefers-color-scheme:dark){body{background:#121a17;color:#e6ece8}a{color:#6fbfa5}}</style></head><body><div class="w"><h1>Лицензии и источники</h1>' + lic + '<p><a href="index.html">На главную</a></p></div></body></html>')
    rows = ''.join(f'<tr><td>{e(i)}</td><td>{e(m.get("title", ""))}</td><td>{e(str(m.get("retrieved_utc", "—")))}</td><td>{m.get("bytes", 0):,}</td><td class=h>{e(str(m.get("sha256", ""))[:16])}…</td><td>{e(m.get("status", ""))}</td></tr>'.replace(',', ' ') for i, m in man.get('datasets', {}).items())
    cards = ''.join(f'<a class="card" href="{u}"><b>{e(t)}</b><span>{e(d)}</span></a>' for u, t, d in pages) or '<p>Страницы ещё не построены.</p>'
    MODEJS = '''<script>(function(){var K='economia_mode',m='user';try{m=localStorage.getItem(K)||'user'}catch(e){}
function ap(){document.querySelectorAll('.mb').forEach(function(b){var on=b.dataset.m===m;b.style.cssText='border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer;font:inherit;background:'+(on?'var(--ac)':'var(--p)')+';color:'+(on?'#fff':'var(--ink)')});
document.querySelectorAll('.pro').forEach(function(x){x.style.display=m==='pro'?'':'none'});var h=document.getElementById('mh');if(h)h.textContent=m==='pro'?'Показаны версии данных, контрольные суммы и технические подробности.':'Простой вид: только панели и отчёты.'}
document.querySelectorAll('.mb').forEach(function(b){b.onclick=function(){m=b.dataset.m;try{localStorage.setItem(K,m)}catch(e){}ap()}});ap()})();</script>'''
    idx = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ECONOMIA · данные Eurostat</title>
<style>:root{{--bg:#f4f5f2;--p:#fff;--ink:#1d2421;--mute:#5f6b66;--line:#d9ddd8;--ac:#2f6f5e}}@media(prefers-color-scheme:dark){{:root{{--bg:#121a17;--p:#1b2622;--ink:#e6ece8;--mute:#9aa8a1;--line:#2e3b36;--ac:#6fbfa5}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif}}.w{{max-width:960px;margin:0 auto;padding:16px}}h1{{font-size:22px;margin:4px 0}}h2{{font-size:17px;margin:22px 0 8px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}.card{{display:flex;flex-direction:column;gap:4px;background:var(--p);border:1px solid var(--line);border-radius:12px;padding:12px;color:inherit;text-decoration:none}}.card span{{color:var(--mute);font-size:13px}}.card:hover{{border-color:var(--ac)}}
.t{{overflow-x:auto;background:var(--p);border:1px solid var(--line);border-radius:12px;padding:8px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}.h{{font-family:ui-monospace,monospace}}.m{{color:var(--mute);font-size:13px}}</style></head><body><div class="w">
<h1>ECONOMIA · Германия по открытым данным</h1><div class="m">Страница пересобирается автоматически раз в сутки. Последняя сборка: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}.</div>
<div class="modes" style="margin:12px 0"><button type="button" data-m="user" class="mb">Пользователь</button> <button type="button" data-m="pro" class="mb">Профессионал</button> <span class="m" id="mh"></span></div>
<h2>Панели и отчёты</h2><div class="g">{cards}</div>{"".join(f'<p class="m">⚠ {e(n)}</p>' for n in notes)}
<div class="pro" style="display:none"><h2>Источники и версии данных</h2><div class="t"><table><tr><th>Набор</th><th>Название</th><th>Получен (UTC)</th><th>Байт</th><th>SHA-256</th><th>Статус</th></tr>{rows}</table></div>
<p class="m"><a href="reports/provenance.csv">provenance.csv</a> — файл с контрольными суммами исходных наборов.</p></div>
<p class="m">Расчёты автоматические; «расчёт выполнен» не означает эмпирическое подтверждение моделей. Прогнозы — статистическая экстраполяция, а не предсказание. Данные Eurostat и Всемирного банка обработаны ECONOMIA. <a href="licences.html">Лицензии и источники</a>.</p></div>{MODEJS}</body></html>'''
    open(out + '/index.html', 'w', encoding='utf-8').write(idx)
    open(out + '/.nojekyll', 'w').write('')
    print('Сайт:', out, '| страниц:', len(pages), '|', '; '.join(notes) or 'без замечаний')


if __name__ == '__main__':
    main()
