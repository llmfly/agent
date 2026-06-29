# 海关交易数据列名变体参考 (Column Mapping Variants)

在处理不同来源的海关贸易数据时，列名经常存在差异。以下是本 skill 适配的常见变体，用于在执行 `calculate_trade_metrics.py` 前进行探测和对齐。

## 核心字段映射表

| 标准内部字段 | 常见中文变体 | 常见英文变体 | 备注 |
| :--- | :--- | :--- | :--- |
| `company` | 主体企业, 供应商, 出口商 | Company, Supplier, Exporter | 贸易发起方 |
| `date` | 交易日期, 交易时间, 日期 | Date, Transaction Date | 需转换为 datetime 格式 |
| `hs_code` | HS Code, HS编码, 商品编码 | HS Code, HS Number | 建议统一为字符串 |
| `desc` | 产品描述, 产品名称, 货物名称 | Description, Product Name | |
| `country` | 出口国家, 目的国/地区, 目的国 | Country, Destination, Target Country | |
| `amount` | 金额美元, 总价, 金额, 贸易额 | Amount, Total Price, Value | 必须为数值类型 |
| `quantity` | 数量, 数量(kg/pcs) | Quantity, Qty | |
| `buyer` | 采购商, 买家, 进口商 | Buyer, Customer, Importer | |

## 探测策略建议

1. **全列扫描**：在加载 DataFrame 后，优先打印 `df.columns.tolist()`。
2. **模糊匹配**：使用关键字（如 '金额'、'国家'、'HS'）检索列名，而非硬编码索引。
3. **类型强制转换**：
   - `amount` $\rightarrow$ `pd.to_numeric(..., errors='coerce')`
   - `date` $\rightarrow$ `pd.to_datetime(...)`
   - `hs_code` $\rightarrow$ `.astype(str).str.replace('.0', '')`
