"""Проверка качества таблиц до передачи экономическим моделям."""
from __future__ import annotations
import csv, math, hashlib, json
from pathlib import Path
from collections import Counter

def audit_csv(path, key_columns=None, required_columns=None, numeric_columns=None, allow_flags=True):
    p=Path(path); raw=p.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    with p.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); headers=reader.fieldnames or []; rows=list(reader)
    issues=[]; warnings=[]
    if not headers: issues.append('Нет заголовков столбцов')
    if len(headers)!=len(set(headers)): issues.append('Повторяются названия столбцов')
    for col in required_columns or []:
        if col not in headers: issues.append(f'Нет обязательного столбца {col}')
    for i,r in enumerate(rows, start=2):
        for col in required_columns or []:
            if col in headers and (r.get(col) is None or not r[col].strip()): warnings.append(f'Строка {i}: пропуск {col}')
        for col in numeric_columns or []:
            if col not in headers: continue
            v=(r.get(col) or '').strip()
            if not v or v in {':','..','-'}:
                warnings.append(f'Строка {i}: пропуск числового {col}'); continue
            try:
                if not math.isfinite(float(v)): raise ValueError()
            except ValueError: issues.append(f'Строка {i}: {col} не конечное число: {v!r}')
    duplicate_count=0
    if key_columns:
        missing=[c for c in key_columns if c not in headers]
        if missing: issues.append('Нет столбцов ключа: '+', '.join(missing))
        else:
            counts=Counter(tuple(r.get(c,'') for c in key_columns) for r in rows)
            duplicate_count=sum(n-1 for n in counts.values() if n>1)
            if duplicate_count: issues.append(f'Дубли ключей: {duplicate_count}')
    return {'file':p.name,'sha256':digest,'rows':len(rows),'columns':headers,'duplicate_keys':duplicate_count,'issues':issues,'warnings':warnings,'quality_status':'FAIL' if issues else ('PASS_WITH_WARNINGS' if warnings else 'PASS')}

def audit_dataset_manifest(manifest):
    errors=[]
    for k in ('dataset_id','source_id','version','retrieved_at','licence_id','attribution','files'):
        if not manifest.get(k): errors.append(f'Не заполнено поле паспорта набора данных: {k}')
    if manifest.get('data_mode') not in {'real','simulation'}: errors.append('data_mode должен быть real или simulation')
    if manifest.get('data_mode')=='real' and manifest.get('origin') in {'synthetic','scenario'}: errors.append('Запрещено маркировать синтетические данные как реальные')
    return {'status':'PASS' if not errors else 'FAIL','errors':errors}

# Extended common quality layer used by economia_ingest and empirical runs.
PERIOD_RE = __import__('re').compile(r'^(?:19|20)\d{2}(?:-Q[1-4]|-\d{2})?$')
MISSING_MARKERS = {'', ':', '..', '-', 'NA', 'N/A', 'NULL', 'NONE'}

def _norm(v):
    if v is None: return ''
    return str(v).strip()

