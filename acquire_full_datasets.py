"""Download full official source files for ECONOMIA stage 2.

No synthetic fallback is permitted. Every downloaded byte is kept under data/raw
with URL, retrieval timestamp, byte count and SHA-256 metadata.
"""
from __future__ import annotations
import argparse, hashlib, json, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from eurostat_api import comext_trade_url

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
EUROSTAT_COMEXT = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/"
OECD = "https://sdmx.oecd.org/public/rest/data/"
SOURCES = {
    "oecd_iot_total": "https://webfs-sti.oecd.org/files/STI-PIE/IOTs/2025/IOTs_TTL.zip",
    "oecd_iot_domestic_imports": "https://webfs-sti.oecd.org/files/STI-PIE/IOTs/2025/IOTs_DOMIMP.zip",
    "oecd_iot_value_added": "https://webfs-sti.oecd.org/files/STI-PIE/IOTs/2025/IOTs_VA.zip",
    "oecd_iot_published_leontief": "https://webfs-sti.oecd.org/files/STI-PIE/IOTs/2025/IOTs_LEONTFT.zip",
    "oecd_stan_2025": OECD + "OECD.STI.PIE,DSD_STAN@DF_STAN_2025,1.0/all?startPeriod=1995&endPeriod=2024&dimensionAtObservation=AllDimensions&format=csvfilewithlabels",
    "eurostat_prodcom_2008_2024": EUROSTAT_COMEXT + "ds-059358?reporter=DE&lang=en&format=JSON",
    "eurostat_prodcom_2025_plus": EUROSTAT_COMEXT + "ds-059367?reporter=DE&lang=en&format=JSON",
    "eurostat_retail_monthly": EUROSTAT + "sts_trtu_m?geo=DE&lang=en&format=JSON",
    "eurostat_hicp_monthly": EUROSTAT + "prc_hicp_minr?geo=DE&lang=en&format=JSON",
    "eurostat_producer_prices_monthly": EUROSTAT + "sts_inpp_m?geo=DE&lang=en&format=JSON",
    "eurostat_unemployment_monthly_candidate_shifter": EUROSTAT + "une_rt_m?geo=DE&lang=en&format=JSON",
}

class DownloadError(RuntimeError): pass

def download(name: str, url: str, timeout: int = 120, retries: int = 3) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    suffix = ".zip" if url.lower().split("?")[0].endswith(".zip") else (".csv" if "format=csv" in url else ".json")
    target = RAW / f"{name}{suffix}"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"ECONOMIA-research/1.9.5", "Accept":"*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                data = resp.read()
            if status != 200 or not data:
                raise DownloadError(f"HTTP {status}; пустой ответ")
            # Detect HTML/JSON error payloads masquerading as data files.
            if data[:256].lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise DownloadError("Вместо файла сервер вернул HTML-страницу")
            if suffix == ".json":
                try: payload=json.loads(data.decode("utf-8"))
                except Exception as exc: raise DownloadError("Ответ JSON не разбирается") from exc
                warning=payload.get("warning") if isinstance(payload,dict) else None
                if isinstance(warning,dict) and warning.get("status")==413:
                    raise DownloadError("Eurostat передал запрос в асинхронную очередь; требуется повторный опрос/получение")
                if isinstance(payload,dict) and "error" in payload and "id" not in payload:
                    raise DownloadError(f"Eurostat API error: {payload['error']}")
            target.write_bytes(data)
            meta = {"name":name,"url":url,"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
                    "http_status":status,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
                    "file":str(target.relative_to(ROOT)),"status":"downloaded"}
            target.with_suffix(target.suffix+".metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
            return meta
        except Exception as exc:
            last = exc
            if attempt + 1 < retries: time.sleep(2 ** attempt)
    raise DownloadError(f"{name}: {last}")

def download_comext_products(products_file: str | Path, *, reporter="DE", partner="WORLD",
                             start_year=2008, end_year=2025, timeout=120) -> list[dict]:
    """Download product-filtered Comext trade quantities and values.

    The product list must be a validated CN/HS concordance output. One request
    per product/flow/indicator keeps each extraction bounded and auditable.
    """
    products=[]
    for line in Path(products_file).read_text(encoding="utf-8-sig").splitlines():
        code=line.strip().upper()
        if not code or code.startswith("#"): continue
        if code not in products: products.append(code)
    if not products: raise DownloadError("Файл кодов Comext пуст")
    results=[]
    for product in products:
        for flow in ("1","2"):
            for indicator in ("QUANTITY_IN_100KG","SUPPLEMENTARY_QUANTITY","VALUE_IN_EUROS"):
                url=comext_trade_url(product,reporter=reporter,partner=partner,flow=flow,
                                     indicator=indicator,start_year=start_year,end_year=end_year)
                name=f"comext_ds045409_{reporter}_{product}_flow{flow}_{indicator.lower()}"
                print(f"Загрузка Comext: {product}, flow={flow}, {indicator}",flush=True)
                try:
                    results.append(download(name,url,timeout=timeout))
                except Exception as exc:
                    # Continue through the product list: some products legitimately
                    # have no supplementary quantity, but every miss must be visible.
                    results.append({"name":name,"url":url,"status":"failed","error":str(exc),
                                    "product_code":product,"flow":flow,"indicator":indicator})
    return results

def main():
    p=argparse.ArgumentParser(description="Загрузка полных официальных наборов ECONOMIA")
    p.add_argument("--only", nargs="*", choices=sorted(SOURCES), help="загрузить только выбранные источники")
    p.add_argument("--timeout",type=int,default=120)
    p.add_argument("--comext-products-file",help="Файл CN/HS кодов после проверки соответствия PRODCOM↔CN")
    p.add_argument("--reporter",default="DE")
    p.add_argument("--partner",default="WORLD",help="WORLD включает внутри- и вне-ЕС торговлю для страны ЕС")
    p.add_argument("--start-year",type=int,default=2008)
    p.add_argument("--end-year",type=int,default=2025)
    a=p.parse_args()
    selected=a.only or list(SOURCES)
    report={"created_at_utc":datetime.now(timezone.utc).isoformat(),"results":[],"failed":[],"deferred":[]}
    for name in selected:
        print(f"Загрузка: {name}",flush=True)
        try: report["results"].append(download(name,SOURCES[name],a.timeout))
        except Exception as e: report["failed"].append({"name":name,"error":str(e)})
    if a.comext_products_file:
        try:
            comext_results=download_comext_products(a.comext_products_file,reporter=a.reporter,
                partner=a.partner,start_year=a.start_year,end_year=a.end_year,timeout=a.timeout)
            for item in comext_results:
                if item.get("status")=="failed": report["failed"].append(item)
                else: report["results"].append(item)
        except Exception as e: report["failed"].append({"name":"eurostat_comext_trade","error":str(e)})
    else:
        report["deferred"].append({"name":"eurostat_comext_trade","reason":"Нужен проверенный список CN/HS кодов и таблица соответствия PRODCOM↔CN; Comext запрещает скачивание полного набора без фильтров."})
    (ROOT/"full_data_download_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report["failed"]: raise SystemExit(2)
if __name__=="__main__": main()
