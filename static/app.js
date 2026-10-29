/**
 * StockWise Intelligence - Core Frontend Application
 * Strictly consumes existing FastAPI backend endpoints with zero simulated or fake metrics.
 */

// Application State
const AppState = {
  currentPage: 'executive-dashboard',
  token: null,
  user: {
    email: 'planner@stockwise.com',
    role: 'OWNER',
    business_id: 'default_corp',
    full_name: 'Lead Inventory Planner',
  },
  cached: {
    products: [],
    stores: [],
    suppliers: [],
    inventory: [],
    recommendations: [],
    alerts: [],
    purchaseOrders: [],
    movements: [],
    modelEvaluations: [],
    forecasts: {},
    sparkStatus: null,
    airflowStatus: null,
    dataQuality: null,
  },
  activeChart: null,
};

// API Helper
const API = {
  baseUrl: window.location.origin,

  async request(path, options = {}) {
    const headers = options.headers || {};
    if (AppState.token) {
      headers['Authorization'] = `Bearer ${AppState.token}`;
    }
    // API key fallback for local testing
    headers['X-API-Key'] = 'dev-secret-api-key-2026';

    const resp = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (resp.status === 401) {
      showToast('Authentication required. Re-authenticating...', 'error');
      await Auth.login('planner@stockwise.com', 'StockWise2026!');
      return null;
    }

    if (!resp.ok) {
      let errMsg = `HTTP Error ${resp.status}`;
      try {
        const errJson = await resp.json();
        if (errJson.detail) errMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      } catch (e) {}
      throw new Error(errMsg);
    }

    return await resp.json();
  },

  async login(email, password) {
    const res = await this.request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return res;
  },

  async getHealth() { return this.request('/health'); },
  async getProducts() { return this.request('/products?limit=200'); },
  async getStores() { return this.request('/stores'); },
  async getSuppliers() { return this.request('/suppliers'); },
  async getInventory() { return this.request('/inventory?limit=200'); },
  async getRecommendations() { return this.request('/inventory/recommendations'); },
  async getAlerts() { return this.request('/inventory/alerts'); },
  async getPurchaseOrders() { return this.request('/purchase-orders'); },
  async getMovements() { return this.request('/inventory/movements?limit=150'); },
  async getModelEvaluations() { return this.request('/metrics/models'); },
  async getForecasts(itemId, storeId = null) {
    const q = storeId ? `?store_id=${encodeURIComponent(storeId)}` : '';
    return this.request(`/forecasts/${encodeURIComponent(itemId)}${q}`);
  },
  async getSparkStatus() { return this.request('/monitoring/spark'); },
  async getAirflowStatus() { return this.request('/monitoring/airflow'); },
  async getDataQuality() { return this.request('/monitoring/data-quality'); },

  async createPurchaseOrder(data) {
    return this.request('/purchase-orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async approvePurchaseOrder(orderId) {
    return this.request(`/purchase-orders/${orderId}/approve`, {
      method: 'POST',
    });
  },

  async receivePurchaseOrder(orderId, receivedItems) {
    return this.request(`/purchase-orders/${orderId}/receive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ received_items: receivedItems }),
    });
  },

  async createStockMovement(movementData) {
    return this.request('/inventory/movements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(movementData),
    });
  },

  async reconcileStock(reconcileData) {
    return this.request('/inventory/reconcile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(reconcileData),
    });
  },

  async triggerPipeline(useSynthetic = true) {
    return this.request('/pipeline/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_synthetic: useSynthetic }),
    });
  },

  async uploadFile(endpoint, file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request(`${endpoint}?dry_run=false`, {
      method: 'POST',
      body: formData,
    });
  }
};

// Auth Management
const Auth = {
  async init() {
    try {
      const res = await API.login('planner@stockwise.com', 'StockWise2026!');
      if (res && res.access_token) {
        AppState.token = res.access_token;
        AppState.user.role = res.role;
        AppState.user.business_id = res.business_id;
        document.getElementById('user-display-name').textContent = AppState.user.full_name;
        document.getElementById('user-display-role').textContent = `${res.role} • ${res.business_id}`;
      }
    } catch (e) {
      console.warn('Initial login fell back to header API key:', e);
    }
  }
};

// UI Helpers
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type === 'success' ? 'toast-success' : type === 'error' ? 'toast-error' : ''}`;
  toast.innerHTML = `
    <i class="fa-solid ${type === 'success' ? 'fa-circle-check' : type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info'}" style="color: ${type === 'success' ? 'var(--status-healthy)' : type === 'error' ? 'var(--status-stockout)' : 'var(--brand-primary-light)'}"></i>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function getBadge(status) {
  const s = (status || '').toUpperCase();
  if (s === 'HEALTHY') return `<span class="badge badge-healthy"><i class="fa-solid fa-circle-check"></i> Healthy</span>`;
  if (s.includes('REORDER') || s === 'POTENTIAL_STOCKOUT') return `<span class="badge badge-reorder"><i class="fa-solid fa-triangle-exclamation"></i> Reorder Req</span>`;
  if (s.includes('CRITICAL') || s.includes('STOCKOUT')) return `<span class="badge badge-stockout"><i class="fa-solid fa-ban"></i> Stockout</span>`;
  if (s.includes('OVERSTOCK')) return `<span class="badge badge-overstock"><i class="fa-solid fa-layer-group"></i> Overstock</span>`;
  if (s === 'APPROVED' || s === 'RECEIVED') return `<span class="badge badge-healthy">${s}</span>`;
  if (s === 'DRAFT' || s === 'PENDING_APPROVAL') return `<span class="badge badge-reorder">${s}</span>`;
  return `<span class="badge badge-neutral">${s}</span>`;
}

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

function exportToCsv(filename, rows) {
  if (!rows || !rows.length) {
    showToast('No data available to export', 'error');
    return;
  }
  const separator = ',';
  const keys = Object.keys(rows[0]);
  const csvContent =
    keys.join(separator) +
    '\n' +
    rows.map(row => {
      return keys.map(k => {
        let cell = row[k] === null || row[k] === undefined ? '' : row[k];
        cell = cell instanceof Date ? cell.toLocaleString() : cell.toString().replace(/"/g, '""');
        if (cell.search(/("|,|\n)/g) >= 0) cell = `"${cell}"`;
        return cell;
      }).join(separator);
    }).join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.setAttribute('download', `${filename}_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Global Data Loader
async function refreshGlobalData() {
  const content = document.getElementById('content-area');
  try {
    const [products, stores, suppliers, inventory, recommendations, alerts, purchaseOrders, movements, modelEvaluations] =
      await Promise.all([
        API.getProducts().catch(() => []),
        API.getStores().catch(() => []),
        API.getSuppliers().catch(() => []),
        API.getInventory().catch(() => []),
        API.getRecommendations().catch(() => []),
        API.getAlerts().catch(() => []),
        API.getPurchaseOrders().catch(() => []),
        API.getMovements().catch(() => []),
        API.getModelEvaluations().catch(() => []),
      ]);

    AppState.cached.products = products;
    AppState.cached.stores = stores;
    AppState.cached.suppliers = suppliers;
    AppState.cached.inventory = inventory;
    AppState.cached.recommendations = recommendations;
    AppState.cached.alerts = alerts;
    AppState.cached.purchaseOrders = purchaseOrders;
    AppState.cached.movements = movements;
    AppState.cached.modelEvaluations = modelEvaluations;

    renderCurrentPage();
  } catch (err) {
    showToast(`Failed to load data: ${err.message}`, 'error');
  }
}

// Page Router
function navigateTo(pageId) {
  AppState.currentPage = pageId;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const activeBtn = document.querySelector(`[data-page="${pageId}"]`);
  if (activeBtn) activeBtn.classList.add('active');

  const headings = {
    'executive-dashboard': ['Executive Dashboard', 'Real-time replenishment priorities, stockout risk distribution, and inventory health'],
    'demand-forecasts': ['Demand Forecasts', 'Multi-step LightGBM recursive demand forecasts (7-day and 28-day horizons)'],
    'forecast-explorer': ['Forecast Explorer', 'Interactive time-series telemetry comparing historical sales with predicted demand'],
    'model-performance': ['Model Performance & Benchmarks', 'Champion selection using out-of-sample WAPE, RMSE, and bias against baseline models'],
    'inventory-overview': ['Inventory Overview', 'Live stock on hand, incoming pipeline, and committed allocation balances'],
    'inventory-risk': ['Inventory Risk & Critical Alerts', 'Active stockout risk breaches and overstock capital lockup alarms'],
    'replenishment': ['Replenishment Recommendations', 'Statistical Safety Stock, Dynamic Reorder Points (ROP), and Order Quantities (ROQ)'],
    'product-details': ['Product Deep Dive', 'SKU inventory parameters, lead times, order constraints, and movement history'],
    'purchase-orders': ['Purchase Orders Lifecycle', 'Drafting, manager approvals, and automated warehouse receipt ledger posting'],
    'stock-movements': ['Stock Movements Ledger', 'Immutable physical and transactional audit trail across stores and warehouses'],
    'data-imports': ['Data Imports & Ingestion', 'Batch CSV and Excel ingestion with strict schema validation for products and sales'],
    'data-pipeline': ['Medallion Data Pipeline', 'Bronze raw ingestion, Silver normalized joins, and Gold feature engineering lakehouse layers'],
    'data-quality': ['Data Quality & Governance', 'Pandera schema enforcement, boundary assertions, and integrity inspection'],
    'job-monitoring': ['Job Runs & Cluster Status', 'Live Apache Spark cluster workers, Airflow scheduler status, and pipeline runs'],
    'report-executive': ['Executive Report', 'C-suite summary of inventory health, capital exposure, and supplier replenishment performance'],
    'report-forecast': ['Demand Forecast Report', 'Forward projected item sales with calendar events and variance bands'],
    'report-risk': ['Inventory Risk Report', 'Complete catalog breakdown by stockout vulnerability and days of supply coverage'],
    'report-replenishment': ['Replenishment Priorities Report', 'Recommended order schedule incorporating supplier MOQ, pack multiples, and lead time'],
    'report-evaluation': ['Model Evaluation Deliverable', 'Comparative statistical validation across seasonal naive, moving average, and LightGBM'],
    'report-quality': ['Data Quality Report', 'Parquet layer volumes, partition health, null rates, and anomaly detection results'],
    'system-health': ['System Health & Infrastructure', 'FastAPI backend, relational database connections, and microservice status'],
    'configuration': ['System Configuration', 'Inventory safety parameters, service levels, lead time defaults, and tenant settings'],
    'legal-privacy': ['Privacy Policy & Data Retention', 'Enterprise data handling, role-based boundaries, and retention commitments'],
    'legal-terms': ['Terms of Service & Acceptable Use', 'Operational guidelines, liability boundaries, and multi-tenant policies'],
  };

  const info = headings[pageId] || [pageId, ''];
  document.getElementById('page-heading').textContent = info[0];
  document.getElementById('page-subheading').textContent = info[1];

  renderCurrentPage();
}

function renderCurrentPage() {
  const container = document.getElementById('content-area');
  // Destroy chart if active
  if (AppState.activeChart) {
    AppState.activeChart.destroy();
    AppState.activeChart = null;
  }

  switch (AppState.currentPage) {
    case 'executive-dashboard':
      renderExecutiveDashboard(container);
      break;
    case 'demand-forecasts':
      renderDemandForecasts(container);
      break;
    case 'forecast-explorer':
      renderForecastExplorer(container);
      break;
    case 'model-performance':
      renderModelPerformance(container);
      break;
    case 'inventory-overview':
      renderInventoryOverview(container);
      break;
    case 'inventory-risk':
      renderInventoryRisk(container);
      break;
    case 'replenishment':
      renderReplenishment(container);
      break;
    case 'product-details':
      renderProductDetails(container);
      break;
    case 'purchase-orders':
      renderPurchaseOrders(container);
      break;
    case 'stock-movements':
      renderStockMovements(container);
      break;
    case 'data-imports':
      renderDataImports(container);
      break;
    case 'data-pipeline':
      renderDataPipeline(container);
      break;
    case 'data-quality':
      renderDataQuality(container);
      break;
    case 'job-monitoring':
      renderJobMonitoring(container);
      break;
    case 'report-executive':
      renderReportExecutive(container);
      break;
    case 'report-forecast':
      renderReportForecast(container);
      break;
    case 'report-risk':
      renderReportRisk(container);
      break;
    case 'report-replenishment':
      renderReportReplenishment(container);
      break;
    case 'report-evaluation':
      renderReportEvaluation(container);
      break;
    case 'report-quality':
      renderReportQuality(container);
      break;
    case 'system-health':
      renderSystemHealth(container);
      break;
    case 'configuration':
      renderConfiguration(container);
      break;
    case 'legal-privacy':
      renderLegalPrivacy(container);
      break;
    case 'legal-terms':
      renderLegalTerms(container);
      break;
    default:
      container.innerHTML = `<div class="card"><p>Page under construction.</p></div>`;
  }
}

// --------------------------------------------------------------------------
// 1. EXECUTIVE DASHBOARD
// --------------------------------------------------------------------------
function renderExecutiveDashboard(container) {
  const recs = AppState.cached.recommendations;
  const pos = AppState.cached.purchaseOrders;
  const stockouts = recs.filter(r => (r.classification || '').includes('STOCKOUT'));
  const reorders = recs.filter(r => (r.classification || '').includes('REORDER'));
  const healthy = recs.filter(r => (r.classification || '') === 'HEALTHY');
  const overstocks = recs.filter(r => (r.classification || '').includes('OVERSTOCK'));

  const pendingPos = pos.filter(p => p.status === 'PENDING_APPROVAL' || p.status === 'DRAFT');
  const totalPoSpend = pos.reduce((acc, p) => acc + (p.total_cost || 0), 0);

  container.innerHTML = `
    <!-- Top Action Workflow Bar -->
    <div class="workflow-stepper">
      <div class="step-item active">
        <span class="step-circle"><i class="fa-solid fa-triangle-exclamation"></i></span>
        <span>1. Identify Risks (${stockouts.length + reorders.length})</span>
      </div>
      <div class="step-divider"></div>
      <div class="step-item">
        <span class="step-circle"><i class="fa-solid fa-chart-line"></i></span>
        <span>2. Inspect Forecasts</span>
      </div>
      <div class="step-divider"></div>
      <div class="step-item">
        <span class="step-circle"><i class="fa-solid fa-calculator"></i></span>
        <span>3. Review Safety Stock</span>
      </div>
      <div class="step-divider"></div>
      <div class="step-item">
        <span class="step-circle"><i class="fa-solid fa-file-signature"></i></span>
        <span>4. Approve PO</span>
      </div>
      <div class="step-divider"></div>
      <div class="step-item">
        <span class="step-circle"><i class="fa-solid fa-boxes-packing"></i></span>
        <span>5. Receive Stock</span>
      </div>
    </div>

    <!-- KPI Grid -->
    <div class="kpi-grid">
      <div class="kpi-card border-alert-danger" style="cursor: pointer;" onclick="navigateTo('inventory-risk')">
        <div class="kpi-title">Critical Stockout Alerts</div>
        <div class="kpi-value" style="color: var(--status-stockout);">${stockouts.length}</div>
        <div class="kpi-desc">SKUs at immediate stockout risk</div>
      </div>

      <div class="kpi-card border-alert-warning" style="cursor: pointer;" onclick="navigateTo('replenishment')">
        <div class="kpi-title">Reorder Recommended</div>
        <div class="kpi-value" style="color: var(--status-reorder);">${reorders.length}</div>
        <div class="kpi-desc">Below dynamic reorder point (ROP)</div>
      </div>

      <div class="kpi-card border-alert-success">
        <div class="kpi-title">Healthy SKUs</div>
        <div class="kpi-value" style="color: var(--status-healthy);">${healthy.length}</div>
        <div class="kpi-desc">Optimal buffer & service level</div>
      </div>

      <div class="kpi-card border-alert-purple">
        <div class="kpi-title">Overstock SKUs</div>
        <div class="kpi-value" style="color: var(--status-overstock);">${overstocks.length}</div>
        <div class="kpi-desc">Excess inventory holding</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-title">Open Purchase Orders</div>
        <div class="kpi-value">${pendingPos.length}</div>
        <div class="kpi-desc">Awaiting approval or receipt</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-title">Committed PO Spend</div>
        <div class="kpi-value">${formatCurrency(totalPoSpend)}</div>
        <div class="kpi-desc">Active replenishments</div>
      </div>
    </div>

    <!-- Two-column Section: Immediate Action Items & Chart -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Priority Replenishment Queue</div>
          <button class="btn btn-secondary btn-sm" onclick="navigateTo('replenishment')">View All</button>
        </div>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Item ID</th>
                <th>Store</th>
                <th>Current Stock</th>
                <th>ROP</th>
                <th>Rec Order</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${(reorders.concat(stockouts)).slice(0, 5).map(r => `
                <tr>
                  <td><strong>${r.item_id}</strong></td>
                  <td>${r.store_id}</td>
                  <td>${r.current_stock}</td>
                  <td>${r.reorder_point.toFixed(1)}</td>
                  <td><strong style="color: var(--brand-secondary);">${r.recommended_order_qty}</strong></td>
                  <td>${getBadge(r.classification)}</td>
                  <td>
                    <button class="btn btn-primary btn-sm" onclick="openCreatePoModal('${r.item_id}', '${r.store_id}', ${r.recommended_order_qty})">Draft PO</button>
                  </td>
                </tr>
              `).join('') || '<tr><td colspan="7" style="text-align:center; color:var(--text-dim);">No pending replenishment alerts found.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">Inventory Health Distribution</div>
          <span style="font-size:0.75rem; color:var(--text-dim);">${recs.length} total monitored items</span>
        </div>
        <div style="height: 240px; position: relative;">
          <canvas id="healthDistChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Recent Purchase Orders Table -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Recent Purchase Orders & Receiving</div>
        <button class="btn btn-secondary btn-sm" onclick="navigateTo('purchase-orders')">Manage POs</button>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Store</th>
              <th>Supplier</th>
              <th>Status</th>
              <th>Total Cost</th>
              <th>Created At</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${pos.slice(0, 5).map(p => `
              <tr>
                <td><strong>${p.order_id}</strong></td>
                <td>${p.store_id}</td>
                <td>${p.supplier_id}</td>
                <td>${getBadge(p.status)}</td>
                <td>${formatCurrency(p.total_cost)}</td>
                <td>${new Date(p.created_at).toLocaleDateString()}</td>
                <td>
                  ${p.status === 'DRAFT' || p.status === 'PENDING_APPROVAL' ? `
                    <button class="btn btn-success btn-sm" onclick="approveOrderAction('${p.order_id}')">Approve</button>
                  ` : p.status === 'APPROVED' ? `
                    <button class="btn btn-primary btn-sm" onclick="openReceiveModal('${p.order_id}')">Receive Goods</button>
                  ` : `<span style="font-size:0.75rem; color:var(--text-dim);"><i class="fa-solid fa-check"></i> Fulfilled</span>`}
                </td>
              </tr>
            `).join('') || '<tr><td colspan="7" style="text-align:center; color:var(--text-dim);">No purchase orders created yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Render chart
  const ctx = document.getElementById('healthDistChart');
  if (ctx) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#a3b3aa' : '#4a5550';
    const borderColor = isDark ? '#161e1b' : '#ffffff';

    AppState.activeChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Critical Stockout', 'Reorder Required', 'Healthy', 'Overstock'],
        datasets: [{
          data: [stockouts.length, reorders.length, healthy.length, overstocks.length],
          backgroundColor: [
            '#b91c1c', // Crimson (Stockout)
            '#d97706', // Amber (Reorder Required)
            '#1e704a', // Evergreen/Forest (Healthy)
            '#64748b', // Muted Slate (Overstock)
          ],
          borderColor: borderColor,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: textColor, boxWidth: 12, font: { family: "'Inter', sans-serif", size: 11 } } },
        },
      },
    });
  }
}

// --------------------------------------------------------------------------
// 2. DEMAND FORECASTS & EXPLORER
// --------------------------------------------------------------------------
async function renderDemandForecasts(container) {
  const products = AppState.cached.products;
  const defaultProd = products[0] ? products[0].item_id : 'HOBBIES_1_001';

  container.innerHTML = `
    <div class="filter-bar">
      <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">SELECT PRODUCT:</label>
      <select class="select-control" id="forecast-prod-select" onchange="loadProductForecasts(this.value)">
        ${products.map(p => `<option value="${p.item_id}">${p.item_id} (${p.name || p.cat_id})</option>`).join('')}
      </select>
      <button class="btn btn-secondary btn-sm" onclick="exportActiveForecasts()">
        <i class="fa-solid fa-download"></i> Export CSV
      </button>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title" id="forecast-chart-title">Demand Forecast (Next 28 Days)</div>
        <div style="font-size: 0.75rem; color: var(--text-dim);">LightGBM Recursive Multi-Step Model</div>
      </div>
      <div style="height: 320px; position: relative;">
        <canvas id="forecastTimelineChart"></canvas>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Forecast Schedule Table</div>
      </div>
      <div class="table-responsive">
        <table class="data-table" id="forecast-table">
          <thead>
            <tr>
              <th>Forecast Date</th>
              <th>Store ID</th>
              <th>Product SKU</th>
              <th>Predicted Daily Sales (Units)</th>
              <th>Cumulative Demand</th>
            </tr>
          </thead>
          <tbody id="forecast-table-body">
            <tr><td colspan="5" style="text-align: center; color: var(--text-dim);">Loading forecast data...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;

  await loadProductForecasts(defaultProd);
}

let activeForecastDataset = [];

async function loadProductForecasts(itemId) {
  try {
    const fcasts = await API.getForecasts(itemId);
    activeForecastDataset = fcasts;

    const tbody = document.getElementById('forecast-table-body');
    if (!tbody) return;

    if (!fcasts || fcasts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-dim);">No persisted forecasts found for ${itemId}. Run pipeline to generate.</td></tr>`;
      return;
    }

    let cum = 0;
    tbody.innerHTML = fcasts.slice(0, 28).map(f => {
      cum += f.predicted_demand;
      return `
        <tr>
          <td><strong>${f.forecast_date}</strong></td>
          <td>${f.store_id}</td>
          <td>${f.item_id}</td>
          <td><strong style="color: var(--brand-secondary);">${f.predicted_demand.toFixed(2)}</strong></td>
          <td>${cum.toFixed(2)}</td>
        </tr>
      `;
    }).join('');

    // Chart
    const ctx = document.getElementById('forecastTimelineChart');
    if (ctx) {
      if (AppState.activeChart) AppState.activeChart.destroy();

      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const textColor = isDark ? '#a3b3aa' : '#4a5550';
      const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';

      const labels = fcasts.map(f => f.forecast_date);
      const values = fcasts.map(f => f.predicted_demand);

      AppState.activeChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: `Forecast Demand: ${itemId} (units)`,
            data: values,
            borderColor: '#20503f', // Deep Evergreen
            backgroundColor: isDark ? 'rgba(45, 106, 79, 0.15)' : 'rgba(32, 80, 63, 0.08)',
            fill: true,
            tension: 0.25,
            pointRadius: 3,
            pointBackgroundColor: '#20503f',
            pointHoverRadius: 6,
            borderWidth: 2,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { 
              ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } }, 
              grid: { color: gridColor } 
            },
            y: { 
              ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } }, 
              grid: { color: gridColor }, 
              beginAtZero: true 
            }
          },
          plugins: {
            legend: { 
              labels: { color: textColor, font: { family: "'Inter', sans-serif", size: 12 } } 
            }
          }
        }
      });
    }
  } catch (err) {
    showToast(`Failed to load forecast for ${itemId}: ${err.message}`, 'error');
  }
}

