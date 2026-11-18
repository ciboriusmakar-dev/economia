"""Eurostat Statistics/Comext API adapter for ECONOMIA.

Supports standard Eurostat datasets and DS-prefixed PRODCOM/Comext datasets.
Raw provider responses are preserved byte-for-byte with request metadata.
No silent dimension, unit, or flag interpretation is performed here.
"""
from __future__ import annotations
import hashlib, json, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_STATISTICS = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
BASE_COMEXT = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/"

class EurostatAPIError(RuntimeError):
    pass

def comext_trade_url(product_code: str, *, reporter: str = "DE", partner: str = "WORLD",
                     flow: str = "1", indicator: str = "QUANTITY_IN_100KG",
                     start_year: int = 2008, end_year: int = 2025, frequency: str = "A") -> str:
    """Build a bounded Comext DS-045409 request for one CN/HS product.

    Eurostat prohibits unfiltered full Comext downloads; product, reporter,
    partner, flow and indicator are deliberately explicit to bound the query.
    """
    product=str(product_code).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,8}", product):
        raise ValueError("Код CN/HS должен содержать от 2 до 8 буквенно-цифровых символов")
    if not re.fullmatch(r"[A-Z0-9_]{2,20}", str(reporter).upper()):
        raise ValueError("Некорректный код страны-отчётчика")
    if not re.fullmatch(r"[A-Z0-9_]{2,30}", str(partner).upper()):
        raise ValueError("Некорректный код партнёра")
    if flow not in {"1", "2"}: raise ValueError("flow должен быть 1 (импорт) или 2 (экспорт)")
    if indicator not in {"QUANTITY_IN_100KG", "SUPPLEMENTARY_QUANTITY", "VALUE_IN_EUROS"}:
        raise ValueError("Недопустимый показатель Comext")
    if frequency not in {"A", "M"}: raise ValueError("frequency должен быть A или M")
    if not (1900 <= int(start_year) <= int(end_year) <= 2100): raise ValueError("Некорректный временной диапазон")
    filters={"freq":frequency,"reporter":str(reporter).upper(),"partner":str(partner).upper(),
             "product":product,"flow":flow,"indicators":indicator,
             "sinceTimePeriod":str(start_year),"untilTimePeriod":str(end_year)}
    return dataset_url("ds-045409",filters)

def dataset_url(dataset_code: str, filters: dict[str, str] | None = None,
                fmt: str = "JSON") -> str:
    code = dataset_code.strip()
    if not re.fullmatch(r"(?:[A-Za-z0-9_]+|ds-[0-9]{6})", code):
        raise ValueError("Некорректный код набора Eurostat")
    base = BASE_COMEXT if code.lower().startswith("ds-") else BASE_STATISTICS
    params = {"lang": "en", "format": fmt, **(filters or {})}
    return base + urllib.parse.quote(code) + "?" + urllib.parse.urlencode(params)

def fetch_dataset(dataset_code: str, filters: dict[str, str], out_dir: str | Path,
                  timeout: int = 60) -> dict:
    url = dataset_url(dataset_code, filters)
    req = urllib.request.Request(url, headers={"User-Agent": "ECONOMIA-research/1.9.5 (dataset audit)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except Exception as exc:
        raise EurostatAPIError(f"Не удалось получить {dataset_code}: {exc}") from exc
    if status != 200:
        raise EurostatAPIError(f"Eurostat вернул HTTP {status}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise EurostatAPIError("Ответ не является корректным JSON-stat") from exc
    if not isinstance(payload, dict) or "id" not in payload or "size" not in payload:
        raise EurostatAPIError("Ответ не похож на JSON-stat набор Eurostat")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data_path = out / f"{dataset_code}_{stamp}.json"
    meta_path = out / f"{dataset_code}_{stamp}.metadata.json"
    data_path.write_bytes(raw)
    metadata = {
      "provider": "Eurostat", "dataset_code": dataset_code, "request_url": url,
      "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
      "http_status": status, "sha256": digest, "bytes": len(raw),
      "dimension_ids": payload.get("id"), "dimension_sizes": payload.get("size"),
      "source_updated_at": None,
      "completeness_scope": "filtered_request; inspect dimension sizes and filters",
      "warning": "Проверьте метаданные, единицы, флаги, классификации и лицензию до расчёта."
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"data_path": str(data_path), "metadata_path": str(meta_path), **metadata}
