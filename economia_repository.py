"""Локальное хранилище паспортов наборов, запусков, результатов и событий контроля."""
from __future__ import annotations
import sqlite3, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

MIGRATION='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS economia_dataset_manifest(
 dataset_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, version TEXT NOT NULL,
 retrieved_at TEXT NOT NULL, licence_id TEXT NOT NULL, attribution TEXT NOT NULL,
 data_mode TEXT NOT NULL CHECK(data_mode IN ('real','simulation')),
 origin TEXT NOT NULL, manifest_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS economia_module_registry(
 model_id TEXT PRIMARY KEY, name_ru TEXT NOT NULL, version TEXT NOT NULL,
 input_contract TEXT NOT NULL, output_contract TEXT NOT NULL, empirical_status TEXT NOT NULL,
 passport_path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS economia_module_dependency(
 model_id TEXT NOT NULL REFERENCES economia_module_registry(model_id),
 dependency_id TEXT NOT NULL, dependency_type TEXT NOT NULL,
 PRIMARY KEY(model_id,dependency_id));
CREATE TABLE IF NOT EXISTS economia_run(
 run_id TEXT PRIMARY KEY, model_id TEXT NOT NULL REFERENCES economia_module_registry(model_id),
 dataset_id TEXT REFERENCES economia_dataset_manifest(dataset_id), mode TEXT NOT NULL,
 status TEXT NOT NULL, input_hash TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
 result_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS economia_intake_file(
 intake_id TEXT PRIMARY KEY, source_file TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 normalized_sha256 TEXT NOT NULL, format TEXT NOT NULL, row_count INTEGER NOT NULL,
 columns_json TEXT NOT NULL, quality_status TEXT NOT NULL, passport_status TEXT NOT NULL,
 retrieved_at TEXT NOT NULL, ingested_at TEXT NOT NULL, record_json TEXT NOT NULL,
 UNIQUE(source_sha256));
CREATE TABLE IF NOT EXISTS economia_intake_row(
 intake_id TEXT NOT NULL REFERENCES economia_intake_file(intake_id) ON DELETE CASCADE,
 row_no INTEGER NOT NULL, row_json TEXT NOT NULL, PRIMARY KEY(intake_id,row_no));
CREATE TABLE IF NOT EXISTS economia_quality_event(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT, severity TEXT NOT NULL,
 code TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
'''

def connect(path):
    c=sqlite3.connect(str(path));c.execute('PRAGMA foreign_keys=ON');c.executescript(MIGRATION);return c

def register_dataset(conn, manifest):
    payload=json.dumps(manifest,ensure_ascii=False,sort_keys=True);h=hashlib.sha256(payload.encode()).hexdigest()
    conn.execute('''INSERT OR REPLACE INTO economia_dataset_manifest VALUES (?,?,?,?,?,?,?,?,?,?)''',(
      manifest['dataset_id'],manifest['source_id'],manifest['version'],manifest['retrieved_at'],manifest['licence_id'],manifest['attribution'],manifest['data_mode'],manifest['origin'],payload,h));conn.commit();return h

def record_run(conn, result, dataset_id=None):
    import uuid
    rid=str(uuid.uuid4())
    conn.execute('''INSERT INTO economia_run VALUES (?,?,?,?,?,?,?,?,?)''',(rid,result['model_id'],dataset_id,result['mode'],result['status'],result['inputs_hash'],result['started_at'],result['completed_at'],json.dumps(result,ensure_ascii=False)))
    conn.commit();return rid

def register_modules(conn, catalog, passport_path='MODEL_PASSPORTS_M01_M14_RU.md'):
    dependencies={
      'M01':['source:Eurostat_PRODCOM','source:Eurostat_Comext'],
      'M02':['source:market_prices','source:demand_shifters','source:supply_shifters'],
      'M03':['source:comparable_price_quantity_series'],
      'M04':['source:OECD_STAN'], 'M05':['source:OECD_IOT_value_added'],
      'M06':['source:OECD_IOT_domestic'], 'M07':['contract:dataset_records'],
      'M08':['design:treatment_control_pre_post'], 'M09':['source:ordered_time_series'],
      'M10':['input:objective_constraints_bounds'], 'M11':['input:market_demand_supply_matrices'],
      'M12':['input:inventory_production_demand_lead_time'], 'M13':['input:directed_capacity_network'],
      'M14':['input:empirical_or_scenario_distribution']}
    for item in catalog:
        mid=item['model_id']
        conn.execute('''INSERT OR REPLACE INTO economia_module_registry VALUES (?,?,?,?,?,?,?)''',(
          mid,item['name'],item['version'],item['interface'],
          'ModelResult v1', 'program_implemented_empirical_status_separate',passport_path))
        conn.execute('DELETE FROM economia_module_dependency WHERE model_id=?',(mid,))
        conn.executemany('INSERT INTO economia_module_dependency VALUES (?,?,?)',[(mid,d,'data_or_design') for d in dependencies.get(mid,[])])
    conn.commit()


def persist_intake(conn, manifest, out_dir=None):
    """Сохраняет результат импорта (economia_ingest.ingest_path) в SQLite.

    Хранятся исходные строки как есть (JSON), хеши, статус качества и события контроля.
    Экономическая семантика (показатель, объект, единица) НЕ присваивается: импорт её не определяет.
    Повторный импорт файла с тем же SHA-256 пропускается, существующие данные не перезаписываются.
    """
    import csv
    now=datetime.now(timezone.utc).isoformat()
    added=skipped=0
    for rec in manifest.get('records',[]):
        sha=rec['source_sha256']
        if conn.execute('SELECT 1 FROM economia_intake_file WHERE source_sha256=?',(sha,)).fetchone():
            skipped+=1;continue
        iid='intake-'+sha[:16]
        pstat=(rec.get('passport_audit') or {}).get('status','NOT_PROVIDED')
        conn.execute('INSERT INTO economia_intake_file VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(
          iid,rec['source_file'],sha,rec['normalized_sha256'],rec['format'],rec['rows'],
          json.dumps(rec['columns'],ensure_ascii=False),rec['quality']['status'],pstat,
          rec['retrieved_at_utc'],now,json.dumps(rec,ensure_ascii=False,default=str)))
        if out_dir is not None:
            norm=Path(out_dir)/rec['normalized_file']
            with norm.open(encoding='utf-8-sig',newline='') as f:
                conn.executemany('INSERT INTO economia_intake_row VALUES (?,?,?)',
                  [(iid,i,json.dumps(r,ensure_ascii=False)) for i,r in enumerate(csv.DictReader(f),1)])
        q=rec['quality']
        for key in ('issues','warnings'):
            for msg in q.get(key,[]) or []:
                conn.execute('INSERT INTO economia_quality_event(dataset_id,severity,code,message,created_at) VALUES (?,?,?,?,?)',
                  (iid,'error' if key=='issues' else 'warning','intake_'+('issue' if key=='issues' else 'warning'),str(msg),now))
        if pstat!='PASS':
            conn.execute('INSERT INTO economia_quality_event(dataset_id,severity,code,message,created_at) VALUES (?,?,?,?,?)',
              (iid,'warning','passport_'+str(pstat).lower(),'Паспорт набора отсутствует или не пройден проверку',now))
        added+=1
    for err in manifest.get('errors',[]):
        conn.execute('INSERT INTO economia_quality_event(dataset_id,severity,code,message,created_at) VALUES (?,?,?,?,?)',
          (None,'error','intake_failed',json.dumps(err,ensure_ascii=False),now))
    conn.commit()
    return {'added':added,'skipped_duplicates':skipped,'failed':len(manifest.get('errors',[]))}
