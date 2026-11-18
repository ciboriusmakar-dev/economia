"""Командная строка единого интерфейса ECONOMIA."""
import argparse,json
from pathlib import Path
from economia_modules import run_model,model_catalog
from economia_report import write_report

def main():
 p=argparse.ArgumentParser(description='Единый запуск моделей ECONOMIA M01–M14')
 sub=p.add_subparsers(dest='cmd',required=True)
 sub.add_parser('catalog')
 r=sub.add_parser('run');r.add_argument('model');r.add_argument('input_json');r.add_argument('--params',default='{}');r.add_argument('--mode',choices=['real','simulation'],default='real');r.add_argument('--output',default='economia_result.json');r.add_argument('--report',default='economia_report.md');r.add_argument('--db',default='')
 a=p.parse_args()
 if a.cmd=='catalog': print(json.dumps(model_catalog(),ensure_ascii=False,indent=2));return
 dataset=json.loads(Path(a.input_json).read_text(encoding='utf-8'));params=json.loads(a.params)
 result=run_model(a.model,dataset,params,a.mode)
 Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 write_report(result,a.report)
 if a.db:
  from economia_repository import connect,register_modules,record_run
  conn=connect(a.db);register_modules(conn,model_catalog());run_id=record_run(conn,result);conn.close();result['run_id']=run_id
  Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
 if result['status'] in {'FAILED','REJECTED_INPUT','FAILED_VALIDATION'}: raise SystemExit(2)
if __name__=='__main__':main()
