#!/usr/bin/env python3
"""M01 из реальных энергобалансов Eurostat (nrg_bal_c): производство, импорт, экспорт, потребление по странам и энергоносителям.

  python m01_from_eurostat_energy.py nrg_bal_c.tsv.gz --out data/real_input/M01_energy_canonical.csv [--countries DE,FR] [--from 2008]
Показатели (единица TJ): PPRD→PRODQNT (первичное производство), IMP→IMPQNT, EXP→EXPQNT, GAE→CONSQNT (валовое доступное
энергоснабжение). Пропуски ':' не заполняются нулями. Невязка «производство + импорт − экспорт» против GAE — это в основном
изменение запасов, бункеровка и пр. (не ошибка данных). Агрегаты (EU27_2020) исключены."""
import argparse, csv, gzip, hashlib, json, os

PRODUCTS = {  # коды SIEC Eurostat -> понятное имя (оригинальный код в скобках)
    'C0000X0350-0370': 'Твёрдое топливо, уголь (C0000X0350-0370)',
    'G3000': 'Природный газ (G3000)',
    'O4000XBIO': 'Нефть и нефтепродукты (O4000XBIO)',
    'E7000': 'Электроэнергия (E7000)',
    'H8000': 'Тепло (H8000)',
    'N900H': 'Ядерное тепло (N900H)',
    'RA000': 'Возобновляемые источники (RA000)',
    'P1000': 'Торф (P1000)',
    'W6100_6220': 'Невозобновляемые отходы (W6100_6220)',
}
MAP = {'PPRD': 'PRODQNT', 'IMP': 'IMPQNT', 'EXP': 'EXPQNT', 'GAE': 'CONSQNT'}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--out', required=True); ap.add_argument('--countries', default='')
    ap.add_argument('--from', dest='y0', type=int, default=2008)
    ap.add_argument('--exclude', default='', help='коды стран через запятую (например UK — вне ЕС/ЕАСТ/кандидатов: только некоммерческое использование)')
    a = ap.parse_args(); want = set(filter(None, a.countries.split(','))); excl = set(filter(None, a.exclude.split(',')))
    op = gzip.open if open(a.file, 'rb').read(2) == b'\x1f\x8b' else open
    n_out = n_miss = 0; found = set()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with op(a.file, 'rt', encoding='utf-8') as f, open(a.out, 'w', newline='', encoding='utf-8') as o:
        head = [x.strip() for x in f.readline().rstrip('\r\n').split('\t')]
        w = csv.writer(o); w.writerow(['country', 'year', 'product_code', 'indicator', 'value', 'unit', 'flag'])
        for line in f:
            c = line.rstrip('\r\n').split('\t'); k = c[0].split(',')
            freq, bal, siec, unit, geo = k
            if bal not in MAP or siec not in PRODUCTS or unit != 'TJ' or geo.startswith(('EU', 'EA')): continue
            if (want and geo not in want) or geo in excl: continue
            found.add(geo)
            for y, cell in zip(head[1:], c[1:]):
                if int(y) < a.y0: continue
                v, _, fl = cell.strip().partition(' ')
                try: float(v)
                except ValueError: n_miss += 1; continue
                w.writerow([geo, y, PRODUCTS[siec], MAP[bal], v, 'TJ', fl.strip()]); n_out += 1
    sha = hashlib.sha256(open(a.file, 'rb').read()).hexdigest()
    json.dump({'source_file': os.path.basename(a.file), 'source_sha256': sha, 'dataset': 'eurostat nrg_bal_c', 'rows_out': n_out,
               'missing_skipped': n_miss, 'countries': sorted(found), 'from_year': a.y0}, open(a.out + '.provenance.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{a.out}: {n_out} значений, {len(found)} стран, пропусков пропущено {n_miss}')


if __name__ == '__main__':
    main()
