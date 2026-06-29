# 海关贸易数据 Excel 列名变体映射表

在处理不同来源的海关贸易数据时，列名经常存在差异。在编写数据清洗脚本或使用 `calculate_trade_metrics.py` 时，请参考以下常见映射关系：

| 标准内部字段 | 常见变体 1 (标准版) | 常见变体 2 (实操版) | 常见变体 3 (英文/其他) |
| :--- | :--- | :--- | :--- |
| `company` | 主体企业 | 供应商 / 出口商 | Supplier / Exporter |
| `date` | 交易日期 | 日期 | Trade Date / Date |
| `amount` | 金额美元 | 总价 / 贸易额 | Total Value / Amount / USD |
| `quantity` | 数量 | 数量 | Quantity / Qty |
| `hs_code` | HS Code | HS编码 / 商品编码 | HS Code / Tariff Code |
| `desc` | 产品描述 | 商品名称 / 描述 | Description / Product Name |
| `country` | 出口国家 | 目的国/地区 / 目的地 | Destination Country / Country |
| `buyer` | 采购商 | 买方 / 进口商 | Buyer / Importer |

## 处理建议
1. **动态映射**：在代码中定义一个 `mapping = { '供应商': 'company', '总价': 'amount', ... }` 字典。
2. **前置探测**：在执行计算前，先运行 `df.columns.tolist()` 打印所有列名。
3. **模糊匹配**：如果列名包含关键词（如 '金额' 或 'Price'），则将其映射为 `amount`。
