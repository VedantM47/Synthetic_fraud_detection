import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Decision, type RingBrief, type RingDetail } from "../api";
import GraphView from "../components/GraphView";
import RetrainBanner from "../components/RetrainBanner";
import { AnalystBadge, AttrChip, Empty, ErrorBox, Loading, PageHead, RiskBadge, Segmented, StatusBadge, TruthBadge } from "../components/ui";
import { useApp, useDataset } from "../context";
import { attributeLabel, dateTime, score } from "../format";
import { useApi, useDebounced } from "../hooks";

type StatusFilter = "pending" | "confirmed" | "dismissed" | "all";
type ScopeFilter = "suspected" | "other" | "all";

function RingReview({
  ringId,
  onDecided,
}: {
  ringId: string;
  onDecided: (ringId: string, decision: Decision) => void;
}) {
  const { dataset, version } = useDataset();
  const { resolvedTheme } = useApp();
  const navigate = useNavigate();
  const [tick, setTick] = useState(0);
  const { data, error, loading } = useApi(() => api.ring(dataset.id, ringId), [dataset.id, ringId, version, tick]);
  const [included, setIncluded] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (!data || data.ring_id !== ringId) return;
    const initial = data.included ?? data.members.filter((member) => member.suggested).map((member) => member.customer_id);
    setIncluded(new Set(initial));
    setNote("");
    setSelected(null);
    setActionError(null);
  }, [data, ringId]);

  const dimmed = useMemo(() => {
    if (!data) return new Set<string>();
    const outside = data.graph.nodes.filter((node) => node.member === false).map((node) => node.id);
    const excluded = data.members.filter((member) => !included.has(member.customer_id)).map((member) => member.customer_id);
    return new Set([...outside, ...excluded]);
  }, [data, included]);

  if (error) return <ErrorBox message={error} />;
  if (!data || data.ring_id !== ringId) return <Loading text="Loading ring…" />;
  const ring: RingDetail = data;

  const decide = async (decision: Decision) => {
    setBusy(true);
    setActionError(null);
    try {
      await api.reviewRing(dataset.id, ring.ring_id, {
        decision,
        note: note.trim(),
        include: decision === "reset" ? undefined : [...included],
      });
      setTick((value) => value + 1);
      onDecided(ring.ring_id, decision);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const toggle = (customerId: string) => {
    setIncluded((current) => {
      const next = new Set(current);
      if (next.has(customerId)) next.delete(customerId);
      else next.add(customerId);
      return next;
    });
  };

  const truth = ring.truth;
  return (
    <div className="stack" style={{ opacity: loading ? 0.6 : 1 }}>
      <div className="card stack">
        <div className="row between">
          <div className="row">
            <h2 style={{ fontSize: 20 }}>{ring.ring_id}</h2>
            <StatusBadge status={ring.status} />
            {!ring.suspected && <span className="badge neutral">Not suspected</span>}
          </div>
          <div className="row">
            <button className="btn small" disabled={!ring.previous_ring} onClick={() => ring.previous_ring && navigate(`/d/${dataset.id}/rings/${ring.previous_ring}`)}>
              ← Previous
            </button>
            <button className="btn small" disabled={!ring.next_ring} onClick={() => ring.next_ring && navigate(`/d/${dataset.id}/rings/${ring.next_ring}`)}>
              Next →
            </button>
          </div>
        </div>
        <p className="summary-text">{ring.explanation}</p>
        <div className="row small text-2">
          <span>
            Ring score <strong className="num">{score(ring.score)}</strong>/100
          </span>
          <span>·</span>
          <span>
            {ring.n_high} of {ring.size} high risk
          </span>
          <span>·</span>
          <span>{ring.n_edges} links (density {Math.round(ring.density * 100)}%)</span>
          {ring.open_span_days !== null && (
            <>
              <span>·</span>
              <span>accounts opened over {ring.open_span_days} days</span>
            </>
          )}
        </div>
        {truth && truth.n_labeled > 0 && (
          <div className="notice small">
            Known labels in this data: {truth.n_fraud} of {ring.size} members are labelled fraud
            {truth.dominant_truth_ring ? ` (${truth.dominant_count} from known ring ${truth.dominant_truth_ring})` : ""}. The
            model did not see these labels if they were hidden or held out.
          </div>
        )}
      </div>

      <div className="grid two">
        <div className="card flush">
          <GraphView
            data={ring.graph}
            size="compact"
            selected={selected}
            onSelect={(node) => setSelected(node?.id ?? null)}
            onOpen={(node) => navigate(`/d/${dataset.id}/customers/${encodeURIComponent(node.id)}`)}
            dimmed={dimmed}
            theme={resolvedTheme}
          />
          <p className="small muted" style={{ padding: "8px 12px" }}>
            Faded: accounts outside the ring or excluded from the decision. Hover a line to see what is shared; double-click
            an account to open it.
          </p>
        </div>
        <div className="card stack">
          <h3>Shared identity details</h3>
          {ring.evidence.length === 0 ? (
            <p className="muted small">No single value is shared by two members (they are linked through chains).</p>
          ) : (
            <ul className="stack tight" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {ring.evidence.map((item) => (
                <li key={`${item.attribute_type}-${item.value}`} className="row between">
                  <AttrChip type={item.attribute_type} value={item.value} />
                  <span className="small text-2">
                    used by {item.members} of {ring.size}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="divider" />
          <h3>Links inside the ring</h3>
          <div className="pill-list">
            {Object.entries(ring.shared_types).map(([kind, count]) => (
              <span className="badge neutral" key={kind}>
                {attributeLabel(kind)} · {count}
              </span>
            ))}
            {Object.keys(ring.shared_types).length === 0 && <span className="muted small">None</span>}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Members</h2>
          <span className="hint">Tick the accounts your decision applies to. Suggested: medium and high risk.</span>
        </div>
        {ring.members.map((member) => (
          <div className="member-row" key={member.customer_id}>
            <input
              type="checkbox"
              checked={included.has(member.customer_id)}
              onChange={() => toggle(member.customer_id)}
              aria-label={`Include ${member.name}`}
            />
            <div style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 6 }}>
                <Link to={`/d/${dataset.id}/customers/${encodeURIComponent(member.customer_id)}`}>
                  <strong>{member.name}</strong>
                </Link>
                <span className="small muted mono">{member.customer_id}</span>
                <AnalystBadge label={member.analyst_label} />
                {member.label !== null && (
                  <span className="small muted">
                    known: <TruthBadge label={member.label} />
                  </span>
                )}
              </div>
              <div className="small text-2 truncate" style={{ maxWidth: "100%" }}>
                {member.top_reason}
              </div>
            </div>
            <RiskBadge level={member.risk_level} risk={member.risk} />
          </div>
        ))}
      </div>

      <div className="card stack">
        <h2>Decision</h2>
        <textarea
          className="input"
          rows={2}
          placeholder="Optional note for the audit trail (e.g. same device used for all applications)"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        {actionError && <div className="notice error">{actionError}</div>}
        <div className="row">
          <button className="btn danger" disabled={busy || included.size === 0} onClick={() => decide("confirm")}>
            ✕ Confirm fraud ring ({included.size} account{included.size === 1 ? "" : "s"})
          </button>
          <button className="btn good" disabled={busy || included.size === 0} onClick={() => decide("dismiss")}>
            ✓ Dismiss: legitimate ({included.size})
          </button>
          {ring.status !== "pending" && (
            <button className="btn ghost" disabled={busy} onClick={() => decide("reset")}>
              Reset to pending
            </button>
          )}
        </div>
        <p className="small muted">
          Decisions become training labels the next time you retrain: confirmed accounts as fraud, dismissed accounts as
          legitimate. Unticked members are left unlabelled.
        </p>
        {ring.history.length > 0 && (
          <>
            <div className="divider" />
            <h3>History</h3>
            <ul className="stack tight small" style={{ margin: 0, paddingLeft: 18 }}>
              {ring.history
                .slice()
                .reverse()
                .map((item) => (
                  <li key={item.id}>
                    <strong>{item.decision === "confirm" ? "Confirmed" : item.decision === "dismiss" ? "Dismissed" : "Reset"}</strong>{" "}
                    {item.decision !== "reset" && `(${item.included.length} accounts)`} · {dateTime(item.created_at)} · model v
                    {item.model_version}
                    {item.note && <span className="text-2"> — “{item.note}”</span>}
                  </li>
                ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

function RingQueueItem({ ring, active, onClick }: { ring: RingBrief; active: boolean; onClick: () => void }) {
  return (
    <button className={`ring-item${active ? " active" : ""}`} onClick={onClick} aria-current={active}>
      <span className="ring-line">
        <strong>{ring.ring_id}</strong>
        <span className="small muted num">
          {ring.size} accts · {score(ring.score)}
        </span>
        <span style={{ marginLeft: "auto" }}>
          <StatusBadge status={ring.status} />
        </span>
      </span>
      <span className="ring-desc">{ring.explanation}</span>
    </button>
  );
}

export default function RingsPage() {
  const { dataset, version } = useDataset();
  const { ringId } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<StatusFilter>("pending");
  const [scope, setScope] = useState<ScopeFilter>("suspected");
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const [flash, setFlash] = useState<string | null>(null);
  const list = useApi(() => api.rings(dataset.id, { status, scope, q, limit: 500 }), [dataset.id, version, status, scope, q]);
  const feedback = useApi(() => api.dataset(dataset.id), [dataset.id, version, list.data]);

  // Open the first ring of the queue when none is selected.
  useEffect(() => {
    if (!ringId && list.data && list.data.items.length > 0) {
      navigate(`/d/${dataset.id}/rings/${list.data.items[0].ring_id}`, { replace: true });
    }
  }, [ringId, list.data, dataset.id, navigate]);

  const onDecided = (decidedId: string, decision: Decision) => {
    const items = list.data?.items ?? [];
    const index = items.findIndex((item) => item.ring_id === decidedId);
    const label = decision === "confirm" ? "confirmed as fraud" : decision === "dismiss" ? "dismissed" : "reset to pending";
    setFlash(`${decidedId} ${label}.`);
    list.reload();
    if (decision !== "reset" && status === "pending") {
      const next = items[index + 1] ?? items[index - 1];
      if (next && next.ring_id !== decidedId) navigate(`/d/${dataset.id}/rings/${next.ring_id}`);
    }
  };

  const counts = list.data?.counts;
  return (
    <div className="stack">
      <PageHead
        title="Fraud-ring review"
        subtitle="Suspected rings are groups of accounts linked by shared identity details where the model rates several members as high risk. Confirm or dismiss each ring; your decisions train the next model version."
      />
      {feedback.data && <RetrainBanner feedback={feedback.data.feedback} compact />}
      {flash && (
        <div className="notice success" role="status">
          <span>{flash}</span>
          <button className="btn small ghost" style={{ marginLeft: "auto" }} onClick={() => setFlash(null)}>
            Close
          </button>
        </div>
      )}
      <div className="grid sidebar-left">
        <div className="card flush" style={{ alignSelf: "start" }}>
          <div className="stack" style={{ padding: 12, gap: 8 }}>
            <Segmented
              label="Review status"
              value={status}
              onChange={setStatus}
              options={[
                { value: "pending", label: `To review${counts ? ` ${counts.pending}` : ""}` },
                { value: "confirmed", label: `Confirmed${counts ? ` ${counts.confirmed}` : ""}` },
                { value: "dismissed", label: `Dismissed${counts ? ` ${counts.dismissed}` : ""}` },
                { value: "all", label: "All" },
              ]}
            />
            <div className="row">
              <select className="input" value={scope} onChange={(event) => setScope(event.target.value as ScopeFilter)} aria-label="Ring scope">
                <option value="suspected">Suspected rings</option>
                <option value="other">Other linked groups</option>
                <option value="all">All linked groups</option>
              </select>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder="Ring or customer…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                aria-label="Search rings"
              />
            </div>
          </div>
          {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}
          {!list.data ? (
            <Loading />
          ) : list.data.items.length === 0 ? (
            <Empty>{status === "pending" ? "Nothing left to review here. 🎉" : "No rings match."}</Empty>
          ) : (
            <div className="ring-list" style={{ opacity: list.loading ? 0.6 : 1 }}>
              {list.data.items.map((ring) => (
                <RingQueueItem
                  key={ring.ring_id}
                  ring={ring}
                  active={ring.ring_id === ringId}
                  onClick={() => navigate(`/d/${dataset.id}/rings/${ring.ring_id}`)}
                />
              ))}
            </div>
          )}
        </div>
        <div>{ringId ? <RingReview ringId={ringId} onDecided={onDecided} /> : <Empty>Select a ring to review.</Empty>}</div>
      </div>
    </div>
  );
}
