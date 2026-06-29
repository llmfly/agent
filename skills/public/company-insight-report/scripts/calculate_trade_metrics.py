import pandas as pd
import numpy as np
import json
import os
import argparse

SHEET_KEYWORDS = ["海关交易数据", "交易信息", "trade"]

COLUMN_ALIASES = {
    "company": ["主体企业", "供应商", "company"],
    "date": ["交易日期", "date"],
    "year": ["年份", "year"],
    "month": ["月份", "month"],
    "hs_code": ["HS Code", "HS编码", "hs_code"],
    "desc": ["产品描述", "商品描述", "desc"],
    "desc_zh": ["产品描述中文", "中文产品描述", "商品描述中文", "desc_zh"],
    "country": ["出口国家", "目的国/地区", "目的国", "country"],
    "amount": ["金额美元", "总价", "金额", "amount"],
    "quantity": ["数量", "quantity"],
    "buyer": ["采购商", "买家", "buyer"],
}

def clean_numpy(obj):
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, np.ndarray): return [clean_numpy(i) for i in obj]
    if isinstance(obj, dict): return {k: clean_numpy(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_numpy(i) for i in obj]
    return obj

def pick_sheet(sheet_names):
    for keyword in SHEET_KEYWORDS:
        for sheet in sheet_names:
            if keyword.lower() in str(sheet).lower():
                return sheet
    return sheet_names[0]

def read_workbook_target_company(excel_path, sheet_names):
    for sheet in sheet_names:
        if "readme" not in str(sheet).lower():
            continue
        try:
            meta = pd.read_excel(excel_path, sheet_name=sheet)
        except Exception:
            continue
        if {"字段", "值"}.issubset(meta.columns):
            matches = meta[meta["字段"].astype(str).str.contains("目标企业", na=False)]
            if not matches.empty:
                value = str(matches.iloc[0]["值"] or "").strip()
                if value:
                    return value
    return ""

def normalize_columns(df):
    normalized = pd.DataFrame(index=df.index)
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                normalized[target] = df[alias]
                break
        if target not in normalized.columns:
            normalized[target] = np.nan

    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    if normalized["year"].isna().all():
        normalized["year"] = normalized["date"].dt.year
    if normalized["month"].isna().all():
        normalized["month"] = normalized["date"].dt.strftime("%Y-%m")
    normalized["year"] = pd.to_numeric(normalized["year"], errors="coerce")
    normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce").fillna(0)
    normalized["quantity"] = pd.to_numeric(normalized["quantity"], errors="coerce").fillna(0)
    for column in ["company", "hs_code", "desc", "desc_zh", "country", "buyer"]:
        normalized[column] = normalized[column].fillna("").astype(str).str.strip()
    normalized["desc"] = np.where(normalized["desc_zh"] != "", normalized["desc_zh"], normalized["desc"])
    return normalized

def calculate_metrics(excel_path, target_company, output_json):
    # 1. Load and normalize
    xl = pd.ExcelFile(excel_path)
    sheet_name = pick_sheet(xl.sheet_names)
    df = normalize_columns(pd.read_excel(excel_path, sheet_name=sheet_name))
    requested_company = str(target_company or "").strip()
    workbook_target = read_workbook_target_company(excel_path, xl.sheet_names)
    target_company = requested_company or workbook_target
    df_target = df[df['company'] == target_company].copy()
    
    if df_target.empty:
        message = f"No data found for company: {requested_company or target_company}"
        if workbook_target and workbook_target != requested_company:
            message += f"; workbook target company is: {workbook_target}"
        raise ValueError(message)
    
    # 2. Overall Stats
    total_amount = df_target['amount'].sum()
    total_count = len(df_target)
    years = sorted(year for year in df_target['year'].dropna().unique())
    main_year = years[-1] if years else None
    prev_year = years[-2] if len(years) > 1 else None
    amount_main = df_target[df_target['year'] == main_year]['amount'].sum() if main_year else 0
    amount_prev = df_target[df_target['year'] == prev_year]['amount'].sum() if prev_year else 0
    growth_rate = (amount_main - amount_prev) / amount_prev if amount_prev > 0 else 0
    
    # 3. Product Analysis
    prod_group = df_target.groupby(['hs_code', 'desc']).agg({'amount': 'sum', 'quantity': 'sum', 'date': 'count'}).reset_index()
    prod_group.columns = ['hs', 'desc', 'amount', 'quantity', 'txn_count']
    prod_group['share'] = prod_group['amount'] / total_amount
    prod_group = prod_group.sort_values('amount', ascending=False)
    cr3 = prod_group.head(3)['share'].sum()
    
    # 4. Country Analysis
    country_group = df_target.groupby('country').agg({'amount': 'sum', 'buyer': 'nunique'}).reset_index()
    country_group.columns = ['country', 'amount', 'customer_count']
    country_group['share'] = country_group['amount'] / total_amount
    country_group = country_group.sort_values('amount', ascending=False)
    
    # 5. Market Performance (Growth by Country)
    market_perf = []
    for country in country_group['country'].unique():
        c_data = df_target[df_target['country'] == country]
        c_amount = c_data['amount'].sum()
        c_share = c_amount / total_amount
        c_customers = c_data['buyer'].nunique()
        c_quantity = c_data['quantity'].sum()
        c_avg_price = c_amount / c_quantity if c_quantity > 0 else 0
        
        c_years = sorted(c_data['year'].unique())
        growth = 0
        if len(c_years) > 1:
            cur_val = c_data[c_data['year'] == c_years[-1]]['amount'].sum()
            pre_val = c_data[c_data['year'] == c_years[-2]]['amount'].sum()
            growth = (cur_val - pre_val) / pre_val if pre_val > 0 else 0
            
        market_perf.append({
            'country': country,
            'amount': float(c_amount),
            'share': float(c_share),
            'avg_price': float(c_avg_price),
            'customer_count': int(c_customers),
            'growth': float(growth)
        })
    
    # 6. Time Series
    annual_summary = df_target.groupby('year')['amount'].sum().to_dict()
    monthly_trend = df_target.groupby('month')['amount'].sum().to_dict()
    
    # 7. Competition (Anchor Market)
    top_hs = prod_group.iloc[0]['hs']
    top_country = country_group.iloc[0]['country']
    market_df = df[(df['hs_code'] == top_hs) & (df['country'] == top_country)]
    market_total = market_df['amount'].sum()
    company_market_amount = df_target[(df_target['hs_code'] == top_hs) & (df_target['country'] == top_country)]['amount'].sum()
    
    competition_market = {}
    if market_total > 0:
        company_ranks = market_df.groupby('company')['amount'].sum().sort_values(ascending=False)
        competition_market = {
            'target_market': top_country,
            'target_hs': str(top_hs),
            'market_supplier_count': len(company_ranks),
            'target_rank': int(company_ranks.index.get_loc(target_company) + 1) if target_company in company_ranks.index else -1,
            'target_share': float(company_market_amount / market_total),
            'cr5': float(company_ranks.head(5).sum() / market_total),
            'market_type': "Concentrated" if (company_ranks.head(5).sum() / market_total) > 0.6 else "Fragmented"
        }

    # 8. Top Buyers
    buyer_group = df_target.groupby('buyer').agg({'amount': 'sum', 'quantity': 'sum'}).reset_index()
    buyer_group['avg_price'] = np.where(buyer_group['quantity'] > 0, buyer_group['amount'] / buyer_group['quantity'], 0)
    buyer_group = buyer_group.sort_values('amount', ascending=False).head(10)
    
    top_buyers = []
    for _, row in buyer_group.iterrows():
        b_name = row['buyer']
        b_suppliers = df[df['buyer'] == b_name]['company'].nunique()
        top_buyers.append({
            'buyer': b_name,
            'amount': float(row['amount']),
            'avg_price': float(row['avg_price']),
            'supplier_count': int(b_suppliers),
            'price_gap_vs_target': 0.0
        })

    metrics = {
        'company': target_company,
        'requested_company': requested_company if requested_company != target_company else target_company,
        'overall_stats': {
            'total_amount': float(total_amount), 
            'total_count': int(total_count), 
            'growth_rate': float(growth_rate), 
            'main_year': int(main_year) if main_year else None
        },
        'product_table': prod_group.to_dict('records'),
        'product_concentration': float(cr3),
        'product_concentration_type': "High" if cr3 > 0.7 else ("Medium" if cr3 > 0.4 else "Low"),
        'country_table': country_group.to_dict('records'),
        'country_coverage_type': "Regional" if 10 <= len(country_group) <= 30 else ("Global" if len(country_group) > 30 else "Single"),
        'annual_summary': annual_summary,
        'monthly_trend': monthly_trend,
        'market_performance': market_perf,
        'competition_market': competition_market,
        'top_buyers': top_buyers
    }
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(clean_numpy(metrics), f, ensure_ascii=False, indent=2)
    
    return metrics

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--company', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    calculate_metrics(args.input, args.company, args.output)
