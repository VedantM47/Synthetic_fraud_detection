import { useCallback, useEffect, useMemo, useState } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useMatch, useNavigate, useParams } from "react-router-dom";
import { api, type Job } from "./api";
import JobProgress from "./components/JobProgress";
import { ErrorBox, Loading } from "./components/ui";
import { AppContext, lastDataset, rememberDataset, useApp, type DatasetContextValue } from "./context";
import { useApi, useTheme, type Theme } from "./hooks";
import CustomerDetailPage from "./pages/CustomerDetail";
import CustomersPage from "./pages/Customers";
import DataPage from "./pages/DataPage";
import MetricsPage from "./pages/Metrics";
import NetworkPage from "./pages/Network";
import OverviewPage from "./pages/Overview";
import RingsPage from "./pages/Rings";
import Welcome from "./pages/Welcome";

function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M9 10L23 10L16 23Z" fill="none" stroke="var(--text-2)" strokeWidth="2" />
      <circle cx="9" cy="10" r="5" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" />
      <circle cx="23" cy="10" r="5" fill="var(--risk-high)" stroke="var(--surface)" strokeWidth="2" />
      <circle cx="16" cy="23" r="5" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" />
    </svg>
  );
}

const THEME_NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const THEME_LABEL: Record<Theme, string> = { system: "Theme: system", light: "Theme: light", dark: "Theme: dark" };

function Shell() {
  const { datasets, theme, setTheme } = useApp();
  const match = useMatch("/d/:datasetId/*");
  const datasetId = match?.params.datasetId ?? null;
  const navigate = useNavigate();
  const current = datasets?.find((dataset) => dataset.id === datasetId) ?? null;
  const ready = Boolean(current && current.active_version > 0);
  const links = datasetId
    ? [
        { to: `/d/${datasetId}`, label: "Overview", end: true },
        { to: `/d/${datasetId}/rings`, label: "Fraud-ring review" },
        { to: `/d/${datasetId}/network`, label: "Network graph" },
        { to: `/d/${datasetId}/customers`, label: "Customers" },
        { to: `/d/${datasetId}/metrics`, label: "Model & metrics" },
      ]
    : [];

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <Logo />
          <span>
            Fraud Ring Console
            <small>Synthetic identity detection</small>
          </span>
        </Link>
        {datasetId && (
          <nav className="nav" aria-label="Dataset">
            <div className="nav-label">Investigate</div>
            {links.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end} className={ready ? "" : "disabled"}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        )}
        <nav className="nav" aria-label="Data">
          <div className="nav-label">Data</div>
          <NavLink to="/data" end>
            Datasets &amp; uploads
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <button className="btn small ghost" onClick={() => setTheme(THEME_NEXT[theme])}>
            {THEME_LABEL[theme]}
          </button>
          <a className="small muted" href="/docs" target="_blank" rel="noreferrer" style={{ padding: "0 10px" }}>
            API docs
          </a>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          {datasets && datasets.length > 0 ? (
            <label className="row" style={{ gap: 8 }}>
              <span className="small muted">Dataset</span>
              <select
                className="input"
                value={datasetId ?? ""}
                onChange={(event) => event.target.value && navigate(`/d/${event.target.value}`)}
                style={{ maxWidth: 360 }}
              >
                {!datasetId && <option value="">Choose a dataset…</option>}
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                    {dataset.status === "processing" ? " (processing…)" : dataset.status === "failed" ? " (failed)" : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className="small muted">No datasets yet</span>
          )}
          <div className="spacer" />
          <Link className="btn small" to="/data">
            + New dataset
          </Link>
        </header>
        {datasetId && (
          <nav className="mobile-nav" aria-label="Sections">
            {links.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end}>
                {link.label}
              </NavLink>
            ))}
            <NavLink to="/data">Data</NavLink>
          </nav>
        )}
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Home() {
  const { datasets, datasetsError, reloadDatasets } = useApp();
  if (datasetsError) return <ErrorBox message={datasetsError} onRetry={reloadDatasets} />;
  if (!datasets) return <Loading />;
  if (datasets.length === 0) return <Welcome />;
  const remembered = lastDataset();
  const target =
    datasets.find((dataset) => dataset.id === remembered) ??
    datasets.find((dataset) => dataset.status === "ready") ??
    datasets[0];
  return <Navigate to={`/d/${target.id}`} replace />;
}

