import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { AnalystBadge, Empty, ErrorBox, Loading, PageHead, RiskBadge, Segmented, TruthBadge } from "../components/ui";
import { useDataset } from "../context";
import { useApi, useDebounced } from "../hooks";

const PAGE_SIZE = 50;
type Level = "all" | "high" | "medium" | "low";
type Reviewed = "all" | "fraud" | "legit" | "unreviewed";
type Sort = "risk" | "name" | "degree";

export default function CustomersPage() {
  const { dataset, version } = useDataset();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounced(search);
  const level = (params.get("level") as Level) || "all";
  const reviewed = (params.get("reviewed") as Reviewed) || "all";
  const sort = (params.get("sort") as Sort) || "risk";
  const order = params.get("order") === "asc" ? "asc" : "desc";
  const page = Math.max(0, Number(params.get("page") ?? 0));
  const ring = params.get("ring") ?? "";
  const hasLabels = Boolean(dataset.summary?.has_labels);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "" || value === "all") next.delete(key);
      else next.set(key, value);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) update({ q });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, error, loading, reload } = useApi(
    () =>
      api.customers(dataset.id, {
        q,
        level,
        reviewed,
        ring: ring || undefined,
        sort,
        order,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    [dataset.id, version, q, level, reviewed, ring, sort, order, page],
  );

  const sortBy = (column: Sort) => {
    if (sort === column) update({ order: order === "desc" ? "asc" : "desc" });
    else update({ sort: column, order: column === "name" ? "asc" : "desc" });
  };
  const arrow = (column: Sort) => (sort === column ? (order === "desc" ? " ↓" : " ↑") : "");
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="stack">
      <PageHead
        title="Customers"
        subtitle="Every customer with a risk score and the main reason behind it. Click a row for the full explanation and connections."
      />
      <div className="toolbar">
        <input
          className="input"
          style={{ minWidth: 240 }}
          placeholder="Search by name or customer ID…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search customers"
        />
        <Segmented
          label="Risk level"
          value={level}
          onChange={(value) => update({ level: value })}
          options={[
            { value: "all", label: "All" },
            { value: "high", label: "High" },
            { value: "medium", label: "Medium" },
            { value: "low", label: "Low" },
          ]}
        />
        <select className="input" value={reviewed} onChange={(event) => update({ reviewed: event.target.value })} aria-label="Analyst decision">
          <option value="all">Any analyst decision</option>
          <option value="fraud">Analyst: fraud</option>
          <option value="legit">Analyst: legitimate</option>
          <option value="unreviewed">Not reviewed</option>
        </select>
        {ring && (
          <span className="chip on">
            Ring {ring}
            <button className="btn small ghost" onClick={() => update({ ring: null })} aria-label="Clear ring filter">
              ✕
            </button>
          </span>
        )}
      </div>
      {error && <ErrorBox message={error} onRetry={reload} />}
      <div className="card flush" style={{ opacity: loading && data ? 0.6 : 1 }}>
        {!data ? (
          <Loading />
        ) : data.items.length === 0 ? (
          <Empty>No customers match.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th className="right">
                    <button className="sort" onClick={() => sortBy("risk")}>
                      Rank{arrow("risk")}
                    </button>
                  </th>
                  <th>
                    <button className="sort" onClick={() => sortBy("name")}>
                      Customer{arrow("name")}
                    </button>
                  </th>
                  <th>Risk</th>
                  <th>Main reason</th>
                  <th>Ring</th>
                  <th className="right">
                    <button className="sort" onClick={() => sortBy("degree")}>
                      Links{arrow("degree")}
                    </button>
                  </th>
                  {hasLabels && <th>Known label</th>}
                </tr>
              </thead>
              <tbody>
                {data.items.map((customer) => (
                  <tr
                    key={customer.customer_id}
                    className="clickable"
                    onClick={() => navigate(`/d/${dataset.id}/customers/${encodeURIComponent(customer.customer_id)}`)}
                  >
                    <td className="right num muted">{customer.rank.toLocaleString()}</td>
                    <td>
                      <div>
                        <strong>{customer.name}</strong>
                      </div>
                      <div className="small muted mono">{customer.customer_id}</div>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 4 }}>
                        <RiskBadge level={customer.risk_level} risk={customer.risk} />
                        <AnalystBadge label={customer.analyst_label} />
                      </div>
                    </td>
                    <td className="small text-2">
                      <div className="truncate">{customer.top_reason}</div>
                    </td>
                    <td onClick={(event) => event.stopPropagation()}>
                      {customer.ring_id ? <Link to={`/d/${dataset.id}/rings/${customer.ring_id}`}>{customer.ring_id}</Link> : <span className="muted">–</span>}
                    </td>
                    <td className="right num">{customer.degree}</td>
                    {hasLabels && (
                      <td>
                        <TruthBadge label={customer.label} />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {data && data.total > PAGE_SIZE && (
        <div className="row between">
          <span className="small muted">
            {(page * PAGE_SIZE + 1).toLocaleString()}–{Math.min(data.total, (page + 1) * PAGE_SIZE).toLocaleString()} of{" "}
            {data.total.toLocaleString()}
          </span>
          <div className="row">
            <button className="btn small" disabled={page === 0} onClick={() => update({ page: String(page - 1) })}>
              ← Previous
            </button>
            <span className="small muted">
              Page {page + 1} of {totalPages}
            </span>
            <button className="btn small" disabled={page + 1 >= totalPages} onClick={() => update({ page: String(page + 1) })}>
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
