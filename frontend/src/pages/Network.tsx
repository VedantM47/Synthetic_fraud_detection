import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type GraphNode } from "../api";
import GraphView, { type ColorMode } from "../components/GraphView";
import { AnalystBadge, ErrorBox, Loading, PageHead, RiskBadge, Segmented, StatusBadge } from "../components/ui";
import { useApp, useDataset } from "../context";
import { attributeLabel } from "../format";
import { useApi, useDebounced } from "../hooks";

function SelectedPanel({ node }: { node: GraphNode }) {
  const { dataset, version } = useDataset();
  const detail = useApi(() => api.customer(dataset.id, node.id), [dataset.id, node.id, version]);
  return (
    <div className="stack">
      <div>
        <h2>{node.name}</h2>
        <div className="small muted mono">{node.id}</div>
      </div>
      <div className="row">
        <RiskBadge level={node.level} risk={node.risk} />
        <AnalystBadge label={node.analyst_label} />
      </div>
      {detail.error && <ErrorBox message={detail.error} />}
      {!detail.data ? (
        <Loading />
      ) : (
        <>
          <p className="text-2">{detail.data.explanation.summary}</p>
          {detail.data.connections.length > 0 && (
            <div className="stack tight">
              <strong className="small">Linked to</strong>
              {detail.data.connections.slice(0, 6).map((connection) => (
                <div key={connection.customer_id} className="row between small">
                  <span className="truncate" style={{ maxWidth: 180 }}>
                    {connection.name}
                  </span>
                  <span className="muted">{connection.types.map(attributeLabel).join(", ")}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      <div className="row">
        <Link className="btn primary small" to={`/d/${dataset.id}/customers/${encodeURIComponent(node.id)}`}>
          Open customer
        </Link>
        {node.ring_id && (
          <Link className="btn small" to={`/d/${dataset.id}/rings/${node.ring_id}`}>
            Review {node.ring_id}
          </Link>
        )}
      </div>
    </div>
  );
}

export default function NetworkPage() {
  const { dataset, version } = useDataset();
  const { resolvedTheme } = useApp();
  const navigate = useNavigate();
  const [scope, setScope] = useState<"suspected" | "all">("suspected");
  const [minScore, setMinScore] = useState(0);
  const debouncedScore = useDebounced(minScore, 400);
  const [types, setTypes] = useState<string[]>([]);
  const [status, setStatus] = useState<"all" | "pending" | "confirmed" | "dismissed">("all");
  const [colorMode, setColorMode] = useState<ColorMode>("risk");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [search, setSearch] = useState("");
  const [searchError, setSearchError] = useState<string | null>(null);
  const available = dataset.summary?.attribute_types ?? [];
  const hasLabels = Boolean(dataset.summary?.has_labels);

  const graph = useApi(
    () =>
      api.network(dataset.id, {
        scope,
        min_score: debouncedScore / 100,
        types: types.join(","),
        status,
      }),
    [dataset.id, version, scope, debouncedScore, types.join(","), status],
  );

  const nodeIndex = useMemo(() => new Map((graph.data?.nodes ?? []).map((node) => [node.id, node])), [graph.data]);

  const find = () => {
    const needle = search.trim().toLowerCase();
    if (!needle || !graph.data) return;
    const match = graph.data.nodes.find(
      (node) => node.id.toLowerCase() === needle || node.name.toLowerCase().includes(needle) || node.id.toLowerCase().includes(needle),
    );
    if (match) {
      setSelected(match);
      setSearchError(null);
    } else {
      setSearchError("Not in the current view. Try 'All linked groups' or open it from Customers.");
    }
  };

  const toggleType = (kind: string) =>
    setTypes((current) => (current.includes(kind) ? current.filter((item) => item !== kind) : [...current, kind]));

  return (
    <div className="stack">
      <PageHead
        title="Network graph"
        subtitle="Every dot is a customer; lines connect customers that share an identity detail. Colour and size show risk. Rings are drawn as separate clusters."
      />
      <div className="toolbar">
        <Segmented
          label="Which groups"
          value={scope}
          onChange={setScope}
          options={[
            { value: "suspected", label: "Suspected rings" },
            { value: "all", label: "All linked groups" },
          ]}
        />
        <label className="row small text-2" style={{ gap: 6 }}>
          Min ring score
          <input type="range" min={0} max={95} step={5} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} />
          <span className="num" style={{ width: 22 }}>
            {minScore}
          </span>
        </label>
        <select className="input" value={status} onChange={(event) => setStatus(event.target.value as typeof status)} aria-label="Review status">
          <option value="all">Any review status</option>
          <option value="pending">Awaiting review</option>
          <option value="confirmed">Confirmed</option>
          <option value="dismissed">Dismissed</option>
        </select>
        {hasLabels && (
          <Segmented
            label="Colour by"
            value={colorMode}
            onChange={setColorMode}
            options={[
              { value: "risk", label: "Model risk" },
              { value: "truth", label: "Known labels" },
            ]}
          />
        )}
      </div>
      <div className="toolbar">
        <span className="small text-2">Links through:</span>
        {available.map((kind) => (
          <button
            key={kind}
            className={`chip${types.length === 0 || types.includes(kind) ? " on" : ""}`}
            onClick={() => toggleType(kind)}
            aria-pressed={types.length === 0 || types.includes(kind)}
          >
            {attributeLabel(kind)}
          </button>
        ))}
        {types.length > 0 && (
          <button className="btn small ghost" onClick={() => setTypes([])}>
            Show all
          </button>
        )}
        <span className="spacer" style={{ flex: 1 }} />
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            find();
          }}
        >
          <input className="input" placeholder="Find customer in view…" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Find a customer" />
          <button className="btn small" type="submit">
            Find
          </button>
        </form>
      </div>
      {searchError && <div className="notice small">{searchError}</div>}
      {graph.error && <ErrorBox message={graph.error} onRetry={graph.reload} />}
      <div className="grid sidebar-right">
        <div className="card flush" style={{ opacity: graph.loading && graph.data ? 0.6 : 1 }}>
          {!graph.data ? (
            <Loading text="Loading the network…" />
          ) : (
            <GraphView
              data={graph.data}
              size="tall"
              selected={selected?.id ?? null}
              onSelect={setSelected}
              onOpen={(node) => navigate(`/d/${dataset.id}/customers/${encodeURIComponent(node.id)}`)}
              colorMode={colorMode}
              theme={resolvedTheme}
              emptyText="No rings match these filters."
            />
          )}
        </div>
        <div className="stack">
          <div className="card">
            {selected && nodeIndex.has(selected.id) ? (
              <SelectedPanel node={nodeIndex.get(selected.id)!} />
            ) : (
              <div className="stack tight">
                <h2>Explore</h2>
                <p className="text-2 small">
                  Click an account to see why it was scored the way it was. Double-click to open its full profile. Scroll to zoom
                  and drag to pan.
                </p>
              </div>
            )}
          </div>
          {graph.data && (
            <div className="card stack tight small">
              <div>
                Showing <strong>{graph.data.nodes.length.toLocaleString()}</strong> accounts and{" "}
                <strong>{graph.data.edges.length.toLocaleString()}</strong> links from{" "}
                <strong>{graph.data.n_rings_shown?.toLocaleString()}</strong> of {graph.data.n_rings_total?.toLocaleString()} groups.
              </div>
              {graph.data.truncated && (
                <div className="muted">Only the highest-scoring groups fit; raise the minimum score to see others.</div>
              )}
              {graph.data.rings && selected?.ring_id && graph.data.rings[selected.ring_id] && (
                <div className="row">
                  {selected.ring_id}: <StatusBadge status={graph.data.rings[selected.ring_id].status} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
