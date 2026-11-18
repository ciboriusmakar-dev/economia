"""SQLite implementation of the ECONOMIA core ontology (prototype v1.1).

This is an executable logical schema, not a production deployment migration.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA = r"""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS ontology_class (
  class_code TEXT PRIMARY KEY, name_ru TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relation_type (
  relation_code TEXT PRIMARY KEY, name_ru TEXT NOT NULL,
  domain_class TEXT NOT NULL REFERENCES ontology_class(class_code),
  range_class TEXT NOT NULL REFERENCES ontology_class(class_code),
  directed INTEGER NOT NULL DEFAULT 1 CHECK(directed IN (0,1))
);
CREATE TABLE IF NOT EXISTS geography (
  geography_id TEXT PRIMARY KEY, name TEXT NOT NULL, geography_type TEXT NOT NULL,
  parent_id TEXT REFERENCES geography(geography_id), valid_from TEXT, valid_to TEXT,
  CHECK(valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE TABLE IF NOT EXISTS industry (
  industry_id TEXT PRIMARY KEY, name TEXT NOT NULL, classification TEXT,
  classification_version TEXT, external_code TEXT
);
CREATE TABLE IF NOT EXISTS unit (
  unit_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, dimension TEXT NOT NULL,
  scale_to_base REAL NOT NULL DEFAULT 1 CHECK(scale_to_base > 0)
);
CREATE TABLE IF NOT EXISTS currency (
  currency_code TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS economic_entity (
  entity_id TEXT PRIMARY KEY, class_code TEXT NOT NULL REFERENCES ontology_class(class_code),
  name TEXT NOT NULL, geography_id TEXT REFERENCES geography(geography_id),
  industry_id TEXT REFERENCES industry(industry_id),
  valid_from TEXT, valid_to TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK(valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE TABLE IF NOT EXISTS product (
  product_id TEXT PRIMARY KEY, name TEXT NOT NULL, product_class TEXT,
  base_unit_id TEXT REFERENCES unit(unit_id), quality_spec_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS indicator (
  indicator_id TEXT PRIMARY KEY, name TEXT NOT NULL, definition TEXT NOT NULL,
  dimension TEXT NOT NULL, allowed_statuses TEXT NOT NULL DEFAULT 'fact,estimate,forecast,scenario,synthetic,derived'
);
CREATE TABLE IF NOT EXISTS source (
  source_id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
  url TEXT, licence_id TEXT, licence_checked_at TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS dataset (
  dataset_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(source_id),
  title TEXT NOT NULL, version TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  published_at TEXT, licence_id TEXT, attribution TEXT NOT NULL,
  data_vintage TEXT, content_hash TEXT
);
CREATE TABLE IF NOT EXISTS economic_relation (
  relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id TEXT NOT NULL REFERENCES economic_entity(entity_id),
  relation_code TEXT NOT NULL REFERENCES relation_type(relation_code),
  object_id TEXT NOT NULL REFERENCES economic_entity(entity_id),
  valid_from TEXT, valid_to TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(subject_id, relation_code, object_id, valid_from),
  CHECK(subject_id <> object_id),
  CHECK(valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE TABLE IF NOT EXISTS observation (
  observation_id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL REFERENCES economic_entity(entity_id),
  product_id TEXT REFERENCES product(product_id),
  indicator_id TEXT NOT NULL REFERENCES indicator(indicator_id),
  value REAL NOT NULL,
  unit_id TEXT NOT NULL REFERENCES unit(unit_id),
  currency_code TEXT REFERENCES currency(currency_code),
  period_start TEXT NOT NULL, period_end TEXT NOT NULL,
  geography_id TEXT REFERENCES geography(geography_id),
  project_id TEXT REFERENCES project(project_id),
  data_mode TEXT NOT NULL CHECK(data_mode IN ('real','simulation')),
  origin_type TEXT NOT NULL CHECK(origin_type IN ('observed','synthetic','scenario','derived','forecast','estimate')),
  price_basis TEXT, status TEXT NOT NULL CHECK(status IN
    ('fact','estimate','forecast','scenario','synthetic','derived')),
  source_id TEXT REFERENCES source(source_id), dataset_id TEXT REFERENCES dataset(dataset_id),
  valid_time TEXT, transaction_time TEXT NOT NULL,
  quality_flags_json TEXT NOT NULL DEFAULT '[]',
  CHECK(period_end >= period_start),
  CHECK((status IN ('synthetic','scenario')) OR source_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_obs_indicator_period ON observation(indicator_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_obs_entity_period ON observation(entity_id, period_start, period_end);
CREATE TABLE IF NOT EXISTS model_registry (
  model_id TEXT NOT NULL, version TEXT NOT NULL, name TEXT NOT NULL,
  method TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','tested','approved','retired')),
  specification_json TEXT NOT NULL, PRIMARY KEY(model_id, version)
);
CREATE TABLE IF NOT EXISTS project (
  project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('real','simulation')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scenario (
  scenario_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(project_id),
  baseline_scenario_id TEXT REFERENCES scenario(scenario_id), name TEXT NOT NULL,
  parameters_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calculation_run (
  run_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(project_id),
  model_id TEXT NOT NULL, model_version TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('real','simulation')),
  data_snapshot_id TEXT, parameters_json TEXT NOT NULL,
  software_version TEXT NOT NULL, random_seed INTEGER,
  validation_status TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT,
  FOREIGN KEY(model_id, model_version) REFERENCES model_registry(model_id, version)
);
CREATE TABLE IF NOT EXISTS calculation_result (
  result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES calculation_run(run_id),
  result_name TEXT NOT NULL, value_json TEXT NOT NULL,
  status TEXT NOT NULL, uncertainty_json TEXT, diagnostics_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS data_transformation (
  transformation_id TEXT PRIMARY KEY, name TEXT NOT NULL, formula_or_method TEXT NOT NULL,
  input_unit_id TEXT REFERENCES unit(unit_id), output_unit_id TEXT REFERENCES unit(unit_id),
  parameters_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observation_lineage (
  child_observation_id TEXT NOT NULL REFERENCES observation(observation_id),
  parent_observation_id TEXT NOT NULL REFERENCES observation(observation_id),
  transformation_id TEXT REFERENCES data_transformation(transformation_id),
  PRIMARY KEY(child_observation_id,parent_observation_id),
  CHECK(child_observation_id <> parent_observation_id)
);
CREATE TABLE IF NOT EXISTS data_snapshot (
  snapshot_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES dataset(dataset_id),
  created_at TEXT NOT NULL, record_count INTEGER NOT NULL CHECK(record_count >= 0),
  content_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS trg_run_project_mode_insert
BEFORE INSERT ON calculation_run
FOR EACH ROW WHEN (SELECT mode FROM project WHERE project_id=NEW.project_id) <> NEW.mode
BEGIN SELECT RAISE(ABORT, 'Режим запуска не совпадает с режимом проекта'); END;
CREATE TRIGGER IF NOT EXISTS trg_run_project_mode_update
BEFORE UPDATE OF project_id, mode ON calculation_run
FOR EACH ROW WHEN (SELECT mode FROM project WHERE project_id=NEW.project_id) <> NEW.mode
BEGIN SELECT RAISE(ABORT, 'Режим запуска не совпадает с режимом проекта'); END;
CREATE TRIGGER IF NOT EXISTS trg_observation_origin_insert
BEFORE INSERT ON observation
FOR EACH ROW WHEN (
  (NEW.origin_type IN ('synthetic','scenario') AND NEW.status NOT IN ('synthetic','scenario'))
  OR (NEW.data_mode='real' AND NEW.origin_type IN ('synthetic','scenario'))
  OR (NEW.project_id IS NOT NULL AND (SELECT mode FROM project WHERE project_id=NEW.project_id) <> NEW.data_mode)
)
BEGIN SELECT RAISE(ABORT, 'Несогласованный режим или происхождение наблюдения'); END;
CREATE TRIGGER IF NOT EXISTS trg_observation_origin_update
BEFORE UPDATE OF origin_type, status, data_mode, project_id ON observation
FOR EACH ROW WHEN (
  (NEW.origin_type IN ('synthetic','scenario') AND NEW.status NOT IN ('synthetic','scenario'))
  OR (NEW.data_mode='real' AND NEW.origin_type IN ('synthetic','scenario'))
  OR (NEW.project_id IS NOT NULL AND (SELECT mode FROM project WHERE project_id=NEW.project_id) <> NEW.data_mode)
)
BEGIN SELECT RAISE(ABORT, 'Несогласованный режим или происхождение наблюдения'); END;
CREATE TRIGGER IF NOT EXISTS trg_relation_domain_insert
BEFORE INSERT ON economic_relation
FOR EACH ROW WHEN
  (SELECT class_code FROM economic_entity WHERE entity_id=NEW.subject_id) <>
  (SELECT domain_class FROM relation_type WHERE relation_code=NEW.relation_code)
  OR
  (SELECT class_code FROM economic_entity WHERE entity_id=NEW.object_id) <>
  (SELECT range_class FROM relation_type WHERE relation_code=NEW.relation_code)
BEGIN SELECT RAISE(ABORT, 'Классы объектов не соответствуют типу связи'); END;
CREATE TRIGGER IF NOT EXISTS trg_relation_domain_update
BEFORE UPDATE OF subject_id, object_id, relation_code ON economic_relation
FOR EACH ROW WHEN
  (SELECT class_code FROM economic_entity WHERE entity_id=NEW.subject_id) <>
  (SELECT domain_class FROM relation_type WHERE relation_code=NEW.relation_code)
  OR
  (SELECT class_code FROM economic_entity WHERE entity_id=NEW.object_id) <>
  (SELECT range_class FROM relation_type WHERE relation_code=NEW.relation_code)
BEGIN SELECT RAISE(ABORT, 'Классы объектов не соответствуют типу связи'); END;
"""

CLASSES = [
 ('ECO-ENT','Экономический участник','Предприятие, домохозяйство, государство или организация'),
 ('ECO-GOOD','Товар или услуга','Объект производства, обмена или потребления'),
 ('ECO-RES','Ресурс','Труд, сырьё, земля, вода или энергия'),
 ('ECO-ACT','Актив','Оборудование, здания и инфраструктура'),
 ('ECO-TECH','Технология','Способ преобразования ресурсов в выпуск'),
 ('ECO-MKT','Рынок','Механизм обмена товарами, услугами или ресурсами'),
 ('ECO-LOC','Территория','Страна, регион или муниципалитет'),
 ('ECO-IND','Отрасль','Группа экономической деятельности'),
 ('ECO-PROC','Процесс','Производство, потребление, инвестиции или торговля'),
 ('ECO-FLOW','Поток','Поставка, платёж, трудовой или энергетический поток'),
 ('ECO-EVENT','Событие','Изменение условий или внешнее событие'),
 ('ECO-RULE','Правило','Налог, тариф, квота или ограничение'),
]
RELATIONS = [
 ('PRODUCES','Производит','ECO-ENT','ECO-GOOD'),
 ('CONSUMES','Потребляет','ECO-ENT','ECO-RES'),
 ('SELLS','Продаёт','ECO-ENT','ECO-GOOD'),
 ('BUYS','Покупает','ECO-ENT','ECO-GOOD'),
 ('SUPPLIES','Поставляет','ECO-ENT','ECO-ENT'),
 ('EMPLOYS','Нанимает','ECO-ENT','ECO-ENT'),
 ('OWNS','Владеет','ECO-ENT','ECO-ACT'),
 ('LOCATED_IN','Находится на территории','ECO-ENT','ECO-LOC'),
 ('BELONGS_TO','Относится к отрасли','ECO-ENT','ECO-IND'),
 ('SUBSTITUTES','Заменяет','ECO-GOOD','ECO-GOOD'),
 ('COMPLEMENTS','Используется совместно','ECO-GOOD','ECO-GOOD'),
 ('REGULATES','Регулирует','ECO-ENT','ECO-RULE'),
 ('INVESTS_IN','Инвестирует в','ECO-ENT','ECO-ACT'),
 ('TRANSPORTS','Перевозит','ECO-ENT','ECO-GOOD'),
]
UNITS = [
 ('one','ед.','count',1),('kg','кг','mass',1),('tonne','т','mass',1000),
 ('m3','м³','volume',1),('kwh','кВт·ч','energy',1),('hour','ч','time',1),
 ('person','чел.','person',1),('eur','EUR','currency',1),('usd','USD','currency',1),
 ('rub','RUB','currency',1),('percent','%','ratio',0.01),
 ('eur_per_kg','EUR/кг','currency_per_mass',1),('usd_per_kg','USD/кг','currency_per_mass',1)
]


def initialize_database(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executescript(SCHEMA)
    conn.executemany('INSERT OR IGNORE INTO ontology_class VALUES (?,?,?)', CLASSES)
    conn.executemany('INSERT OR IGNORE INTO relation_type VALUES (?,?,?,?,1)', RELATIONS)
    conn.executemany('INSERT OR IGNORE INTO unit VALUES (?,?,?,?)', UNITS)
    conn.executemany('INSERT OR IGNORE INTO currency VALUES (?,?)', [
        ('EUR','Евро'),('USD','Доллар США'),('RUB','Российский рубль')])
    conn.commit()
    return conn


def validate_database(conn: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    fk = conn.execute('PRAGMA foreign_key_check').fetchall()
    if fk:
        errors.append(f'Нарушения внешних ключей: {len(fk)}')
    required = {'ontology_class','relation_type','economic_entity','observation',
                'indicator','unit','source','dataset','model_registry','project',
                'scenario','calculation_run','calculation_result','data_snapshot','data_transformation','observation_lineage'}
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = sorted(required - present)
    if missing:
        errors.append('Отсутствуют таблицы: ' + ', '.join(missing))
    for table in required & present:
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if table in {'ontology_class','relation_type','unit'} and count == 0:
            errors.append(f'Справочник {table} пуст')
    return errors