def audit_table(rows, headers, key_columns=None, required_columns=None,
                numeric_columns=None, expected_periods=None, metadata=None):
    """Audit tabular structure, duplicates, missingness, periods and metadata.

    Unknown units/classifications are warnings, never guessed. Domain-specific
    validity must be configured by each dataset passport/module contract.
    """
    import re
    from collections import Counter
    metadata=metadata or {}; issues=[]; warnings=[]
    if not headers: issues.append('Нет заголовков столбцов')
    if len(headers)!=len(set(headers)): issues.append('Повторяются названия столбцов')
    for c in required_columns or []:
        if c not in headers: issues.append(f'Нет обязательного столбца {c}')
    missing_by_column={}
    for c in headers:
        n=sum(1 for r in rows if _norm(r.get(c)).upper() in MISSING_MARKERS)
        if n: missing_by_column[c]=n
    for c,n in missing_by_column.items(): warnings.append(f'Пропуски в {c}: {n}/{len(rows)}')
    numeric_cols=list(numeric_columns or [])
    if not numeric_cols:
        for c in headers:
            vals=[_norm(r.get(c)) for r in rows if _norm(r.get(c)).upper() not in MISSING_MARKERS]
            if vals and sum(bool(re.fullmatch(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',v.replace(',','.'))) for v in vals)/len(vals)>=0.9:
                numeric_cols.append(c)
    for i,r in enumerate(rows,start=2):
        for c in numeric_cols:
            if c not in headers: continue
            v=_norm(r.get(c))
            if v.upper() in MISSING_MARKERS: continue
            try:
                x=float(v.replace(',','.'))
                if not math.isfinite(x): raise ValueError()
            except ValueError: issues.append(f'Строка {i}: {c} не является конечным числом: {v!r}')
    exact=Counter(tuple(_norm(r.get(c)) for c in headers) for r in rows)
    exact_dups=sum(n-1 for n in exact.values() if n>1)
    if exact_dups: warnings.append(f'Полные дубли строк: {exact_dups}')
    if key_columns:
        absent=[c for c in key_columns if c not in headers]
        if absent: issues.append('Нет столбцов ключа: '+', '.join(absent))
        else:
            keys=Counter(tuple(_norm(r.get(c)) for c in key_columns) for r in rows)
            dups=sum(n-1 for n in keys.values() if n>1)
            if dups: issues.append(f'Дубли ключей: {dups}')
    # Period gap scan: only run where an identifiable period column exists.
    pcols=[c for c in headers if re.search(r'period|time|year|год|период',c,re.I)]
    period_report={'column':None,'frequency':'unknown','gaps':[]}
    if pcols:
        pc=pcols[0]; vals=sorted({_norm(r.get(pc)) for r in rows if _norm(r.get(pc))})
        annual=[]; monthly=[]; quarterly=[]
        for v in vals:
            if re.fullmatch(r'(?:19|20)\d{2}',v): annual.append(int(v))
            elif re.fullmatch(r'(?:19|20)\d{2}-\d{2}',v):
                y,m=map(int,v.split('-'))
                if 1<=m<=12: monthly.append(y*12+m-1)
            elif re.fullmatch(r'(?:19|20)\d{2}-Q[1-4]',v):
                y,q=v.split('-Q'); quarterly.append(int(y)*4+int(q)-1)
        seq=annual if len(annual)==len(vals) else monthly if len(monthly)==len(vals) else quarterly if len(quarterly)==len(vals) else []
        freq='annual' if seq is annual and seq else 'monthly' if seq is monthly and seq else 'quarterly' if seq is quarterly and seq else 'unknown'
        period_report={'column':pc,'observed_periods':len(vals),'frequency':freq,'gaps':[]}
        if len(seq)>1:
            missing=sorted(set(range(min(seq),max(seq)+1))-set(seq))
            if freq=='annual': period_report['gaps']=[str(x) for x in missing]
            elif freq=='monthly': period_report['gaps']=[f'{x//12:04d}-{x%12+1:02d}' for x in missing]
            elif freq=='quarterly': period_report['gaps']=[f'{x//4:04d}-Q{x%4+1}' for x in missing]
            if period_report['gaps']: warnings.append(f'Пропущенные периоды ({freq}): '+', '.join(period_report['gaps']))
    units=metadata.get('units') or metadata.get('unit') or metadata.get('unit_measure')
    classification=metadata.get('classification') or metadata.get('classification_version')
    if not units: warnings.append('Единицы измерения не подтверждены метаданными; автоматическое определение только подсказочное')
    if not classification: warnings.append('Классификация и её версия не подтверждены метаданными')
    return {'rows':len(rows),'columns':list(headers),'numeric_columns_detected':numeric_cols,
      'missing_by_column':missing_by_column,'exact_duplicate_rows':exact_dups,
      'periods':period_report,'units_metadata':units,'classification_metadata':classification,
      'issues':issues,'warnings':warnings,
      'status':'FAIL' if issues else ('PASS_WITH_WARNINGS' if warnings else 'PASS')}

def compare_sources(datasets, key_columns, value_column, tolerance_abs=0.0, tolerance_rel=1e-9):
    """Find same-key observations with conflicting values across sources.

    datasets: list of {'source_id': str, 'rows': list[dict]}. Only comparable
    observations with identical explicit units/currency/price basis should be
    passed here; metadata mismatches are reported as non-comparable.
    """
    index={}; conflicts=[]; skipped=[]
    for ds in datasets:
        sid=ds.get('source_id','unknown'); meta=ds.get('metadata') or {}
        for row in ds.get('rows',[]):
            key=tuple(_norm(row.get(c)) for c in key_columns)
            raw=row.get(value_column)
            try: val=float(str(raw).replace(',','.'))
            except (TypeError,ValueError): skipped.append({'source_id':sid,'key':key,'reason':'missing_or_non_numeric'}); continue
            signature=(meta.get('unit'),meta.get('currency'),meta.get('price_basis'),meta.get('classification'))
            index.setdefault(key,[]).append((sid,val,signature))
    for key, vals in index.items():
        if len(vals)<2: continue
        signatures={v[2] for v in vals}
        if len(signatures)>1:
            conflicts.append({'key':key,'type':'METADATA_MISMATCH','observations':[{'source_id':v[0],'value':v[1],'metadata':v[2]} for v in vals]}); continue
        lo=min(v[1] for v in vals); hi=max(v[1] for v in vals)
        tol=max(tolerance_abs,tolerance_rel*max(abs(lo),abs(hi),1.0))
        if hi-lo>tol:
            conflicts.append({'key':key,'type':'VALUE_CONFLICT','difference':hi-lo,'tolerance':tol,'observations':[{'source_id':v[0],'value':v[1]} for v in vals]})
    return {'compared_keys':len(index),'conflict_count':len(conflicts),'conflicts':conflicts,'skipped':skipped,
      'status':'FAIL' if conflicts else 'PASS_WITH_WARNINGS' if skipped else 'PASS',
      'limitation':'Сравнение допустимо только после приведения к одинаковым определениям, единицам, валюте, ценовой базе и классификации.'}
