"""Independent benchmark comparison for ECONOMIA model outputs."""
from __future__ import annotations
import csv, json, math
from pathlib import Path

def compare_to_reference(predictions, references, key_columns, value_column='value',
                         abs_tolerance=None, rel_tolerance=None):
    """Compare predictions to independently published reference values.

    Reference source and unit are mandatory. Duplicate keys, same-source
    comparisons, incompatible declared units/price bases/classifications,
    and missing reference keys cannot pass.
    """
    ref={}; errors=[]
    for r in references:
        key=tuple(str(r.get(k,'')) for k in key_columns)
        if not r.get('reference_source') or not r.get('unit'):
            errors.append({'key':key,'reason':'reference_source_or_unit_missing'}); continue
        if key in ref:
            errors.append({'key':key,'reason':'duplicate_reference_key'}); continue
        try:
            val=float(r[value_column])
            if not math.isfinite(val): raise ValueError()
            ref[key]={'value':val,'meta':r}
        except (TypeError,ValueError,KeyError): errors.append({'key':key,'reason':'reference_value_not_numeric'})
    diffs=[]; missing=[]; matched=[]; seen_predictions=set()
    comparable_fields=('unit','currency','price_basis','classification')
    for p in predictions:
        key=tuple(str(p.get(k,'')) for k in key_columns)
        if key in seen_predictions:
            errors.append({'key':key,'reason':'duplicate_prediction_key'}); continue
        seen_predictions.add(key)
        if key not in ref: missing.append(key); continue
        r=ref[key]; rmeta=r['meta']
        if p.get('source_id') and str(p.get('source_id'))==str(rmeta.get('reference_source')):
            errors.append({'key':key,'reason':'reference_is_not_independent_source'}); continue
        mismatch=[]
        for field in comparable_fields:
            pv=p.get(field); rv=rmeta.get(field)
            if pv not in (None,'') and rv not in (None,'') and str(pv)!=str(rv): mismatch.append(field)
        if mismatch:
            errors.append({'key':key,'reason':'metadata_mismatch','fields':mismatch}); continue
        try: pred=float(p[value_column]); actual=r['value']
        except (TypeError,ValueError,KeyError): errors.append({'key':key,'reason':'prediction_not_numeric'}); continue
        if not math.isfinite(pred): errors.append({'key':key,'reason':'non_finite_value'}); continue
        e=pred-actual; diffs.append((e,actual)); matched.append(key)
    if not diffs:
        return {'status':'FAIL' if errors or (ref and missing) else 'NOT_TESTABLE','matched':0,
          'missing_references':len(missing),'missing_keys':[list(k) for k in missing[:100]],'errors':errors,
          'reason':'Нет сопоставимых наблюдений с независимыми эталонными значениями.'}
    mae=sum(abs(e) for e,_ in diffs)/len(diffs)
    rmse=math.sqrt(sum(e*e for e,_ in diffs)/len(diffs))
    nonzero=[(e,a) for e,a in diffs if a!=0]
    mape=sum(abs(e/a) for e,a in nonzero)/len(nonzero)*100 if nonzero else None
    max_abs=max(abs(e) for e,_ in diffs)
    tolerance_ok=True
    for e,a in diffs:
        tol=max(abs_tolerance or 0, (rel_tolerance or 0)*abs(a))
        if abs(e)>tol: tolerance_ok=False; break
    status='FAIL' if errors or missing or not tolerance_ok else 'PASS'
    return {'status':status,'matched':len(diffs),'missing_references':len(missing),
      'missing_keys':[list(k) for k in missing[:100]],'errors':errors,
      'MAE':mae,'RMSE':rmse,'MAPE_percent':mape,'max_absolute_error':max_abs,
      'tolerance_pass':tolerance_ok,'abs_tolerance':abs_tolerance,'rel_tolerance':rel_tolerance,
      'matched_keys':[list(k) for k in matched[:100]],
      'note':'Метрики описывают согласие с выбранным эталоном; качество самого эталона и сопоставимость определений проверяются отдельно.'}

def load_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def main():
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('predictions'); ap.add_argument('references'); ap.add_argument('--keys',required=True); ap.add_argument('--value',default='value'); ap.add_argument('--abs-tol',type=float); ap.add_argument('--rel-tol',type=float); ap.add_argument('--out',default='independent_validation_result.json'); a=ap.parse_args()
    result=compare_to_reference(load_csv(a.predictions),load_csv(a.references),a.keys.split(','),a.value,a.abs_tol,a.rel_tol)
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
