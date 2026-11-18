#!/usr/bin/env python3
"""Ежедневное обновление данных Eurostat (только стандартная библиотека).

  python update_data.py [--raw raw] [--manifest data/manifest.json] [--config site_config/datasets.json]

Для каждого набора: условный запрос (If-None-Match / If-Modified-Since по прошлому манифесту), загрузка во временный файл,
проверка (читается как gzip, есть заголовок TIME_PERIOD и данные), сравнение SHA-256 с прошлой версией.
Хорошая прежняя копия никогда не затирается плохой загрузкой. Манифест хранит историю версий (дата, SHA-256, размер).
Переменная ECONOMIA_BASE_URL подменяет адрес (для тестов). Код возврата 0, если у всех наборов есть пригодный файл."""
import argparse, gzip, hashlib, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def valid(path):
    """Файл пригоден: .json (Всемирный банк) — список из двух частей с данными; иначе .gz TSV Eurostat с заголовком TIME_PERIOD."""
    kind_json = path[:-5].endswith('.json') if path.endswith('.part') else path.endswith('.json')
    try:
        if kind_json:
            j = json.load(open(path, encoding='utf-8'))
            return isinstance(j, list) and len(j) == 2 and bool(j[1])
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            head = f.readline()
            return 'TIME_PERIOD' in head and bool(f.readline().strip())
    except Exception:
        return False


def fetch(url, tmp, prev):
    hdr = {'User-Agent': 'ECONOMIA-update/1.0'}
    if prev.get('etag'): hdr['If-None-Match'] = prev['etag']
    elif prev.get('last_modified'): hdr['If-Modified-Since'] = prev['last_modified']
    req = urllib.request.Request(url, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, 'wb') as out:
            while True:
                b = r.read(1 << 20)
                if not b: break
                out.write(b)
            return 200, r.headers.get('ETag'), r.headers.get('Last-Modified')
    except urllib.error.HTTPError as e:
        if e.code == 304: return 304, None, None
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default='raw'); ap.add_argument('--manifest', default='data/manifest.json')
    ap.add_argument('--config', default='site_config/datasets.json')
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    base = os.environ.get('ECONOMIA_BASE_URL', cfg['base_url'])
    os.makedirs(a.raw, exist_ok=True); os.makedirs(os.path.dirname(a.manifest) or '.', exist_ok=True)
    man = json.load(open(a.manifest, encoding='utf-8')) if os.path.exists(a.manifest) else {'datasets': {}}
    ok_all = True
    for d in cfg['datasets']:
        i = d['id']; wb = d.get('source') == 'worldbank'
        path = os.path.join(a.raw, i + ('.json' if wb else '.tsv.gz')); tmp = path + '.part'
        m = man['datasets'].setdefault(i, {'title': d['title'], 'history': []})
        have = os.path.exists(path) and valid(path)
        prev = m if have else {}
        m['last_check_utc'] = now(); m['status'] = ''
        try:
            code, etag, lm = fetch((os.environ.get('ECONOMIA_WB_BASE_URL') or cfg['wb_url']).format(indicator=d['indicator']) if wb else base.format(id=i), tmp, prev)
            if code == 304:
                m['status'] = 'не изменялся (304)'
            elif not valid(tmp):
                m['status'] = 'загрузка отклонена: файл не прошёл проверку; оставлена прежняя копия' if have else 'ОШИБКА: файл не прошёл проверку'
                os.remove(tmp); ok_all &= have
            else:
                new = sha(tmp)
                if have and m.get('sha256') == new:
                    m['status'] = 'без изменений (тот же SHA-256)'; os.remove(tmp)
                else:
                    os.replace(tmp, path)
                    m.update({'sha256': new, 'bytes': os.path.getsize(path), 'retrieved_utc': now(), 'etag': etag, 'last_modified': lm})
                    m['history'].append({'retrieved_utc': m['retrieved_utc'], 'sha256': new, 'bytes': m['bytes']})
                    m['history'] = m['history'][-30:]
                    m['status'] = 'обновлён'
        except Exception as e:
            if os.path.exists(tmp): os.remove(tmp)
            m['status'] = ('ошибка загрузки, оставлена прежняя копия: ' if have else 'ОШИБКА: ') + str(e)[:120]
            ok_all &= have
        if have or os.path.exists(path):
            m.setdefault('sha256', sha(path)); m.setdefault('bytes', os.path.getsize(path))
        print(i, '-', m['status'])
    man['updated_utc'] = now()
    json.dump(man, open(a.manifest, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