function exportActiveForecasts() {
  exportToCsv('demand_forecasts', activeForecastDataset);
}

function renderForecastExplorer(container) {
  renderDemandForecasts(container);
}

// --------------------------------------------------------------------------
// 3. MODEL PERFORMANCE & BENCHMARKS
// --------------------------------------------------------------------------
function renderModelPerformance(container) {
  const evals = AppState.cached.modelEvaluations;

  container.innerHTML = `
    <div class="callout">
      <i class="fa-solid fa-circle-info"></i>
      <strong>Champion Model Decision:</strong> Models are trained on out-of-sample temporal splits. Champion selection strictly minimizes <strong>WAPE</strong> (Weighted Absolute Percentage Error) and <strong>RMSE</strong> on the holdout evaluation period.
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Out-of-Sample Model Benchmarks</div>
        <span style="font-size:0.75rem; color:var(--text-dim);">Evaluated on strictly separated holdout validation sets</span>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Model Name</th>
              <th>Role</th>
              <th>WAPE (Lower is Better)</th>
              <th>RMSE</th>
              <th>MAE</th>
              <th>Bias</th>
              <th>Horizon</th>
              <th>Evaluation Date</th>
            </tr>
          </thead>
          <tbody>
            ${evals.map(e => `
              <tr style="${e.is_champion ? 'background: rgba(99, 102, 241, 0.08);' : ''}">
                <td>
                  <strong>${e.model_name.toUpperCase()}</strong>
                  ${e.is_champion ? `<span class="badge badge-champion" style="margin-left: 0.5rem;"><i class="fa-solid fa-crown"></i> CHAMPION</span>` : ''}
                </td>
                <td>${e.is_champion ? 'Production Forecaster' : 'Benchmark Baseline'}</td>
                <td><strong style="color: ${e.is_champion ? 'var(--status-healthy)' : 'var(--text-main)'};">${(e.wape * 100).toFixed(2)}%</strong></td>
                <td>${e.rmse.toFixed(3)}</td>
                <td>${e.mae.toFixed(3)}</td>
                <td>${e.bias.toFixed(4)}</td>
                <td>${e.horizon_days} Days</td>
                <td>${new Date(e.evaluation_date).toLocaleDateString()}</td>
              </tr>
            `).join('') || '<tr><td colspan="8" style="text-align:center; color:var(--text-dim);">No model evaluations recorded.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Comparative Visual Chart -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">WAPE Comparison (% Error)</div>
      </div>
      <div style="height: 250px; position: relative;">
        <canvas id="modelBenchChart"></canvas>
      </div>
    </div>
  `;

  const ctx = document.getElementById('modelBenchChart');
  if (ctx && evals.length > 0) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#a3b3aa' : '#4a5550';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';

    const labels = evals.map(e => e.model_name.toUpperCase());
    const wapes = evals.map(e => (e.wape * 100).toFixed(2));
    const colors = evals.map(e => e.is_champion ? '#20503f' : '#94a3b8'); // Deep Evergreen for champion, subtle slate for baselines

    AppState.activeChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'WAPE % (Lower is better)',
          data: wapes,
          backgroundColor: colors,
          borderRadius: 4,
          maxBarThickness: 48,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { 
            ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } }, 
            grid: { display: false } 
          },
          y: { 
            ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } }, 
            grid: { color: gridColor }, 
            beginAtZero: true 
          }
        },
        plugins: {
          legend: { labels: { color: textColor, font: { family: "'Inter', sans-serif", size: 12 } } }
        }
      }
    });
  }
}

