# Comprehensive Trade Metrics Calculation Logic

To produce a high-quality, evidence-oriented trade report, the basic metric calculation must be extended to provide granular data for the "Evidence" sections of the analysis.

## 1. Enhanced Product Analysis
Beyond total amount and share, include:
- **Description Mapping**: Ensure `desc` is captured and grouped with `hs_code` to avoid generic "HS Code" labels in the report.
- **Transaction Count**: Use `count` of dates/transactions per product to distinguish between "few large orders" and "consistent small orders".

## 2. Market Performance (Per-Country Growth)
The basic summary is insufficient for Chapter 2.2 (Growth Trend). Calculate:
- **Country-Level Growth**: For each country, calculate $\frac{Amount_{current} - Amount_{prev}}{Amount_{prev}}$.
- **Average Price per Market**: Calculate $\frac{\sum Amount}{\sum Quantity}$ per country to identify "Profit-driven" vs "Volume-driven" markets.
- **Customer Concentration**: Count unique buyers per country.

## 3. Competition (Anchor Market)
To avoid "absolute leading" fallacies in Chapter 3.1:
- **Market Total**: Sum amount for (Top HS $\cap$ Top Country) across ALL companies in the dataset.
- **Target Share**: $\frac{CompanyAmount}{MarketTotal}$.
- **Concentration (CR5)**: Sum of top 5 companies' shares to determine if the market is "Concentrated" or "Fragmented".

## 4. Buyer Depth Analysis
For Chapter 4.2:
- **Buyer-Supplier Ratio**: For each top buyer, count how many unique companies they purchase from across the entire dataset. This indicates "Buyer Openness".
- **Price Gap**: Compare the target company's avg price for a specific buyer against the buyer's overall avg purchase price from all suppliers.

## 5. Technical Implementation Note
Always apply a recursive `clean_numpy` function to the final metrics dictionary before `json.dump` to prevent `TypeError: Object of type int64 is not JSON serializable`.
