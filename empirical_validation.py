"""Small empirical holdout check using World Bank WDI Germany nominal GDP.
Data are manually snapshotted from the cited WDI DataBank result, not fetched live.
This validates a baseline forecasting procedure on one series only.
"""
from __future__ import annotations
import csv, json
from pathlib import Path
from statistics import mean

DATA = Path(__file__).parent/'data'/'pilot_input'/'empirical_germany_gdp_2016_2025.csv'
SOURCE_URL = 'https://databank.worldbank.org/reports.aspx?country=DEU&series=NY.GDP.MKTP.CD&source=2'


def load_series(path=DATA):
    with open(path, newline='', encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    years=[int(r['year']) for r in rows]
    values=[float(r['gdp_current_usd']) for r in rows]
    if years != list(range(years[0], years[-1]+1)):
        raise ValueError('Годы должны идти подряд без пропусков')
    if any(v <= 0 for v in values): raise ValueError('GDP должен быть положительным')
    return years, values


def metrics(actual, predicted):
    errors=[a-p for a,p in zip(actual,predicted)]
    mae=mean(abs(e) for e in errors)
    rmse=(mean(e*e for e in errors))**0.5
    mape=mean(abs(e)/abs(a) for e,a in zip(errors,actual))*100
    return {'MAE_USD':mae,'RMSE_USD':rmse,'MAPE_percent':mape}


def run_empirical_check():
    years, values=load_series()
    # Strict chronological split: model only sees 2016-2022; 2023-2025 are held out.
    split=years.index(2023)
    train=values[:split]
    actual=values[split:]
    horizon=len(actual)
    naive=[train[-1]]*horizon
    annual_drift=(train[-1]-train[0])/(len(train)-1)
    drift=[train[-1]+annual_drift*(i+1) for i in range(horizon)]
    rolling = {'naive_last_value': [], 'linear_drift': []}
    # Expanding-window one-step-ahead validation; every prediction uses only prior years.
    for idx in range(5, len(values)):
        prior=values[:idx]
        actual_one=values[idx]
        drift_one=prior[-1]+(prior[-1]-prior[0])/(len(prior)-1)
        rolling['naive_last_value'].append({'year':years[idx], 'actual':actual_one, 'prediction':prior[-1]})
        rolling['linear_drift'].append({'year':years[idx], 'actual':actual_one, 'prediction':drift_one})
    rolling_metrics={}
    for name, rows in rolling.items():
        rolling_metrics[name]=metrics([r['actual'] for r in rows],[r['prediction'] for r in rows])
    return {
      'dataset':'Germany GDP (current US$), annual',
      'indicator':'NY.GDP.MKTP.CD', 'source':'World Bank World Development Indicators',
      'source_url':SOURCE_URL, 'licence':'CC BY 4.0 (as shown on WDI indicator page)',
      'years':years, 'train_period':[years[0],years[split-1]],
      'holdout_period':[years[split],years[-1]], 'train_n':len(train), 'holdout_n':len(actual),
      'actual_holdout_usd':actual,
      'rolling_origin_one_step':{'forecast_rows':rolling,'metrics':rolling_metrics},
      'models':{
        'naive_last_value':{'predicted_usd':naive,'metrics':metrics(actual,naive)},
        'linear_drift_from_training_endpoints':{'predicted_usd':drift,'metrics':metrics(actual,drift)}
      },
      'interpretation':[
        'Это ограниченная эмпирическая проверка двух простых прогнозных ориентиров на одной годовой серии.',
        'GDP в текущих долларах зависит от реального выпуска, внутренних цен и валютного курса; он не является чистым показателем реального роста.',
        'Три наблюдения в фиксированном контрольном периоде и пять последовательных одношаговых прогнозов — ограниченная проверка, недостаточная для общего вывода о точности ECONOMIA.',
        'Снимок данных не является автоматическим обновлением; перед промышленным использованием нужно повторно получить полный ряд и зафиксировать дату/версию.'
      ],
      'status':'EMPIRICAL_PILOT_COMPLETED_LIMITED_SCOPE'
    }

if __name__=='__main__': print(json.dumps(run_empirical_check(),ensure_ascii=False,indent=2))
