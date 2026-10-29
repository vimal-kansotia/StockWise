"""Business CSV and Excel file import parsing, schema validation, and persistence."""

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pandas as pd
from sqlalchemy.orm import Session
from inventory_forecasting.database.models import DailySales, InventorySnapshot, Product, Supplier


class ImportValidator:
    """Validates CSV and Excel files, data types, formats, and business identifiers."""

    @staticmethod
    def read_file(file_contents: bytes, filename: str) -> pd.DataFrame:
        """Reads file safely without executing macros or formulas."""
        if filename.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_contents))
        elif filename.endswith((".xls", ".xlsx")):
            return pd.read_excel(io.BytesIO(file_contents), engine="openpyxl")
        else:
            raise ValueError(f"Unsupported file extension for '{filename}'. Use .csv or .xlsx.")

    @staticmethod
    def validate_products(df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        required = ["item_id", "dept_id", "cat_id"]
        errors = []
        valid_rows = []

        for idx, row in df.iterrows():
            row_num = idx + 2
            missing = [c for c in required if c not in row or pd.isna(row[c])]
            if missing:
                errors.append(f"Row {row_num}: Missing required columns: {missing}")
                continue
            valid_rows.append({
                "item_id": str(row["item_id"]).strip(),
                "dept_id": str(row["dept_id"]).strip(),
                "cat_id": str(row["cat_id"]).strip(),
                "name": str(row.get("name", f"Product {row['item_id']}")).strip(),
            })
        return valid_rows, errors

    @staticmethod
    def validate_sales(df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        required = ["store_id", "item_id", "date", "units_sold"]
        errors = []
        valid_rows = []

        for idx, row in df.iterrows():
            row_num = idx + 2
            missing = [c for c in required if c not in row or pd.isna(row[c])]
            if missing:
                errors.append(f"Row {row_num}: Missing required sales fields: {missing}")
                continue
            try:
                d_val = pd.to_datetime(row["date"]).date()
                u_val = int(row["units_sold"])
                p_val = float(row.get("sell_price", 0.0))
            except Exception as e:
                errors.append(f"Row {row_num}: Invalid number or date format: {e}")
                continue

            valid_rows.append({
                "store_id": str(row["store_id"]).strip(),
                "item_id": str(row["item_id"]).strip(),
                "date": d_val,
                "units_sold": u_val,
                "sell_price": max(0.0, p_val),
                "has_event": int(row.get("has_event", 0)),
            })
        return valid_rows, errors


class DataImportService:
    def __init__(self, db: Session):
        self.db = db

    def import_products(self, business_id: str, df: pd.DataFrame, dry_run: bool = False) -> Dict[str, Any]:
        valid_rows, errors = ImportValidator.validate_products(df)
        if dry_run or not valid_rows:
            return {
                "dry_run": dry_run,
                "total_rows": len(df),
                "valid_rows": len(valid_rows),
                "rejected_rows": len(errors),
                "errors": errors[:50],
            }

        # Transactional upsert
        accepted = 0
        for r in valid_rows:
            existing = self.db.query(Product).filter_by(business_id=business_id, item_id=r["item_id"]).first()
            if not existing:
                self.db.add(Product(
                    business_id=business_id,
                    item_id=r["item_id"],
                    dept_id=r["dept_id"],
                    cat_id=r["cat_id"],
                    name=r["name"],
                ))
                accepted += 1
            else:
                existing.dept_id = r["dept_id"]
                existing.cat_id = r["cat_id"]
                existing.name = r["name"]
                accepted += 1

        self.db.commit()
        return {
            "status": "SUCCESS",
            "business_id": business_id,
            "total_rows": len(df),
            "accepted_rows": accepted,
            "errors": errors[:50],
        }

    def import_sales(self, business_id: str, df: pd.DataFrame, dry_run: bool = False) -> Dict[str, Any]:
        valid_rows, errors = ImportValidator.validate_sales(df)
        if dry_run or not valid_rows:
            return {
                "dry_run": dry_run,
                "total_rows": len(df),
                "valid_rows": len(valid_rows),
                "rejected_rows": len(errors),
                "errors": errors[:50],
            }

        accepted = 0
        for r in valid_rows:
            existing = (
                self.db.query(DailySales)
                .filter_by(business_id=business_id, store_id=r["store_id"], item_id=r["item_id"], date=r["date"])
                .first()
            )
            if existing:
                existing.units_sold = r["units_sold"]
                existing.sell_price = r["sell_price"]
            else:
                self.db.add(DailySales(
                    business_id=business_id,
                    store_id=r["store_id"],
                    item_id=r["item_id"],
                    date=r["date"],
                    units_sold=r["units_sold"],
                    sell_price=r["sell_price"],
                    has_event=r["has_event"],
                ))
            accepted += 1

        self.db.commit()
        return {
            "status": "SUCCESS",
            "business_id": business_id,
            "total_rows": len(df),
            "accepted_rows": accepted,
            "errors": errors[:50],
        }
