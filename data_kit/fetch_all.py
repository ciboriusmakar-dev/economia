#!/usr/bin/env python3
"""ECONOMIA 1.8.1 — загрузчик исходных данных (Германия, DE).

Только стандартная библиотека Python 3.8+. Запуск:  python fetch_all.py
Файлы сохраняются БЕЗ изменений в папку raw/, а в provenance.csv пишутся:
название, источник, URL, дата получения (UTC), размер, SHA-256, HTTP-статус, лицензия.
Пропуски не заполняются, ничего не объединяется и не пересчитывается.
"""
import csv, hashlib, json, os, shutil, ssl, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)

ES = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/{}?format=TSV&compressed=true"
WB = ("https://api.worldbank.org/v2/country/DEU/indicator/{}"
      "?format=json&per_page=20000&date=2000:2025")

# (модули, источник, id, url, имя файла, лицензия)
ITEMS = []
for mods, ds in [
    # ds-059358 / ds-059367 (PRODCOM) и ds-045409 (Comext) здесь НЕ качаются: это DS-наборы,
    # которые отдаются через Comext API только с фильтрами (см. eurostat_api.py в ECONOMIA 1.8.2).
    ("M02;M03", "sts_trtu_m"), ("M02", "sts_inpp_m"), ("M02;M09", "une_rt_m"),
    ("M03;M11;M14", "prc_hicp_minr"), ("M07;M09;M12", "nama_10_gdp"),
    ("M09;M12", "namq_10_gdp"), ("M10;M14", "nrg_bal_c"),
    ("M13", "road_go_ta_dctg"),
    # дополнительные (нужны для M09/M14 по тексту ТЗ: пром. производство, инфляция, ставки, курсы)
    ("M09;M14", "sts_inpr_m"), ("M09;M14", "prc_hicp_midx"),
    ("M02;M14", "irt_st_m"), ("M14", "ert_bil_eur_m"),
]:
    ITEMS.append((mods, "Eurostat", ds, ES.format(ds), ds + ".tsv.gz",
                  "CC BY 4.0 (Eurostat reuse policy)"))

for ind in ["NY.GDP.MKTP.KD", "NY.GDP.MKTP.CD", "FP.CPI.TOTL.ZG", "NE.GDI.TOTL.KD",
            "NE.EXP.GNFS.KD", "NE.IMP.GNFS.KD", "SL.UEM.TOTL.ZS", "FR.INR.RINR",
            "PA.NUS.FCRF", "NE.CON.GOVT.KD", "NV.IND.TOTL.KD", "EG.USE.PCAP.KG.OE"]:
    ITEMS.append(("M07;M09;M14", "World Bank WDI", ind, WB.format(ind),
                  "wdi_DEU_" + ind + ".json", "CC BY 4.0 (World Bank)"))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    rows = []
    for mods, src, ident, url, fname, lic in ITEMS:
        path = os.path.join(RAW, fname)
        status, size, digest, note = "", 0, "", ""
        try:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ECONOMIA-fetch/1.0"})
                with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as out:
                    status = r.status
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
            except (ssl.SSLError, urllib.error.URLError) as e:
                if "CERTIFICATE_VERIFY_FAILED" not in str(e):
                    raise
                # Сертификаты Python не распознали цепочку: качаем системным curl (Windows 10+),
                # проверка сертификата при этом НЕ отключается.
                curl = shutil.which("curl.exe") or shutil.which("curl")
                if not curl:
                    raise
                res = subprocess.run([curl, "-L", "-sS", "--fail", "--max-time", "600", "-o", path, url],
                                     capture_output=True, text=True)
                if res.returncode != 0:
                    raise RuntimeError("curl: " + (res.stderr or "").strip()[:150])
                status, note = 200, "downloaded via system curl"
            size, digest = os.path.getsize(path), sha256(path)
            print("OK  ", fname, size, "(curl)" if note else "")
        except Exception as e:  # noqa
            status, note = "ERROR", str(e)[:200]
            if os.path.exists(path) and os.path.getsize(path) == 0:
                os.remove(path)
            print("FAIL", fname, note)
        rows.append([fname, mods, src, ident, url,
                     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "DE; 2008-2025 (WDI/nama/namq/HICP: 2000-2025)", size, digest, status, lic, note])
        time.sleep(1)
    with open(os.path.join(HERE, "provenance.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "modules", "source", "dataset_id", "url", "retrieved_utc",
                    "country_period_note", "bytes", "sha256", "http_status", "license", "error"])
        w.writerows(rows)
    print("\nГотово. Затем скачайте файлы из MANUAL_DOWNLOADS.md, положите в raw/ "
          "и запустите:  python make_zip.py")


if __name__ == "__main__":
    main()
