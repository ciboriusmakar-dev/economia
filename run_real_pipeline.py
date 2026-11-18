#!/usr/bin/env python3
"""Прогон модулей на РЕАЛЬНЫХ файлах Eurostat (Германия), режим real.
  python run_real_pipeline.py --raw <папка с .tsv или .tsv.gz> --out <папка результатов>
Читает исходные файлы без изменений, пишет provenance.csv (SHA-256) и отчёты HTML/MD.
Пропуски (':') пропускаются, нулями не заполняются. Данные с пометками качества используются, пометки сводятся в предупреждения."""
import argparse, csv, gzip, hashlib, os, sys
from collections import Counter
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from economia_modules import run_model
from economia_report import write_report


def _open(p):
    with open(p, 'rb') as f: gz = f.read(2) == b'\x1f\x8b'
    return gzip.open(p, 'rt', encoding='utf-8') if gz else open(p, encoding='utf-8')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def find(raw, name):
    for f in sorted(os.listdir(raw)):
        if name in f and not f.startswith('DE_') and not f.endswith(('.json', '.csv', '.provenance.json')): return os.path.join(raw, f)
    raise FileNotFoundError(name)


def series(path, key, since='2008'):
    """Ряд по точному ключу строки (например 'M,PRD,C,SCA,I21,DE') -> ([(период, значение)], пометки)."""
    with _open(path) as f:
        head = [x.strip() for x in f.readline().rstrip('\r\n').split('\t')]
        for line in f:
            c = line.rstrip('\r\n').split('\t')
            if c[0] == key:
                out, flags = [], Counter()
                for p, cell in zip(head[1:], c[1:]):
                    v, _, fl = cell.strip().partition(' ')
                    try: x = float(v)
                    except ValueError: continue
                    if p[:4] >= since:
                        out.append((p, x))
                        if fl: flags[fl.strip()] += 1
                return out, flags
    raise KeyError(key)


def wb_series(path, iso, since=2008):
    import json as _j
    j = _j.load(open(path, encoding='utf-8'))
    return sorted((int(x['date']), float(x['value'])) for x in j[1] if x.get('countryiso3code') == iso and x.get('value') is not None and int(x['date']) >= since)


def ds(name, src, key, recs):
    return {'dataset_id': f'eurostat:{src}:{key}', 'source_id': f'eurostat-{src}', 'origin': 'observed', 'data_mode': 'real', 'records': recs}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--raw', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    prov, summary = [], []

    def use(name):
        p = find(a.raw, name); prov.append([os.path.basename(p), name, sha(p), os.path.getsize(p)]); return p

    def go(mid, label, dataset, params, flags=None):
        r = run_model(mid, dataset, params, mode='real')
        if flags:
            r.setdefault('warnings', []).append('Пометки качества Eurostat в использованных значениях: ' + ', '.join(f'{k}: {v}' for k, v in sorted(flags.items())) + ' (d — отличается определение, b — разрыв ряда, e — оценка, p — предварительно, u — ненадёжно).')
        write_report(r, os.path.join(a.out, f'{label}.html')); write_report(r, os.path.join(a.out, f'{label}.md'))
        summary.append((label, r['status'], '; '.join(r.get('errors', []))))
        print(label, r['status'], r.get('errors') or '')

    # M07: годовой ВВП ФРГ (сопоставимые цены 2010 и текущие)
    p = use('nama_10_gdp'); real, f1 = series(p, 'A,CLV10_MEUR,B1GQ,DE'); nom, f2 = series(p, 'A,CP_MEUR,B1GQ,DE')
    nm = dict(nom); recs = [{'year': int(t), 'gdp_real': v, 'gdp_nominal': nm[t]} for t, v in real if t in nm]
    go('M07', 'M07_DE_GDP_real', ds('M07', 'nama_10_gdp', 'A,CLV10_MEUR+CP_MEUR,B1GQ,DE', recs), {}, f1 + f2)
    # M09: безработица и промышленное производство
    p = use('une_rt_m'); s, fl = series(p, 'M,SA,TOTAL,PC_ACT,T,DE')
    go('M09', 'M09_DE_unemployment', ds('M09', 'une_rt_m', 'M,SA,TOTAL,PC_ACT,T,DE', [{'period': t, 'value': v} for t, v in s]), {'horizon': 12}, fl)
    p = use('sts_inpr_m'); s, fl = series(p, 'M,PRD,C,SCA,I21,DE')
    go('M09', 'M09_DE_industrial_production', ds('M09', 'sts_inpr_m', 'M,PRD,C,SCA,I21,DE', [{'period': t, 'value': v} for t, v in s]), {'horizon': 12}, fl)
    # M03: потребительские цены по группам (HICP, старая ECOICOP, 2015=100)
    p = use('prc_hicp_midx'); recs, fl = [], Counter()
    for code, name in (('CP00', 'Всего'), ('CP01', 'Продукты и безалк. напитки'), ('CP04', 'Жильё, вода, энергия, топливо'), ('CP07', 'Транспорт'), ('CP11', 'Рестораны и гостиницы')):
        s, f = series(p, f'M,I15,{code},DE'); fl += f; recs += [{'period': t, 'group': name, 'price': v} for t, v in s]
    go('M03', 'M03_DE_HICP', ds('M03', 'prc_hicp_midx', 'M,I15,CP00+CP01+CP04+CP07+CP11,DE', recs), {'group': 'group'}, fl)
    # M02: розничные продажи (объём) и цены
    pr = dict(series(find(a.raw, 'prc_hicp_midx'), 'M,I15,CP00,DE')[0])
    p = use('sts_trtu_m'); s, fl = series(p, 'M,VOL_SLS,G47,SCA,I21,DE')
    go('M02', 'M02_DE_retail', ds('M02', 'sts_trtu_m', 'M,VOL_SLS,G47,SCA,I21,DE', [{'period': t, 'value': v, 'price': pr[t]} for t, v in s if t in pr]), {'price': 'price'}, fl)
    # Всемирный банк (WDI): ВВП в постоянных и текущих ценах (долл. США), Германия и Франция
    kd, cd = os.path.join(a.raw, 'wdi_NY.GDP.MKTP.KD.json'), os.path.join(a.raw, 'wdi_NY.GDP.MKTP.CD.json')
    if os.path.exists(kd) and os.path.exists(cd):
        for p in (kd, cd): prov.append([os.path.basename(p), 'worldbank WDI', sha(p), os.path.getsize(p)])
        for iso, nm in (('DEU', 'Германия'), ('FRA', 'Франция')):
            try:
                real, nom = wb_series(kd, iso), dict(wb_series(cd, iso))
                recs = [{'year': y, 'gdp_real': v, 'gdp_nominal': nom[y]} for y, v in real if y in nom]
                if len(recs) >= 3: go('M07', f'M07_WB_{iso}_GDP', ds('M07', 'worldbank-wdi', f'NY.GDP.MKTP.KD+CD,{iso}', recs), {})
            except Exception as e:
                print('WDI', iso, 'пропущено:', e)
    with open(os.path.join(a.out, 'provenance.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['file', 'dataset', 'sha256', 'bytes', 'processed_utc'])
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for r in prov: w.writerow(r + [now])


if __name__ == '__main__':
    main()
