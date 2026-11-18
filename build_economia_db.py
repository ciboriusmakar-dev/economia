from pathlib import Path
from economia_ontology import initialize_database, validate_database
from economia_repository import MIGRATION, register_modules
from economia_modules import model_catalog

path=Path(__file__).with_name('economia_ontology.sqlite')
conn=initialize_database(path)
conn.executescript(MIGRATION)
register_modules(conn,model_catalog())
errors=validate_database(conn)
required={'economia_dataset_manifest','economia_module_registry','economia_module_dependency','economia_run','economia_quality_event'}
present={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
missing=required-present
if missing: errors.append('Отсутствуют таблицы платформенного контура: '+', '.join(sorted(missing)))
if conn.execute('SELECT COUNT(*) FROM economia_module_registry').fetchone()[0]!=14: errors.append('В реестре должно быть 14 моделей')
conn.close()
if errors: raise SystemExit('\n'.join(errors))
print(f'База создана и проверена: {path.name}; зарегистрировано 14 моделей')
