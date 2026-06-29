# Excel to Metrics Implementation Guide

This reference provides a robust Python implementation for transforming raw customs trade data into the `company_metrics.json` format.

## 1. Robust Column Mapping
Do not rely on fixed column names. Use a keyword-based mapping to handle variations across different data sources.

```python
mapping = {
    '主体企业': 'company',  # real exports may use 供应商
    '交易日期': 'date',
    '年份': 'year',
    '月份': 'month',
    'HS Code': 'hs_code',  # real exports may use HS编码
    '出口国家': 'country',  # real exports may use 目的国/地区
    '金额美元': 'amount',  # real exports may use 总价
    '数量': 'quantity',
    '采购商': 'buyer'
}
df_clean = df.rename(columns=mapping)
```

## 2. Metric Aggregation Logic

### Overall Stats
```python
total_amount = df_target['amount'].sum()
years = sorted(df_target['year'].unique())
main_year = years[-1]
prev_year = years[-2] if len(years) > 1 else None

amount_main = df_target[df_target['year'] == main_year]['amount'].sum()
amount_prev = df_target[df_target['year'] == prev_year]['amount'].sum() if prev_year else 0
growth_rate = (amount_main - amount_prev) / amount_prev if amount_prev > 0 else 0
```

### Product & Concentration (CR3)
```python
prod_group = df_target.groupby('hs_code').agg({'amount': 'sum', 'quantity': 'sum', 'date': 'count'}).reset_index()
prod_group.columns = ['hs', 'amount', 'quantity', 'txn_count']
prod_group['share'] = prod_group['amount'] / total_amount
prod_group = prod_group.sort_values('amount', ascending=False)

cr3 = prod_group.head(3)['share'].sum()
concentration_type = "High" if cr3 > 0.7 else ("Medium" if cr3 > 0.4 else "Low")
```

### Anchor Market Selection for Competition Analysis
To showcase the most competitive position, select the intersection of the Top Product and Top Country.

```python
top_hs = prod_group.iloc[0]['hs']
top_country = country_group.iloc[0]['country']

market_df = df_clean[(df_clean['hs_code'] == top_hs) & (df_clean['country'] == top_country)]
market_total = market_df['amount'].sum()
company_market_amount = df_target[(df_target['hs_code'] == top_hs) & (df_target['country'] == top_country)]['amount'].sum()

if market_total > 0:
    target_share = company_market_amount / market_total
    company_ranks = market_df.groupby('company')['amount'].sum().sort_values(ascending=False)
    target_rank = company_ranks.index.get_loc(target_company) + 1 if target_company in company_ranks.index else -1
    cr5 = company_ranks.head(5).sum() / market_total
    market_type = "Concentrated" if cr5 > 0.6 else "Fragmented"
```

## 3. Data Cleaning (NumPy to Python)
Essential for `json.dump` to avoid `TypeError`.

```python
import numpy as np

def clean_numpy(obj):
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, np.ndarray): return [clean_numpy(i) for i in obj]
    if isinstance(obj, dict): return {k: clean_numpy(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_numpy(i) for i in obj]
    return obj
```