function DatasetGate() {
  const { datasetId = "" } = useParams();
  const { reloadDatasets } = useApp();
  const { data: dataset, error, reload } = useApi(() => api.dataset(datasetId), [datasetId]);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    rememberDataset(datasetId);
    setJobId(null);
  }, [datasetId]);

  // Follow whichever job is running for this dataset (e.g. after a page reload).
  useEffect(() => {
    if (dataset?.id === datasetId && dataset.active_job) setJobId(dataset.active_job.id);
  }, [dataset, datasetId]);

  const onFinish = useCallback(
    (job: Job) => {
      reload();
      reloadDatasets();
      if (job.status === "completed") {
        window.setTimeout(() => setJobId((current) => (current === job.id ? null : current)), 2500);
      }
    },
    [reload, reloadDatasets],
  );

  const context = useMemo<DatasetContextValue | null>(
    () =>
      dataset
        ? {
            dataset,
            version: dataset.active_version,
            reloadDataset: reload,
            startJob: (id: string) => {
              setJobId(id);
              reloadDatasets();
            },
          }
        : null,
    [dataset, reload, reloadDatasets],
  );

  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!dataset || !context || dataset.id !== datasetId) return <Loading />;

  const running = dataset.active_job ?? null;
  const jobCard = jobId && (
    <div className="card" style={{ borderColor: "var(--accent)", maxWidth: dataset.active_version === 0 ? 720 : undefined }}>
      <JobProgress key={jobId} jobId={jobId} onFinish={onFinish} />
      {dataset.active_version > 0 && (
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
          <button className="btn small ghost" onClick={() => setJobId(null)}>
            Hide
          </button>
        </div>
      )}
    </div>
  );

  if (dataset.active_version === 0) {
    return (
      <div className="stack">
        <div className="page-head">
          <div className="titles">
            <h1>{dataset.name}</h1>
            <p>
              {dataset.status === "failed"
                ? "Processing failed. Fix the problem below and upload the data again."
                : "Processing this dataset. Progress updates live; the dashboards open automatically when it finishes."}
            </p>
          </div>
        </div>
        {dataset.status === "failed" && dataset.error && <ErrorBox message={dataset.error} />}
        {jobCard}
        {dataset.status === "failed" && (
          <div>
            <Link className="btn" to="/data">
              Back to datasets
            </Link>
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      {jobCard}
      {dataset.error && dataset.status === "ready" && !running && (
        <div className="notice error">The last job failed: {dataset.error} The previous results are still shown.</div>
      )}
      <Outlet context={context} />
    </>
  );
}

function NotFound() {
  return (
    <div className="stack">
      <h1>Page not found</h1>
      <Link to="/">Go to the start page</Link>
    </div>
  );
}

export default function App() {
  const { data, error, reload } = useApi(() => api.datasets(), []);
  const { theme, resolved, setTheme } = useTheme();
  const value = useMemo(
    () => ({
      datasets: data,
      datasetsError: error,
      reloadDatasets: reload,
      theme,
      resolvedTheme: resolved,
      setTheme,
    }),
    [data, error, reload, theme, resolved, setTheme],
  );

  // Keep the dataset list fresh while anything is processing.
  useEffect(() => {
    if (!data?.some((dataset) => dataset.status === "processing")) return;
    const timer = window.setInterval(reload, 4000);
    return () => window.clearInterval(timer);
  }, [data, reload]);

  return (
    <AppContext.Provider value={value}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<Home />} />
            <Route path="/data" element={<DataPage />} />
            <Route path="/d/:datasetId" element={<DatasetGate />}>
              <Route index element={<OverviewPage />} />
              <Route path="rings" element={<RingsPage />} />
              <Route path="rings/:ringId" element={<RingsPage />} />
              <Route path="network" element={<NetworkPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="customers/:customerId" element={<CustomerDetailPage />} />
              <Route path="metrics" element={<MetricsPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppContext.Provider>
  );
}
