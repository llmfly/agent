# Customs Trade Excel Schema Example

This document describes the typical column structure encountered in the customs trade simulation files used for company insight reports.

## Observed Column Names
The following columns are standard in the `海关交易数据2026最新` (or similar) sheets:

| Column Name | Description | Usage in Metrics |
|-------------|-------------|-------------------|
| 主体企业 | Company Name | Filtering target company |
| 交易日期 | Transaction Date | Time series analysis |
| 年份 | Year | Annual aggregation |
| 月份 | Month | Monthly trend |
| HS Code | Harmonized System Code | Product classification/concentration |
| 产品描述 | Product Description | Product labeling in reports |
| 出口国家 | Destination Country | Market distribution/coverage |
| 采购商 | Buyer | Customer concentration/Buyer digging |
| 供应商 | Supplier | Competition analysis (when target is buyer) |
| 金额美元 | Amount (USD) | Primary metric for all calculations |
| 数量 | Quantity | Unit price calculation (`Amount/Quantity`) |
| 单位 | Unit | Data verification |
| 贸易角色 | Trade Role | Verifying 'Export' vs 'Import' |
| 来源 | Source | Data lineage |

Some real database exports use `交易信息表` with the following equivalent schema:

| Column Name | Equivalent Standard Field | Usage in Metrics |
|-------------|---------------------------|------------------|
| 供应商 | 主体企业 / company | Filtering target exporting company |
| 交易日期 | 交易日期 / date | Time series analysis |
| HS编码 | HS Code / hs_code | Product classification/concentration |
| 产品描述 | 产品描述 / desc | Product labeling in reports |
| 目的国/地区 | 出口国家 / country | Market distribution/coverage |
| 采购商 | 采购商 / buyer | Customer concentration/Buyer digging |
| 总价 | 金额美元 / amount | Primary metric for all calculations |
| 数量 | 数量 / quantity | Unit price calculation when reliable |
| 单价 | 单价 / unit_price | Optional price reference |
| 供应商国家 | 供应商国家 | Supplier country reference |
| 采购商国家 | 采购商国家 | Buyer country reference |

## Probing Strategy
When loading these files, always inspect `pd.ExcelFile(path).sheet_names` and use keyword matching for sheet names such as `海关交易数据`, `交易信息`, or `trade`. Do not hard-code only one sheet name family.
