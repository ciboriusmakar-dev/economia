#!/usr/bin/env python3
"""Независимая сверка модулей ECONOMIA с цифрами, которые публикует сам Eurostat (Германия).
  python independent_check.py --raw raw --out check.html [--json check.json]
Проверки:
  1) M07: реальный рост ВВП из рядов CLV10_MEUR против опубликованного Eurostat CLV_PCH_PRE (все годы);
  2) M02: изменение к предыдущему месяцу промышленного производства против опубликованного PCH_PRE;
  3) M03: инфляция к году назад по индексу с базой 2015 против расчёта по индексу с базой 1996 (одна и та же статистика в разных базах).
Опубликованные Eurostat проценты округлены до 0,1, поэтому допуск 0,06 п.п. Это сверка вычислений с независимо опубликованными числами,
а не подтверждение прогностической силы моделей."""
import argparse, html, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from economia_modules import run_model
from run_real_pipeline import series, find, sha, ds

TOL = 0.06


def table_of(res, key_part):
    for k, t in res['outputs']['tables'].items():
        if key_part in k or key_part in (t.get('title') or ''): return t
    raise KeyError(key_part)


def compare(ours, pub):
    common = sorted(set(ours) & set(pub)); diffs = [(k, ours[k], pub[k], abs(ours[k] - pub[k])) for k in common]
    return diffs


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--raw', required=True); ap.add_argument('--out', default='check.html'); ap.add_argument('--json', default=None)
    a = ap.parse_args(); out = []
    # 1. ВВП
    p = find(a.raw, 'nama_10_gdp'); real, _ = series(p, 'A,CLV10_MEUR,B1GQ,DE', '2000'); nom, _ = series(p, 'A,CP_MEUR,B1GQ,DE', '2000'); pub, _ = series(p, 'A,CLV_PCH_PRE,B1GQ,DE', '2000')
    nm = dict(nom); recs = [{'year': int(t), 'gdp_real': v, 'gdp_nominal': nm[t]} for t, v in real if t in nm]
    r = run_model('M07', ds('M07', 'nama_10_gdp', 'check', recs), {}, mode='real'); rows = table_of(r, 'показатели')['rows']
    ours = {str(row[0]): row[3] for row in rows if row[3] is not None}
    out.append(('M07: реальный рост ВВП, % (Eurostat CLV_PCH_PRE)', os.path.basename(p), sha(p), compare(ours, dict(pub))))
    # 2. промышленное производство, к предыдущему месяцу
    p = find(a.raw, 'sts_inpr_m'); lvl, _ = series(p, 'M,PRD,C,SCA,I21,DE', '2015'); pub, _ = series(p, 'M,PRD,C,SCA,PCH_PRE,DE', '2015')
    r = run_model('M02', ds('M02', 'sts_inpr_m', 'check', [{'period': t, 'value': v} for t, v in lvl]), {}, mode='real'); rows = table_of(r, 'Динамика')['rows']
    ours = {str(row[0]): row[2] for row in rows if row[2] is not None}
    out.append(('M02: промышленное производство, % к предыдущему месяцу (Eurostat PCH_PRE)', os.path.basename(p), sha(p), compare(ours, dict(pub))))
    # 3. цены: две базы индекса
    p = find(a.raw, 'prc_hicp_midx'); res = {}
    for base in ('I15', 'I96'):
        s, _ = series(p, f'M,{base},CP00,DE', '2000')
        res[base] = run_model('M03', ds('M03', 'prc_hicp_midx', 'check', [{'period': t, 'group': 'Всего', 'price': v} for t, v in s]), {'group': 'group'}, mode='real')
    t15, t96 = table_of(res['I15'], 'Динамика')['rows'][0], table_of(res['I96'], 'Динамика')['rows'][0]
    out.append(('M03: инфляция к году назад, % (последний месяц; база 2015 против базы 1996)', os.path.basename(p), sha(p), [(str(t15[1]), float(t15[4]), float(t96[4]), abs(float(t15[4]) - float(t96[4])))]))
    summary = []
    for title, f, h, d in out:
        mx = max((x[3] for x in d), default=None); summary.append({'check': title, 'file': f, 'sha256': h, 'n': len(d), 'max_abs_diff_pp': mx, 'passed': mx is not None and mx <= TOL, 'tolerance_pp': TOL,
                                                                'worst': sorted(d, key=lambda x: -x[3])[:3]})
    if a.json: json.dump(summary, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    e = html.escape
    body = ''.join(f'<h2>{e(s["check"])}</h2><p>Сравнено значений: {s["n"]}. Наибольшее расхождение: {s["max_abs_diff_pp"]:.4f} п.п. (допуск {TOL}). <b>{"Пройдена" if s["passed"] else "НЕ ПРОЙДЕНА"}</b>.</p>'
                   f'<p class="m">Файл {e(s["file"])}, SHA-256 {s["sha256"][:16]}…</p><table><tr><th>Период</th><th>ECONOMIA</th><th>Eurostat</th><th>Разница</th></tr>' +
                   ''.join(f'<tr><td>{e(str(k))}</td><td>{o:.3f}</td><td>{q:.3f}</td><td>{d:.3f}</td></tr>' for k, o, q, d in s['worst']) + '</table><p class="m">Показаны три наибольших расхождения.</p>' for s in summary)
    open(a.out, 'w', encoding='utf-8').write('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Независимая сверка · ECONOMIA</title><style>body{margin:0;font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;background:#f4f5f2;color:#1d2421}.w{max-width:860px;margin:0 auto;padding:16px}h2{font-size:16px;margin-top:22px}table{border-collapse:collapse;font-size:14px}td,th{padding:5px 12px;border-bottom:1px solid #d9ddd8;text-align:right}th:first-child,td:first-child{text-align:left}.m{color:#5f6b66;font-size:13px}@media(prefers-color-scheme:dark){body{background:#121a17;color:#e6ece8}}</style></head><body><div class="w"><h1>Независимая сверка с цифрами Eurostat</h1><p class="m">Сравниваем вычисления ECONOMIA с процентами, которые опубликовал сам Eurostat. Опубликованные числа округлены до 0,1, поэтому допуск 0,06 п.п. Это проверка арифметики и обработки данных, а не точности прогнозов.</p>' + body + '<p><a href="index.html">На главную</a></p></div></body></html>')
    for s in summary: print(('OK  ' if s['passed'] else 'FAIL'), s['check'], '| n =', s['n'], '| макс. расхождение', s['max_abs_diff_pp'])
    sys.exit(0 if all(s['passed'] for s in summary) else 1)


if __name__ == '__main__':
    main()
