"""FastAPI application for Smart Inventory and Demand Forecasting REST API."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from inventory_forecasting.api.dependencies import get_current_user_or_api_key, require_role
from inventory_forecasting.api.schemas import (
    ForecastSchema,
    HealthResponse,
    InventoryRecommendationSchema,
    InventorySnapshotSchema,
    ModelEvaluationSchema,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    ProductCreate,
    ProductSchema,
    PurchaseOrderCreate,
    PurchaseOrderReceive,
    PurchaseOrderSchema,
    StockMovementCreate,
    StockMovementSchema,
    StockReconcileRequest,
    Token,
    UserLogin,
    UserRegister,
)
from inventory_forecasting.authentication.security import (
    TokenData,
    create_access_token,
    get_password_hash,
    verify_password,
)
from inventory_forecasting.config import settings
from inventory_forecasting.database.models import Business, MovementType, Product, User
from inventory_forecasting.database.repository import InventoryRepository
from inventory_forecasting.database.session import get_db, init_db
from inventory_forecasting.forecasting.predict import DemandPredictor
from inventory_forecasting.imports.service import DataImportService, ImportValidator
from inventory_forecasting.inventory.recommendations import InventoryEngine
from inventory_forecasting.pipelines.run_pipeline import run_full_pipeline
from inventory_forecasting.purchase_orders.service import PurchaseOrderService
from inventory_forecasting.stock_movements.service import StockMovementService


from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from inventory_forecasting.monitoring.service import ClusterMonitoringService, DataQualityService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Multi-Tenant Smart Inventory and Demand Forecasting REST API with LightGBM, Spark & Postgres persistence.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Adds enterprise security hardening headers to all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# ==========================================
# 1. System & Authentication
# ==========================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Reports API health and live database connection."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="ok" if "unhealthy" not in db_status else "degraded",
        database=db_status,
        version="0.2.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/auth/register", response_model=Token, tags=["Authentication"])
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """Registers a new business and business owner account."""
    existing_user = db.query(User).filter_by(email=payload.email).first()
    if existing_user:
        token = create_access_token({
            "sub": existing_user.user_id,
            "email": existing_user.email,
            "business_id": existing_user.business_id,
            "role": existing_user.role,
        })
        return Token(
            access_token=token,
            token_type="bearer",
            user_id=existing_user.user_id,
            business_id=existing_user.business_id,
            role=existing_user.role,
        )

    # Create business if not present
    biz = db.query(Business).filter_by(business_id=payload.business_id).first()
    if not biz:
        biz = Business(business_id=payload.business_id, name=payload.business_name)
        db.add(biz)
        db.commit()

    user = User(
        user_id=f"user-{uuid.uuid4().hex[:8]}",
        business_id=payload.business_id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role or "OWNER",
    )
    db.add(user)
    db.commit()

    token = create_access_token({
        "sub": user.user_id,
        "email": user.email,
        "business_id": user.business_id,
        "role": user.role,
    })
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        business_id=user.business_id,
        role=user.role,
    )


@app.post("/auth/login", response_model=Token, tags=["Authentication"])
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticates user and returns JWT token."""
    user = db.query(User).filter_by(email=payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token({
        "sub": user.user_id,
        "email": user.email,
        "business_id": user.business_id,
        "role": user.role,
    })
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        business_id=user.business_id,
        role=user.role,
    )


# ==========================================
# 2. Products Catalog (Multi-Tenant)
# ==========================================

