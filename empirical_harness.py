"""Leakage-resistant evaluation helpers for ECONOMIA time-series models.

The harness evaluates a user-supplied forecasting function on chronological
expanding windows. It never shuffles observations and always compares against
naive-last-value baseline. This is an evaluation utility, not a model itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import mean
from typing import Callable, Sequence

ForecastFunction = Callable[[Sequence[float]], float]


@dataclass(frozen=True)
class ForecastRow:
    index: int
    actual: float
    prediction: float
    baseline: float


def _validate_series(values: Sequence[float], min_train: int) -> list[float]:
    if isinstance(min_train, bool) or not isinstance(min_train, int) or min_train < 2:
        raise ValueError("min_train должен быть целым числом не меньше 2")
    data = [float(v) for v in values]
    if len(data) <= min_train:
        raise ValueError("Для проверки нужны данные и обучающий период, и контрольные наблюдения")
    if any(not isfinite(v) for v in data):
        raise ValueError("Ряд содержит пропуски или нечисловые/бесконечные значения")
    return data


def calculate_metrics(actual: Sequence[float], predicted: Sequence[float]) -> dict:
    if len(actual) == 0 or len(actual) != len(predicted):
        raise ValueError("actual и predicted должны иметь одинаковую ненулевую длину")
    pairs = [(float(a), float(p)) for a, p in zip(actual, predicted)]
    if any(not isfinite(a) or not isfinite(p) for a, p in pairs):
        raise ValueError("Метрики нельзя считать по нечисловым или бесконечным значениям")
    errors = [a - p for a, p in pairs]
    abs_errors = [abs(e) for e in errors]
    denominators = [abs(a) for a, _ in pairs]
    mape_values = [ae / den for ae, den in zip(abs_errors, denominators) if den > 0]
    smape_values = [2 * ae / (abs(a) + abs(p)) for ae, (a, p) in zip(abs_errors, pairs)
                    if abs(a) + abs(p) > 0]
    return {
        "n": len(pairs),
        "MAE": mean(abs_errors),
        "RMSE": sqrt(mean(e * e for e in errors)),
        "MAPE_percent": mean(mape_values) * 100 if mape_values else None,
        "MAPE_excluded_zero_actuals": len(pairs) - len(mape_values),
        "sMAPE_percent": mean(smape_values) * 100 if smape_values else 0.0,
        "mean_error_bias": mean(errors),
    }


def expanding_window_evaluation(
    values: Sequence[float],
    forecast: ForecastFunction,
    *,
    min_train: int = 3,
    model_name: str = "candidate",
) -> dict:
    """One-step-ahead expanding-window test; forecast sees past values only."""
    data = _validate_series(values, min_train)
    rows: list[ForecastRow] = []
    for target_index in range(min_train, len(data)):
        history = tuple(data[:target_index])
        prediction = float(forecast(history))
        if not isfinite(prediction):
            raise ValueError(f"Модель вернула неконечный прогноз для индекса {target_index}")
        rows.append(ForecastRow(target_index, data[target_index], prediction, history[-1]))
    actual = [r.actual for r in rows]
    model_predictions = [r.prediction for r in rows]
    baseline_predictions = [r.baseline for r in rows]
    model_metrics = calculate_metrics(actual, model_predictions)
    baseline_metrics = calculate_metrics(actual, baseline_predictions)
    return {
        "evaluation": "expanding_window_one_step_ahead",
        "model": model_name,
        "n_observations": len(data),
        "min_train": min_train,
        "n_forecasts": len(rows),
        "chronological_order_preserved": True,
        "future_observations_exposed_to_model": False,
        "model_metrics": model_metrics,
        "naive_last_value_baseline_metrics": baseline_metrics,
        "beats_naive_baseline_on_MAE": model_metrics["MAE"] < baseline_metrics["MAE"],
        "rows": [r.__dict__ for r in rows],
        "limitations": [
            "Одношаговая проверка не гарантирует качество многопериодного прогноза.",
            "Результат зависит от выбранного ряда, периода, частоты и пересмотров статистики.",
            "Сравнение с наивным ориентиром не заменяет независимую внешнюю проверку."
        ],
        "status": "EMPIRICAL_TEST_ON_SUPPLIED_SERIES_REQUIRES_DATA_PROVENANCE_AUDIT"
    }
