# Multi-Tenant Security, RBAC & Data Isolation

## 1. Authentication Design
The system uses JSON Web Tokens (JWT) signed using HMAC-SHA256 (`HS256`).
Upon calling `POST /auth/login` or `POST /auth/register`, the client receives a token payload containing:
- `sub`: User ID
- `email`: User email
- `business_id`: The business entity that the user belongs to
- `role`: Role (`OWNER`, `MANAGER`, `INVENTORY_STAFF`, or `ANALYST`)
- `exp`: Token expiration timestamp (default: 24 hours)

## 2. Role-Based Access Control (RBAC)
- **`OWNER`**: Full business administrator rights (can register business, manage users, run pipeline, create products, approve POs).
- **`MANAGER`**: Operational manager (can create products, import sales, draft POs, approve POs, reconcile physical stock).
- **`INVENTORY_STAFF`**: Warehouse/store staff (can record stock movements, receive goods against approved POs).
- **`ANALYST`**: Read-only access to products, forecasts, inventory snapshots, and model evaluation metrics.

## 3. Cross-Tenant Data Isolation
Every data table (`products`, `daily_sales`, `inventory_snapshots`, `stock_movements`, `purchase_orders`, `demand_forecasts`, `inventory_recommendations`) contains a `business_id` indexed foreign key.
FastAPI route dependencies extract `current_user.business_id` from the decoded JWT token. Repositories automatically constrain all SQL queries:
`WHERE business_id = :current_user_business_id`.
Direct URL manipulation (e.g., trying to read another company's product ID or purchase order) fails with `404 Not Found`.
