# System Architecture & Technical Specifications

## 1. High-Level Architecture Flow

```mermaid
flowchart TD
    subgraph Data_Sources [Business Data Sources]
        S1[Walmart M5 CSVs]
        S2[CSV / Excel Sales Imports]
        S3[Physical Audit Stock Counts]
        S4[Purchase Order Receipts]
    end

    subgraph Lakehouse_ETL [Medallion Lakehouse Architecture]
        S1 & S2 --> B[(Bronze Parquet Data Lake)]
        B -->|Cleaning, Joining, Normalization| Sil[(Silver Daily Sales Table)]
        Sil -->|Window Lags, Rolling Stats, Time Features| G[(Gold ML Analytics Table)]
    end

    subgraph Processing_Engines [Processing Engines]
        P1[Local Pandas Pipeline] -.-> Sil
        P2[Apache Spark Standalone Cluster: 1 Master + 2 Workers] -.-> G
    end

    subgraph Forecasting_Core [Demand Forecasting & Evaluation]
        G --> M1[Strict Temporal Splitting: Train/Val/Test]
        M1 --> M2[Seasonal-Naive Benchmark]
        M1 --> M3[Moving-Average Benchmark]
        M1 --> M4[LightGBM Gradient Boosted Regressor]
        M2 & M3 & M4 --> ME[Out-of-Sample Evaluation: WAPE, RMSE, Bias]
        ME --> MC[Champion Model Selection]
        MC --> MP[Recursive Forward Multi-step Forecaster: 7 & 28 Days]
    end

    subgraph Inventory_Optimization [Statistical Inventory Engine]
        MP --> I1[Demand During Lead Time: DDLT]
        I1 --> I2[Statistical Safety Stock: SS]
        I2 --> I3[Dynamic Reorder Point: ROP]
        I3 --> I4[Recommended Order Quantity with MOQ & Multiples]
        I4 --> I5[Classification: Reorder, Stockout Risk, Overstock, Healthy]
    end

    subgraph Storage_and_API [Multi-Tenant Persistence & Serving]
        I5 & MP & S3 & S4 --> DB[(PostgreSQL Multi-Tenant DB)]
        DB --> API[FastAPI Enterprise Backend]
        API --> Sec[JWT Auth & Tenant Isolation]
        API --> PO[Purchase Order Workflow & Movement Ledger]
        API --> Docs[Swagger / OpenAPI Documentation]
    end
```

## 2. Multi-Tenant Business Isolation
Each business registers independently. All relational queries across products, daily sales, forecasts, inventory snapshots, stock movements, and purchase orders are strictly partitioned by `business_id`. A request from Business B attempting to access records of Business A returns an HTTP 404/403.
