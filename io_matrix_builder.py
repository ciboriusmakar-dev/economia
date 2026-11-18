"""Build and validate a genuine Leontief system from full domestic IO tables.

Canonical inputs:
Z.csv: square intermediate transactions matrix; rows=input industries,
      columns=producing industries; first column contains row industry IDs.
x.csv: industry_id,gross_output
Y.csv: industry_id,domestic_final_demand
Optional published_x.csv: industry_id,published_output
All monetary values must share currency, price basis, year and valuation.
"""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import numpy as np

def read_square(path):
    with open(path,encoding='utf-8-sig',newline='') as f: rows=list(csv.reader(f))
    if len(rows)<3 or len(rows[0])<3: raise ValueError('Матрица слишком мала')
    ids=[x.strip() for x in rows[0][1:]]
    row_ids=[r[0].strip() for r in rows[1:]]
    if ids!=row_ids: raise ValueError('Коды отраслей строк и столбцов не совпадают и не упорядочены одинаково')
    Z=np.asarray([[float(v) for v in r[1:]] for r in rows[1:]],float)
    if Z.shape!=(len(ids),len(ids)) or not np.isfinite(Z).all() or (Z<0).any(): raise ValueError('Z должна быть квадратной, конечной и неотрицательной')
    return ids,Z

def read_vector(path,ids,value_col):
    with open(path,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    d={}
    for r in rows:
        key=r['industry_id']
        if key in d: raise ValueError(f'Повторяется отрасль {key} в {path}')
        d[key]=float(r[value_col])
    if set(d)!=set(ids): raise ValueError(f'В {path} набор отраслей не совпадает с Z')
    v=np.asarray([d[i] for i in ids],float)
    if not np.isfinite(v).all() or (v<0).any(): raise ValueError(f'Некорректный вектор {value_col}')
    return v

def build_and_validate(z_path,x_path,y_path,published_x_path=None,tolerance=1e-8):
    ids,Z=read_square(z_path); x=read_vector(x_path,ids,'gross_output'); y=read_vector(y_path,ids,'domestic_final_demand')
    if np.any(x<=0): raise ValueError('Валовой выпуск должен быть строго положительным')
    # a_ij = z_ij / x_j
    A=Z/x[np.newaxis,:]
    rho=float(max(abs(np.linalg.eigvals(A))))
    if rho>=1: raise ValueError(f'Условие продуктивности не выполнено: rho(A)={rho:.10g}')
    x_model=np.linalg.solve(np.eye(len(x))-A,y)
    residual=float(np.linalg.norm((np.eye(len(x))-A)@x-y,ord=np.inf))
    reconstruction=float(np.max(np.abs(x_model-x)/np.maximum(np.abs(x),1e-12)))
    # Accounting cross-check: column intermediate input + value added should equal output.
    col_inputs=Z.sum(axis=0)
    result={"model":"M06","n_industries":len(ids),"industry_ids":ids,"rho_A":rho,
            "condition_number":float(np.linalg.cond(np.eye(len(x))-A)),
            "equation_residual_inf":residual,"observed_output_reconstruction_max_relative_error":reconstruction,
            "calculated_output":x_model.tolist(),"accounting_intermediate_input_by_industry":col_inputs.tolist(),
            "source_matrix_checksum":None,"status":"PASS_MATHEMATICAL_RECONSTRUCTION" if reconstruction<=tolerance else "FAIL_RECONSTRUCTION"}
    if published_x_path:
        xp=read_vector(published_x_path,ids,'published_output')
        result['published_output_max_relative_error']=float(np.max(np.abs(x_model-xp)/np.maximum(np.abs(xp),1e-12)))
        result['published_output_match']=bool(np.allclose(x_model,xp,rtol=1e-5,atol=1e-7))
        result['status']='PASS_INDEPENDENT_REPRODUCTION' if result['published_output_match'] and reconstruction<=tolerance else 'FAIL_INDEPENDENT_REPRODUCTION'
    return A,result

def write_matrix(path,ids,M):
    with open(path,'w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['industry_id']+ids)
        for i,row in zip(ids,M):w.writerow([i]+[f'{v:.12g}' for v in row])

def main():
    p=argparse.ArgumentParser();p.add_argument('Z');p.add_argument('x');p.add_argument('Y');p.add_argument('--published-x');p.add_argument('--out-dir',default='m06_full');a=p.parse_args()
    A,res=build_and_validate(a.Z,a.x,a.Y,a.published_x)
    ids,_=read_square(a.Z);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    write_matrix(out/'A.csv',ids,A);write_matrix(out/'leontief_inverse.csv',ids,np.linalg.inv(np.eye(len(ids))-A))
    (out/'m06_full_validation.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(res,ensure_ascii=False,indent=2))
    if res['status'].startswith('FAIL'): raise SystemExit(2)
if __name__=='__main__':main()
