"""ECONOMIA: first executable research core.

Scope: data-observation validation, goods balance, and Leontief input-output model.
This module is a prototype, not a production statistical system.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Iterable, Sequence
import argparse
import json
import math

import numpy as np


@dataclass(frozen=True)
class Observation:
    """One sourced measurement. Values are never silently treated as forecasts."""
    entity_id: str
    indicator_id: str
    period_start: date
    period_end: date
    value: float
    unit: str
    source_id: str
    status: str = "fact"  # fact | estimate | forecast
    territory_id: str | None = None
    price_basis: str | None = None  # e.g. current_prices | constant_2020_prices
    currency: str | None = None
    retrieved_at: date | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        for field_name in ("entity_id", "indicator_id", "unit", "source_id"):
            if not getattr(self, field_name) or not getattr(self, field_name).strip():
                errors.append(f"{field_name}: пустое обязательное поле")
        if self.period_end < self.period_start:
            errors.append("period_end: дата окончания раньше даты начала")
        if not math.isfinite(float(self.value)):
            errors.append("value: значение должно быть конечным числом")
        if self.status not in {"fact", "estimate", "forecast"}:
            errors.append("status: допустимы fact, estimate, forecast")
        if self.currency and not self.price_basis:
            errors.append("currency: для денежного показателя требуется price_basis")
        return errors


def validate_observations(observations: Iterable[Observation]) -> list[str]:
    """Validate records and detect duplicate observation identities."""
    errors: list[str] = []
    seen: set[tuple] = set()
    for i, obs in enumerate(observations):
        for error in obs.validate():
            errors.append(f"Запись {i}: {error}")
        key = (obs.entity_id, obs.indicator_id, obs.period_start, obs.period_end,
               obs.territory_id, obs.unit, obs.status, obs.price_basis, obs.currency)
        if key in seen:
            errors.append(f"Запись {i}: возможный дубль наблюдения")
        seen.add(key)
    return errors


@dataclass(frozen=True)
class BalanceResult:
    supply: float
    uses: float
    residual: float
    relative_residual: float
    is_balanced: bool


def goods_balance(*, production: float, imports: float, opening_stocks: float,
                  intermediate_use: float, final_use: float, exports: float,
                  losses: float, closing_stocks: float,
                  abs_tolerance: float = 1e-9,
                  rel_tolerance: float = 1e-9) -> BalanceResult:
    """Check physical/monetary balance in one consistent unit and price basis.

    Supply = production + imports + opening stocks
    Uses   = intermediate + final + exports + losses + closing stocks
    """
    values = [production, imports, opening_stocks, intermediate_use, final_use,
              exports, losses, closing_stocks]
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("Все компоненты баланса должны быть конечными числами")
    supply = production + imports + opening_stocks
    uses = intermediate_use + final_use + exports + losses + closing_stocks
    residual = supply - uses
    scale = max(abs(supply), abs(uses), 1.0)
    relative = abs(residual) / scale
    balanced = abs(residual) <= abs_tolerance or relative <= rel_tolerance
    return BalanceResult(supply, uses, residual, relative, balanced)


@dataclass(frozen=True)
class LeontiefResult:
    output: tuple[float, ...]
    spectral_radius: float
    equation_residual_norm: float
    condition_number: float


def solve_leontief(A: Sequence[Sequence[float]], final_demand: Sequence[float],
                   *, tolerance: float = 1e-9) -> LeontiefResult:
    """Solve x = A x + y without explicitly forming (I-A)^(-1)."""
    matrix = np.asarray(A, dtype=float)
    demand = np.asarray(final_demand, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("A должна быть квадратной матрицей n×n")
    n = matrix.shape[0]
    if demand.shape != (n,):
        raise ValueError("Вектор конечного спроса должен иметь размер n")
    if not np.isfinite(matrix).all() or not np.isfinite(demand).all():
        raise ValueError("Матрица и спрос должны содержать конечные числа")
    if (matrix < -tolerance).any():
        raise ValueError("Коэффициенты A не должны быть отрицательными")
    if (demand < -tolerance).any():
        raise ValueError("Конечный спрос не должен быть отрицательным")

    rho = float(np.max(np.abs(np.linalg.eigvals(matrix))))
    if rho >= 1.0 - tolerance:
        raise ValueError(f"Условие продуктивности не подтверждено: rho(A)={rho:.12g} >= 1")
    system = np.eye(n) - matrix
    try:
        output = np.linalg.solve(system, demand)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Система (I-A)x=y не имеет устойчивого единственного решения") from exc
    residual = float(np.linalg.norm(system @ output - demand, ord=np.inf))
    condition = float(np.linalg.cond(system))
    if (output < -100 * tolerance).any():
        raise ArithmeticError("Получен отрицательный выпуск; проверьте исходные данные и модель")
    if residual > 100 * tolerance * max(1.0, float(np.linalg.norm(demand, ord=np.inf))):
        raise ArithmeticError("Остаток решения превышает установленный допуск")
    return LeontiefResult(tuple(float(v) for v in output), rho, residual, condition)


def run_self_test() -> dict:
    """Small deterministic synthetic checks; not empirical validation."""
    tests = []
    b = goods_balance(production=100, imports=20, opening_stocks=5,
                      intermediate_use=40, final_use=60, exports=15,
                      losses=2, closing_stocks=8)
    tests.append({"id": "T001", "passed": b.is_balanced,
                  "residual": b.residual, "type": "synthetic"})

    l = solve_leontief([[0.2, 0.1], [0.1, 0.2]], [100, 80])
    expected = (139.68253968253967, 117.46031746031746)
    close = all(abs(a - e) < 1e-8 for a, e in zip(l.output, expected))
    tests.append({"id": "T002", "passed": close and l.spectral_radius < 1,
                  "output": list(l.output), "rho": l.spectral_radius,
                  "residual": l.equation_residual_norm, "type": "synthetic"})

    good = Observation("country:XX", "GDP", date(2025, 1, 1), date(2025, 12, 31),
                       1000, "million_EUR", "source:demo", "estimate",
                       price_basis="current_prices", currency="EUR")
    tests.append({"id": "T003", "passed": not validate_observations([good]),
                  "type": "synthetic"})
    return {"suite": "ECONOMIA-core-self-test", "tests": tests,
            "all_passed": all(t["passed"] for t in tests),
            "warning": "Синтетические проверки не подтверждают точность на реальных данных."}


def main() -> None:
    parser = argparse.ArgumentParser(description="ECONOMIA prototype core")
    parser.add_argument("--self-test", action="store_true", help="run synthetic checks")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(run_self_test(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
