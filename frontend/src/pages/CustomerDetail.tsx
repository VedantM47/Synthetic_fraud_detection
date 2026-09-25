import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Decision } from "../api";
import { ContributionChart, eventName, UtilizationTimeline } from "../components/charts";
import GraphView from "../components/GraphView";
import {
  AnalystBadge,
  AttrChip,
  ErrorBox,
  Loading,
  PageHead,
  RiskBadge,
  ScoreMeter,
  Segmented,
  StatusBadge,
  TruthBadge,
} from "../components/ui";
import { useApp, useDataset } from "../context";
import { attributeLabel, dateTime, featureValue, score } from "../format";
import { useApi } from "../hooks";

export default function CustomerDetailPage() {
  const { dataset, version } = useDataset();
  const { resolvedTheme } = useApp();
  const { customerId = "" } = useParams();
  const navigate = useNavigate();
  const [tick, setTick] = useState(0);
  const [hops, setHops] = useState<"1" | "2">("2");
  const detail = useApi(() => api.customer(dataset.id, customerId), [dataset.id, customerId, version, tick]);
  const graph = useApi(() => api.customerGraph(dataset.id, customerId, Number(hops)), [dataset.id, customerId, version, hops, tick]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  if (detail.error) return <ErrorBox message={detail.error} onRetry={detail.reload} />;
  if (!detail.data || detail.data.customer_id !== customerId) return <Loading />;
  const customer = detail.data;
  const explanation = customer.explanation;

  const review = async (decision: Decision) => {
    setBusy(true);
    setActionError(null);
    try {
      await api.reviewCustomer(dataset.id, customer.customer_id, { decision, note: note.trim() });
      setNote("");
      setTick((value) => value + 1);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const valueText = (feature: string, value: number) => featureValue(feature, value);
  const featureRows = Object.entries(customer.features);

  return (
    <div className="stack">
      <PageHead
        title={
          <span className="row" style={{ gap: 10 }}>
            {customer.name}
            <RiskBadge level={customer.risk_level} />
            <AnalystBadge label={customer.analyst_label} />
          </span>
        }
        subtitle={
          <>
            <span className="mono">{customer.customer_id}</span> · rank {customer.rank.toLocaleString()} of{" "}
            {customer.n_customers?.toLocaleString()} by risk
            {customer.open_date && <> · account opened {customer.open_date}</>}
            {customer.label !== null && (
              <>
                {" "}
                · known label <TruthBadge label={customer.label} />
              </>
            )}
          </>
        }
        actions={
          <button className="btn" onClick={() => navigate(-1)}>
            ← Back
          </button>
        }
      />

      <div className="grid sidebar-right">
        <div className="card stack">
          <div className="score-ring">
            <div>
              <div className="score-number num" style={{ color: `var(--risk-${customer.risk_level})` }}>
                {score(customer.risk)}
              </div>
              <div className="small muted">risk score</div>
            </div>
            <div style={{ flex: 1 }}>
              <ScoreMeter risk={customer.risk} threshold={customer.threshold} level={customer.risk_level} />
            </div>
          </div>
          <p className="summary-text">{explanation.summary}</p>
          <div className="grid two">
            <div className="stack tight">
              <h3>Raises the score</h3>
              {explanation.reasons.length === 0 ? (
                <p className="small muted">Nothing notable.</p>
              ) : (
                <ul className="reason-list">
                  {explanation.reasons.map((reason) => (
                    <li key={reason.feature}>
                      <span className="impact up">+{reason.impact.toFixed(1)}</span>
                      <span>{reason.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="stack tight">
              <h3>Lowers the score</h3>
              {explanation.mitigating.length === 0 ? (
                <p className="small muted">Nothing notable.</p>
              ) : (
                <ul className="reason-list">
                  {explanation.mitigating.map((reason) => (
                    <li key={reason.feature}>
                      <span className="impact down">−{Math.abs(reason.impact).toFixed(1)}</span>
                      <span>{reason.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          {explanation.context.length > 0 && (
            <>
              <div className="divider" />
              <ul style={{ margin: 0, paddingLeft: 18 }} className="stack tight text-2">
                {explanation.context.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </>
          )}
          <p className="small muted">
            Points show how much each fact moved this customer's score compared with a typical legitimate customer (score{" "}
            {explanation.baseline_score.toFixed(0)}), averaged over many orderings of the features (Shapley values), so the
            numbers add up to the final score.
          </p>
        </div>

        <div className="stack">
          <div className="card stack">
            <h2>Analyst decision</h2>
            {customer.analyst_label !== null ? (
              <p className="text-2">
                This account is currently labelled{" "}
                <strong>{customer.analyst_label === 1 ? "fraud" : "legitimate"}</strong> by an analyst.
              </p>
            ) : (
              <p className="text-2">No decision yet for this account.</p>
            )}
            <textarea className="input" rows={2} placeholder="Optional note" value={note} onChange={(event) => setNote(event.target.value)} />
            {actionError && <div className="notice error">{actionError}</div>}
            <div className="row">
              <button className="btn danger small" disabled={busy} onClick={() => review("confirm")}>
                ✕ Fraud
              </button>
              <button className="btn good small" disabled={busy} onClick={() => review("dismiss")}>
                ✓ Legitimate
              </button>
              {customer.analyst_label !== null && (
                <button className="btn ghost small" disabled={busy} onClick={() => review("reset")}>
                  Clear
                </button>
              )}
            </div>
            {customer.reviews.length > 0 && (
              <ul className="small text-2" style={{ margin: 0, paddingLeft: 18 }}>
                {customer.reviews
                  .slice()
                  .reverse()
                  .slice(0, 5)
                  .map((item) => (
                    <li key={item.id}>
                      {item.target_type === "ring" ? `Ring ${item.target_id}` : "Account"}{" "}
                      {item.decision === "confirm" ? "confirmed" : item.decision === "dismiss" ? "dismissed" : "reset"}
                      {item.target_type === "ring" && !item.included ? " (this account excluded)" : ""} ·{" "}
                      {dateTime(item.created_at)}
                    </li>
                  ))}
              </ul>
            )}
          </div>
          {customer.ring && (
            <div className="card stack tight">
              <div className="row between">
                <h2>{customer.ring.ring_id}</h2>
                <StatusBadge status={customer.ring.status} />
              </div>
              <p className="small text-2">{customer.ring.explanation}</p>
              <div>
                <Link className="btn small" to={`/d/${dataset.id}/rings/${customer.ring.ring_id}`}>
                  {customer.ring.suspected ? "Review this ring" : "Open this group"}
                </Link>
              </div>
            </div>
          )}
          <div className="card stack tight">
            <h2>Identity details</h2>
            {customer.attributes.length === 0 && <p className="small muted">No identity details on file.</p>}
            {customer.attributes.map((attribute) => (
              <div className="attr-row" key={attribute.key}>
                <AttrChip type={attribute.type} value={attribute.value} />
                <span className={`small ${attribute.shared_with > 0 ? "" : "muted"}`}>
                  {attribute.ignored
                    ? `shared by ${attribute.shared_with + 1} (ignored: too common)`
                    : attribute.shared_with > 0
                      ? `shared with ${attribute.shared_with}`
                      : "unique"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>How each factor moved the score</h2>
        </div>
        <ContributionChart
          items={explanation.contributions}
          baseline={explanation.baseline_score}
          finalScore={score(customer.risk)}
          valueText={(item) => valueText(item.feature, item.value)}
        />
      </div>

      <div className="grid two">
        <div className="card flush">
          <div className="card-head" style={{ padding: "16px 16px 0" }}>
            <h2>Connections</h2>
            <Segmented
              label="Hops"
              value={hops}
              onChange={setHops}
              options={[
                { value: "1", label: "Direct" },
                { value: "2", label: "2 hops" },
              ]}
            />
          </div>
          {graph.error && <ErrorBox message={graph.error} />}
          {!graph.data ? (
            <Loading />
          ) : (
            <GraphView
              data={graph.data}
              size="compact"
              center={customer.customer_id}
              onOpen={(node) => navigate(`/d/${dataset.id}/customers/${encodeURIComponent(node.id)}`)}
              theme={resolvedTheme}
              emptyText="Not linked to any other account."
            />
          )}
          {graph.data?.truncated && <p className="small muted" style={{ padding: "0 12px 8px" }}>Showing the nearest 120 accounts.</p>}
        </div>
        <div className="card flush">
          <div className="card-head" style={{ padding: "16px 16px 0" }}>
            <h2>Directly linked accounts ({customer.connections.length})</h2>
          </div>
          {customer.connections.length === 0 ? (
            <p className="empty">This account shares no identity details with other accounts.</p>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 380 }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Shares</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {customer.connections.map((connection) => (
                    <tr
                      key={connection.customer_id}
                      className="clickable"
                      onClick={() => navigate(`/d/${dataset.id}/customers/${encodeURIComponent(connection.customer_id)}`)}
                    >
                      <td>
                        <strong>{connection.name}</strong>
                        <div className="small muted mono">{connection.customer_id}</div>
                      </td>
                      <td className="small">
                        <div className="pill-list">
                          {connection.shared.length > 0
                            ? connection.shared.map((item) => <AttrChip key={`${item.type}${item.value}`} type={item.type} value={item.value} />)
                            : connection.types.map((kind) => (
                                <span key={kind} className="badge neutral">
                                  {attributeLabel(kind)}
                                </span>
                              ))}
                        </div>
                      </td>
                      <td>
                        <RiskBadge level={connection.risk_level} risk={connection.risk} />
                        <AnalystBadge label={connection.analyst_label} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="card-head">
            <h2>Account activity</h2>
            <span className="hint">{customer.events.length} events</span>
          </div>
          <UtilizationTimeline events={customer.events} />
          {customer.events.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary className="small text-2" style={{ cursor: "pointer" }}>
                Event list
              </summary>
              <div className="table-wrap" style={{ maxHeight: 260 }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Event</th>
                      <th className="right">Utilization</th>
                      <th className="right">Limit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {customer.events.map((event, index) => (
                      <tr key={index}>
                        <td className="num">{event.event_date}</td>
                        <td>{eventName(event.event_type)}</td>
                        <td className="right num">{event.utilization !== null ? `${Math.round(event.utilization * 100)}%` : "–"}</td>
                        <td className="right num">{event.credit_limit !== null ? event.credit_limit.toLocaleString() : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
        <div className="card flush">
          <div className="card-head" style={{ padding: "16px 16px 0" }}>
            <h2>Feature values</h2>
          </div>
          <div className="table-wrap" style={{ maxHeight: 420 }}>
            <table className="data">
              <tbody>
                {featureRows.map(([feature, value]) => (
                  <tr key={feature}>
                    <td className="text-2">{customer.feature_labels[feature] ?? explanation.contributions.find((c) => c.feature === feature)?.label ?? feature}</td>
                    <td className="right num">{valueText(feature, value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
