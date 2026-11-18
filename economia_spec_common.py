"""Общие помощники для модулей, реализованных по спецификации."""
from __future__ import annotations
import math, re
import numpy as np

MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

def fnum(x, d=1):
    """Число по-русски: 12 345,6"""
    if x is None or (isinstance(x, float) and not math.isfinite(x)): return '—'
    if float(f'{x:.{d}f}') == 0: x = 0.0           # без «−0,00»
    s = f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')
    return s

def pct(x, d=1):
    return '—' if x is None else fnum(x, d) + ' %'

def num(v, name):
    try: x = float(v)
    except (TypeError, ValueError): raise ValueError(f'«{name}»: значение {v!r} не является числом')
    if not math.isfinite(x): raise ValueError(f'«{name}»: значение должно быть конечным числом')
    return x

def period_index(p):
    """Номер периода для проверки полноты ряда: 2020 / 2020-05 / 2020-Q2 / целое. Иначе None."""
    s = str(p).strip()
    if re.fullmatch(r'-?\d+', s) and len(s) != 6: return int(s)
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', s)
    if m and 1 <= int(m[2]) <= 12: return int(m[1]) * 12 + int(m[2]) - 1
    m = re.fullmatch(r'(\d{4})-?Q([1-4])', s, re.I)
    if m: return int(m[1]) * 4 + int(m[2]) - 1
    return None

def sorted_rows(records, key):
    rows = sorted(records, key=lambda r: (period_index(r[key]) is None, period_index(r[key]) if period_index(r[key]) is not None else 0, str(r[key])))
    return rows

def require_complete(periods, what='ряд'):
    """Пропущенные периоды не заполняются молча: расчёт, которому они мешают, отклоняется."""
    idx = [period_index(p) for p in periods]
    if any(i is None for i in idx): return
    if len(set(idx)) != len(idx): raise ValueError(f'В «{what}» есть повторяющиеся периоды')
    for a, b in zip(idx, idx[1:]):
        if b - a != 1:
            raise ValueError(f'В «{what}» пропущены периоды между {periods[idx.index(a)]} и {periods[idx.index(b)]}; пропуски не заполняются автоматически')

def pos_label(period, m):
    s = str(period)
    if m == 12:
        r = re.fullmatch(r'(\d{4})-(\d{1,2})', s)
        if r: return MONTHS[int(r[2]) - 1]
    if m == 4:
        r = re.fullmatch(r'(\d{4})-?Q([1-4])', s, re.I)
        if r: return f'Q{r[2]}'
    return None

def ols(X, y):
    """МНК с робастными ошибками HC1. Возвращает коэффициенты, SE, R²."""
    X = np.asarray(X, float); y = np.asarray(y, float); n, k = X.shape
    if n <= k: raise ValueError('Наблюдений не больше, чем параметров')
    XtXi = np.linalg.inv(X.T @ X); b = XtXi @ X.T @ y; u = y - X @ b
    meat = (X * u[:, None]).T @ (X * u[:, None]); V = XtXi @ meat @ XtXi * n / (n - k)
    sst = float(((y - y.mean()) ** 2).sum())
    return b, np.sqrt(np.diag(V)), (1 - float(u @ u) / sst) if sst > 0 else None

def table(columns, rows, title=''):
    return {'title': title, 'columns': columns, 'rows': rows}
