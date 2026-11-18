"""M01 apparent-consumption calculation from full PRODCOM/Comext-derived records.

Canonical CSV: country,year,product_code,indicator,value,unit,flag.
Required indicators: PRODQNT, IMPQNT, EXPQNT. This is apparent consumption,
not a complete physical balance: inventories, losses and intermediate uses are
not observed in these three indicators.
"""
from __future__ import annotations
import csv,json,math
from pathlib import Path

def calculate(path):
    with open(path,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    groups={}
    for r in rows:
        key=(r['country'],r['year'],r['product_code'],r['unit'])
        g=groups.setdefault(key,{})
        ind=r['indicator'].upper()
        if ind not in {'PRODQNT','IMPQNT','EXPQNT'}: continue
        if ind in g: raise ValueError(f'Дублируется {ind} для {key}')
        flag=(r.get('flag') or '').strip().upper()
        raw_value=(r.get('value') or '').strip()
        if flag in {'C','U',':','-'} or raw_value in {'',':','..','-'}:
            g[ind]={'value':None,'flag':flag}
        else:
            value=float(raw_value)
            if not math.isfinite(value) or value<0: raise ValueError(f'Недопустимое физическое значение {r["value"]!r} для {key}/{ind}')
            g[ind]={'value':value,'flag':flag}
    out=[]
    for key,g in sorted(groups.items()):
        missing=[i for i in ('PRODQNT','IMPQNT','EXPQNT') if i not in g or g[i]['value'] is None]
        if missing:
            out.append({'country':key[0],'year':int(key[1]),'product_code':key[2],'unit':key[3],
                        'status':'INCOMPLETE_OR_SUPPRESSED','missing_indicators':missing,'apparent_consumption':None})
            continue
        p,im,ex=(g[i]['value'] for i in ('PRODQNT','IMPQNT','EXPQNT'))
        out.append({'country':key[0],'year':int(key[1]),'product_code':key[2],'unit':key[3],
                    'sold_production':p,'imports':im,'exports':ex,'apparent_consumption':p+im-ex,
                    'source_flags':{i:g[i]['flag'] for i in ('PRODQNT','IMPQNT','EXPQNT')},
                    'status':'APPARENT_CONSUMPTION_ONLY'})
    return {'model':'M01','n_product_years':len(out),'complete':sum(r['status']=='APPARENT_CONSUMPTION_ONLY' for r in out),
            'incomplete':sum(r['status']!='APPARENT_CONSUMPTION_ONLY' for r in out),'rows':out,
            'warning':'Проданная продукция + импорт - экспорт — кажущееся потребление. Не является полным балансом запасов, потерь и промежуточного использования.'}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('csv');p.add_argument('--output',default='m01_apparent_consumption.json');a=p.parse_args()
    r=calculate(a.csv);Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
