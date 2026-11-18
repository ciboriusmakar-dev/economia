"""Unified, conservative data intake for ECONOMIA 1.9.5.

Supports CSV, TSV, XLSX, JSON-stat 2.0 and ZIP bundles. Original files are
never modified. ZIP extraction is path-safe and bounded. Normalized outputs
are convenience copies; source payloads and SHA-256 are retained separately.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, re, zipfile
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from typing import Any

SUPPORTED = {'.csv', '.tsv', '.xlsx', '.json'}
MAX_MEMBER = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024

class IntakeError(ValueError): pass

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def _decode(raw: bytes) -> str:
    for enc in ('utf-8-sig','utf-8','cp1252'):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    raise IntakeError('Не удалось определить текстовую кодировку; оригинал сохранён без изменений')

def _csv_rows(path: Path) -> tuple[list[dict[str,Any]], list[str]]:
    text=_decode(path.read_bytes())
    sample=text[:8192]
    try: dialect=csv.Sniffer().sniff(sample, delimiters=',;\t|')
    except csv.Error: dialect=csv.excel_tab if path.suffix.lower()=='.tsv' else csv.excel
    reader=csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames: raise IntakeError('Нет строки заголовков')
    headers=[str(x).strip() if x is not None else '' for x in reader.fieldnames]
    if any(not x for x in headers): raise IntakeError('Пустое имя столбца')
    if len(headers)!=len(set(headers)): raise IntakeError('Повторяющиеся имена столбцов')
    rows=[]
    for row in reader:
        rows.append({headers[i]: (row.get(reader.fieldnames[i]) if row.get(reader.fieldnames[i]) is not None else None) for i in range(len(headers))})
    return rows, headers

def _xlsx_rows(path: Path) -> tuple[list[dict[str,Any]], list[str], str]:
    try: import openpyxl
    except ImportError as e: raise IntakeError('Для XLSX установите openpyxl') from e
    wb=openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws=wb.active
    iterator=ws.iter_rows(values_only=True)
    try: raw_headers=next(iterator)
    except StopIteration: raise IntakeError('Пустой XLSX лист')
    headers=[str(x).strip() if x is not None else '' for x in raw_headers]
    while headers and not headers[-1]: headers.pop()
    if not headers or any(not x for x in headers) or len(headers)!=len(set(headers)):
        raise IntakeError('Некорректные/повторяющиеся заголовки XLSX')
    rows=[]
    for vals in iterator:
        vals=list(vals[:len(headers)])
        if not any(v is not None for v in vals): continue
        vals += [None]*(len(headers)-len(vals))
        rows.append(dict(zip(headers, vals)))
    return rows, headers, ws.title

def _jsonstat_rows(path: Path) -> tuple[list[dict[str,Any]], list[str], dict[str,Any]]:
    from jsonstat_ingest import parse_jsonstat
    payload=json.loads(path.read_text(encoding='utf-8-sig'))
    rows, report=parse_jsonstat(payload)
    return rows, (list(rows[0]) if rows else ['value']), report

def _unit_hints(headers: list[str], rows: list[dict[str,Any]], metadata: dict[str,Any]) -> dict[str,Any]:
    hints=[]
    patterns=[r'\(([^()]{1,40}(?:%|eur|usd|ton|tonne|kg|mwh|kwh|persons?|hours?|index|points?)[^()]*)\)', r'\[([^\[\]]{1,40})\]']
    for h in headers:
        for pat in patterns:
            m=re.search(pat,h,re.I)
            if m: hints.append({'column':h,'unit_candidate':m.group(1).strip(),'confidence':'header_hint'})
    for key in ('unit','units','unit_measure','unit_metadata'):
        val=metadata.get(key)
        if val: hints.append({'column':'*','unit_candidate':str(val),'confidence':'source_metadata'})
    if not hints:
        hints.append({'column':'*','unit_candidate':None,'confidence':'unknown_requires_metadata'})
    return {'unit_hints':hints,'unit_detection_is_advisory':True}

def _period_hint(headers: list[str], rows: list[dict[str,Any]]) -> dict[str,Any]:
    candidates=[h for h in headers if re.search(r'period|time|year|month|quarter|date|год|период',h,re.I)]
    if not candidates: return {'period_column':None,'frequency':None,'gaps':[],'status':'NOT_DETECTED'}
    col=candidates[0]; vals=sorted({str(r[col]).strip() for r in rows if r.get(col) not in (None,'')})
    years=[]
    for v in vals:
        m=re.search(r'(19|20)\d{2}',v)
        if m: years.append(int(m.group()))
    gaps=[]
    if len(years)>=2 and len(years)==len(vals):
        present=set(years); gaps=[y for y in range(min(years),max(years)+1) if y not in present]
        freq='annual_candidate'
    else: freq='unclassified_requires_review'
    return {'period_column':col,'frequency':freq,'observed_period_count':len(vals),'gaps':gaps,'status':'GAPS_FOUND' if gaps else 'NO_GAP_DETECTED_OR_NOT_INFERABLE'}

def read_table(path: str|Path) -> tuple[list[dict[str,Any]], list[str], dict[str,Any]]:
    p=Path(path); ext=p.suffix.lower(); meta={}
    if ext in {'.csv','.tsv'}: rows,headers=_csv_rows(p)
    elif ext=='.xlsx': rows,headers,sheet=_xlsx_rows(p); meta['sheet']=sheet
    elif ext=='.json': rows,headers,meta=_jsonstat_rows(p)
    else: raise IntakeError(f'Неподдерживаемый формат: {ext}')
    return rows,headers,meta

def _write_normalized(rows, headers, out: Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

def ingest_one(source: Path, out_dir: Path) -> dict[str,Any]:
    raw_hash=sha256(source); rows,headers,meta=read_table(source)
    from economia_quality import audit_table, audit_dataset_manifest
    audit=audit_table(rows,headers)
    passport_candidates=[source.with_suffix(source.suffix+'.manifest.json'), source.parent/'dataset_manifest.json']
    passport_path=next((x for x in passport_candidates if x.exists()),None)
    passport=None; passport_audit={'status':'NOT_PROVIDED','errors':['Паспорт набора не найден']}
    if passport_path:
        passport=json.loads(passport_path.read_text(encoding='utf-8-sig'))
        passport_audit=audit_dataset_manifest(passport)
    unit=_unit_hints(headers,rows,meta); period=audit.get('periods') or _period_hint(headers,rows)
    stem=re.sub(r'[^A-Za-z0-9_.-]+','_',source.stem)[:100]
    normalized=out_dir/'processed'/f'{stem}.normalized.csv'
    _write_normalized(rows,headers,normalized)
    record={'source_file':source.name,'source_path':str(source),'source_sha256':raw_hash,
      'format':source.suffix.lower().lstrip('.'),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
      'rows':len(rows),'columns':headers,'metadata':meta,'units':unit,'periods':period,
      'quality':audit,'normalized_file':str(normalized.relative_to(out_dir)),
      'normalized_sha256':sha256(normalized),'source_preserved':True,
      'dataset_passport':passport,'passport_audit':passport_audit,
      'semantic_validation':'REQUIRES_VALID_PASSPORT_AND_DOMAIN_REVIEW'}
    return record

def _safe_zip_members(zf: zipfile.ZipFile):
    total=0; selected=[]
    for info in zf.infolist():
        if info.is_dir(): continue
        name=info.filename.replace('\\','/')
        pp=PurePosixPath(name)
        if pp.is_absolute() or '..' in pp.parts or re.match(r'^[A-Za-z]:',name):
            raise IntakeError(f'Опасный путь в ZIP: {info.filename}')
        if info.file_size>MAX_MEMBER: raise IntakeError(f'Слишком большой элемент ZIP: {name}')
        total+=info.file_size
        if total>MAX_TOTAL: raise IntakeError('Превышен общий лимит распаковки ZIP')
        base=Path(name).name.lower()
        if base in {'dataset_manifest.json'} or base.endswith('.manifest.json'): continue
        if Path(name).suffix.lower() in SUPPORTED: selected.append(info)
    return selected

def ingest_path(source: str|Path, out_dir: str|Path) -> dict[str,Any]:
    source=Path(source); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    if source.is_dir():
        files=sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED and p.name.lower()!='dataset_manifest.json' and not p.name.lower().endswith('.manifest.json'))
        records=[]; errors=[]
        for item in files:
            try: records.append(ingest_one(item,out))
            except Exception as e: errors.append({'file':str(item.relative_to(source)),'error':str(e)})
        manifest={'source_directory':str(source),'created_at_utc':datetime.now(timezone.utc).isoformat(),
          'ingested_files':len(records),'failed_files':len(errors),'records':records,'errors':errors,
          'overall_status':'FAIL' if errors else ('PASS_WITH_WARNINGS' if any(r['quality']['status']!='PASS' for r in records) else 'PASS'),
          'warning':'Структурная проверка не подтверждает корректность экономической семантики или лицензии.'}
        (out/'intake_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        return manifest
    records=[]; errors=[]
    if source.suffix.lower()=='.zip':
        raw_dir=out/'raw'/source.stem; raw_dir.mkdir(parents=True,exist_ok=True)
        try:
            with zipfile.ZipFile(source) as zf:
                members=_safe_zip_members(zf)
                for info in members:
                    target=raw_dir/Path(info.filename.replace('\\','/'))
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with zf.open(info) as src, target.open('wb') as dst:
                        import shutil; shutil.copyfileobj(src,dst)
                    try: records.append(ingest_one(target,out))
                    except Exception as e: errors.append({'file':info.filename,'error':str(e)})
        except (zipfile.BadZipFile, IntakeError) as e: errors.append({'file':source.name,'error':str(e)})
    else:
        try: records.append(ingest_one(source,out))
        except Exception as e: errors.append({'file':source.name,'error':str(e)})
    manifest={'source_archive':source.name,'source_archive_sha256':sha256(source),
      'created_at_utc':datetime.now(timezone.utc).isoformat(),'ingested_files':len(records),
      'failed_files':len(errors),'records':records,'errors':errors,
      'overall_status':'FAIL' if errors else ('PASS_WITH_WARNINGS' if any(r['quality']['status']!='PASS' for r in records) else 'PASS'),
      'warning':'Структурная проверка не доказывает корректность экономической семантики или лицензии.'}
    (out/'intake_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    return manifest

def main():
    ap=argparse.ArgumentParser(description='Единый безопасный импорт данных ECONOMIA')
    ap.add_argument('source',help='Файл, ZIP или папка с исходными таблицами'); ap.add_argument('--out',default='data/intake')
    ap.add_argument('--db',default='',help='SQLite-файл: сохранить результат импорта в базу')
    a=ap.parse_args(); m=ingest_path(a.source,a.out)
    if a.db:
        from economia_repository import connect,persist_intake
        conn=connect(a.db); m['db']=persist_intake(conn,m,a.out); conn.close()
    print(json.dumps(m,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__': main()
