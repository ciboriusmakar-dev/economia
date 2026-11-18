"""End-to-end Eurostat JSON-stat download and audited long-table export."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from eurostat_api import fetch_dataset
from jsonstat_ingest import ingest_file


def run_pipeline(dataset_code: str, filters: dict[str, str], out_dir: str | Path) -> dict:
    out = Path(out_dir)
    raw_dir = out / "raw"
    table_dir = out / "tables"
    report_dir = out / "reports"
    downloaded = fetch_dataset(dataset_code, filters, raw_dir)
    table_path = table_dir / f"{dataset_code}.csv"
    report_path = report_dir / f"{dataset_code}.quality.json"
    report = ingest_file(downloaded["data_path"], table_path, report_path)
    return {
        "dataset_code": dataset_code,
        "download": downloaded,
        "table_path": str(table_path),
        "quality_report_path": str(report_path),
        "quality_report": report,
        "pipeline_status": "DOWNLOADED_AND_STRUCTURALLY_PARSED_REQUIRES_SEMANTIC_REVIEW"
    }


def main():
    p = argparse.ArgumentParser(description="Загрузка и структурная проверка набора Eurostat")
    p.add_argument("dataset_code")
    p.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE",
                   help="Фильтр API; можно повторять, например --filter geo=DE --filter time=2024")
    p.add_argument("--out", default="data/eurostat")
    a = p.parse_args()
    filters = {}
    for item in a.filter:
        if "=" not in item:
            p.error(f"Некорректный фильтр: {item}")
        key, value = item.split("=", 1)
        if not key or not value or key in filters:
            p.error(f"Пустой или повторяющийся фильтр: {item}")
        filters[key] = value
    print(json.dumps(run_pipeline(a.dataset_code, filters, a.out), ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
