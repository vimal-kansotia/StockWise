"""Updated Pydantic schemas supporting multi-tenant auth, stock movements, and purchase orders."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    timestamp: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    business_id: str
    role: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    business_id: str
    business_name: str
    role: Optional[str] = "OWNER"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    business_id: str
    dept_id: str
    cat_id: str
    name: Optional[str] = None
    created_at: Optional[datetime] = None


class ProductCreate(BaseModel):
    item_id: str
    dept_id: str
    cat_id: str
    name: Optional[str] = None


class ForecastSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: str
    item_id: str
    forecast_date: date
    predicted_demand: float


class InventorySnapshotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: str
    item_id: str
    snapshot_date: date
    stock_on_hand: int
    incoming_stock: int
    committed_stock: int
    unit_cost: float
    supplier_lead_time_days: int
    min_order_qty: int
    order_multiple: int


class InventoryRecommendationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: str
    item_id: str
    recommendation_date: date
    current_stock: int
    incoming_stock: int
    committed_stock: int
    inventory_position: int
    lead_time_demand: float
    safety_stock: float
    reorder_point: float
    recommended_order_qty: int
    classification: str
    alert_triggered: bool
    alert_status: Optional[str] = "OPEN"
    policy_notes: Optional[str] = None


class StockMovementCreate(BaseModel):
    store_id: str
    item_id: str
    movement_type: str
    quantity: int
    reference_id: Optional[str] = None
    notes: Optional[str] = None


class StockMovementSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: str
    store_id: str
    item_id: str
    movement_type: str
    quantity: int
    reference_id: Optional[str] = None
    user_id: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime


class StockReconcileRequest(BaseModel):
    store_id: str
    item_id: str
    physical_count: int
    notes: Optional[str] = None


class PurchaseOrderItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    recommended_qty: int
    ordered_qty: int
    received_qty: int
    unit_cost: float


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    store_id: str
    items: List[Dict[str, Any]]
    notes: Optional[str] = None


class PurchaseOrderReceive(BaseModel):
    received_items: List[Dict[str, Any]]


class PurchaseOrderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    business_id: str
    supplier_id: str
    store_id: str
    status: str
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    total_cost: float
    notes: Optional[str] = None
    created_at: datetime
    items: List[PurchaseOrderItemSchema] = []


class ModelEvaluationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_name: str
    evaluation_date: datetime
    mae: float
    rmse: float
    wape: float
    bias: float
    horizon_days: int
    validation_split: str
    feature_count: int
    is_champion: bool


class PipelineTriggerRequest(BaseModel):
    use_synthetic: bool = True
    num_stores: Optional[int] = 3
    num_products: Optional[int] = 15


class PipelineTriggerResponse(BaseModel):
    status: str
    run_id: str
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None
