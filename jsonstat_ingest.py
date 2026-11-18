"""Validated JSON-stat 2.0 ingestion for ECONOMIA.

Preserves source payload separately; exports an explicit long-form table and
quality report. Dimension codes are retained alongside labels: labels are not
used as primary keys and missing cells are never converted to zero.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JSONStatError(ValueError):
    pass


def _ordered_categories(dimension: dict[str, Any]) -> list[tuple[str, str]]:
    category = dimension.get("category") or {}
    index = category.get("index")
    labels = category.get("label") or {}
    if isinstance(index, dict):
        codes = sorted(index, key=lambda code: index[code])
    elif isinstance(index, list):
        codes = index
    elif labels:
        codes = list(labels)
    else:
        raise JSONStatError("У измерения отсутствует category.index/label")
    return [(str(code), str(labels.get(code, code))) for code in codes]


def parse_jsonstat(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), list):
        raise JSONStatError("Ожидается объект JSON-stat с массивом id")
    ids = payload["id"]
    sizes = payload.get("size")
    dims = payload.get("dimension")
    if not isinstance(sizes, list) or len(ids) != len(sizes) or not isinstance(dims, dict):
        raise JSONStatError("Некорректные id/size/dimension")
    if any(not isinstance(n, int) or n < 1 for n in sizes):
        raise JSONStatError("Размеры измерений должны быть положительными целыми числами")
    if any(dim_id not in dims for dim_id in ids):
        raise JSONStatError("Для одного или нескольких измерений нет метаданных")

    categories = [_ordered_categories(dims[dim_id]) for dim_id in ids]
    if any(len(cats) != size for cats, size in zip(categories, sizes)):
        raise JSONStatError("Число категорий не совпадает с размером измерения")
    for dim_id in ids:
        index = (dims[dim_id].get("category") or {}).get("index")
        if isinstance(index, dict) and sorted(index.values()) != list(range(len(index))):
            raise JSONStatError(f"Индексы категорий измерения {dim_id} не образуют последовательность 0..n-1")

    values = payload.get("value")
    if not isinstance(values, (list, dict)):
        raise JSONStatError("Поле value должно быть массивом или разреженным объектом")
    total = math.prod(sizes)
    if isinstance(values, list) and len(values) != total:
        raise JSONStatError(f"Размер массива value ({len(values)}) не совпадает с ожидаемым ({total})")

    statuses = payload.get("status") or {}
    if not isinstance(statuses, (list, dict)):
        raise JSONStatError("Поле status имеет неподдерживаемый формат")
    if isinstance(statuses, list) and len(statuses) != total:
        raise JSONStatError("Размер массива status не совпадает с value")

    def get_item(container: list | dict, offset: int):
        return container[offset] if isinstance(container, list) else container.get(str(offset))

    rows: list[dict[str, Any]] = []
    non_missing = 0
    flagged = 0
    missing = 0
    for offset in range(total):
        value = get_item(values, offset)
        status = get_item(statuses, offset) if statuses else None
        if value is None:
            missing += 1
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise JSONStatError(f"Недопустимое числовое значение в ячейке {offset}")
        # JSON-stat uses row-major ordering: the last dimension varies fastest.
        remainder = offset
        coords = [0] * len(sizes)
        for i in range(len(sizes) - 1, -1, -1):
            coords[i] = remainder % sizes[i]
            remainder //= sizes[i]
        row: dict[str, Any] = {"value": value, "status": status or ""}
        for dim_id, cats, coord in zip(ids, categories, coords):
            code, label = cats[coord]
            row[f"{dim_id}_code"] = code
            row[f"{dim_id}_label"] = label
        rows.append(row)
        non_missing += 1
        if status:
            flagged += 1

    report = {
        "format": "JSON-stat",
        "dataset_label": payload.get("label"),
        "dimension_ids": ids,
        "dimension_sizes": sizes,
        "expected_cells": total,
        "non_missing_cells": non_missing,
        "missing_cells": missing,
        "flagged_non_missing_cells": flagged,
        "unit_metadata": (payload.get("extension") or {}).get("unit"),
        "source_updated_at": payload.get("updated"),
        "status": "PARSED_REQUIRES_SEMANTIC_REVIEW",
        "limitations": [
            "Проверка структуры не подтверждает корректность экономического смысла показателя.",
            "Необходимо проверить единицы, ценовую базу, классификации, флаги и методологию источника.",
            "Отсутствующие значения сохранены как пропуски, а не заменены нулями."
        ]
    }
    return rows, report


def ingest_file(source: str | Path, output_csv: str | Path, report_json: str | Path) -> dict[str, Any]:
    source_path = Path(source)
    raw = source_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    rows, report = parse_jsonstat(payload)
    report.update({
        "source_file": source_path.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fields = list(rows[0])
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    else:
        output_path.write_text("", encoding="utf-8")
    report_path = Path(report_json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт JSON-stat в проверенную таблицу ECONOMIA")
    parser.add_argument("source_json")
    parser.add_argument("output_csv")
    parser.add_argument("report_json")
    args = parser.parse_args()
    print(json.dumps(ingest_file(args.source_json, args.output_csv, args.report_json),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
