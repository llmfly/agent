# Customs Data to Metrics Processing Guide

This reference provides the standard logic for transforming raw customs transaction data (Excel/CSV) into the `company_metrics.json` format required by the `company-insight-report` rendering script.

## 1. Data Mapping & Normalization

Raw customs data often varies in column naming. Do not assume exact matches. Use a keyword-based mapping strategy to standardize columns to the following internal keys:

| Internal Key | Target Keywords (Chinese/English) | Description |
| :--- | :--- | :--- |
| `company` | 主体企业, 企业名称, Company | The exporting entity |
| `date` | 交易日期, 日期, Date | Transaction date |
| `year` | 年份, Year | Calendar year |
| `month` | 月份, Month | Calendar month |
| `hs_code` | HS Code, 税号, 商品编码 | Harmonized System code |
| `country` | 出口国家, 目的地, Country | Destination country |
| `amount` | 金额美元, 出口金额, Amount | Trade value in USD |
| `quantity` | 数量, Quantity | Trade volume |
| `buyer` | 采购商, 买家, Buyer | Importing entity |

**Implementation Tip:** Iterate through the dataframe's actual columns and match them against these keywords to create a rename mapping before processing.

## 2. Key Metric Calculations

### Overall Stats
- **Total Amount**: $\sum(\text{金额美元})$
- **Growth Rate**: $\frac{\text{Amount}_{\text{CurrentYear}} - \text{Amount}_{\text{PrevYear}}}{\text{Amount}_{\text{PrevYear}}}$
- **Transaction Count**: Count of unique transaction records.

### Product Analysis
- **Product Table**: Group by `HS Code`, sum `金额美元`, calculate `percentage = amount / total_amount`.
- **Product Concentration (CR3)**: Sum of percentages of the top 3 HS Codes.
- **Concentration Type**:
    - High: $CR3 > 0.7$
    - Medium: $0.4 < CR3 \le 0.7$
    - Low: $CR3 \le 0.4$

### Country Analysis
- **Country Table**: Group by `出口国家`, sum `金额美元`, calculate `percentage`.
- **Coverage Type**:
    - Global: $> 30$ countries
    - Regional: $10-30$ countries
    - Single: $< 10$ countries

### Time Series Analysis
- **Annual Summary**: Group by `年份`, sum `金额美元`.
- **Monthly Trend**: Group by `月份`, sum `金额美元`.
- **Product Trend**: Group by `年份` and `HS Code`, sum `金额美元`, then `unstack` to get a year-to-product map.

### Competition Analysis (Market Share)
For a target `HS Code` in a target `Country`:
- **Market Total**: $\sum(\text{金额美元})$ for all companies in that segment.
- **Company Share**: $\frac{\text{Company Amount}}{\text{Market Total}}$
- **Company Rank**: Rank based on descending amount.
- **CR5**: Sum of shares of the top 5 companies.

## 3. JSON Schema Requirements
Ensure the output JSON follows the structure:
- `overall_stats`: `{total_amount, total_count, growth_rate, main_year}`
- `product_table`: List of `{HS Code, 金额美元, 数量, percentage}`
- `product_concentration`: `float` (CR3)
- `product_concentration_type`: `string` ("High" | "Medium" | "Low")
- `product_trend`: Dict `{year: {hs_code: amount}}`
- `country_table`: List of `{出口国家, 金额美元, 数量, percentage}`
- `country_coverage_type`: `string` ("Global" | "Regional" | "Single")
- `annual_summary`: Dict `{year: amount}`
- `monthly_trend`: Dict `{month: amount}`
- `competition_market`: `{target_market, target_hs, market_supplier_count, target_rank, target_share, cr5, market_type}`
- `top_buyers`: List of `{采购商, 金额美元, 数量}`



## 5. Anchor Market Selection for Competition Analysis

When the user does not explicitly specify a target market or HS code for the competition analysis section, the agent should programmatically determine an "Anchor Market" to showcase the enterprise's strongest competitive position:
- **Target HS Code**: Select the HS code with the highest total export amount from the `product_table`.
- **Target Country**: Select the country with the highest total export amount from the `country_table`.
- **Logic**: By analyzing the intersection of the top product and top country, the report provides the most evidence-backed insight into the company's core competitiveness. If no data exists for this intersection, fallback to the top country overall for the top product.

## 4. Implementation Snippets

### Handling Multiple Sheets
To avoid loading the wrong sheet (e.g., company info instead of trade data), always probe the file first:
```python
xl = pd.ExcelFile(path)
print(xl.sheet_names)
# Then load the specific trade data sheet
df = pd.read_excel(path, sheet_name='Your_Trade_Sheet_Name')
```

### NumPy to Python Conversion
To prevent `TypeError: Object of type int64 is not JSON serializable`, use this recursive cleaner before `json.dump`:
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
