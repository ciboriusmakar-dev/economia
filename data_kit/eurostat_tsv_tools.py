#!/usr/bin/env python3
"""ECONOMIA: работа с файлами Eurostat TSV (обычными или .gz; только стандартная библиотека).

  python eurostat_tsv_tools.py filter  файл.tsv[.gz]  --geo DE  [--out DE_файл.tsv]
      оставляет только строки выбранных стран (формат TSV сохраняется, значения и флаги не меняются) —
      для файлов, которые слишком велики, чтобы прислать целиком;
  python eurostat_tsv_tools.py long    файл.tsv[.gz]  --geo DE --from 2008 [--out файл_long.csv]
      длинный CSV: измерения..., period, value, flag. Пропуски ':' в value не попадают (нулями не заменяются),
      их число выводится в сводке.
Рядом с результатом пишется *.provenance.json: SHA-256 исходного файла, число строк, фильтры.
Исходный файл никогда не изменяется.
"""
import argparse, csv, gzip, hashlib, json, os, sys
from datetime import datetime, timezone


def _open(path):
    with open(path, 'rb') as f:
        gz = f.read(2) == b'\x1f\x8b'
    return gzip.open(path, 'rt', encoding='utf-8', newline='') if gz else open(path, 'rt', encoding='utf-8', newline='')


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _geo(line):
    return line.split('\t', 1)[0].rsplit(',', 1)[-1].strip()


def _prov(src, out, kind, args, rows_in, rows_out, extra=None):
    d = {'source_file': os.path.basename(src), 'source_sha256': _sha(src), 'output_file': os.path.basename(out),
         'operation': kind, 'geo': args.geo, 'from_year': getattr(args, 'from_year', None),
         'rows_in': rows_in, 'rows_out': rows_out, 'created_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    d.update(extra or {})
    json.dump(d, open(out + '.provenance.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def cmd_filter(a):
    geos = set(a.geo.split(','))
    out = a.out or 'DE_' + os.path.basename(a.file).replace('.gz', '').replace('.tsv', '') + '.tsv'
    n_in = n_out = 0
    with _open(a.file) as f, open(out, 'w', encoding='utf-8', newline='') as o:
        o.write(f.readline())
        for line in f:
            n_in += 1
            if _geo(line.rstrip('\r\n')) in geos:
                o.write(line); n_out += 1
    _prov(a.file, out, 'filter_geo', a, n_in, n_out)
    print(f'{out}: оставлено {n_out} из {n_in} строк, {os.path.getsize(out)} байт')


def cmd_long(a):
    geos = set(a.geo.split(',')) if a.geo else None
    out = a.out or os.path.basename(a.file).replace('.gz', '').replace('.tsv', '') + '_long.csv'
    n_in = n_out = n_missing = 0
    with _open(a.file) as f, open(out, 'w', encoding='utf-8', newline='') as o:
        head = f.readline().rstrip('\r\n').split('\t')
        dims = head[0].split('\\')[0].split(',')
        periods = [p.strip() for p in head[1:]]
        w = csv.writer(o); w.writerow(dims + ['period', 'value', 'flag'])
        for line in f:
            n_in += 1
            c = line.rstrip('\r\n').split('\t'); key = c[0].split(',')
            if geos and key[-1] not in geos:
                continue
            for p, cell in zip(periods, c[1:]):
                if int(p[:4]) < a.from_year:
                    continue
                cell = cell.strip()
                if cell in (':', ''):
                    n_missing += 1; continue
                v, _, fl = cell.partition(' ')
                try:
                    float(v)
                except ValueError:
                    n_missing += 1; continue
                w.writerow(key + [p, v, fl.strip()]); n_out += 1
    _prov(a.file, out, 'to_long_csv', a, n_in, n_out, {'missing_cells_skipped': n_missing})
    print(f'{out}: {n_out} значений, пропусков пропущено {n_missing} (нулями не заполнялись)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    for name, fn in (('filter', cmd_filter), ('long', cmd_long)):
        p = sp.add_parser(name); p.add_argument('file'); p.add_argument('--geo', default='DE'); p.add_argument('--out')
        if name == 'long': p.add_argument('--from', dest='from_year', type=int, default=0)
        p.set_defaults(fn=fn)
    a = ap.parse_args(); a.fn(a)


if __name__ == '__main__':
    main()
