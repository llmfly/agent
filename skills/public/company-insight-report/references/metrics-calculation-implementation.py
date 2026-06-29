import pandas as pd
import json
import os

def calculate_trade_metrics(file_path, sheet_name, target_company):
    \"\"\"
    Implementation of the customs data to metrics logic for company-insight-report.
    Transforms raw Excel trade data into the required company_metrics.json format.
    \"\"\"
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    df_target = df[df['主体企业'] == target_company]
    
    # 1. Overall Stats
    total_amount = float(df_target['金额美元'].sum())
    total_count = int(df_target.shape[0])
    
    yearly_amounts = df_target.groupby('年份')['金额美元'].sum()
    current_year = int(yearly_amounts.index.max()) if not yearly_amounts.empty else 0
    prev_year = current_year - 1
    amount_curr = yearly_amounts.get(current_year, 0)
    amount_prev = yearly_amounts.get(prev_year, 0)
    growth_rate = (amount_curr - amount_prev) / amount_prev if amount_prev != 0 else 0
    
    overall_stats = {
        "total_amount": total_amount,
        "total_count": total_count,
        "growth_rate": float(growth_rate),
        "main_year": current_year
    }
    
    # 2. Product Analysis
    product_grp = df_target.groupby('HS Code').agg({'金额美元': 'sum', '数量': 'sum'}).sort_values('金额美元', ascending=False)
    product_grp['percentage'] = product_grp['金额美元'] / total_amount if total_amount != 0 else 0
    product_table = [
        {"HS Code": str(hs), "金额美元": float(row['金额美元']), "数量": float(row['数量']), "percentage": float(row['percentage'])}
        for hs, row in product_grp.iterrows()
    ]
    
    cr3 = float(product_grp['percentage'].head(3).sum())
    conc_type = "High" if cr3 > 0.7 else ("Medium" if cr3 > 0.4 else "Low")
    
    # 3. Country Analysis
    country_grp = df_target.groupby('出口国家').agg({'金额美元': 'sum', '数量': 'sum'}).sort_values('金额美元', ascending=False)
    country_grp['percentage'] = country_grp['金额美元'] / total_amount if total_amount != 0 else 0
    country_table = [
        {"出口国家": str(country), "金额美元": float(row['金额美元']), "数量": float(row['数量']), "percentage": float(row['percentage'])}
        for country, row in country_grp.iterrows()
    ]
    
    country_count = len(country_grp)
    coverage_type = "Global" if country_count > 30 else ("Regional" if country_count >= 10 else "Single")
    
    # 4. Competition Analysis (Target: Top Country, Top Product)
    top_country = country_grp.index[0] if not country_grp.empty else "Unknown"
    top_hs = product_grp.index[0] if not product_grp.empty else "Unknown"
    
    market_df = df[(df['出口国家'] == top_country) & (df['HS Code'] == top_hs)]
    market_total = market_df['金额美元'].sum()
    company_amount = df_target[(df_target['出口国家'] == top_country) & (df_target['HS Code'] == top_hs)]['金额美元'].sum()
    target_share = company_amount / market_total if market_total != 0 else 0
    
    company_shares = market_df.groupby('主体企业')['金额美元'].sum().sort_values(ascending=False)
    target_rank = int(company_shares.index.get_loc(target_company) + 1) if target_company in company_shares.index else 999
    market_supplier_count = len(company_shares)
    cr5 = float(company_shares.head(5).sum() / market_total) if market_total != 0 else 0
    
    competition_market = {
        "target_market": top_country,
        "target_hs": str(top_hs),
        "market_supplier_count": market_supplier_count,
        "target_rank": target_rank,
        "target_share": float(target_share),
        "cr5": cr5,
        "market_type": "Concentrated" if cr5 > 0.5 else "Fragmented"
    }
    
    # 5. Top Buyers
    buyer_grp = df_target.groupby('采购商').agg({'金额美元': 'sum', '数量': 'sum'}).sort_values('金额美元', ascending=False)
    top_buyers = [
        {"采购商": str(buyer), "金额美元": float(row['金额美元']), "数量": float(row['数量'])}
        for buyer, row in buyer_grp.head(10).iterrows()
    ]
    
    # 6. Trends
    annual_summary = {str(k): float(v) for k, v in yearly_amounts.to_dict().items()}
    monthly_trend = df_target[df_target['年份'] == current_year].groupby('月份')['金额美元'].sum().to_dict()
    monthly_trend = {str(k): float(v) for k, v in monthly_trend.items()}
    
    return {
        "company": target_company,
        "overall_stats": overall_stats,
        "product_table": product_table,
        "product_concentration": cr3,
        "product_concentration_type": conc_type,
        "country_table": country_table,
        "country_coverage_type": coverage_type,
        "annual_summary": annual_summary,
        "monthly_trend": monthly_trend,
        "competition_market": competition_market,
        "top_buyers": top_buyers,
        "core_findings": [],
        "risks": [],
        "recommendations": []
    }
