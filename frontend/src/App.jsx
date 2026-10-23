import React, { useEffect, useState } from "react";
import MeetingWorkspace from "./MeetingWorkspace.jsx";
import {
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
} from "recharts";

const API = "http://127.0.0.1:8000";

function money(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Request failed. Please check the entered data."
    );
  }

  return body;
}

const emptyCustomer = {
  name: "",
  company: "",
  email: "",
  notes: "",
};

const emptyProduct = {
  name: "",
  category: "",
  item_type: "product",
  unit_cost: 0,
  list_price: 0,
};

const emptyDeal = {
  title: "",
  customer_id: "",
  product_id: "",
  quantity: 1,
  proposed_unit_price: 0,
  status: "proposed",
  expected_close_date: "",
  notes: "",
};

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [deals, setDeals] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);

  const [page, setPage] = useState("overview");

  const [customerForm, setCustomerForm] = useState({ ...emptyCustomer });
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [saving, setSaving] = useState(false);

  const [productForm, setProductForm] = useState({ ...emptyProduct });
  const [editingProduct, setEditingProduct] = useState(null);
  const [savingProduct, setSavingProduct] = useState(false);
  const [productSearch, setProductSearch] = useState("");

  const [dealForm, setDealForm] = useState({ ...emptyDeal });
  const [editingDeal, setEditingDeal] = useState(null);
  const [savingDeal, setSavingDeal] = useState(false);
  const [dealSearch, setDealSearch] = useState("");

  // AI DEAL RISK ANALYZER
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskError, setRiskError] = useState("");

  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadData() {
    setError("");

    try {
      const [dashboardData, dealData, customerData, productData] =
        await Promise.all([
          request("/analytics/dashboard"),
          request("/deals"),
          request("/customers"),
          request("/products"),
        ]);

      setDashboard(dashboardData);
      setDeals(dealData);
      setCustomers(customerData);
      setProducts(productData);
    } catch (e) {
      setError(`${e.message} Check that the backend is running.`);
    }
  }

  async function loadDealRisk() {
    setRiskLoading(true);
    setRiskError("");

    try {
      const result = await request("/ai/deal-risk");
      setRiskAnalysis(result);
    } catch (e) {
      setRiskError(
        `${e.message || "Unable to load deal risk analysis."} Check that the backend is running.`
      );
    } finally {
      setRiskLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (page === "risk") {
      loadDealRisk();
    }
  }, [page]);

  function navigate(nextPage) {
    setPage(nextPage);
    setMessage("");
    setError("");
    setRiskError("");
  }

  async function seedDemo() {
    setBusy(true);
    setMessage("");
    setError("");

    try {
      await request("/demo/seed", { method: "POST" });
      setMessage("Fictional demo data added successfully.");
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  // CUSTOMER MANAGEMENT

  function openAddCustomer() {
    setEditingCustomer(null);
    setCustomerForm({ ...emptyCustomer });
    setMessage("");
    setError("");
  }

  function openEditCustomer(customer) {
    setEditingCustomer(customer.id);
    setCustomerForm({
      name: customer.name || "",
      company: customer.company || "",
      email: customer.email || "",
      notes: customer.notes || "",
    });
    setMessage("");
    setError("");
  }

  function updateCustomerField(event) {
    const { name, value } = event.target;
    setCustomerForm((current) => ({ ...current, [name]: value }));
  }

  async function saveCustomer(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");

    try {
      const editing = editingCustomer !== null;

      await request(
        editing ? `/customers/${editingCustomer}` : "/customers",
        {
          method: editing ? "PUT" : "POST",
          body: JSON.stringify(customerForm),
        }
      );

      setMessage(
        editing
          ? "Customer updated successfully."
          : "Customer added successfully."
      );

      setCustomerForm({ ...emptyCustomer });
      setEditingCustomer(null);
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteCustomer(customer) {
    const confirmed = window.confirm(
      `Delete ${customer.name}?\n\nCustomers linked to deals cannot be deleted.`
    );

    if (!confirmed) return;

    setMessage("");
    setError("");

    try {
      await request(`/customers/${customer.id}`, {
        method: "DELETE",
      });

      if (editingCustomer === customer.id) {
        openAddCustomer();
      }

      setMessage(`${customer.name} was deleted successfully.`);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  }

  // PRODUCT AND SERVICE MANAGEMENT

  function openAddProduct() {
    setEditingProduct(null);
    setProductForm({ ...emptyProduct });
    setMessage("");
    setError("");
  }

  function openEditProduct(product) {
    setEditingProduct(product.id);
    setProductForm({
      name: product.name || "",
      category: product.category || "",
      item_type: product.item_type || "product",
      unit_cost: product.unit_cost ?? 0,
      list_price: product.list_price ?? 0,
    });
    setMessage("");
    setError("");
  }

  async function saveProduct(event) {
    event.preventDefault();
    setSavingProduct(true);
    setMessage("");
    setError("");

    try {
      const editing = editingProduct !== null;

      await request(
        editing ? `/products/${editingProduct}` : "/products",
        {
          method: editing ? "PUT" : "POST",
          body: JSON.stringify({
            ...productForm,
            unit_cost: Number(productForm.unit_cost),
            list_price: Number(productForm.list_price),
          }),
        }
      );

      setMessage(
        editing
          ? "Product updated successfully."
          : "Product created successfully."
      );

      setProductForm({ ...emptyProduct });
      setEditingProduct(null);
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingProduct(false);
    }
  }

  async function deleteProduct(product) {
    const confirmed = window.confirm(
      `Delete "${product.name}"?\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    setMessage("");
    setError("");

    try {
      await request(`/products/${product.id}`, {
        method: "DELETE",
      });

      if (editingProduct === product.id) {
        openAddProduct();
      }

      setMessage(`${product.name} deleted successfully.`);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  }

  // DEALS AND QUOTATIONS

  function openAddDeal() {
    setEditingDeal(null);
    setDealForm({
      ...emptyDeal,
      customer_id: customers.length ? String(customers[0].id) : "",
    });
    setMessage("");
    setError("");
  }

  function openEditDeal(deal) {
    setEditingDeal(deal.id);
    setDealForm({
      title: deal.title || "",
      customer_id: String(deal.customer_id ?? ""),
      product_id:
        deal.product_id == null ? "" : String(deal.product_id),
      quantity: deal.quantity ?? 1,
      proposed_unit_price: deal.proposed_unit_price ?? 0,
      status: deal.status || "proposed",
      expected_close_date: deal.expected_close_date || "",
      notes: deal.notes || "",
    });
    setMessage("");
    setError("");
  }

  async function saveDeal(event) {
    event.preventDefault();
    setSavingDeal(true);
    setMessage("");
    setError("");

    try {
      if (!dealForm.customer_id) {
        throw new Error(
          "Please create a customer before creating a deal."
        );
      }

      const payload = {
        ...dealForm,
        customer_id: Number(dealForm.customer_id),
        product_id: dealForm.product_id
          ? Number(dealForm.product_id)
          : null,
        quantity: Number(dealForm.quantity),
        proposed_unit_price: Number(dealForm.proposed_unit_price),
        expected_close_date: dealForm.expected_close_date || "",
      };

      const editing = editingDeal !== null;

      await request(editing ? `/deals/${editingDeal}` : "/deals", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });

      setMessage(
        editing
          ? "Deal updated successfully."
          : "Deal created successfully."
      );

      setDealForm({ ...emptyDeal });
      setEditingDeal(null);
      await loadData();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingDeal(false);
    }
  }

  async function deleteDeal(deal) {
    const confirmed = window.confirm(
      `Delete deal "${deal.title}"?\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    setMessage("");
    setError("");

    try {
      await request(`/deals/${deal.id}`, {
        method: "DELETE",
      });

      if (editingDeal === deal.id) {
        setEditingDeal(null);
        setDealForm({ ...emptyDeal });
      }

      setMessage(`Deal "${deal.title}" deleted successfully.`);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  }

  const statusData = dashboard
    ? Object.entries(dashboard.deal_status_counts || {}).map(
        ([status, count]) => ({
          status: status.charAt(0).toUpperCase() + status.slice(1),
          count,
        })
      )
    : [];

  const latestDeals = [...deals]
    .sort((a, b) => b.id - a.id)
    .slice(0, 5);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">D</div>
          <div>
            <strong>DealPilot</strong>
            <small>SALES INTELLIGENCE</small>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <button
          className={`nav-item ${page === "overview" ? "active" : ""}`}
          onClick={() => navigate("overview")}
        >
          ▦ <span>Overview</span>
        </button>

        <button
          className={`nav-item ${page === "customers" ? "active" : ""}`}
          onClick={() => navigate("customers")}
        >
          ◎ <span>Customers</span>
        </button>

        <button
          className={`nav-item ${page === "products" ? "active" : ""}`}
          onClick={() => navigate("products")}
        >
          ◇ <span>Products &amp; services</span>
        </button>

        <button
          className={`nav-item ${page === "deals" ? "active" : ""}`}
          onClick={() => navigate("deals")}
        >
          ↗ <span>Deals &amp; quotations</span>
        </button>

        <button
          className={`nav-item ${page === "risk" ? "active" : ""}`}
          onClick={() => navigate("risk")}
        >
          ◉ <span>AI deal risk</span>
        </button>

        <button
          className={`nav-item ${page === "meetings" ? "active" : ""}`}
          onClick={() => navigate("meetings")}
        >
          ◖ <span>Meeting intelligence</span>
        </button>

        <div className="sidebar-bottom">
          <span className="pulse"></span> API workspace
          <small>Phase 2 · Sales management</small>
        </div>
      </aside>

      <section className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              WORKSPACE / {page.toUpperCase()}
            </div>

            <h1>
              {page === "overview"
                ? "Sales overview"
                : page === "customers"
                  ? "Customer management"
                  : page === "products"
                    ? "Products & services"
                    : page === "deals"
                      ? "Deals & quotations"
                      : page === "meetings"
                        ? "Meeting Intelligence"
                        : "AI Deal Risk Analyzer"}
            </h1>

            <p>
              {page === "overview"
                ? "Understand your pipeline. Make your next move with confidence."
                : page === "customers"
                  ? "Manage customer relationships in one place."
                  : page === "products"
                    ? "Manage your product and service catalog."
                    : page === "deals"
                      ? "Manage your sales opportunities."
                      : page === "meetings"
                        ? "Turn meeting transcripts into clear commitments and follow-ups."
                        : "Find warning signals and prioritize open sales opportunities."}
            </p>
          </div>

          <div className="top-actions">
            <span className="live">
              <i></i> Connected workspace
            </span>

            {page === "overview" ? (
              <button
                className="primary"
                onClick={seedDemo}
                disabled={busy}
              >
                {busy ? "Adding…" : "＋ Load demo data"}
              </button>
            ) : page === "customers" ? (
              <button className="primary" onClick={openAddCustomer}>
                ＋ Add customer
              </button>
            ) : page === "products" ? (
              <button className="primary" onClick={openAddProduct}>
                ＋ Add product
              </button>
            ) : page === "deals" ? (
              <button className="primary" onClick={openAddDeal}>
                ＋ Create deal
              </button>
            ) : page === "risk" ? (
              <button
                className="primary"
                onClick={loadDealRisk}
                disabled={riskLoading}
              >
                {riskLoading ? "Analyzing..." : "↻ Analyze deals"}
              </button>
            ) : null}
          </div>
        </header>

        {message && <div className="notice success">{message}</div>}
        {error && <div className="notice error">{error}</div>}

        {page === "overview" ? (
          <OverviewWorkspace
            dashboard={dashboard}
            deals={deals}
            statusData={statusData}
            latestDeals={latestDeals}
            onRefresh={loadData}
          />
        ) : page === "customers" ? (
          <CustomersWorkspace
            customers={customers}
            deals={deals}
            form={customerForm}
            editingCustomer={editingCustomer}
            saving={saving}
            onFieldChange={updateCustomerField}
            onSubmit={saveCustomer}
            onEdit={openEditCustomer}
            onDelete={deleteCustomer}
            onCancel={openAddCustomer}
            onRefresh={loadData}
          />
        ) : page === "products" ? (
          <ProductsWorkspace
            products={products}
            deals={deals}
            form={productForm}
            setForm={setProductForm}
            search={productSearch}
            setSearch={setProductSearch}
            editingProduct={editingProduct}
            saving={savingProduct}
            onEdit={openEditProduct}
            onDelete={deleteProduct}
            onSubmit={saveProduct}
            onCancel={openAddProduct}
            onRefresh={loadData}
          />
        ) : page === "deals" ? (
          <DealsWorkspace
            deals={deals}
            customers={customers}
            products={products}
            form={dealForm}
            setForm={setDealForm}
            search={dealSearch}
            setSearch={setDealSearch}
            editingDeal={editingDeal}
            saving={savingDeal}
            onEdit={openEditDeal}
            onDelete={deleteDeal}
            onSubmit={saveDeal}
            onCancel={openAddDeal}
            onRefresh={loadData}
          />
        ) : page === "meetings" ? (
          <MeetingWorkspace />
        ) : (
          <DealRiskWorkspace
            analysis={riskAnalysis}
            loading={riskLoading}
            error={riskError}
            onRefresh={loadDealRisk}
          />
        )}
                <footer>
          DealPilot AI <span>•</span> Industry-independent sales intelligence
          <span>•</span> Phase 4 · Meeting intelligence
        </footer>
      </section>
    </main>
  );
}

// OVERVIEW DASHBOARD

function OverviewWorkspace({
  dashboard,
  deals,
  statusData,
  latestDeals,
  onRefresh,
}) {
  return (
    <>
      <div className="demo-note">
        <span>ⓘ</span> Demo records are fictional. Metrics are calculated
        from saved records; no forecast is shown until we build and evaluate
        the forecasting model.
      </div>

      <div className="section-heading">
        <div>
          <h2>Pipeline snapshot</h2>
          <p>Current totals from your workspace database</p>
        </div>

        <button className="ghost" onClick={onRefresh}>
          ↻ Refresh
        </button>
      </div>

      <div className="kpi-grid">
        <Metric
          label="PRODUCTS & SERVICES"
          value={dashboard?.products_count ?? "—"}
          icon="◇"
          sub="Catalog records"
        />

        <Metric
          label="CUSTOMERS"
          value={dashboard?.customers_count ?? "—"}
          icon="◎"
          sub="Customer records"
        />

        <Metric
          label="OPEN PROPOSAL VALUE"
          value={dashboard ? money(dashboard.proposed_value) : "—"}
          icon="↗"
          sub="Proposed + approved"
        />

        <Metric
          label="WON DEAL VALUE"
          value={dashboard ? money(dashboard.won_value) : "—"}
          icon="✓"
          sub="Recorded won deals"
        />
      </div>

      <div className="chart-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Deal status</h3>
              <p>Deals grouped by current status</p>
            </div>
            <span className="panel-icon">▥</span>
          </div>

          <div className="chart-wrap">
            {statusData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={statusData}
                  margin={{ top: 10, right: 10, left: -18, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="#222d42"
                  />

                  <XAxis
                    dataKey="status"
                    tick={{ fill: "#91a0b9", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />

                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: "#91a0b9", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />

                  <Tooltip
                    contentStyle={{
                      background: "#111a2d",
                      border: "1px solid #2a3852",
                      borderRadius: 10,
                      color: "#eef3ff",
                    }}
                  />

                  <Bar
                    dataKey="count"
                    fill="#8b9cff"
                    radius={[5, 5, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty>Load demo data or add deals to see this chart.</Empty>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Gross profit estimate</h3>
              <p>Won deals × stored unit-cost assumptions</p>
            </div>
            <span className="panel-icon">⌁</span>
          </div>

          <div className="profit-value">
            {dashboard
              ? money(dashboard.won_gross_profit_estimate)
              : "—"}
          </div>

          <div className="profit-caption">
            Indicative only · not verified accounting profit
          </div>

          <div className="mini-bars">
            {[30, 45, 36, 65, 54, 82, 70, 100, 78, 88, 64, 94].map(
              (height, i) => (
                <span key={i} style={{ height: `${height}%` }} />
              )
            )}
          </div>

          <div className="chart-foot">
            Decorative preview bars only — not historical monthly data.
          </div>
        </div>
      </div>

      <div className="panel deals-panel">
        <div className="panel-head">
          <div>
            <h3>Recent deals</h3>
            <p>Latest saved opportunities in the workspace</p>
          </div>

          <span className="count-pill">{deals.length} total</span>
        </div>

        {latestDeals.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>DEAL</th>
                  <th>CUSTOMER ID</th>
                  <th>QUANTITY</th>
                  <th>PROPOSED VALUE</th>
                  <th>STATUS</th>
                </tr>
              </thead>

              <tbody>
                {latestDeals.map((deal) => (
                  <tr key={deal.id}>
                    <td>
                      <strong>{deal.title}</strong>
                      <small>Deal #{deal.id}</small>
                    </td>

                    <td>Customer #{deal.customer_id}</td>
                    <td>{deal.quantity}</td>

                    <td>
                      {money(deal.quantity * deal.proposed_unit_price)}
                    </td>

                    <td>
                      <span className={`status ${deal.status}`}>
                        {deal.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>
            No deals yet. Load fictional demo data to explore the dashboard.
          </Empty>
        )}
      </div>
    </>
  );
}

// CUSTOMER MANAGEMENT WORKSPACE

function CustomersWorkspace({
  customers,
  deals,
  form,
  editingCustomer,
  saving,
  onFieldChange,
  onSubmit,
  onEdit,
  onDelete,
  onCancel,
  onRefresh,
}) {
  const [search, setSearch] = useState("");

  const filteredCustomers = customers.filter((customer) =>
    [
      customer.name,
      customer.company,
      customer.email,
      customer.notes,
    ]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  return (
    <>
      <div className="kpi-grid customer-kpis">
        <Metric
          label="TOTAL CUSTOMERS"
          value={customers.length}
          icon="◎"
          sub="Saved customer records"
        />

        <Metric
          label="LINKED DEALS"
          value={
            deals.filter((deal) =>
              customers.some((c) => c.id === deal.customer_id)
            ).length
          }
          icon="↗"
          sub="Deals linked to customers"
        />
      </div>

      <div className="customer-layout">
        <section className="panel customer-list-panel">
          <div className="panel-head">
            <div>
              <h3>Customer directory</h3>
              <p>Search and manage your customer records</p>
            </div>

            <button className="ghost" onClick={onRefresh}>
              ↻ Refresh
            </button>
          </div>

          <input
            className="search-input"
            type="search"
            placeholder="Search name, company, email..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          {filteredCustomers.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>CUSTOMER</th>
                    <th>COMPANY</th>
                    <th>EMAIL</th>
                    <th>DEALS</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredCustomers.map((customer) => {
                    const linkedDeals = deals.filter(
                      (deal) => deal.customer_id === customer.id
                    ).length;

                    return (
                      <tr key={customer.id}>
                        <td>
                          <strong>{customer.name}</strong>
                          <small>Customer #{customer.id}</small>
                        </td>

                        <td>{customer.company || "—"}</td>
                        <td>{customer.email || "—"}</td>
                        <td>{linkedDeals}</td>

                        <td>
                          <div className="row-actions">
                            <button
                              className="small-action"
                              onClick={() => onEdit(customer)}
                            >
                              Edit
                            </button>

                            <button
                              className="small-action danger-action"
                              onClick={() => onDelete(customer)}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>
              {search
                ? "No customers match your search."
                : "No customers yet. Add your first customer using the form."}
            </Empty>
          )}
        </section>

        <section className="panel customer-form-panel">
          <div className="panel-head">
            <div>
              <h3>
                {editingCustomer !== null ? "Edit customer" : "Add customer"}
              </h3>

              <p>
                {editingCustomer !== null
                  ? `Updating customer #${editingCustomer}`
                  : "Save a new customer to your workspace"}
              </p>
            </div>
          </div>

          <form className="customer-form" onSubmit={onSubmit}>
            <label>
              Customer name *
              <input
                name="name"
                value={form.name}
                onChange={onFieldChange}
                placeholder="e.g. Aster Lane"
                maxLength={200}
                required
              />
            </label>

            <label>
              Company
              <input
                name="company"
                value={form.company}
                onChange={onFieldChange}
                placeholder="Company name"
                maxLength={200}
              />
            </label>

            <label>
              Email
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={onFieldChange}
                placeholder="buyer@example.com"
                maxLength={320}
              />
            </label>

            <label>
              Notes
              <textarea
                name="notes"
                value={form.notes}
                onChange={onFieldChange}
                placeholder="Customer requirements or useful context..."
                rows={4}
              />
            </label>

            <button className="primary form-submit" disabled={saving}>
              {saving
                ? "Saving..."
                : editingCustomer !== null
                  ? "Save changes"
                  : "＋ Create customer"}
            </button>

            {editingCustomer !== null && (
              <button
                type="button"
                className="ghost cancel-button"
                onClick={onCancel}
              >
                Cancel editing
              </button>
            )}
          </form>

          <div className="form-hint">
            Customers linked to existing deals cannot be deleted until those
            deals are removed.
          </div>
        </section>
      </div>
    </>
  );
}

// PRODUCTS AND SERVICES WORKSPACE

function ProductsWorkspace({
  products,
  deals,
  form,
  setForm,
  search,
  setSearch,
  editingProduct,
  saving,
  onEdit,
  onDelete,
  onSubmit,
  onCancel,
  onRefresh,
}) {
  const filteredProducts = products.filter((product) =>
    [product.name, product.category, product.item_type]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const totalProducts = products.filter(
    (product) => product.item_type === "product"
  ).length;

  const totalServices = products.filter(
    (product) => product.item_type === "service"
  ).length;

  function updateField(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  return (
    <>
      <div className="kpi-grid customer-kpis">
        <Metric
          label="TOTAL CATALOG ITEMS"
          value={products.length}
          icon="◇"
          sub="Products and services"
        />

        <Metric
          label="PRODUCTS"
          value={totalProducts}
          icon="▣"
          sub="Physical or digital products"
        />

        <Metric
          label="SERVICES"
          value={totalServices}
          icon="↗"
          sub="Service offerings"
        />
      </div>

      <div className="customer-layout">
        <section className="panel customer-list-panel">
          <div className="panel-head">
            <div>
              <h3>Product &amp; service catalog</h3>
              <p>Manage names, costs, pricing and estimated margins</p>
            </div>

            <button className="ghost" onClick={onRefresh}>
              ↻ Refresh
            </button>
          </div>

          <input
            className="search-input"
            type="search"
            placeholder="Search name, category, or type..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          {filteredProducts.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>ITEM</th>
                    <th>TYPE</th>
                    <th>UNIT COST</th>
                    <th>LIST PRICE</th>
                    <th>GROSS MARGIN</th>
                    <th>DEALS</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredProducts.map((product) => {
                    const cost = Number(product.unit_cost) || 0;
                    const price = Number(product.list_price) || 0;
                    const margin = price - cost;
                    const marginPercent =
                      price > 0 ? (margin / price) * 100 : null;

                    const linkedDeals = deals.filter(
                      (deal) => deal.product_id === product.id
                    ).length;

                    return (
                      <tr key={product.id}>
                        <td>
                          <strong>{product.name}</strong>
                          <small>
                            {product.category || "Uncategorized"} · #
                            {product.id}
                          </small>
                        </td>

                        <td>
                          <span className="status">
                            {product.item_type || "product"}
                          </span>
                        </td>

                        <td>{money(cost)}</td>
                        <td>{money(price)}</td>

                        <td>
                          <strong>{money(margin)}</strong>
                          <small>
                            {marginPercent === null
                              ? "No list price"
                              : `${marginPercent.toFixed(1)}% margin`}
                          </small>
                        </td>

                        <td>{linkedDeals}</td>

                        <td>
                          <div className="row-actions">
                            <button
                              className="small-action"
                              onClick={() => onEdit(product)}
                            >
                              Edit
                            </button>

                            <button
                              className="small-action danger-action"
                              onClick={() => onDelete(product)}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>
              {search
                ? "No products or services match your search."
                : "Your catalog is empty. Create your first product or service using the form."}
            </Empty>
          )}
        </section>

        <section className="panel customer-form-panel">
          <div className="panel-head">
            <div>
              <h3>
                {editingProduct !== null
                  ? "Edit catalog item"
                  : "Add catalog item"}
              </h3>

              <p>
                {editingProduct !== null
                  ? `Updating item #${editingProduct}`
                  : "Add a product or service with its pricing"}
              </p>
            </div>
          </div>

          <form className="customer-form" onSubmit={onSubmit}>
  <label>
    Product / service name *
    <input
      name="name"
      value={form.name}
      onChange={updateField}
      placeholder="e.g. AI Sales Platform"
      maxLength={200}
      required
    />
  </label>

  <label>
    Category
    <input
      name="category"
      value={form.category}
      onChange={updateField}
      placeholder="e.g. Software, Consulting"
      maxLength={200}
    />
  </label>

  <label>
    Item type *
    <select
      name="item_type"
      value={form.item_type}
      onChange={updateField}
      required
    >
      <option value="product">Product</option>
      <option value="service">Service</option>
    </select>
  </label>

  <label>
    Unit cost (₹) *
    <input
      type="number"
      name="unit_cost"
      value={form.unit_cost}
      onChange={updateField}
      min="0"
      step="0.01"
      required
    />
  </label>

  <label>
    List price (₹) *
    <input
      type="number"
      name="list_price"
      value={form.list_price}
      onChange={updateField}
      min="0"
      step="0.01"
      required
    />
  </label>

  <div className="form-hint">
    <strong>Estimated gross margin</strong>
    <p>
      {money(
        (Number(form.list_price) || 0) -
          (Number(form.unit_cost) || 0)
      )}{" "}
      per unit
    </p>
    <small>
      List price minus unit cost. This is an estimate, not accounting profit.
    </small>
  </div>

  <button className="primary form-submit" disabled={saving}>
    {saving
      ? "Saving..."
      : editingProduct !== null
        ? "Save changes"
        : "＋ Create catalog item"}
  </button>

  {editingProduct !== null && (
    <button
      type="button"
      className="ghost cancel-button"
      onClick={onCancel}
    >
      Cancel editing
    </button>
  )}
</form>

        <div className="form-hint">
          Items connected to existing deals may not be deletable until
          those deals are removed.
        </div>
      </section>
    </div>
  </>
);
}

// DEALS AND QUOTATIONS WORKSPACE

function DealsWorkspace({
  deals,
  customers,
  products,
  form,
  setForm,
  search,
  setSearch,
  editingDeal,
  saving,
  onEdit,
  onDelete,
  onSubmit,
  onCancel,
  onRefresh,
}) {
  const customerById = Object.fromEntries(
    customers.map((customer) => [customer.id, customer])
  );

  const productById = Object.fromEntries(
    products.map((product) => [product.id, product])
  );

  const filteredDeals = deals.filter((deal) => {
    const customer = customerById[deal.customer_id];
    const product = productById[deal.product_id];

    return [
      deal.title,
      customer?.name,
      customer?.company,
      product?.name,
      deal.status,
      deal.notes,
    ]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase());
  });

  const totalValue = deals.reduce(
    (sum, deal) =>
      sum +
      Number(deal.quantity || 0) *
        Number(deal.proposed_unit_price || 0),
    0
  );

  const openValue = deals
    .filter((deal) =>
      ["proposed", "approved"].includes(deal.status)
    )
    .reduce(
      (sum, deal) =>
        sum +
        Number(deal.quantity || 0) *
          Number(deal.proposed_unit_price || 0),
      0
    );

  const wonCount = deals.filter(
    (deal) => deal.status === "won"
  ).length;

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  return (
    <>
      <div className="kpi-grid customer-kpis">
        <Metric
          label="TOTAL DEALS"
          value={deals.length}
          icon="↗"
          sub="Saved opportunities"
        />

        <Metric
          label="TOTAL PIPELINE VALUE"
          value={money(totalValue)}
          icon="₹"
          sub="All deal statuses"
        />

        <Metric
          label="OPEN PIPELINE"
          value={money(openValue)}
          icon="◷"
          sub="Proposed + approved"
        />

        <Metric
          label="WON DEALS"
          value={wonCount}
          icon="✓"
          sub="Marked as won"
        />
      </div>

      {customers.length === 0 && (
        <div className="notice error">
          Add a customer in Customer Management before creating a deal.
        </div>
      )}

      <div className="customer-layout">
        <section className="panel customer-list-panel">
          <div className="panel-head">
            <div>
              <h3>Deals &amp; quotations</h3>
              <p>
                Track sales opportunities, proposal value and outcomes
              </p>
            </div>

            <button className="ghost" onClick={onRefresh}>
              ↻ Refresh
            </button>
          </div>

          <input
            className="search-input"
            type="search"
            placeholder="Search deal, customer, product, status..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          {filteredDeals.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>DEAL</th>
                    <th>CUSTOMER</th>
                    <th>PRODUCT / SERVICE</th>
                    <th>QUANTITY</th>
                    <th>UNIT PRICE</th>
                    <th>TOTAL VALUE</th>
                    <th>STATUS</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredDeals.map((deal) => {
                    const customer = customerById[deal.customer_id];
                    const product = productById[deal.product_id];

                    const value =
                      Number(deal.quantity || 0) *
                      Number(deal.proposed_unit_price || 0);

                    return (
                      <tr key={deal.id}>
                        <td>
                          <strong>{deal.title}</strong>
                          <small>
                            Deal #{deal.id}
                            {deal.expected_close_date
                              ? ` · Close ${deal.expected_close_date}`
                              : ""}
                          </small>
                        </td>

                        <td>
                          {customer?.name ||
                            `Customer #${deal.customer_id}`}
                        </td>

                        <td>
                          {product?.name ||
                            (deal.product_id == null
                              ? "Not specified"
                              : `Item #${deal.product_id}`)}
                        </td>

                        <td>{deal.quantity}</td>
                        <td>{money(deal.proposed_unit_price)}</td>

                        <td>
                          <strong>{money(value)}</strong>
                        </td>

                        <td>
                          <span className={`status ${deal.status}`}>
                            {deal.status}
                          </span>
                        </td>

                        <td>
                          <div className="row-actions">
                            <button
                              className="small-action"
                              onClick={() => onEdit(deal)}
                            >
                              Edit
                            </button>

                            <button
                              className="small-action danger-action"
                              onClick={() => onDelete(deal)}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>
              {search
                ? "No deals match your search."
                : "No deals yet. Create a deal using the form."}
            </Empty>
          )}

          <div className="form-hint">
            Total value is quantity × proposed unit price. It is a quotation
            value, not necessarily recognized revenue.
          </div>
        </section>

        <section className="panel customer-form-panel">
          <div className="panel-head">
            <div>
              <h3>
                {editingDeal !== null ? "Edit deal" : "Create a deal"}
              </h3>

              <p>
                {editingDeal !== null
                  ? `Updating deal #${editingDeal}`
                  : "Create a sales opportunity or quotation"}
              </p>
            </div>
          </div>

          <form className="customer-form" onSubmit={onSubmit}>
            <label>
              Deal title *
              <input
                name="title"
                value={form.title}
                onChange={updateField}
                placeholder="e.g. Annual software subscription"
                maxLength={240}
                required
              />
            </label>

            <label>
              Customer *
              <select
                name="customer_id"
                value={form.customer_id}
                onChange={updateField}
                required
              >
                <option value="">Select a customer</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                    {customer.company ? ` — ${customer.company}` : ""}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Product / service
              <select
                name="product_id"
                value={form.product_id}
                onChange={updateField}
              >
                <option value="">Not specified</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="form-row">
              <label>
                Quantity *
                <input
                  type="number"
                  name="quantity"
                  value={form.quantity}
                  onChange={updateField}
                  min="0.01"
                  step="any"
                  required
                />
              </label>

              <label>
                Unit price (₹) *
                <input
                  type="number"
                  name="proposed_unit_price"
                  value={form.proposed_unit_price}
                  onChange={updateField}
                  min="0"
                  step="0.01"
                  required
                />
              </label>
            </div>

            <label>
              Status *
              <select
                name="status"
                value={form.status}
                onChange={updateField}
                required
              >
                <option value="proposed">Proposed</option>
                <option value="approved">Approved</option>
                <option value="won">Won</option>
                <option value="lost">Lost</option>
              </select>
            </label>

            <label>
              Expected close date
              <input
                type="date"
                name="expected_close_date"
                value={form.expected_close_date}
                onChange={updateField}
              />
            </label>

            <label>
              Deal notes
              <textarea
                name="notes"
                value={form.notes}
                onChange={updateField}
                placeholder="Customer feedback, objections, next steps..."
                rows={4}
              />
            </label>

            <div className="form-hint">
              <strong>Calculated deal value</strong>
              <p>
                {money(
                  (Number(form.quantity) || 0) *
                    (Number(form.proposed_unit_price) || 0)
                )}
              </p>
              <small>Quantity × proposed unit price</small>
            </div>

            <button
              className="primary form-submit"
              disabled={saving || customers.length === 0}
            >
              {saving
                ? "Saving..."
                : editingDeal !== null
                  ? "Save changes"
                  : "＋ Create deal"}
            </button>

            {editingDeal !== null && (
              <button
                type="button"
                className="ghost cancel-button"
                onClick={onCancel}
              >
                Cancel editing
              </button>
            )}
          </form>
        </section>
      </div>
    </>
  );
}

// AI DEAL RISK ANALYZER WORKSPACE

function DealRiskWorkspace({ analysis, loading, error, onRefresh }) {
  const deals = analysis?.deals || [];

  return (
    <div className="risk-workspace">
      <style>{`
        .risk-workspace { display: grid; gap: 18px; }
        .risk-intro { color: #91a0b9; font-size: 13px; line-height: 1.6; margin: 0; }
        .risk-disclaimer { padding: 12px 14px; border: 1px solid #2a3852; background: #111a2d; border-radius: 12px; color: #aab7cc; font-size: 12px; line-height: 1.6; }
        .risk-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
        .risk-summary-card { border: 1px solid #26334a; border-radius: 14px; padding: 18px; background: #111a2d; min-width: 0; }
        .risk-summary-label { color: #91a0b9; font-size: 10px; font-weight: 700; letter-spacing: .08em; }
        .risk-summary-value { font-size: 28px; font-weight: 750; color: #eef3ff; margin-top: 12px; }
        .risk-summary-sub { color: #91a0b9; font-size: 11px; margin-top: 5px; }
        .risk-high-text { color: #ff8c96; } .risk-medium-text { color: #ffc979; } .risk-low-text { color: #7ce0b0; }
        .risk-level-badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 5px 9px; font-size: 11px; font-weight: 700; text-transform: capitalize; white-space: nowrap; }
        .risk-level-badge.high { color: #ff9da5; background: rgba(239,68,68,.13); border: 1px solid rgba(239,68,68,.28); }
        .risk-level-badge.medium { color: #ffd28a; background: rgba(245,158,11,.13); border: 1px solid rgba(245,158,11,.28); }
        .risk-level-badge.low { color: #8be4b9; background: rgba(16,185,129,.12); border: 1px solid rgba(16,185,129,.25); }
        .risk-score-number { font-weight: 750; font-variant-numeric: tabular-nums; }
        .risk-score-track { width: 86px; height: 5px; border-radius: 99px; background: #26334a; overflow: hidden; margin-top: 7px; }
        .risk-score-fill { display: block; height: 100%; border-radius: 99px; background: #8b9cff; }
        .risk-detail-list { padding-left: 17px; margin: 0; min-width: 170px; color: #b8c4d8; font-size: 12px; line-height: 1.65; }
        .risk-detail-list li + li { margin-top: 4px; }
        .risk-no-signal { color: #91a0b9; font-size: 12px; }
        .risk-error { border: 1px solid rgba(239,68,68,.35); color: #ffb1b8; background: rgba(127,29,29,.2); border-radius: 12px; padding: 13px 15px; font-size: 13px; }
        .risk-loading { color: #aab7cc; padding: 26px 10px; text-align: center; }
        .risk-table td { vertical-align: top; }
        @media (max-width: 1050px) { .risk-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (max-width: 600px) { .risk-summary-grid { grid-template-columns: 1fr 1fr; gap: 9px; } .risk-summary-card { padding: 13px; } .risk-summary-value { font-size: 23px; } }
      `}</style>

      <div className="section-heading">
        <div>
          <h2>AI Deal Risk Analyzer</h2>
          <p className="risk-intro">
            Detect deal warning signals, understand why a deal may be at risk,
            and choose a practical next action.
          </p>
        </div>

        <button className="ghost" onClick={onRefresh} disabled={loading}>
          {loading ? "Analyzing…" : "↻ Refresh analysis"}
        </button>
      </div>

      <div className="risk-disclaimer">
        <strong>How to read this:</strong> Risk scores are rule-based indicators
        calculated from deal dates, pricing and notes. They are not trained-ML
        predictions or calibrated probabilities that a deal will be lost.
      </div>

      {error && <div className="risk-error">{error}</div>}

      {loading && !analysis ? (
        <div className="panel risk-loading">Analyzing your open deals…</div>
      ) : analysis ? (
        <>
          <div className="risk-summary-grid">
            <div className="risk-summary-card">
              <div className="risk-summary-label">OPEN DEALS</div>
              <div className="risk-summary-value">
                {analysis.total_open_deals ?? deals.length}
              </div>
              <div className="risk-summary-sub">Proposed + approved</div>
            </div>

            <div className="risk-summary-card">
              <div className="risk-summary-label">HIGH RISK</div>
              <div className="risk-summary-value risk-high-text">
                {analysis.high_risk_count ?? 0}
              </div>
              <div className="risk-summary-sub">Review first</div>
            </div>

            <div className="risk-summary-card">
              <div className="risk-summary-label">MEDIUM RISK</div>
              <div className="risk-summary-value risk-medium-text">
                {analysis.medium_risk_count ?? 0}
              </div>
              <div className="risk-summary-sub">Follow up proactively</div>
            </div>

            <div className="risk-summary-card">
              <div className="risk-summary-label">LOW RISK</div>
              <div className="risk-summary-value risk-low-text">
                {analysis.low_risk_count ?? 0}
              </div>
              <div className="risk-summary-sub">Continue monitoring</div>
            </div>
          </div>

          <section className="panel deals-panel">
            <div className="panel-head">
              <div>
                <h3>Deal risk assessment</h3>
                <p>
                  Warning signals and recommended next steps for each open deal
                </p>
              </div>

              <span className="count-pill">{deals.length} analyzed</span>
            </div>

            {deals.length ? (
              <div className="table-scroll">
                <table className="risk-table">
                  <thead>
                    <tr>
                      <th>DEAL</th>
                      <th>CUSTOMER</th>
                      <th>DEAL VALUE</th>
                      <th>RISK SCORE</th>
                      <th>LEVEL</th>
                      <th>WARNING SIGNALS</th>
                      <th>RECOMMENDED ACTIONS</th>
                    </tr>
                  </thead>

                  <tbody>
                    {deals.map((deal) => (
                      <tr key={deal.id}>
                        <td>
                          <strong>{deal.title}</strong>
                          <small>Deal #{deal.id}</small>
                          <small>{deal.status}</small>
                        </td>

                        <td>{deal.company || deal.customer || "—"}</td>
                        <td>{money(deal.deal_value)}</td>

                        <td>
                          <span className="risk-score-number">
                            {deal.risk_score ?? 0}/100
                          </span>

                          <div className="risk-score-track">
                            <span
                              className="risk-score-fill"
                              style={{
                                width: `${Math.min(
                                  100,
                                  Math.max(0, Number(deal.risk_score) || 0)
                                )}%`,
                              }}
                            />
                          </div>
                        </td>

                        <td>
                          <span
                            className={`risk-level-badge ${String(
                              deal.risk_level || "low"
                            ).toLowerCase()}`}
                          >
                            {deal.risk_level || "Low"}
                          </span>
                        </td>

                        <td>
                          {deal.signals?.length ? (
                            <ul className="risk-detail-list">
                              {deal.signals.map((signal, index) => (
                                <li key={`${deal.id}-signal-${index}`}>
                                  {signal}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="risk-no-signal">
                              No warning signals detected
                            </span>
                          )}
                        </td>

                        <td>
                          {deal.recommendations?.length ? (
                            <ul className="risk-detail-list">
                              {deal.recommendations.map((action, index) => (
                                <li key={`${deal.id}-action-${index}`}>
                                  {action}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="risk-no-signal">
                              Continue regular follow-up
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>
                No open deals to analyze. Create a deal with Proposed or
                Approved status, then refresh this analysis.
              </Empty>
            )}
          </section>
        </>
      ) : (
        <div className="panel">
          <h3>Ready to analyze</h3>
          <p className="risk-intro">
            Choose “Analyze deals” to retrieve the latest risk assessment from
            your backend.
          </p>
        </div>
      )}
    </div>
  );
}

// REUSABLE COMPONENTS

function Metric({ label, value, icon, sub }) {
  return (
    <div className="metric">
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon">{icon}</span>
      </div>

      <div className="metric-value">{value}</div>

      <div className="metric-sub">
        <span className="metric-dot"></span>
        {sub}
      </div>
    </div>
  );
}

function Empty({ children }) {
  return <div className="empty">{children}</div>;
}