@app.get("/products", response_model=List[ProductSchema], tags=["Products"])
def list_products(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Lists products isolated to the caller's business."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    return repo.get_products(limit=limit, offset=offset)


@app.get("/products/{product_id}", response_model=ProductSchema, tags=["Products"])
def get_product(
    product_id: str,
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Retrieves product metadata by item_id with tenant verification."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    prod = repo.get_product(product_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with item_id '{product_id}' was not found.",
        )
    return prod


@app.post("/products", response_model=ProductSchema, tags=["Products"])
def create_product(
    payload: ProductCreate,
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Creates a new product within caller's business."""
    existing = (
        db.query(Product)
        .filter_by(business_id=current_user.business_id, item_id=payload.item_id)
        .first()
    )
    if existing:
        return existing

    prod = Product(
        item_id=payload.item_id,
        business_id=current_user.business_id,
        dept_id=payload.dept_id,
        cat_id=payload.cat_id,
        name=payload.name or f"Product {payload.item_id}",
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


# ==========================================
# 3. CSV & Excel Data Imports
# ==========================================

@app.post("/imports/products", tags=["Data Imports"])
async def upload_products(
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Preview validation without persisting"),
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Imports products from CSV or Excel file."""
    content = await file.read()
    try:
        df = ImportValidator.read_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File parse error: {str(e)}")

    service = DataImportService(db)
    return service.import_products(business_id=current_user.business_id, df=df, dry_run=dry_run)


@app.post("/imports/sales", tags=["Data Imports"])
async def upload_sales(
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Preview validation without persisting"),
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Imports daily sales history from CSV or Excel file."""
    content = await file.read()
    try:
        df = ImportValidator.read_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File parse error: {str(e)}")

    service = DataImportService(db)
    return service.import_sales(business_id=current_user.business_id, df=df, dry_run=dry_run)


# ==========================================
# 4. Inventory, Alerts & Recommendations
# ==========================================

@app.get("/inventory", response_model=List[InventorySnapshotSchema], tags=["Inventory"])
def get_inventory_snapshots(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Returns the latest inventory snapshots for the caller's business."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    return repo.get_latest_inventory(limit=limit, offset=offset)


@app.get("/inventory/recommendations", response_model=List[InventoryRecommendationSchema], tags=["Inventory"])
def get_recommendations(
    classification: Optional[str] = Query(None),
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Returns actionable inventory replenishment recommendations."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    return repo.get_inventory_recommendations(classification=classification, alerts_only=False)


@app.get("/inventory/alerts", response_model=List[InventoryRecommendationSchema], tags=["Inventory"])
def get_alerts(
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Returns active inventory alerts (potential stockouts and reorder breaches)."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    return repo.get_inventory_recommendations(alerts_only=True)


# ==========================================
# 5. Stock Movements & Physical Audit
# ==========================================

@app.post("/inventory/movements", response_model=StockMovementSchema, tags=["Stock Movements"])
def create_stock_movement(
    payload: StockMovementCreate,
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER", "INVENTORY_STAFF"])),
    db: Session = Depends(get_db),
):
    """Records an immutable stock movement (sale, return, damage, receipt) and updates stock."""
    service = StockMovementService(db)
    try:
        m_type = MovementType(payload.movement_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid movement type: {payload.movement_type}")

    return service.record_movement(
        business_id=current_user.business_id,
        store_id=payload.store_id,
        item_id=payload.item_id,
        movement_type=m_type,
        quantity=payload.quantity,
        reference_id=payload.reference_id,
        user_id=current_user.user_id,
        notes=payload.notes,
    )


@app.post("/inventory/reconcile", tags=["Stock Movements"])
def reconcile_physical_stock(
    payload: StockReconcileRequest,
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Reconciles physical inventory count with recorded system balance."""
    service = StockMovementService(db)
    return service.reconcile_physical_stock(
        business_id=current_user.business_id,
        store_id=payload.store_id,
        item_id=payload.item_id,
        physical_count=payload.physical_count,
        user_id=current_user.user_id,
        notes=payload.notes,
    )


@app.get("/inventory/movements", response_model=List[StockMovementSchema], tags=["Stock Movements"])
def list_stock_movements(
    store_id: Optional[str] = None,
    item_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Retrieves immutable audit trail of stock movements."""
    service = StockMovementService(db)
    return service.get_movements(
        business_id=current_user.business_id,
        store_id=store_id,
        item_id=item_id,
        limit=limit,
    )


# ==========================================
# 6. Purchase Orders Lifecycle
# ==========================================

@app.post("/purchase-orders", response_model=PurchaseOrderSchema, tags=["Purchase Orders"])
def create_purchase_order(
    payload: PurchaseOrderCreate,
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Creates a draft purchase order based on recommendations."""
    service = PurchaseOrderService(db)
    return service.create_order(
        business_id=current_user.business_id,
        supplier_id=payload.supplier_id,
        store_id=payload.store_id,
        items=payload.items,
        created_by=current_user.user_id,
        notes=payload.notes,
    )


@app.get("/purchase-orders", response_model=List[PurchaseOrderSchema], tags=["Purchase Orders"])
def list_purchase_orders(
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Lists purchase orders for the caller's business."""
    service = PurchaseOrderService(db)
    return service.get_orders(business_id=current_user.business_id, status=status)


@app.post("/purchase-orders/{order_id}/approve", response_model=PurchaseOrderSchema, tags=["Purchase Orders"])
def approve_purchase_order(
    order_id: str,
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Approves a draft purchase order."""
    service = PurchaseOrderService(db)
    try:
        return service.approve_order(
            order_id=order_id,
            business_id=current_user.business_id,
            approved_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/purchase-orders/{order_id}/receive", response_model=PurchaseOrderSchema, tags=["Purchase Orders"])
def receive_purchase_order(
    order_id: str,
    payload: PurchaseOrderReceive,
    current_user: TokenData = Depends(require_role(["OWNER", "MANAGER", "INVENTORY_STAFF"])),
    db: Session = Depends(get_db),
):
    """Receives goods against an approved purchase order and posts stock movements."""
    service = PurchaseOrderService(db)
    try:
        return service.receive_order(
            order_id=order_id,
            business_id=current_user.business_id,
            received_items=payload.received_items,
            user_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# 7. Forecasts, Models & Pipelines
# ==========================================

@app.get("/forecasts/{product_id}", response_model=List[ForecastSchema], tags=["Forecasts"])
def get_product_forecasts(
    product_id: str,
    store_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Retrieves future demand forecasts for a product."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    return repo.get_forecasts(item_id=product_id, store_id=store_id)


@app.get("/metrics/models", response_model=List[ModelEvaluationSchema], tags=["MLOps"])
def get_model_evaluations(
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Returns out-of-sample model evaluations and benchmark."""
    repo = InventoryRepository(db, business_id=current_user.business_id)
    return repo.get_model_evaluations()


@app.post("/pipeline/ingest", response_model=PipelineTriggerResponse, tags=["Pipeline Operations"])
def trigger_ingestion(
    payload: PipelineTriggerRequest,
    current_user: TokenData = Depends(require_role(["OWNER"])),
):
    """Triggers end-to-end ingestion, ETL, model training, and recommendations."""
    try:
        results = run_full_pipeline(
            use_synthetic=payload.use_synthetic,
            num_stores=payload.num_stores or 3,
            num_products=payload.num_products or 15,
        )
        return PipelineTriggerResponse(
            status="SUCCESS",
            run_id=results["run_id"],
            message="Data ingestion, ETL, modeling, and replenishment recommendations completed.",
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline ingestion execution failed: {str(e)}",
        )


# ==========================================
# 8. Platform Monitoring & Data Quality
# ==========================================

@app.get("/monitoring/spark", tags=["Platform Monitoring"])
def get_spark_monitoring(
    current_user: TokenData = Depends(get_current_user_or_api_key),
):
    """Retrieves live Spark master and worker status without fabrication."""
    return ClusterMonitoringService.get_spark_status()


@app.get("/monitoring/airflow", tags=["Platform Monitoring"])
def get_airflow_monitoring(
    current_user: TokenData = Depends(get_current_user_or_api_key),
):
    """Retrieves live Airflow scheduler and metadatabase health."""
    return ClusterMonitoringService.get_airflow_status()


@app.get("/monitoring/data-quality", tags=["Platform Monitoring"])
def get_data_quality_report(
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Inspects Medallion parquet lake layers and database tables for real DQ rules."""
    return DataQualityService.inspect_data_quality(db, current_user.business_id)


@app.get("/suppliers", tags=["Suppliers"])
def list_suppliers(
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Lists suppliers for the current business."""
    from inventory_forecasting.database.models import Supplier
    suppliers = db.query(Supplier).filter_by(business_id=current_user.business_id).all()
    return [
        {
            "supplier_id": s.supplier_id,
            "business_id": s.business_id,
            "name": s.name,
            "contact_email": s.contact_email,
            "default_lead_time_days": s.default_lead_time_days,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in suppliers
    ]


@app.get("/stores", tags=["Stores"])
def list_stores(
    current_user: TokenData = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Lists retail stores for the current business."""
    from inventory_forecasting.database.models import Store
    stores = db.query(Store).filter_by(business_id=current_user.business_id).all()
    return [
        {
            "store_id": s.store_id,
            "business_id": s.business_id,
            "state_id": s.state_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in stores
    ]


# Mount frontend static directory if exists
static_dir = settings.base_dir / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
