# Retail Practical Analysis & Domain Guide

This document analyzes the practical application of this system for retail businesses (local shopkeepers, small supermarket chains, and enterprise retailers), highlights industry challenges, details real-world limitations, and provides a strategic roadmap for future enhancements.

---

## 1. How This System Solves Real-World Problems for Retailers

Local shop owners and retail managers typically rely on **intuition, gut feeling, or static pen-and-paper order books** to decide what to order. This leads to two critical financial pitfalls:

1. **Working Capital Locked in Overstock:**
   - Retailers buy bulk inventory to avoid running out, trapping thousands in unsold goods.
   - For items with limited shelf life or rapid obsolescence, this turns directly into waste (spoilage/shrinkage).
   - *How the system helps:* By calculating dynamic Days of Supply and flagging `POTENTIAL_OVERSTOCK` when stock exceeds a 45-day threshold, retailers stop ordering slow-moving items and free up liquid cash.

2. **Lost Revenue and Customer Churn from Stockouts:**
   - If a customer visits a local store and an item is missing twice in a row, they switch to a competitor or e-commerce platform.
   - *How the system helps:* The system calculates dynamic **Demand During Lead Time (DDLT)** and **Safety Stock (SS)**. It triggers a `POTENTIAL_STOCKOUT` alert days *before* the shelf is empty, accounting for the supplier's delivery lag.

3. **Supplier Order Constraints (MOQ & Multiples):**
   - Suppliers do not sell single units; they sell in carton boxes (e.g., minimum 20 units, multiples of 6).
   - *How the system helps:* The engine rounds order quantities up to exact supplier packaging specifications (`min_order_qty` and `order_multiple`), preventing order rejection.

4. **Actionable Restocking Decisions:**
   - Instead of looking through thousands of inventory rows, the manager receives a single daily prioritised list:
     - Exact SKU to order
     - Recommended Order Quantity ($ROQ$)
     - The business reason (e.g., "Inventory position 18 fell below reorder point 42.5").

---

## 2. Industry Challenges in Demand Forecasting & Inventory

Retail Data Science and Data Engineering face several domain-specific hurdles:

| Challenge | Real-World Impact | How Our Project Addresses It |
| :--- | :--- | :--- |
| **Intermittent / Zero Demand** | Many retail SKUs have days with 0 sales. Traditional MAPE divides by zero and fails. | We implement **WAPE** ($\frac{\sum |y - \hat{y}|}{\sum y}$) and **Bias**, which remain stable and numerically sound on sparse data. |
| **Data Leakage in Time Series** | Engineers accidentally use future sales or future rolling statistics to predict past dates. | Strict temporal splitting and backward-shifted features (`shift(1)`) ensure no future information leaks into training. |
| **Volatile Supplier Lead Times** | Suppliers may quote 5 days but take 12 days during holiday spikes. | The safety stock formula incorporates both demand standard deviation ($\sigma_d$) and lead time uncertainty ($\sigma_L$). |
| **Cold-Start Products** | New items have zero sales history for rolling averages. | Fallback logic uses department/category medians and baseline moving averages until 28 days of history accumulate. |
| **Promotions and Price Shifts** | Temporary discounts cause short demand spikes followed by post-promotion dips. | The LightGBM feature set incorporates `sell_price`, price ratios, and promotional calendar event flags. |

---

## 3. What Could Lack in the Future & What to Keep in Mind

If deployed in a long-term production setting, keep these factors in mind:

1. **Concept Drift & Black Swan Events:**
   - Sudden structural shifts (pandemics, extreme weather, economic inflation) render historical sales unrepresentative.
   - *Mitigation:* Implement continuous model drift monitoring (e.g., Evidently AI or rolling WAPE alerts) to retrain models when error crosses a defined threshold.
2. **Cannibalization & Substitution Effects:**
   - When Brand A is discounted, sales of Brand B drop; if Brand A is out of stock, customers buy Brand B instead.
   - *Mitigation:* Future iterations can group cross-price elasticity features across competing product categories.
3. **Storage Capacity Constraints:**
   - A recommendation engine might suggest ordering 500 units of paper towels, but the retailer may have only 20 cubic feet of backroom space.
   - *Mitigation:* Add volume/weight warehouse capacity limits to the linear programming optimization in the inventory engine.
4. **Perishability & Batch Expiration:**
   - Milk or fresh produce requires FIFO/FEFO expiration tracking rather than simple unit counting.
