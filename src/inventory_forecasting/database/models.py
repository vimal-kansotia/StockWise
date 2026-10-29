"""SQLAlchemy models for multi-tenant businesses, users, stock movements, and purchase orders."""

from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    Index,
    Text,
    Enum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    INVENTORY_STAFF = "INVENTORY_STAFF"
    ANALYST = "ANALYST"


class MovementType(str, enum.Enum):
    SALE = "SALE"
    CUSTOMER_RETURN = "CUSTOMER_RETURN"
    SUPPLIER_RECEIPT = "SUPPLIER_RECEIPT"
    SUPPLIER_RETURN = "SUPPLIER_RETURN"
    DAMAGE_SPOILAGE = "DAMAGE_SPOILAGE"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"
    STOCK_RECONCILIATION = "STOCK_RECONCILIATION"


class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ORDERED = "ORDERED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class Business(Base):
    __tablename__ = "businesses"

    business_id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="business", cascade="all, delete-orphan")
    stores = relationship("Store", back_populates="business", cascade="all, delete-orphan")
    suppliers = relationship("Supplier", back_populates="business", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="business", cascade="all, delete-orphan")
    movements = relationship("StockMovement", back_populates="business", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(String(32), default=UserRole.MANAGER.value, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="users")


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    contact_email = Column(String(128), nullable=True)
    default_lead_time_days = Column(Integer, default=7)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="suppliers")


class Product(Base):
    __tablename__ = "products"

    item_id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    dept_id = Column(String(64), nullable=False, index=True)
    cat_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="products")
    sales = relationship("DailySales", back_populates="product", cascade="all, delete-orphan")
    forecasts = relationship("DemandForecast", back_populates="product", cascade="all, delete-orphan")
    inventory = relationship("InventorySnapshot", back_populates="product", cascade="all, delete-orphan")
    recommendations = relationship("InventoryRecommendation", back_populates="product", cascade="all, delete-orphan")
    movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")


class Store(Base):
    __tablename__ = "stores"

    store_id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    state_id = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="stores")
    sales = relationship("DailySales", back_populates="store", cascade="all, delete-orphan")
    forecasts = relationship("DemandForecast", back_populates="store", cascade="all, delete-orphan")
    inventory = relationship("InventorySnapshot", back_populates="store", cascade="all, delete-orphan")
    recommendations = relationship("InventoryRecommendation", back_populates="store", cascade="all, delete-orphan")
    movements = relationship("StockMovement", back_populates="store", cascade="all, delete-orphan")


