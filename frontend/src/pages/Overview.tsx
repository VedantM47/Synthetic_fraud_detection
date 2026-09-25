import { Link, useNavigate } from "react-router-dom";
import { api, exportUrl } from "../api";
import { BarList, RiskHistogram } from "../components/charts";
import RetrainBanner from "../components/RetrainBanner";
import { AnalystBadge, ErrorBox, Loading, PageHead, RiskBadge, Stat, StatusBadge } from "../components/ui";
import { useDataset } from "../context";
import { attributeLabel, dateTime, dec, GROUP_LABELS, modeLabel, pct } from "../format";
import { useApi } from "../hooks";

const GROUP_COLORS: Record<string, string> = {
  tabular: "var(--series-1)",
  network: "var(--series-2)",
  temporal: "var(--series-3)",
};

export default function OverviewPage() {
  const { dataset, version } = useDataset();
  const navigate = useNavigate();
  const { data, error, reload } = useApi(() => api.overview(dataset.id), [dataset.id, version]);
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return <Loading />;

  const summary = data.dataset.summary;
  const total = summary.n_customers;
  const high = data.level_counts.high ?? 0;
  const truth = data.ring_detection.truth;
  const progress = data.review_progress;

  return (
    <div className="stack">
      <PageHead
        title={data.dataset.name}
        subtitle={
          <>
            {modeLabel(data.model.mode)} · model v{data.model.version} · updated {dateTime(data.model.created_at)}
            {data.model.mode === "transfer" && data.model.reference && (
              <> · trained on the {data.model.reference.source.toLowerCase()}</>
            )}
          </>
        }
        actions={
          <>
            <a className="btn" href={exportUrl(dataset.id)} download>
              Export scores (CSV)
            </a>
            <Link className="btn primary" to={`/d/${dataset.id}/rings`}>
              Review rings
            </Link>
          </>
        }
      />

      <RetrainBanner feedback={data.feedback} compact />

      {data.changes && (
        <div className="notice success">
          <span aria-hidden="true">↻</span>
          <span>
            <strong>Model v{data.model.version} vs v{data.changes.previous_version}:</strong>{" "}
            {data.changes.level_changes.toLocaleString()} customers changed risk level ({data.changes.newly_high} newly high,{" "}
            {data.changes.no_longer_high} no longer high); {data.changes.rings_newly_suspected} ring
            {data.changes.rings_newly_suspected === 1 ? "" : "s"} newly suspected, {data.changes.rings_cleared} cleared.{" "}
            <Link to={`/d/${dataset.id}/metrics`}>See the version history</Link>
          </span>
        </div>
      )}

      <div className="stats">
        <Stat label="Suspected fraud rings" value={data.ring_detection.n_suspected.toLocaleString()} sub={`${progress.reviewed} of ${progress.suspected} reviewed · ${progress.confirmed} confirmed`} hero />
        <Stat label="High-risk customers" value={high.toLocaleString()} sub={`${pct(high / Math.max(total, 1), 1)} of ${total.toLocaleString()} customers`} />
        <Stat
          label={data.model.roc_auc !== null ? "Model ROC-AUC" : "Reference model ROC-AUC"}
          value={dec(data.model.roc_auc ?? data.model.reference?.reference_roc_auc ?? null, 3)}
          sub={
            data.model.roc_auc !== null
              ? `PR-AUC ${dec(data.model.pr_auc, 3)} · recall ${pct(data.model.recall)}`
              : "No labels in this dataset; measured on the reference data"
          }
        />
        <Stat
          label="Linked customers"
          value={data.graph.linked_customers.toLocaleString()}
          sub={`${data.graph.n_edges.toLocaleString()} shared-identity links · ${data.ring_detection.n_candidates.toLocaleString()} groups`}
        />
      </div>

      {data.notes.length > 0 && (
        <div className="notice">
          <span aria-hidden="true">ℹ</span>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {data.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
            {data.graph.hub_values_skipped.map((hub) => (
              <li key={hub.value}>
                Ignored a very common {attributeLabel(hub.attribute_type).toLowerCase()} shared by {hub.customers} customers
                ("{hub.value}") — likely a placeholder or an office, not a ring.
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.notes.length === 0 && data.graph.hub_values_skipped.length > 0 && (
        <div className="notice">
          <span aria-hidden="true">ℹ</span>
          <span>
            Ignored {data.graph.hub_values_skipped.length} very common value(s), e.g. "{data.graph.hub_values_skipped[0].value}" shared by{" "}
            {data.graph.hub_values_skipped[0].customers} customers — likely a placeholder or an office, not a ring.
          </span>
        </div>
      )}

      <div className="grid two">
        <div className="card">
          <div className="card-head">
            <h2>Top suspected rings</h2>
            <Link className="small" to={`/d/${dataset.id}/rings`}>
              All {data.ring_detection.n_suspected} →
            </Link>
          </div>
          {data.top_rings.length === 0 ? (
            <p className="empty">No suspected rings. Customers that share identity details all look low risk.</p>
          ) : (
            <div className="stack tight">
              {data.top_rings.map((ring) => (
                <Link key={ring.ring_id} to={`/d/${dataset.id}/rings/${ring.ring_id}`} className="ring-item" style={{ borderRadius: 8 }}>
                  <span className="ring-line">
                    <strong>{ring.ring_id}</strong>
                    <span className="small muted">
                      {ring.size} accounts · score {Math.round(ring.score * 100)}
                    </span>
                    <span style={{ marginLeft: "auto" }}>
                      <StatusBadge status={ring.status} />
                    </span>
                  </span>
                  <span className="ring-desc">{ring.explanation}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="card flush">
          <div className="card-head" style={{ padding: "16px 16px 0" }}>
            <h2>Highest-risk customers</h2>
            <Link className="small" to={`/d/${dataset.id}/customers`}>
              All customers →
            </Link>
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Risk</th>
                  <th>Why</th>
                </tr>
              </thead>
              <tbody>
                {data.top_customers.map((customer) => (
                  <tr
                    key={customer.customer_id}
                    className="clickable"
                    onClick={() => navigate(`/d/${dataset.id}/customers/${encodeURIComponent(customer.customer_id)}`)}
                  >
                    <td>
                      <div>
                        <strong>{customer.name}</strong>
                      </div>
                      <div className="small muted mono">{customer.customer_id}</div>
                    </td>
                    <td>
                      <RiskBadge level={customer.risk_level} risk={customer.risk} />
                      <AnalystBadge label={customer.analyst_label} />
                    </td>
                    <td className="small text-2">{customer.top_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="card-head">
            <h2>Risk score distribution</h2>
            <span className="hint">
              {high.toLocaleString()} high · {(data.level_counts.medium ?? 0).toLocaleString()} medium ·{" "}
              {(data.level_counts.low ?? 0).toLocaleString()} low
            </span>
          </div>
          <RiskHistogram bins={data.risk_histogram} threshold={data.model.threshold} />
        </div>
        <div className="card stack">
          <div className="card-head" style={{ marginBottom: 0 }}>
            <h2>What drives the scores</h2>
            <span className="hint">Average size of each feature group's effect on a customer's score</span>
          </div>
          <BarList
            rows={data.group_importance.map((row) => ({
              key: row.group,
              label: GROUP_LABELS[row.group] ?? row.group,
              value: row.importance * 100,
              color: GROUP_COLORS[row.group],
            }))}
            format={(value) => `${value.toFixed(1)} pts`}
          />
          {truth && (
            <>
              <div className="divider" />
              <div className="card-head" style={{ marginBottom: 0 }}>
                <h2>Ring detection vs. known labels</h2>
              </div>
              <dl className="kv">
                <dt>Suspected rings that are mostly fraud</dt>
                <dd className="num">{pct(truth.precision, 1)}</dd>
                <dt>Fraud customers inside a suspected ring</dt>
                <dd className="num">
                  {pct(truth.member_recall, 1)} of {truth.n_fraud_customers.toLocaleString()}
                </dd>
                {truth.ring_recall !== null && (
                  <>
                    <dt>Known rings found (2+ members together)</dt>
                    <dd className="num">
                      {pct(truth.ring_recall, 1)} of {truth.n_true_rings}
                    </dd>
                  </>
                )}
              </dl>
            </>
          )}
          <div className="divider" />
          <div className="card-head" style={{ marginBottom: 0 }}>
            <h2>Links by shared detail</h2>
          </div>
          <BarList
            rows={Object.entries(data.graph.edges_by_type).map(([kind, count]) => ({
              key: kind,
              label: attributeLabel(kind),
              value: count,
            }))}
          />
        </div>
      </div>
    </div>
  );
}
