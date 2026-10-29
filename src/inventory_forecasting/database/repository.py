"""Multi-tenant database repository layer enforcing strict business-level isolation."""

from datetime import date
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import desc
from inventory_forecasting.database.models import (
    Business,
    DailySales,
    DemandForecast,
    ForecastRun,
    InventoryRecommendation,
    InventorySnapshot,
    ModelEvaluation,
    PipelineExecution,
    Product,
    Store,
    Supplier,
    User,
)


class InventoryRepository:
    def __init__(self, db: Session, business_id: str = "default_corp"):
        self.db = db
        self.business_id = business_id

    def ensure_business(self, name: str = "Default Corporation") -> Business:
        b = self.db.query(Business).filter_by(business_id=self.business_id).first()
        if not b:
            b = Business(business_id=self.business_id, name=name)
            self.db.add(b)
            self.db.commit()
        return b

    def upsert_products_and_stores(self, df: pd.DataFrame):
        self.ensure_business()
        if "item_id" in df.columns:
            prod_sub = df[["item_id", "dept_id", "cat_id"]].drop_duplicates()
            for _, row in prod_sub.iterrows():
                existing = self.db.query(Product).filter_by(
                    business_id=self.business_id, item_id=row["item_id"]
                ).first()
                if not existing:
                    self.db.add(Product(
                        business_id=self.business_id,
                        item_id=row["item_id"],
                        dept_id=row["dept_id"],
                        cat_id=row["cat_id"],
                        name=f"Product {row['item_id']}"
                    ))

        if "store_id" in df.columns:
            store_sub = df[["store_id", "state_id"]].drop_duplicates()
            for _, row in store_sub.iterrows():
                existing = self.db.query(Store).filter_by(
                    business_id=self.business_id, store_id=row["store_id"]
                ).first()
                if not existing:
                    self.db.add(Store(
                        business_id=self.business_id,
                        store_id=row["store_id"],
                        state_id=row["state_id"]
                    ))
        self.db.commit()

    def persist_daily_sales(self, df: pd.DataFrame, batch_size: int = 1000):
        self.upsert_products_and_stores(df)
        records = []
        for _, row in df.iterrows():
            d_val = row["date"]
            if isinstance(d_val, str):
                d_val = pd.to_datetime(d_val).date()
            elif hasattr(d_val, "date"):
                d_val = d_val.date()

            existing = (
                self.db.query(DailySales)
                .filter_by(
                    business_id=self.business_id,
                    store_id=row["store_id"],
                    item_id=row["item_id"],
                    date=d_val,
                )
                .first()
            )
            if not existing:
                records.append(
                    DailySales(
                        business_id=self.business_id,
                        store_id=row["store_id"],
                        item_id=row["item_id"],
                        date=d_val,
                        units_sold=int(row["units_sold"]),
                        sell_price=float(row.get("sell_price", 0.0)),
                        has_event=int(row.get("has_event", 0)),
                    )
                )
            if len(records) >= batch_size:
                self.db.bulk_save_objects(records)
                self.db.commit()
                records = []
        if records:
            self.db.bulk_save_objects(records)
            self.db.commit()

    def persist_inventory_snapshots(self, df: pd.DataFrame):
        self.ensure_business()
        for _, row in df.iterrows():
            d_val = row["snapshot_date"]
            if isinstance(d_val, str):
                d_val = pd.to_datetime(d_val).date()
            elif hasattr(d_val, "date"):
                d_val = d_val.date()

            existing = (
                self.db.query(InventorySnapshot)
                .filter_by(
                    business_id=self.business_id,
                    store_id=row["store_id"],
                    item_id=row["item_id"],
                    snapshot_date=d_val,
                )
                .first()
            )
            if existing:
                existing.stock_on_hand = int(row["stock_on_hand"])
                existing.incoming_stock = int(row["incoming_stock"])
                existing.committed_stock = int(row.get("committed_stock", 0))
                existing.unit_cost = float(row.get("unit_cost", 1.0))
                existing.supplier_lead_time_days = int(row.get("supplier_lead_time_days", 7))
            else:
                self.db.add(
                    InventorySnapshot(
                        business_id=self.business_id,
                        store_id=row["store_id"],
                        item_id=row["item_id"],
                        snapshot_date=d_val,
                        stock_on_hand=int(row["stock_on_hand"]),
                        incoming_stock=int(row["incoming_stock"]),
                        committed_stock=int(row.get("committed_stock", 0)),
                        unit_cost=float(row.get("unit_cost", 1.0)),
                        supplier_lead_time_days=int(row.get("supplier_lead_time_days", 7)),
                        min_order_qty=int(row.get("min_order_qty", 10)),
                        order_multiple=int(row.get("order_multiple", 5)),
                    )
                )
        self.db.commit()

    def persist_forecasts(self, run_id: str, model_name: str, horizon_days: int, forecasts: List[Dict]):
        self.ensure_business()
        run = self.db.query(ForecastRun).filter_by(run_id=run_id, business_id=self.business_id).first()
        if not run:
            run = ForecastRun(
                run_id=run_id,
                business_id=self.business_id,
                model_name=model_name,
                horizon_days=horizon_days,
            )
            self.db.add(run)
            self.db.commit()

        self.db.query(DemandForecast).filter_by(run_id=run_id, business_id=self.business_id).delete()

        db_forecasts = []
        for f in forecasts:
            f_date = f["forecast_date"]
            if isinstance(f_date, str):
                f_date = pd.to_datetime(f_date).date()
            elif hasattr(f_date, "date"):
                f_date = f_date.date()

            db_forecasts.append(
                DemandForecast(
                    run_id=run_id,
                    business_id=self.business_id,
                    store_id=f["store_id"],
                    item_id=f["item_id"],
                    forecast_date=f_date,
                    predicted_demand=float(f["predicted_demand"]),
                )
            )
        self.db.bulk_save_objects(db_forecasts)
        self.db.commit()

    def persist_recommendations(self, recommendations: List[Dict]):
        self.ensure_business()
        for r in recommendations:
            r_date = r["recommendation_date"]
            if isinstance(r_date, str):
                r_date = pd.to_datetime(r_date).date()
            elif hasattr(r_date, "date"):
                r_date = r_date.date()

            existing = (
                self.db.query(InventoryRecommendation)
                .filter_by(
                    business_id=self.business_id,
                    store_id=r["store_id"],
                    item_id=r["item_id"],
                    recommendation_date=r_date,
                )
                .first()
            )
            if existing:
                for k, v in r.items():
                    if hasattr(existing, k) and k != "recommendation_date":
                        setattr(existing, k, v)
            else:
                self.db.add(
                    InventoryRecommendation(
                        business_id=self.business_id,
                        store_id=r["store_id"],
                        item_id=r["item_id"],
                        recommendation_date=r_date,
                        current_stock=r["current_stock"],
                        incoming_stock=r["incoming_stock"],
                        committed_stock=r["committed_stock"],
                        inventory_position=r["inventory_position"],
                        lead_time_demand=r["lead_time_demand"],
                        safety_stock=r["safety_stock"],
                        reorder_point=r["reorder_point"],
                        recommended_order_qty=r["recommended_order_qty"],
                        classification=r["classification"],
                        alert_triggered=r["alert_triggered"],
                        alert_status="OPEN" if r["alert_triggered"] else "RESOLVED",
                        policy_notes=r.get("policy_notes", ""),
                    )
                )
        self.db.commit()

    def get_products(self, limit: int = 50, offset: int = 0) -> List[Product]:
        return (
            self.db.query(Product)
            .filter_by(business_id=self.business_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_product(self, item_id: str) -> Optional[Product]:
        return self.db.query(Product).filter_by(business_id=self.business_id, item_id=item_id).first()

    def get_forecasts(self, item_id: str, store_id: Optional[str] = None) -> List[DemandForecast]:
        query = self.db.query(DemandForecast).filter_by(business_id=self.business_id, item_id=item_id)
        if store_id:
            query = query.filter_by(store_id=store_id)
        return query.order_by(DemandForecast.forecast_date.asc()).all()

    def get_latest_inventory(self, limit: int = 50, offset: int = 0) -> List[InventorySnapshot]:
        return (
            self.db.query(InventorySnapshot)
            .filter_by(business_id=self.business_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_inventory_recommendations(
        self, classification: Optional[str] = None, alerts_only: bool = False
    ) -> List[InventoryRecommendation]:
        query = self.db.query(InventoryRecommendation).filter_by(business_id=self.business_id)
        if classification:
            query = query.filter_by(classification=classification)
        if alerts_only:
            query = query.filter_by(alert_triggered=True)
        return query.order_by(desc(InventoryRecommendation.created_at)).all()

    def get_model_evaluations(self) -> List[ModelEvaluation]:
        return self.db.query(ModelEvaluation).order_by(desc(ModelEvaluation.evaluation_date)).all()
