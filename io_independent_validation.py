"""Independent validation of an input-output system supplied as CSV matrices.

Expected CSV files are deliberately explicit and are not inferred from raw
Eurostat files: the analyst must document the mapping from source codes.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
import numpy as np


def validate_io(A, final_demand, published_output=None, tolerance=1e-8):
    A = np.asarray(A, dtype=float)
    y = np.asarray(final_demand, dtype=float)
    if A.ndim != 2 or A.shape[0] != A.shape[1] or y.shape != (A.shape[0],):
        raise ValueError("A должна быть квадратной, y — вектором той же размерности")
    if not np.isfinite(A).all() or not np.isfinite(y).all() or (A < 0).any() or (y < 0).any():
        raise ValueError("A и y должны быть конечными неотрицательными величинами")
    rho = float(max(abs(np.linalg.eigvals(A))))
    if rho >= 1:
        raise ValueError(f"Система не подтверждает продуктивность: rho={rho:.12g}")
    M = np.eye(len(y)) - A
    condition = float(np.linalg.cond(M))
    x = np.linalg.solve(M, y)
    residual = M @ x - y
    residual_inf = float(np.linalg.norm(residual, ord=np.inf))
    result = {
        "model": "M06",
        "spectral_radius_A": rho,
        "condition_number_I_minus_A": condition,
        "computed_output": x.tolist(),
        "equation_residual_inf": residual_inf,
        "equation_pass": residual_inf <= tolerance * max(1.0, float(np.linalg.norm(y, ord=np.inf))),
        "published_output_comparison": None,
        "status": "MATHEMATICAL_CHECK_ONLY_UNTIL_REAL_SOURCE_MAPPING_IS_AUDITED"
    }
    if published_output is not None:
        ref = np.asarray(published_output, dtype=float)
        if ref.shape != y.shape or not np.isfinite(ref).all():
            raise ValueError("Опубликованный выпуск должен быть конечным вектором той же размерности")
        diff = x - ref
        result["published_output_comparison"] = {
            "max_abs_difference": float(np.max(np.abs(diff))),
            "max_relative_difference": float(np.max(np.abs(diff) / np.maximum(np.abs(ref), 1e-15))),
            "pass": bool(np.allclose(x, ref, rtol=1e-6, atol=1e-8))
        }
        result["status"] = "SOURCE_MAPPING_AND_INDEPENDENT_REPRODUCTION_REQUIRED"
    return result


def read_matrix(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return np.asarray([[float(v) for v in row] for row in rows], dtype=float)


def main():
    p = argparse.ArgumentParser(description="Проверка межотраслевой модели ECONOMIA M06")
    p.add_argument("A_csv"); p.add_argument("y_csv"); p.add_argument("--published-x-csv")
    p.add_argument("--output", default="m06_validation.json")
    a = p.parse_args()
    A = read_matrix(a.A_csv); y = read_matrix(a.y_csv).reshape(-1)
    ref = read_matrix(a.published_x_csv).reshape(-1) if a.published_x_csv else None
    result = validate_io(A, y, ref)
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