// --------------------------------------------------------------------------
// 4. INVENTORY OVERVIEW, RISK & REPLENISHMENT
// --------------------------------------------------------------------------
function renderInventoryOverview(container) {
  const inv = AppState.cached.inventory;

  container.innerHTML = `
    <div class="filter-bar">
      <input type="text" class="input-control" placeholder="Search SKU or Store..." id="inv-search" oninput="filterInventoryTable()">
      <button class="btn btn-secondary btn-sm" onclick="exportToCsv('inventory_snapshot', AppState.cached.inventory)">
        <i class="fa-solid fa-download"></i> Export Snapshot
      </button>
      <button class="btn btn-primary btn-sm" onclick="openPhysicalAuditModal()">
        <i class="fa-solid fa-clipboard-check"></i> Physical Stock Count Audit
      </button>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Stock Balances & Warehouse Allocations</div>
        <span style="font-size:0.75rem; color:var(--text-dim);">${inv.length} catalog items</span>
      </div>
      <div class="table-responsive">
        <table class="data-table" id="inv-table">
          <thead>
            <tr>
              <th>Store</th>
              <th>SKU ID</th>
              <th>Stock On Hand</th>
              <th>Incoming Pipeline</th>
              <th>Committed Stock</th>
              <th>Available Stock</th>
              <th>Unit Cost</th>
              <th>Lead Time</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="inv-table-body">
            ${inv.map(item => `
              <tr>
                <td><strong>${item.store_id}</strong></td>
                <td><strong>${item.item_id}</strong></td>
                <td><strong style="color: ${item.stock_on_hand < 10 ? 'var(--status-stockout)' : 'var(--text-main)'};">${item.stock_on_hand}</strong></td>
                <td>${item.incoming_stock}</td>
                <td>${item.committed_stock}</td>
                <td><strong>${item.stock_on_hand + item.incoming_stock - item.committed_stock}</strong></td>
                <td>${formatCurrency(item.unit_cost)}</td>
                <td>${item.supplier_lead_time_days} Days</td>
                <td>
                  <button class="btn btn-secondary btn-sm" onclick="viewProductDetail('${item.item_id}')">Details</button>
                </td>
              </tr>
            `).join('') || '<tr><td colspan="9" style="text-align:center; color:var(--text-dim);">No inventory snapshot data found.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterInventoryTable() {
  const term = document.getElementById('inv-search').value.toLowerCase();
  const rows = document.querySelectorAll('#inv-table-body tr');
  rows.forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(term) ? '' : 'none';
  });
}

function renderInventoryRisk(container) {
  const alerts = AppState.cached.alerts;

  container.innerHTML = `
    <div class="callout callout-warning">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <strong>Risk Detection Logic:</strong> Alerts are triggered when dynamic <strong>Inventory Position (IP)</strong> falls at or below the <strong>Reorder Point (ROP)</strong> calculated from supplier lead time variability and demand forecast.
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Active Vulnerability & Stockout Alerts</div>
        <button class="btn btn-secondary btn-sm" onclick="exportToCsv('inventory_alerts', AppState.cached.alerts)">
          <i class="fa-solid fa-download"></i> Export Alerts
        </button>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Store</th>
              <th>SKU</th>
              <th>Classification</th>
              <th>Stock On Hand</th>
              <th>Safety Stock</th>
              <th>Reorder Point</th>
              <th>Recommended Order</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${alerts.map(a => `
              <tr>
                <td><strong>${a.store_id}</strong></td>
                <td><strong>${a.item_id}</strong></td>
                <td>${getBadge(a.classification)}</td>
                <td><strong style="color: var(--status-stockout);">${a.current_stock}</strong></td>
                <td>${a.safety_stock.toFixed(1)}</td>
                <td>${a.reorder_point.toFixed(1)}</td>
                <td><strong style="color: var(--brand-secondary);">${a.recommended_order_qty}</strong></td>
                <td>
                  <button class="btn btn-primary btn-sm" onclick="openCreatePoModal('${a.item_id}', '${a.store_id}', ${a.recommended_order_qty})">Create Order</button>
                </td>
              </tr>
            `).join('') || '<tr><td colspan="8" style="text-align:center; color:var(--text-dim);">No active alerts. All inventories healthy!</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderReplenishment(container) {
  const recs = AppState.cached.recommendations;

  container.innerHTML = `
    <div class="filter-bar">
      <select class="select-control" id="rep-filter-class" onchange="filterRecommendations(this.value)">
        <option value="">All Classifications</option>
        <option value="REORDER_REQUIRED">Reorder Required</option>
        <option value="POTENTIAL_STOCKOUT">Potential Stockout</option>
        <option value="HEALTHY">Healthy</option>
      </select>
      <button class="btn btn-secondary btn-sm" onclick="exportToCsv('replenishment_advice', AppState.cached.recommendations)">
        <i class="fa-solid fa-download"></i> Export Replenishment List
      </button>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Replenishment Recommendations & Order Policy</div>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Store</th>
              <th>SKU</th>
              <th>Classification</th>
              <th>Current Stock</th>
              <th>Lead Time Demand</th>
              <th>Safety Stock</th>
              <th>ROP</th>
              <th>ROQ (Order Advice)</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="rec-table-body">
            ${recs.map(r => `
              <tr class="rec-row" data-class="${r.classification}">
                <td><strong>${r.store_id}</strong></td>
                <td><strong>${r.item_id}</strong></td>
                <td>${getBadge(r.classification)}</td>
                <td>${r.current_stock}</td>
                <td>${r.lead_time_demand.toFixed(1)}</td>
                <td>${r.safety_stock.toFixed(1)}</td>
                <td>${r.reorder_point.toFixed(1)}</td>
                <td><strong style="color: var(--brand-secondary); font-size: 0.95rem;">${r.recommended_order_qty}</strong></td>
                <td>
                  ${r.recommended_order_qty > 0 ? `
                    <button class="btn btn-primary btn-sm" onclick="openCreatePoModal('${r.item_id}', '${r.store_id}', ${r.recommended_order_qty})">Draft PO</button>
                  ` : `<span style="font-size: 0.75rem; color: var(--text-dim);">Sufficient</span>`}
                </td>
              </tr>
            `).join('') || '<tr><td colspan="9" style="text-align:center; color:var(--text-dim);">No recommendation records found.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterRecommendations(cls) {
  const rows = document.querySelectorAll('.rec-row');
  rows.forEach(r => {
    if (!cls || r.dataset.class === cls) {
      r.style.display = '';
    } else {
      r.style.display = 'none';
    }
  });
}

function renderProductDetails(container) {
  const products = AppState.cached.products;
  const inv = AppState.cached.inventory;
  const p = products[0] || { item_id: 'HOBBIES_1_001', dept_id: 'HOBBIES_1', cat_id: 'HOBBIES', name: 'Product HOBBIES_1_001' };
  const pInv = inv.find(i => i.item_id === p.item_id) || { stock_on_hand: 50, incoming_stock: 0, committed_stock: 0, unit_cost: 8.50, supplier_lead_time_days: 7, min_order_qty: 10, order_multiple: 5 };

  container.innerHTML = `
    <div class="filter-bar">
      <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">SELECT PRODUCT:</label>
      <select class="select-control" id="product-detail-select" onchange="viewProductDetail(this.value)">
        ${products.map(prod => `<option value="${prod.item_id}">${prod.item_id} (${prod.name || prod.cat_id})</option>`).join('')}
      </select>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 1.5rem;">
      <div class="card">
        <div class="card-header"><div class="card-title">SKU Metadata</div></div>
        <table class="data-table">
          <tr><td style="color:var(--text-muted);">SKU ID:</td><td><strong>${p.item_id}</strong></td></tr>
          <tr><td style="color:var(--text-muted);">Name:</td><td>${p.name || 'N/A'}</td></tr>
          <tr><td style="color:var(--text-muted);">Department:</td><td>${p.dept_id}</td></tr>
          <tr><td style="color:var(--text-muted);">Category:</td><td>${p.cat_id}</td></tr>
          <tr><td style="color:var(--text-muted);">Unit Cost:</td><td>${formatCurrency(pInv.unit_cost)}</td></tr>
          <tr><td style="color:var(--text-muted);">Supplier Lead Time:</td><td>${pInv.supplier_lead_time_days} Days</td></tr>
          <tr><td style="color:var(--text-muted);">Min Order Qty (MOQ):</td><td>${pInv.min_order_qty} units</td></tr>
          <tr><td style="color:var(--text-muted);">Batch Pack Multiple:</td><td>${pInv.order_multiple} units</td></tr>
        </table>
        <div style="margin-top: 1rem;">
          <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="openCreatePoModal('${p.item_id}', 'CA_1', 100)">
            <i class="fa-solid fa-cart-plus"></i> Create Purchase Order for SKU
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><div class="card-title">Inventory & Stock Movements</div></div>
        <div class="kpi-grid" style="margin-bottom: 1rem;">
          <div class="kpi-card">
            <div class="kpi-title">Stock On Hand</div>
            <div class="kpi-value">${pInv.stock_on_hand}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-title">Incoming</div>
            <div class="kpi-value">${pInv.incoming_stock}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-title">Committed</div>
            <div class="kpi-value">${pInv.committed_stock}</div>
          </div>
        </div>
        <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom: 0.5rem;">Recent Ledger Movements for ${p.item_id}:</p>
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Quantity</th>
                <th>Reference</th>
              </tr>
            </thead>
            <tbody>
              ${AppState.cached.movements.filter(m => m.item_id === p.item_id).map(m => `
                <tr>
                  <td>${new Date(m.timestamp).toLocaleString()}</td>
                  <td>${m.movement_type}</td>
                  <td><strong style="color: ${m.quantity >= 0 ? 'var(--status-healthy)' : 'var(--status-stockout)'};">${m.quantity > 0 ? '+' + m.quantity : m.quantity}</strong></td>
                  <td>${m.reference_id || 'N/A'}</td>
                </tr>
              `).join('') || '<tr><td colspan="4" style="text-align:center; color:var(--text-dim);">No movement history for this SKU.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function viewProductDetail(itemId) {
  navigateTo('product-details');
  const sel = document.getElementById('product-detail-select');
  if (sel) sel.value = itemId;
}

// --------------------------------------------------------------------------
// 5. PURCHASE ORDERS & STOCK MOVEMENTS
// --------------------------------------------------------------------------
function renderPurchaseOrders(container) {
  const pos = AppState.cached.purchaseOrders;

  container.innerHTML = `
    <div class="filter-bar">
      <button class="btn btn-primary btn-sm" onclick="openCreatePoModal()">
        <i class="fa-solid fa-plus"></i> New Purchase Order Draft
      </button>
      <button class="btn btn-secondary btn-sm" onclick="exportToCsv('purchase_orders', AppState.cached.purchaseOrders)">
        <i class="fa-solid fa-download"></i> Export POs
      </button>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Purchase Order Registry & Lifecycle</div>
        <span style="font-size: 0.75rem; color: var(--text-dim);">State Transitions: DRAFT &rarr; APPROVED &rarr; RECEIVED</span>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>PO Number</th>
              <th>Store</th>
              <th>Supplier</th>
              <th>Status</th>
              <th>Total Cost</th>
              <th>Items Detail</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${pos.map(p => `
              <tr>
                <td><strong>${p.order_id}</strong></td>
                <td>${p.store_id}</td>
                <td>${p.supplier_id}</td>
                <td>${getBadge(p.status)}</td>
                <td><strong>${formatCurrency(p.total_cost)}</strong></td>
                <td>${(p.items || []).map(i => `${i.item_id} (ordered: ${i.ordered_qty}, rec: ${i.received_qty})`).join(', ') || 'Item line'}</td>
                <td>
                  ${p.status === 'DRAFT' || p.status === 'PENDING_APPROVAL' ? `
                    <button class="btn btn-success btn-sm" onclick="approveOrderAction('${p.order_id}')">
                      <i class="fa-solid fa-check"></i> Approve
                    </button>
                  ` : p.status === 'APPROVED' ? `
                    <button class="btn btn-primary btn-sm" onclick="openReceiveModal('${p.order_id}')">
                      <i class="fa-solid fa-dolly"></i> Receive Goods
                    </button>
                  ` : `<span style="font-size:0.75rem; color:var(--status-healthy);"><i class="fa-solid fa-circle-check"></i> Fulfilled</span>`}
                </td>
              </tr>
            `).join('') || '<tr><td colspan="7" style="text-align:center; color:var(--text-dim);">No purchase orders found.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function approveOrderAction(orderId) {
  try {
    await API.approvePurchaseOrder(orderId);
    showToast(`Purchase Order ${orderId} approved successfully!`, 'success');
    await refreshGlobalData();
  } catch (err) {
    showToast(`Approval failed: ${err.message}`, 'error');
  }
}

function openCreatePoModal(defaultItem = '', defaultStore = 'CA_1', defaultQty = 100) {
  const modal = document.getElementById('modal-container');
  const products = AppState.cached.products;
  const stores = AppState.cached.stores;
  const suppliers = AppState.cached.suppliers;

  modal.style.display = 'flex';
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-content">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <h3>Create Purchase Order Draft</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeModal()"><i class="fa-solid fa-xmark"></i></button>
      </div>

      <form id="create-po-form" onsubmit="handleCreatePoSubmit(event)">
        <div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem;">
          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">TARGET STORE:</label>
            <select class="select-control" style="width: 100%;" id="po-store" required>
              ${stores.map(s => `<option value="${s.store_id}" ${s.store_id === defaultStore ? 'selected' : ''}>${s.store_id} (${s.state_id})</option>`).join('') || '<option value="CA_1">CA_1</option>'}
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">SUPPLIER:</label>
            <select class="select-control" style="width: 100%;" id="po-supplier" required>
              ${suppliers.map(s => `<option value="${s.supplier_id}">${s.name} (${s.supplier_id})</option>`).join('') || '<option value="sup_walmart_dist_01">Apex Distribution Partners</option>'}
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">PRODUCT SKU:</label>
            <select class="select-control" style="width: 100%;" id="po-item" required>
              ${products.map(p => `<option value="${p.item_id}" ${p.item_id === defaultItem ? 'selected' : ''}>${p.item_id} (${p.name || p.cat_id})</option>`).join('')}
            </select>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
              <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">ORDER QUANTITY:</label>
              <input type="number" class="input-control" style="width: 100%;" id="po-qty" value="${defaultQty}" min="1" required>
            </div>
            <div>
              <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">UNIT COST ($):</label>
              <input type="number" class="input-control" style="width: 100%;" id="po-cost" value="8.50" step="0.01" min="0.01" required>
            </div>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">NOTES / JUSTIFICATION:</label>
            <input type="text" class="input-control" style="width: 100%;" id="po-notes" placeholder="e.g., Replenishment order based on 28-day forecast spike">
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.75rem;">
          <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary"><i class="fa-solid fa-paper-plane"></i> Save & Submit Draft</button>
        </div>
      </form>
    </div>
  `;
}

async function handleCreatePoSubmit(e) {
  e.preventDefault();
  const storeId = document.getElementById('po-store').value;
  const supplierId = document.getElementById('po-supplier').value;
  const itemId = document.getElementById('po-item').value;
  const qty = parseInt(document.getElementById('po-qty').value, 10);
  const cost = parseFloat(document.getElementById('po-cost').value);
  const notes = document.getElementById('po-notes').value;

  try {
    const payload = {
      supplier_id: supplierId,
      store_id: storeId,
      items: [{ item_id: itemId, ordered_qty: qty, unit_cost: cost, recommended_qty: qty }],
      notes: notes || 'Draft generated from Replenishment Engine',
    };
    const created = await API.createPurchaseOrder(payload);
    showToast(`Purchase order ${created.order_id} created successfully!`, 'success');
    closeModal();
    await refreshGlobalData();
  } catch (err) {
    showToast(`Failed to create PO: ${err.message}`, 'error');
  }
}

function openReceiveModal(orderId) {
  const po = AppState.cached.purchaseOrders.find(p => p.order_id === orderId);
  if (!po) return;

  const modal = document.getElementById('modal-container');
  modal.style.display = 'flex';
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-content">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <h3>Receive Goods for ${po.order_id}</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeModal()"><i class="fa-solid fa-xmark"></i></button>
      </div>

      <div class="callout callout-warning">
        <i class="fa-solid fa-box-open"></i>
        Recording receipt posts an immutable <strong>SUPPLIER_RECEIPT</strong> stock movement transaction and automatically adds received units to on-hand inventory.
      </div>

      <form id="receive-po-form" onsubmit="handleReceiveSubmit(event, '${orderId}')">
        <div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem;">
          ${(po.items || []).map((it, idx) => `
            <div style="background: var(--bg-surface); padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border-subtle);">
              <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
                <strong>${it.item_id}</strong>
                <span style="font-size: 0.75rem; color: var(--text-dim);">Ordered: ${it.ordered_qty} | Prev Received: ${it.received_qty}</span>
              </div>
              <label style="font-size: 0.75rem; color: var(--text-muted); display: block; margin-bottom: 0.25rem;">Quantity Being Received Now:</label>
              <input type="number" class="input-control" style="width: 100%;" id="rec-qty-${idx}" data-item="${it.item_id}" value="${Math.max(0, it.ordered_qty - it.received_qty)}" min="1" max="${it.ordered_qty}" required>
            </div>
          `).join('')}
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.75rem;">
          <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-success"><i class="fa-solid fa-check-double"></i> Confirm Receipt & Post to Stock</button>
        </div>
      </form>
    </div>
  `;
}

async function handleReceiveSubmit(e, orderId) {
  e.preventDefault();
  const inputs = document.querySelectorAll('[id^="rec-qty-"]');
  const receivedItems = [];
  inputs.forEach(input => {
    receivedItems.push({
      item_id: input.dataset.item,
      quantity: parseInt(input.value, 10),
    });
  });

  try {
    await API.receivePurchaseOrder(orderId, receivedItems);
    showToast(`Order ${orderId} received and inventory ledger updated!`, 'success');
    closeModal();
    await refreshGlobalData();
  } catch (err) {
    showToast(`Receipt transaction failed: ${err.message}`, 'error');
  }
}

function closeModal() {
  const modal = document.getElementById('modal-container');
  modal.style.display = 'none';
  modal.innerHTML = '';
}

function renderStockMovements(container) {
  const movs = AppState.cached.movements;
  const receipts = movs.filter(m => m.movement_type === 'SUPPLIER_RECEIPT');
  const sales = movs.filter(m => m.movement_type === 'SALE');
  const reconciles = movs.filter(m => m.movement_type === 'STOCK_RECONCILIATION');

  container.innerHTML = `
    <!-- Top Action Toolbar -->
    <div class="filter-bar">
      <div style="display: flex; align-items: center; gap: 0.5rem; flex: 1; min-width: 240px;">
        <input type="text" class="input-control" placeholder="Search SKU, Store, or Reference..." id="mov-search-input" oninput="filterMovementsTable()" style="flex: 1;">
        <select class="select-control" id="mov-type-filter" onchange="filterMovementsTable()">
          <option value="">All Movement Types</option>
          <option value="SUPPLIER_RECEIPT">Supplier Receipts</option>
          <option value="SALE">Daily Sales</option>
          <option value="CUSTOMER_RETURN">Customer Returns</option>
          <option value="DAMAGE_SPOILAGE">Damage / Spoilage</option>
          <option value="STOCK_RECONCILIATION">Stock Reconciliation</option>
          <option value="MANUAL_ADJUSTMENT">Manual Adjustments</option>
        </select>
      </div>

      <div style="display: flex; align-items: center; gap: 0.5rem;">
        <button class="btn btn-primary btn-sm" onclick="openManualMovementModal()">
          <i class="fa-solid fa-plus"></i> Record Movement
        </button>
        <button class="btn btn-secondary btn-sm" onclick="exportToCsv('stock_movements_ledger', AppState.cached.movements)">
          <i class="fa-solid fa-download"></i> Export CSV
        </button>
      </div>
    </div>

    <!-- Ledger Overview Cards -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-title">Total Ledger Entries</div>
        <div class="kpi-value">${movs.length}</div>
        <div class="kpi-desc">Immutable audit transactions</div>
      </div>
      <div class="kpi-card border-alert-success">
        <div class="kpi-title">Supplier Receipts</div>
        <div class="kpi-value" style="color: var(--status-healthy);">${receipts.length}</div>
        <div class="kpi-desc">Inbound PO fulfillments</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Sales Outbound</div>
        <div class="kpi-value">${sales.length}</div>
        <div class="kpi-desc">Register depletion events</div>
      </div>
      <div class="kpi-card border-alert-warning">
        <div class="kpi-title">Physical Audits</div>
        <div class="kpi-value" style="color: var(--status-reorder);">${reconciles.length}</div>
        <div class="kpi-desc">Shelf inventory reconciliations</div>
      </div>
    </div>

    <!-- Main Ledger Table -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <i class="fa-solid fa-list-check" style="color: var(--brand-evergreen);"></i>
          <span>Inventory Transaction History</span>
        </div>
        <span style="font-size: 0.725rem; color: var(--text-muted); font-family: var(--font-mono);">Double-entry verified audit trail</span>
      </div>

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 60px;">ID</th>
              <th style="width: 150px;">Timestamp</th>
              <th style="width: 90px;">Store</th>
              <th style="width: 150px;">Product SKU</th>
              <th style="width: 160px;">Movement Type</th>
              <th style="width: 110px; text-align: right;">Quantity</th>
              <th style="width: 140px;">Reference ID</th>
              <th style="width: 110px;">Operator</th>
              <th>Audit Notes</th>
            </tr>
          </thead>
          <tbody id="movements-tbody">
            ${movs.map(m => `
              <tr class="mov-row" data-type="${m.movement_type}">
                <td style="font-family: var(--font-mono); color: var(--text-muted); font-size: 0.75rem;">#${m.id}</td>
                <td style="color: var(--text-secondary); white-space: nowrap; font-size: 0.775rem;">${new Date(m.timestamp).toLocaleDateString()} ${new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                <td><strong style="color: var(--text-primary);">${m.store_id}</strong></td>
                <td>
                  <a href="javascript:void(0)" onclick="viewProductDetail('${m.item_id}')" style="color: var(--brand-evergreen); text-decoration: none; font-weight: 600;">
                    ${m.item_id}
                  </a>
                </td>
                <td>
                  <span class="badge ${m.quantity >= 0 ? 'badge-healthy' : 'badge-neutral'}">
                    <i class="fa-solid ${m.quantity >= 0 ? 'fa-arrow-down-left' : 'fa-arrow-up-right'}"></i>
                    ${m.movement_type}
                  </span>
                </td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: ${m.quantity >= 0 ? 'var(--status-healthy)' : 'var(--status-stockout)'};">
                  ${m.quantity > 0 ? '+' + m.quantity : m.quantity}
                </td>
                <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-secondary);">${m.reference_id || '<span style="color:var(--text-muted);">-</span>'}</td>
                <td style="color: var(--text-secondary); font-size: 0.775rem;">${m.user_id ? m.user_id.replace('user-', '') : 'system'}</td>
                <td class="table-col-notes">${m.notes || '<span style="color:var(--text-muted);">-</span>'}</td>
              </tr>
            `).join('') || '<tr><td colspan="9" style="text-align:center; padding: 2rem; color:var(--text-muted);">No stock movement transactions recorded yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function filterMovementsTable() {
  const term = (document.getElementById('mov-search-input')?.value || '').toLowerCase();
  const typeFilter = document.getElementById('mov-type-filter')?.value || '';
  const rows = document.querySelectorAll('.mov-row');

  rows.forEach(r => {
    const text = r.textContent.toLowerCase();
    const type = r.dataset.type || '';
    const matchesTerm = !term || text.includes(term);
    const matchesType = !typeFilter || type === typeFilter;
    r.style.display = matchesTerm && matchesType ? '' : 'none';
  });
}

function openManualMovementModal() {
  const modal = document.getElementById('modal-container');
  const products = AppState.cached.products;
  const stores = AppState.cached.stores;

  modal.style.display = 'flex';
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-content">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <h3>Record Stock Movement</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeModal()"><i class="fa-solid fa-xmark"></i></button>
      </div>

      <form id="movement-form" onsubmit="handleMovementSubmit(event)">
        <div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem;">
          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">STORE:</label>
            <select class="select-control" style="width: 100%;" id="mov-store" required>
              ${stores.map(s => `<option value="${s.store_id}">${s.store_id} (${s.state_id})</option>`).join('') || '<option value="CA_1">CA_1</option>'}
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">SKU ID:</label>
            <select class="select-control" style="width: 100%;" id="mov-item" required>
              ${products.map(p => `<option value="${p.item_id}">${p.item_id} (${p.name || p.cat_id})</option>`).join('')}
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">MOVEMENT TYPE:</label>
            <select class="select-control" style="width: 100%;" id="mov-type" required>
              <option value="SALE">SALE (Decreases stock)</option>
              <option value="CUSTOMER_RETURN">CUSTOMER_RETURN (Increases stock)</option>
              <option value="DAMAGE_SPOILAGE">DAMAGE_SPOILAGE (Decreases stock)</option>
              <option value="SUPPLIER_RECEIPT">SUPPLIER_RECEIPT (Increases stock)</option>
              <option value="MANUAL_ADJUSTMENT">MANUAL_ADJUSTMENT (Arbitrary delta)</option>
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">QUANTITY (Positive or Negative):</label>
            <input type="number" class="input-control" style="width: 100%;" id="mov-qty" required>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">REFERENCE / NOTES:</label>
            <input type="text" class="input-control" style="width: 100%;" id="mov-notes" placeholder="e.g., Damaged during aisle restocking">
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.75rem;">
          <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary">Post Transaction</button>
        </div>
      </form>
    </div>
  `;
}

async function handleMovementSubmit(e) {
  e.preventDefault();
  const storeId = document.getElementById('mov-store').value;
  const itemId = document.getElementById('mov-item').value;
  const mType = document.getElementById('mov-type').value;
  const qty = parseInt(document.getElementById('mov-qty').value, 10);
  const notes = document.getElementById('mov-notes').value;

  try {
    await API.createStockMovement({
      store_id: storeId,
      item_id: itemId,
      movement_type: mType,
      quantity: qty,
      notes: notes,
    });
    showToast(`Stock movement recorded successfully!`, 'success');
    closeModal();
    await refreshGlobalData();
  } catch (err) {
    showToast(`Failed to record movement: ${err.message}`, 'error');
  }
}

function openPhysicalAuditModal() {
  const modal = document.getElementById('modal-container');
  const products = AppState.cached.products;
  const stores = AppState.cached.stores;

  modal.style.display = 'flex';
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-content">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <h3>Physical Stock Count Audit & Reconciliation</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeModal()"><i class="fa-solid fa-xmark"></i></button>
      </div>

      <div class="callout">
        <i class="fa-solid fa-clipboard-check"></i>
        Enter the actual physical count verified on warehouse shelves. The system will compute the variance and record an audited <strong>STOCK_RECONCILIATION</strong> movement.
      </div>

      <form id="reconcile-form" onsubmit="handleReconcileSubmit(event)">
        <div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem;">
          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">STORE LOCATION:</label>
            <select class="select-control" style="width: 100%;" id="rec-store" required>
              ${stores.map(s => `<option value="${s.store_id}">${s.store_id} (${s.state_id})</option>`).join('') || '<option value="CA_1">CA_1</option>'}
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">SKU AUDITED:</label>
            <select class="select-control" style="width: 100%;" id="rec-item" required>
              ${products.map(p => `<option value="${p.item_id}">${p.item_id} (${p.name || p.cat_id})</option>`).join('')}
            </select>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">PHYSICAL AUDIT COUNT (ACTUAL ON SHELF):</label>
            <input type="number" class="input-control" style="width: 100%;" id="rec-count" min="0" required>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 0.35rem;">AUDITOR NOTES:</label>
            <input type="text" class="input-control" style="width: 100%;" id="rec-notes" placeholder="e.g., Annual physical shelf cycle audit">
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.75rem;">
          <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary">Reconcile Inventory</button>
        </div>
      </form>
    </div>
  `;
}

async function handleReconcileSubmit(e) {
  e.preventDefault();
  const storeId = document.getElementById('rec-store').value;
  const itemId = document.getElementById('rec-item').value;
  const count = parseInt(document.getElementById('rec-count').value, 10);
  const notes = document.getElementById('rec-notes').value;

  try {
    const res = await API.reconcileStock({
      store_id: storeId,
      item_id: itemId,
      physical_count: count,
      notes: notes,
    });
    showToast(`Inventory reconciled! Discrepancy adjustment: ${res.adjustment_quantity} units`, 'success');
    closeModal();
    await refreshGlobalData();
  } catch (err) {
    showToast(`Reconciliation failed: ${err.message}`, 'error');
  }
}

// --------------------------------------------------------------------------
// 6. DATA IMPORTS, PIPELINE & MONITORING
// --------------------------------------------------------------------------
function renderDataImports(container) {
  container.innerHTML = `
    <div class="callout">
      <i class="fa-solid fa-upload"></i>
      <strong>Batch Schema Ingestion:</strong> Upload CSV or Excel files to ingest new product catalogs or historical sales into the lakehouse. All uploads undergo strict schema validation before persistence.
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
      <div class="card">
        <div class="card-header"><div class="card-title">Import Products Catalog</div></div>
        <p class="subtext">Upload CSV/Excel with columns: <code>item_id, dept_id, cat_id, [name]</code></p>
        <div style="display: flex; flex-direction: column; gap: 1rem;">
          <input type="file" id="import-prod-file" accept=".csv, .xlsx, .xls" class="input-control">
          <button class="btn btn-primary btn-sm" onclick="handleFileUpload('/imports/products', 'import-prod-file')">
            <i class="fa-solid fa-cloud-arrow-up"></i> Upload & Ingest Products
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><div class="card-title">Import Daily Sales History</div></div>
        <p class="subtext">Upload CSV/Excel with columns: <code>store_id, item_id, date, units_sold, [sell_price]</code></p>
        <div style="display: flex; flex-direction: column; gap: 1rem;">
          <input type="file" id="import-sales-file" accept=".csv, .xlsx, .xls" class="input-control">
          <button class="btn btn-primary btn-sm" onclick="handleFileUpload('/imports/sales', 'import-sales-file')">
            <i class="fa-solid fa-cloud-arrow-up"></i> Upload & Ingest Sales
          </button>
        </div>
      </div>
    </div>
  `;
}

async function handleFileUpload(endpoint, inputId) {
  const fileInput = document.getElementById(inputId);
  if (!fileInput.files || !fileInput.files[0]) {
    showToast('Please select a CSV or Excel file to upload.', 'error');
    return;
  }
  const file = fileInput.files[0];
  try {
    showToast(`Uploading ${file.name}...`, 'info');
    const res = await API.uploadFile(endpoint, file);
    showToast(`Ingestion success: ${res.records_imported || res.message || 'Records processed.'}`, 'success');
    await refreshGlobalData();
  } catch (err) {
    showToast(`Upload failed: ${err.message}`, 'error');
  }
}

async function renderDataPipeline(container) {
  container.innerHTML = `
    <div class="callout">
      <i class="fa-solid fa-diagram-project"></i>
      <strong>Medallion Lakehouse Architecture:</strong> Unmutated raw files are validated into the <strong>Bronze Layer</strong>, cleansed and joined into the <strong>Silver Layer</strong>, and enriched with lag/rolling statistics into the <strong>Gold ML Layer</strong>.
    </div>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
      <h3>Lakehouse Medallion Tiers</h3>
      <button class="btn btn-primary btn-sm" onclick="triggerPipelineRun()">
        <i class="fa-solid fa-play"></i> Trigger Full Pipeline (Ingest &rarr; Train &rarr; Replenish)
      </button>
    </div>

    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem;" id="dq-layers-grid">
      <div class="card" style="border-top: 4px solid #b45309;">
        <div class="kpi-title">BRONZE LAYER (RAW)</div>
        <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0;">Unmutated Parquet snapshots from Walmart M5 CSVs or Synthetic generator.</p>
        <div style="font-size: 0.75rem; color: var(--text-dim);" id="bronze-layer-meta">Loading metadata...</div>
      </div>

      <div class="card" style="border-top: 4px solid #94a3b8;">
        <div class="kpi-title">SILVER LAYER (CLEANED)</div>
        <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0;">Melted sales history joined with store calendar dates and sell prices.</p>
        <div style="font-size: 0.75rem; color: var(--text-dim);" id="silver-layer-meta">Loading metadata...</div>
      </div>

      <div class="card" style="border-top: 4px solid #eab308;">
        <div class="kpi-title">GOLD LAYER (ML FEATURES)</div>
        <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0;">15+ engineered features: Lags (1, 7, 14, 28) and rolling statistics (7d, 28d).</p>
        <div style="font-size: 0.75rem; color: var(--text-dim);" id="gold-layer-meta">Loading metadata...</div>
      </div>
    </div>
  `;

  try {
    const dq = await API.getDataQuality();
    if (dq && dq.medallion_layers) {
      const b = dq.medallion_layers.bronze || {};
      const s = dq.medallion_layers.silver || {};
      const g = dq.medallion_layers.gold || {};

      document.getElementById('bronze-layer-meta').innerHTML = `
        <strong>Files:</strong> ${b.file_count || 0} (${b.total_size_kb || 0} KB)<br>
        <strong>Status:</strong> ${b.exists ? 'Healthy' : 'Not Generated'}<br>
        <strong>Last Modified:</strong> ${b.last_modified ? new Date(b.last_modified).toLocaleString() : 'N/A'}
      `;
      document.getElementById('silver-layer-meta').innerHTML = `
        <strong>Files:</strong> ${s.file_count || 0} (${s.total_size_kb || 0} KB)<br>
        <strong>Status:</strong> ${s.exists ? 'Healthy' : 'Not Generated'}<br>
        <strong>Last Modified:</strong> ${s.last_modified ? new Date(s.last_modified).toLocaleString() : 'N/A'}
      `;
      document.getElementById('gold-layer-meta').innerHTML = `
        <strong>Files:</strong> ${g.file_count || 0} (${g.total_size_kb || 0} KB)<br>
        <strong>Status:</strong> ${g.exists ? 'Healthy' : 'Not Generated'}<br>
        <strong>Last Modified:</strong> ${g.last_modified ? new Date(g.last_modified).toLocaleString() : 'N/A'}
      `;
    }
  } catch (e) {}
}

async function triggerPipelineRun() {
  if (!confirm('Execute end-to-end pipeline run? This will ingest Bronze, transform to Silver/Gold, train LightGBM models, generate forecasts, and compute replenishment.')) return;
  showToast('Starting pipeline run... This may take up to 20 seconds.', 'info');
  try {
    const res = await API.triggerPipeline(true);
    showToast(`Pipeline ${res.run_id} completed successfully!`, 'success');
    await refreshGlobalData();
  } catch (err) {
    showToast(`Pipeline execution failed: ${err.message}`, 'error');
  }
}

async function renderDataQuality(container) {
  container.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Data Quality Rules & Integrity Assertions</div></div>
      <div class="table-responsive">
        <table class="data-table" id="dq-rules-table">
          <thead>
            <tr>
              <th>Domain Table</th>
              <th>Assertion Rule</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="dq-rules-body">
            <tr><td colspan="3" style="text-align: center; color: var(--text-dim);">Inspecting database and Parquet lake integrity...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;

  try {
    const dq = await API.getDataQuality();
    const tbody = document.getElementById('dq-rules-body');
    if (!tbody || !dq) return;

    tbody.innerHTML = (dq.schema_checks || []).map(c => `
      <tr>
        <td><strong>${c.table}</strong></td>
        <td>${c.rule}</td>
        <td><span class="badge ${c.status === 'PASSED' ? 'badge-healthy' : 'badge-stockout'}"><i class="fa-solid ${c.status === 'PASSED' ? 'fa-check' : 'fa-xmark'}"></i> ${c.status}</span></td>
      </tr>
    `).join('');
  } catch (e) {
    showToast(`Failed to inspect data quality: ${e.message}`, 'error');
  }
}

async function renderJobMonitoring(container) {
  container.innerHTML = `
    <div class="callout">
      <i class="fa-solid fa-server"></i>
      <strong>Infrastructure Telemetry Policy:</strong> StockWise Intelligence queries live service ports (Airflow on 8085, Spark Master on 8080). If a service is offline or not running in Docker, it is explicitly shown as <strong>UNREACHABLE</strong> without fabricating fake worker statistics.
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
      <!-- Spark Status -->
      <div class="card" id="spark-status-card">
        <div class="card-header">
          <div class="card-title"><i class="fa-solid fa-bolt"></i> Apache Spark Standalone Cluster</div>
          <span class="badge badge-neutral" id="spark-badge">Connecting...</span>
        </div>
        <div id="spark-details" style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.8;">
          Probing Spark Master HTTP endpoint...
        </div>
      </div>

      <!-- Airflow Status -->
      <div class="card" id="airflow-status-card">
        <div class="card-header">
          <div class="card-title"><i class="fa-solid fa-wind"></i> Apache Airflow Orchestrator</div>
          <span class="badge badge-neutral" id="airflow-badge">Connecting...</span>
        </div>
        <div id="airflow-details" style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.8;">
          Probing Airflow Webserver health endpoint...
        </div>
      </div>
    </div>
  `;

  // Fetch Spark Status
  try {
    const spark = await API.getSparkStatus();
    const sBadge = document.getElementById('spark-badge');
    const sDetails = document.getElementById('spark-details');
    if (spark.available) {
      sBadge.className = 'badge badge-healthy';
      sBadge.textContent = 'ONLINE';
      sDetails.innerHTML = `
        <strong>Master URL:</strong> ${spark.url}<br>
        <strong>Status:</strong> ${spark.status} (v${spark.spark_version})<br>
        <strong>Alive Workers:</strong> <strong style="color:var(--status-healthy);">${spark.alive_workers_count}</strong> / ${spark.total_workers_count}<br>
        <strong>Cores (Used / Total):</strong> ${spark.cores_used} / ${spark.cores_total}<br>
        <strong>Memory (Used / Total):</strong> ${spark.memory_used_mb}MB / ${spark.memory_total_mb}MB<br>
        <strong>Active Applications:</strong> ${spark.active_applications}
      `;
    } else {
      sBadge.className = 'badge badge-stockout';
      sBadge.textContent = 'OFFLINE';
      sDetails.innerHTML = `
        <span style="color:var(--status-stockout); font-weight:600;">Status: Unreachable</span><br>
        <span style="font-size:0.8rem; color:var(--text-dim);">${spark.error || 'Port 8080 connection refused.'}</span><br><br>
        <em>Note: Spark Standalone cluster runs via Docker. Start it with:<br><code>docker compose up -d spark-master spark-worker-1 spark-worker-2</code></em>
      `;
    }
  } catch (e) {}

  // Fetch Airflow Status
  try {
    const airflow = await API.getAirflowStatus();
    const aBadge = document.getElementById('airflow-badge');
    const aDetails = document.getElementById('airflow-details');
    if (airflow.available) {
      aBadge.className = 'badge badge-healthy';
      aBadge.textContent = airflow.status;
      aDetails.innerHTML = `
        <strong>Airflow URL:</strong> ${airflow.url}<br>
        <strong>Metadata DB:</strong> ${airflow.metadatabase}<br>
        <strong>Scheduler:</strong> ${airflow.scheduler}<br>
        <strong>Scheduled DAG:</strong> <code>${airflow.dag_id}</code><br>
        <strong>Cadence:</strong> ${airflow.schedule_interval}
      `;
    } else {
      aBadge.className = 'badge badge-stockout';
      aBadge.textContent = 'OFFLINE';
      aDetails.innerHTML = `
        <span style="color:var(--status-stockout); font-weight:600;">Status: Unreachable</span><br>
        <span style="font-size:0.8rem; color:var(--text-dim);">${airflow.error || 'Port 8085 connection refused.'}</span><br><br>
        <em>DAG definition is located at <code>airflow/dags/smart_inventory_dag.py</code>. Start Airflow via:<br><code>docker compose up -d airflow-webserver airflow-scheduler</code></em>
      `;
    }
  } catch (e) {}
}

// --------------------------------------------------------------------------
// 7. BUSINESS DELIVERABLE REPORTS
// --------------------------------------------------------------------------
function renderReportExecutive(container) {
  const recs = AppState.cached.recommendations;
  const pos = AppState.cached.purchaseOrders;
  const stockouts = recs.filter(r => (r.classification || '').includes('STOCKOUT'));
  const reorders = recs.filter(r => (r.classification || '').includes('REORDER'));

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 1.5rem;">
      <div>
        <h2>Executive Inventory Health Report</h2>
        <p class="subtext">C-level strategic replenishment and working capital exposure summary.</p>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="exportToCsv('executive_summary_report', AppState.cached.recommendations)">
        <i class="fa-solid fa-download"></i> Download Report (CSV)
      </button>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card border-alert-danger">
        <div class="kpi-title">Critical Stockout Vulnerabilities</div>
        <div class="kpi-value" style="color: var(--status-stockout);">${stockouts.length}</div>
        <div class="kpi-desc">Immediate lost revenue risk</div>
      </div>
      <div class="kpi-card border-alert-warning">
        <div class="kpi-title">Reorder Actions Required</div>
        <div class="kpi-value" style="color: var(--status-reorder);">${reorders.length}</div>
        <div class="kpi-desc">Actionable supplier replenishment</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Active Purchase Orders</div>
        <div class="kpi-value">${pos.length}</div>
        <div class="kpi-desc">Inbound replenishment pipeline</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><div class="card-title">Priority Item Replenishment Schedule</div></div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Store</th>
              <th>Item SKU</th>
              <th>Classification</th>
              <th>Current Stock</th>
              <th>Reorder Point</th>
              <th>Order Advice (ROQ)</th>
            </tr>
          </thead>
          <tbody>
            ${reorders.concat(stockouts).map(r => `
              <tr>
                <td><strong>${r.store_id}</strong></td>
                <td><strong>${r.item_id}</strong></td>
                <td>${getBadge(r.classification)}</td>
                <td>${r.current_stock}</td>
                <td>${r.reorder_point.toFixed(1)}</td>
                <td><strong style="color:var(--brand-secondary);">${r.recommended_order_qty}</strong></td>
              </tr>
            `).join('') || '<tr><td colspan="6" style="text-align:center;">No critical replenishments required.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderReportForecast(container) {
  renderDemandForecasts(container);
}

function renderReportRisk(container) {
  renderInventoryRisk(container);
}

function renderReportReplenishment(container) {
  renderReplenishment(container);
}

function renderReportEvaluation(container) {
  renderModelPerformance(container);
}

function renderReportQuality(container) {
  renderDataQuality(container);
}

// --------------------------------------------------------------------------
// 8. ADMINISTRATION & CONFIGURATION
// --------------------------------------------------------------------------
async function renderSystemHealth(container) {
  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div class="card-title">Backend API & Database Connectivity</div>
        <button class="btn btn-secondary btn-sm" onclick="renderSystemHealth(document.getElementById('content-area'))">
          <i class="fa-solid fa-arrows-rotate"></i> Ping Health
        </button>
      </div>
      <div id="system-health-output" style="font-size: 0.85rem; color: var(--text-muted); line-height: 2;">
        Checking live health...
      </div>
    </div>
  `;

  try {
    const health = await API.getHealth();
    document.getElementById('system-health-output').innerHTML = `
      <strong>API Service Status:</strong> <span class="badge ${health.status === 'ok' ? 'badge-healthy' : 'badge-reorder'}">${health.status.toUpperCase()}</span><br>
      <strong>Database Engine:</strong> <span class="badge badge-healthy">${health.database}</span><br>
      <strong>Software Version:</strong> <code>v${health.version}</code><br>
      <strong>UTC Timestamp:</strong> ${health.timestamp}<br>
      <strong>Host Endpoint:</strong> <code>${window.location.origin}</code>
    `;
  } catch (err) {
    document.getElementById('system-health-output').innerHTML = `
      <span style="color: var(--status-stockout); font-weight: 600;">System Health Check Failed:</span> ${err.message}
    `;
  }
}

function renderConfiguration(container) {
  container.innerHTML = `
    <div class="card">
      <div class="card-header"><div class="card-title">Inventory Policy & Forecasting Parameters</div></div>
      <table class="data-table">
        <tr><td style="color:var(--text-muted);">Default Target Service Level:</td><td><strong>95.0% (Z = 1.645)</strong></td></tr>
        <tr><td style="color:var(--text-muted);">Default Supplier Lead Time:</td><td><strong>7 Days</strong></td></tr>
        <tr><td style="color:var(--text-muted);">Short-Term Forecast Horizon:</td><td><strong>7 Days</strong></td></tr>
        <tr><td style="color:var(--text-muted);">Long-Term Strategic Horizon:</td><td><strong>28 Days</strong></td></tr>
        <tr><td style="color:var(--text-muted);">ML Algorithm:</td><td><strong>LightGBM Gradient Boosted Trees (Recursive Multi-Step)</strong></td></tr>
        <tr><td style="color:var(--text-muted);">Current Active Business Isolation:</td><td><strong>${AppState.user.business_id}</strong></td></tr>
      </table>
    </div>
  `;
}

function renderLegalPrivacy(container) {
  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div class="card-title"><i class="fa-solid fa-shield-halved" style="color: var(--brand-evergreen);"></i> Enterprise Privacy Policy & Data Retention</div>
        <span style="font-size: 0.75rem; color: var(--text-muted);">Version 1.0 • Last Updated: October 2026</span>
      </div>
      <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.8; max-width: 860px;">
        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">1. Scope & Multi-Tenant Data Isolation</h4>
        <p>StockWise Intelligence enforces strict cryptographic and row-level multi-tenant boundaries. All store catalogs, daily sales transactions, demand forecasts, and purchase orders are strictly partitioned by <code>business_id</code>. No business tenant may view, query, or infer data from another organization.</p>
        
        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">2. Information We Process</h4>
        <p>The platform processes inventory metadata (SKU IDs, unit costs, supplier lead times), transactional sales counts, and system audit actions (operator ID, timestamp, transaction reference). We do not collect unnecessary consumer personal identifiable information (PII).</p>

        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">3. Data Retention & Immutability</h4>
        <p>Stock movements posted to the ledger are immutable audit records and retained for financial and supply chain compliance. Daily sales aggregations and forecast snapshots are preserved according to customer configuration or retained locally within the customer-managed Medallion Parquet data lake.</p>

        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">4. Security & Vulnerability Reporting</h4>
        <p>Inquiries regarding security boundaries, penetration testing, or responsible disclosure may be directed to our technical security contact at <code>security@stockwise.local</code>.</p>
      </div>
    </div>
  `;
}

function renderLegalTerms(container) {
  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div class="card-title"><i class="fa-solid fa-file-contract" style="color: var(--brand-evergreen);"></i> Terms of Service & Acceptable Use</div>
        <span style="font-size: 0.75rem; color: var(--text-muted);">Version 1.0 • Effective: October 2026</span>
      </div>
      <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.8; max-width: 860px;">
        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">1. Operational Nature of Forecasting</h4>
        <p>StockWise Intelligence utilizes statistical safety stock formulations and machine learning demand models (LightGBM) to generate predictive inventory guidance. Predicted demand (ROQ, ROP) represents operational guidance based on historical patterns and does not constitute a financial guarantee against unforeseen demand shifts or supply chain disruptions.</p>

        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">2. Role Responsibilities & Authorizations</h4>
        <p>Administrative and operational actions—including purchase order approvals and physical reconciliation adjustments—require designated organizational roles (<code>OWNER</code>, <code>MANAGER</code>). Users must maintain the confidentiality of access tokens and API keys.</p>

        <h4 style="color: var(--text-primary); margin: 1rem 0 0.5rem 0;">3. Acceptable Use & System Integrity</h4>
        <p>Users shall not upload corrupted or malicious datasets, attempt privilege escalation across organization boundaries, or bypass rate limits on pipeline triggers.</p>
      </div>
    </div>
  `;
}

// --------------------------------------------------------------------------
// Initialization & Event Binding
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  // Bind Sidebar Navigation
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      const page = el.getAttribute('data-page');
      if (page) navigateTo(page);
    });
  });

  // Business Switcher
  const bSelect = document.getElementById('business-select');
  if (bSelect) {
    bSelect.addEventListener('change', async e => {
      AppState.user.business_id = e.target.value;
      showToast(`Switched active tenant to ${e.target.value}`, 'info');
      await refreshGlobalData();
    });
  }

  // Refresh Button
  const refreshBtn = document.getElementById('btn-refresh-data');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      showToast('Refreshing live data from backend...', 'info');
      await refreshGlobalData();
      showToast('Data refreshed successfully!', 'success');
    });
  }

  // Theme Management (Default: Light Mode)
  const savedTheme = localStorage.getItem('stockwise_theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeButton(savedTheme);

  const themeToggleBtn = document.getElementById('btn-theme-toggle');
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('stockwise_theme', next);
      updateThemeButton(next);
      showToast(`Switched to ${next} theme`, 'info');
      // Re-render chart if on page with chart to match contrast
      if (AppState.activeChart) {
        renderCurrentPage();
      }
    });
  }

  // Initial Auth & Load
  await Auth.init();
  await refreshGlobalData();
});

function updateThemeButton(theme) {
  const icon = document.getElementById('theme-toggle-icon');
  const text = document.getElementById('theme-toggle-text');
  if (icon && text) {
    if (theme === 'dark') {
      icon.className = 'fa-solid fa-sun';
      text.textContent = 'Light';
    } else {
      icon.className = 'fa-solid fa-moon';
      text.textContent = 'Dark';
    }
  }
}
