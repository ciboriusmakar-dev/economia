#!/usr/bin/env python3
"""Скачивает запросы из comext_requests_draft.csv БЕЗ изменений в raw_comext/ и пишет provenance_comext.csv.
Запуск рядом с comext_requests_draft.csv:  python fetch_comext.py
Статус черновика не проверен: при ошибке запись остаётся в provenance_comext.csv с текстом ошибки."""
import csv, hashlib, os, time, urllib.request
from datetime import datetime, timezone
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,"raw_comext"); os.makedirs(OUT,exist_ok=True)
rows=list(csv.DictReader(open(os.path.join(HERE,"comext_requests_draft.csv"),encoding="utf-8-sig"),delimiter=";"))
log=[]
for i,r in enumerate(rows,1):
    name=f"{r['reporter']}_{r['hs_code']}_{r['flow']}_{r['indicator']}.json"; path=os.path.join(OUT,name)
    st,err,size,sha="","",0,""
    try:
        req=urllib.request.Request(r["url"],headers={"User-Agent":"ECONOMIA-fetch-comext/1.0"})
        with urllib.request.urlopen(req,timeout=180) as resp:
            data=resp.read(); st=resp.status
        open(path,"wb").write(data); size=len(data); sha=hashlib.sha256(data).hexdigest(); print("OK  ",i,name,size)
    except Exception as e:
        st,err="ERROR",str(e)[:200]; print("FAIL",i,name,err)
    log.append([name,r["url"],datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),size,sha,st,err]); time.sleep(1)
with open(os.path.join(HERE,"provenance_comext.csv"),"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["file","url","retrieved_utc","bytes","sha256","http_status","error"]); w.writerows(log)
