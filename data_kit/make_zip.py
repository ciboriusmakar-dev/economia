#!/usr/bin/env python3
"""Упаковывает raw/ и provenance.csv в один zip (без изменения файлов)."""
import os, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(HERE, "ECONOMIA_data_delivery.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for name in ("provenance.csv", "README.md", "MODULE_MAP.csv"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            z.write(p, name)
    raw = os.path.join(HERE, "raw")
    for root, _, files in os.walk(raw):
        for f in files:
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, HERE))
print("Создан", out)
