"""Единый контракт исполнения моделей ECONOMIA.
Не подменяет реальные данные синтетическими; фиксирует происхождение и диагностику."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable
import hashlib, json, math

VALID_MODES = {'real', 'simulation'}
VALID_ORIGINS = {'observed','synthetic','scenario','derived','forecast','estimate'}

@dataclass
class ModelResult:
    model_id: str
    model_version: str
    status: str
    mode: str
    inputs_hash: str
    outputs: dict[str, Any]
    diagnostics: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    started_at: str
    completed_at: str

    def to_dict(self): return asdict(self)

class DataContractError(ValueError): pass

def canonical_hash(obj: Any) -> str:
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def validate_dataset(dataset: dict, mode: str) -> list[str]:
    errors=[]
    if mode not in VALID_MODES: errors.append('mode должен быть real или simulation')
    if not isinstance(dataset,dict): return ['dataset должен быть объектом']
    for field in ('dataset_id','source_id','records','origin','data_mode'):
        if field not in dataset: errors.append(f'Отсутствует обязательное поле {field}')
    if dataset.get('data_mode') != mode: errors.append('data_mode набора не совпадает с режимом запуска')
    if not str(dataset.get('dataset_id') or '').strip(): errors.append('dataset_id не может быть пустым')
    if not str(dataset.get('source_id') or '').strip(): errors.append('source_id не может быть пустым')
    origin=dataset.get('origin')
    if origin not in VALID_ORIGINS: errors.append('Недопустимый origin')
    if mode=='real' and origin in {'synthetic','scenario'}: errors.append('Синтетические/сценарные данные запрещены в режиме real')
    if mode=='simulation' and origin=='observed':
        # Observed facts may seed simulations, but must be explicitly declared as baseline.
        if not dataset.get('baseline_import',False): errors.append('Фактические данные в simulation требуют baseline_import=true')
    if not isinstance(dataset.get('records'),list): errors.append('records должен быть списком')
    elif not dataset['records']: errors.append('records не должен быть пустым')
    return errors

def validate_numeric_records(records, required, *, allow_missing=False):
    errors=[]; warnings=[]
    if not records: return ['Нет наблюдений'], warnings
    for i,row in enumerate(records):
        if not isinstance(row,dict): errors.append(f'Строка {i}: ожидается объект'); continue
        for key in required:
            if key not in row or row[key] is None or row[key]=='':
                (warnings if allow_missing else errors).append(f'Строка {i}: пропуск {key}')
            else:
                try:
                    x=float(row[key])
                    if not math.isfinite(x): raise ValueError()
                except (TypeError,ValueError): errors.append(f'Строка {i}: {key} не является конечным числом')
    return errors,warnings

def execute_model(model_id: str, fn: Callable, dataset: dict, parameters: dict|None=None, *, mode='real', version='1.0') -> ModelResult:
    started=datetime.now(timezone.utc).isoformat(); params=parameters or {}; warnings=[]; errors=[]; outputs={}; diagnostics={}
    errors.extend(validate_dataset(dataset,mode))
    if errors:
        status='REJECTED_INPUT'
    else:
        try:
            raw=fn(dataset['records'],**params)
            if not isinstance(raw,dict): raise TypeError('Модель должна вернуть словарь результатов')
            outputs=raw.pop('outputs',raw)
            diagnostics=raw.pop('diagnostics',{}) if 'diagnostics' in raw else {}
            warnings=list(raw.pop('warnings',[])) if 'warnings' in raw else []
            if isinstance(outputs,dict) and outputs.get('warning'):
                warnings.append(str(outputs['warning']))
            if isinstance(outputs,dict) and outputs.get('incomplete',0):
                warnings.append(f"Неполных групп/наблюдений: {outputs['incomplete']}")
            diagnostics.update({'input_record_count':len(dataset['records']),'dataset_origin':dataset.get('origin'),'dataset_id':dataset.get('dataset_id')})
            failed_validation=isinstance(outputs,dict) and str(outputs.get('status','')).startswith('FAIL')
            status='FAILED_VALIDATION' if failed_validation else ('COMPLETED_WITH_WARNINGS' if warnings else 'COMPLETED')
        except Exception as exc:
            errors=[f'{type(exc).__name__}: {exc}']; status='FAILED'
    return ModelResult(model_id,version,status,mode,canonical_hash(dataset),outputs,diagnostics,warnings,errors,started,datetime.now(timezone.utc).isoformat())