class DailySales(Base):
    __tablename__ = "daily_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    store_id = Column(String(64), ForeignKey("stores.store_id"), nullable=False)
    item_id = Column(String(64), ForeignKey("products.item_id"), nullable=False)
    date = Column(Date, nullable=False)
    units_sold = Column(Integer, nullable=False, default=0)
    sell_price = Column(Float, nullable=False, default=0.0)
    has_event = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="sales")
    store = relationship("Store", back_populates="sales")

    __table_args__ = (
        Index("idx_sales_b_store_item_date", "business_id", "store_id", "item_id", "date", unique=True),
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    store_id = Column(String(64), ForeignKey("stores.store_id"), nullable=False)
    item_id = Column(String(64), ForeignKey("products.item_id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    stock_on_hand = Column(Integer, nullable=False, default=0)
    incoming_stock = Column(Integer, nullable=False, default=0)
    committed_stock = Column(Integer, nullable=False, default=0)
    unit_cost = Column(Float, nullable=False, default=1.0)
    supplier_lead_time_days = Column(Integer, nullable=False, default=7)
    min_order_qty = Column(Integer, nullable=False, default=10)
    order_multiple = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="inventory")
    store = relationship("Store", back_populates="inventory")

    __table_args__ = (
        Index("idx_inv_b_store_item_date", "business_id", "store_id", "item_id", "snapshot_date", unique=True),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, index=True)
    store_id = Column(String(64), ForeignKey("stores.store_id"), nullable=False)
    item_id = Column(String(64), ForeignKey("products.item_id"), nullable=False)
    movement_type = Column(String(32), nullable=False)  # MovementType enum
    quantity = Column(Integer, nullable=False)  # Positive for addition, negative for reduction
    reference_id = Column(String(64), nullable=True)  # PO id, Order id, etc.
    user_id = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    business = relationship("Business", back_populates="movements")
    product = relationship("Product", back_populates="movements")
    store = relationship("Store", back_populates="movements")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    order_id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, index=True)
    supplier_id = Column(String(64), ForeignKey("suppliers.supplier_id"), nullable=False)
    store_id = Column(String(64), ForeignKey("stores.store_id"), nullable=False)
    status = Column(String(32), default=OrderStatus.DRAFT.value, nullable=False)
    created_by = Column(String(64), nullable=True)
    approved_by = Column(String(64), nullable=True)
    total_cost = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), ForeignKey("purchase_orders.order_id"), nullable=False)
    item_id = Column(String(64), ForeignKey("products.item_id"), nullable=False)
    recommended_qty = Column(Integer, nullable=False)
    ordered_qty = Column(Integer, nullable=False)
    received_qty = Column(Integer, default=0)
    unit_cost = Column(Float, default=0.0)

    order = relationship("PurchaseOrder", back_populates="items")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    run_id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    model_name = Column(String(64), nullable=False)
    horizon_days = Column(Integer, nullable=False)
    status = Column(String(32), default="COMPLETED")
    metadata_json = Column(Text, nullable=True)

    forecasts = relationship("DemandForecast", back_populates="run", cascade="all, delete-orphan")


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("forecast_runs.run_id"), nullable=False)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    store_id = Column(String(64), ForeignKey("stores.store_id"), nullable=False)
    item_id = Column(String(64), ForeignKey("products.item_id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    predicted_demand = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    run = relationship("ForecastRun", back_populates="forecasts")
    product = relationship("Product", back_populates="forecasts")
    store = relationship("Store", back_populates="forecasts")

    __table_args__ = (
        Index("idx_forecast_b_run_store_item_date", "business_id", "run_id", "store_id", "item_id", "forecast_date", unique=True),
    )


class InventoryRecommendation(Base):
    __tablename__ = "inventory_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String(64), ForeignKey("businesses.business_id"), nullable=False, default="default_corp", index=True)
    store_id = Column(String(64), ForeignKey("stores.store_id"), nullable=False)
    item_id = Column(String(64), ForeignKey("products.item_id"), nullable=False)
    recommendation_date = Column(Date, nullable=False)
    current_stock = Column(Integer, nullable=False)
    incoming_stock = Column(Integer, nullable=False)
    committed_stock = Column(Integer, nullable=False)
    inventory_position = Column(Integer, nullable=False)
    lead_time_demand = Column(Float, nullable=False)
    safety_stock = Column(Float, nullable=False)
    reorder_point = Column(Float, nullable=False)
    recommended_order_qty = Column(Integer, nullable=False)
    classification = Column(String(32), nullable=False)
    alert_triggered = Column(Boolean, default=False)
    alert_status = Column(String(32), default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED
    policy_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="recommendations")
    store = relationship("Store", back_populates="recommendations")

    __table_args__ = (
        Index("idx_rec_b_store_item_date", "business_id", "store_id", "item_id", "recommendation_date", unique=True),
    )


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(64), nullable=False)
    evaluation_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    mae = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    wape = Column(Float, nullable=False)
    bias = Column(Float, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    validation_split = Column(String(64), nullable=False)
    feature_count = Column(Integer, default=0)
    is_champion = Column(Boolean, default=False)
    parameters_json = Column(Text, nullable=True)


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"

    run_id = Column(String(64), primary_key=True)
    pipeline_type = Column(String(64), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="RUNNING")
    records_processed = Column(Integer, default=0)
    details_json = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
