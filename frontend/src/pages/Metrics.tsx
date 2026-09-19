import { api, type Experiment, type VersionSummary } from "../api";
import { BarList, ConfusionMatrix, CurveChart, GroupedColumns } from "../components/charts";
import RetrainBanner from "../components/RetrainBanner";
import { ErrorBox, Loading, PageHead, Stat } from "../components/ui";
import { useDataset } from "../context";
import { attributeLabel, dateTime, dec, EXPERIMENT_LABELS, GROUP_LABELS, MODEL_LABELS, modeLabel, pct } from "../format";
import { useApi } from "../hooks";

const GROUP_COLORS: Record<string, string> = {
  tabular: "var(--series-1)",
  network: "var(--series-2)",
  temporal: "var(--series-3)",
};

function Delta({ now, before }: { now: number | null | undefined; before: number | null | undefined }) {
  if (now === null || now === undefined || before === null || before === undefined) return null;
  const diff = now - before;
  if (Math.abs(diff) < 0.0005) return <span className="muted"> (±0)</span>;
  return (
    <span style={{ color: diff > 0 ? "var(--good-ink)" : "var(--critical-ink)" }}>
      {" "}
      ({diff > 0 ? "▲ +" : "▼ "}
      {diff.toFixed(3)})
    </span>
  );
}

function ExperimentTable({ rows }: { rows: Experiment[] }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Model</th>
            <th>Features</th>
            <th className="right">Precision</th>
            <th className="right">Recall</th>
            <th className="right">F1</th>
            <th className="right">ROC-AUC</th>
            <th className="right">PR-AUC</th>
            <th className="right">Accuracy</th>
            <th className="right">TP / FP / FN</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.model}-${row.experiment}`}>
              <td>{MODEL_LABELS[row.model] ?? row.model}</td>
              <td>{EXPERIMENT_LABELS[row.experiment] ?? row.experiment}</td>
              <td className="right num">{dec(row.precision, 4)}</td>
              <td className="right num">{dec(row.recall, 4)}</td>
              <td className="right num">{dec(row.f1, 4)}</td>
              <td className="right num">{dec(row.roc_auc, 4)}</td>
              <td className="right num">{dec(row.pr_auc, 4)}</td>
              <td className="right num">{dec(row.accuracy, 4)}</td>
              <td className="right num">
                {row.tp} / {row.fp} / {row.fn}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VersionTable({ history }: { history: VersionSummary[] }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Version</th>
            <th>Created</th>
            <th className="right">Analyst labels</th>
            <th className="right">ROC-AUC</th>
            <th className="right">PR-AUC</th>
            <th className="right">F1</th>
            <th>Previous version on the same customers</th>
            <th>What changed</th>
          </tr>
        </thead>
        <tbody>
          {history
            .slice()
            .reverse()
            .map((row) => {
              const previous = row.previous_same_customers;
              return (
                <tr key={row.version}>
                  <td>
                    <strong>v{row.version}</strong>
                    <div className="small muted">{row.mode === "supervised" ? "your labels" : "reference model"}</div>
                  </td>
                  <td className="small muted">{dateTime(row.created_at)}</td>
                  <td className="right num">
                    {row.n_feedback}
                    {row.feedback && row.n_feedback > 0 && (
                      <div className="small muted">
                        {row.feedback.fraud} fraud · {row.feedback.legit} legit
                      </div>
                    )}
                  </td>
                  <td className="right num">
                    {dec(row.roc_auc)}
                    <Delta now={row.roc_auc} before={previous?.roc_auc} />
                  </td>
                  <td className="right num">
                    {dec(row.pr_auc)}
                    <Delta now={row.pr_auc} before={previous?.pr_auc} />
                  </td>
                  <td className="right num">
                    {dec(row.f1)}
                    <Delta now={row.f1} before={previous?.f1} />
                  </td>
                  <td className="small text-2">
                    {previous ? (
                      <>
                        v{previous.version}: ROC-AUC {dec(previous.roc_auc)} · PR-AUC {dec(previous.pr_auc)} · F1 {dec(previous.f1)}
                      </>
                    ) : (
                      "–"
                    )}
                  </td>
                  <td className="small text-2">
                    {row.changes ? (
                      <>
                        {row.changes.level_changes} level changes ({row.changes.newly_high} newly high, {row.changes.no_longer_high} no
                        longer high); rings +{row.changes.rings_newly_suspected} / −{row.changes.rings_cleared}
                      </>
                    ) : (
                      "First version"
                    )}
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>
    </div>
  );
}

export default function MetricsPage() {
  const { dataset, version } = useDataset();
  const { data, error, reload } = useApi(() => api.metrics(dataset.id), [dataset.id, version]);
  const feedback = useApi(() => api.dataset(dataset.id), [dataset.id, version]);
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const metrics = data.current;
  const evaluation = metrics.evaluation;
  const experiments = metrics.experiments;
  const categories = Array.from(new Set(experiments.map((row) => row.experiment))).map((key) => ({
    key,
    label: EXPERIMENT_LABELS[key] ?? key,
  }));
  const models = Array.from(new Set(experiments.map((row) => row.model)));
  const seriesColors = ["var(--series-1)", "var(--series-2)"];
  const prevalence = evaluation ? evaluation.n_positive / Math.max(evaluation.n, 1) : undefined;
  const groupsPresent = Array.from(new Set(metrics.feature_importance.map((row) => row.group)));

  return (
    <div className="stack">
      <PageHead
        title="Model & metrics"
        subtitle={
          <>
            {modeLabel(metrics.mode)} · model v{data.version} · {metrics.model} · alert threshold{" "}
            {Math.round(metrics.threshold * 100)}/100 (chosen to maximise F1
            {metrics.mode === "transfer" ? " on the reference data" : " on out-of-fold predictions"})
          </>
        }
      />
      {feedback.data && <RetrainBanner feedback={feedback.data.feedback} />}

      {metrics.mode === "transfer" && metrics.reference && (
        <div className="notice info">
          <span aria-hidden="true">ℹ</span>
          <span>
            This dataset {dataset.summary?.label_mode === "evaluate" ? "has labels but they were hidden from the model" : "has no fraud labels"}
            , so it is scored by a model trained on the {metrics.reference.source.toLowerCase()} using only the features your
            data provides ({metrics.reference.features.length} features:{" "}
            {metrics.reference.attribute_types.map(attributeLabel).join(", ") || "no core identity types"}
            {metrics.reference.features.some(
              (feature) => !feature.endsWith("_shared_count") && feature !== "network_degree" && feature !== "shared_attribute_count",
            )
              ? " + account behaviour"
              : ""}
            ).
            Cross-validated ROC-AUC on the reference data: {dec(metrics.reference.reference_roc_auc)}.
            {metrics.feedback.n_labels > 0 && ` ${metrics.feedback.n_labels} analyst labels from this dataset were added to training.`}
          </span>
        </div>
      )}

      {evaluation ? (
        <>
          <div className="stats">
            <Stat label="ROC-AUC" value={dec(evaluation.roc_auc)} sub="Chance of ranking a fraud above a legit customer" />
            <Stat label="PR-AUC" value={dec(evaluation.pr_auc)} sub={`Baseline (fraud rate) ${pct(prevalence, 1)}`} />
            <Stat label="Precision at threshold" value={pct(evaluation.precision, 1)} sub={`${evaluation.tp} of ${evaluation.tp + evaluation.fp} alerts are fraud`} />
            <Stat label="Recall at threshold" value={pct(evaluation.recall, 1)} sub={`${evaluation.tp} of ${evaluation.n_positive} fraud customers caught`} />
            <Stat label="F1" value={dec(evaluation.f1)} sub={`${evaluation.n.toLocaleString()} customers evaluated`} />
          </div>
          <p className="small muted">Evaluated on: {evaluation.scope}.</p>
          {evaluation.previous_version && (
            <div className="notice">
              <span>
                Same customers under model v{evaluation.previous_version.version}: ROC-AUC {dec(evaluation.previous_version.roc_auc)}
                <Delta now={evaluation.roc_auc} before={evaluation.previous_version.roc_auc} />, PR-AUC{" "}
                {dec(evaluation.previous_version.pr_auc)}
                <Delta now={evaluation.pr_auc} before={evaluation.previous_version.pr_auc} />, F1 {dec(evaluation.previous_version.f1)}
                <Delta now={evaluation.f1} before={evaluation.previous_version.f1} />. This like-for-like comparison is the fair way to judge
                whether feedback helped.
              </span>
            </div>
          )}
          <div className="grid two">
            <div className="card">
              <div className="card-head">
                <h2>ROC curve</h2>
                <span className="hint">Diagonal = random guessing</span>
              </div>
              <CurveChart points={evaluation.roc_curve} xLabel="False-positive rate" yLabel="True-positive rate" diagonal />
            </div>
            <div className="card">
              <div className="card-head">
                <h2>Precision–recall curve</h2>
                <span className="hint">Flat line = fraud base rate</span>
              </div>
              <CurveChart points={evaluation.pr_curve} xLabel="Recall" yLabel="Precision" baseline={prevalence} />
            </div>
          </div>
          <div className="grid two">
            <div className="card">
              <div className="card-head">
                <h2>Confusion matrix</h2>
                <span className="hint">At the alert threshold</span>
              </div>
              <ConfusionMatrix tn={evaluation.tn} fp={evaluation.fp} fn={evaluation.fn} tp={evaluation.tp} />
            </div>
            <div className="card flush">
              <div className="card-head" style={{ padding: "16px 16px 0" }}>
                <h2>If analysts review the top K customers</h2>
              </div>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th className="right">Top K</th>
                      <th className="right">Share that is fraud</th>
                      <th className="right">Share of all fraud found</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.at_k.map((row) => (
                      <tr key={row.k}>
                        <td className="right num">{row.k.toLocaleString()}</td>
                        <td className="right num">{pct(row.precision, 1)}</td>
                        <td className="right num">{pct(row.recall, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="notice">
          This dataset has no fraud labels, so accuracy can't be measured here. Confirm or dismiss rings in the review screen: those
          decisions are used for training when you retrain, and the reference model's own performance is shown above.
        </div>
      )}

      {experiments.length > 0 && (
        <div className="card stack">
          <div className="card-head" style={{ marginBottom: 0 }}>
            <h2>Which features matter: model comparison</h2>
            {metrics.experiment_split && (
              <span className="hint">
                Ring-aware 80/20 split: {metrics.experiment_split.n_train.toLocaleString()} train /{" "}
                {metrics.experiment_split.n_test.toLocaleString()} test ({metrics.experiment_split.n_test_positive} fraud); no ring
                is split across train and test
              </span>
            )}
          </div>
          <p className="text-2 small">
            ROC-AUC on the held-out test set. Profile data alone (income, credit score, tenure) is no better than chance; the
            identity network adds most of the signal, and behaviour over time adds more.
          </p>
          <GroupedColumns
            categories={categories}
            series={models.map((model, index) => ({
              key: model,
              label: MODEL_LABELS[model] ?? model,
              color: seriesColors[index % seriesColors.length],
              values: Object.fromEntries(experiments.filter((row) => row.model === model).map((row) => [row.experiment, row.roc_auc])),
            }))}
          />
          <ExperimentTable rows={experiments} />
        </div>
      )}

      <div className="grid two">
        <div className="card">
          <div className="card-head">
            <h2>Feature importance</h2>
            <span className="hint">Average effect on a customer's score (points)</span>
          </div>
          <BarList
            rows={metrics.feature_importance.slice(0, 15).map((row) => ({
              key: row.feature,
              label: row.label,
              value: row.importance * 100,
              color: GROUP_COLORS[row.group],
              detail: GROUP_LABELS[row.group],
            }))}
            format={(value) => value.toFixed(1)}
            legend={groupsPresent.map((group) => ({ label: GROUP_LABELS[group] ?? group, color: GROUP_COLORS[group] }))}
          />
        </div>
        <div className="card stack">
          <div className="card-head" style={{ marginBottom: 0 }}>
            <h2>Identity graph</h2>
          </div>
          <dl className="kv">
            <dt>Customers</dt>
            <dd className="num">{metrics.graph.n_nodes.toLocaleString()}</dd>
            <dt>Linked customers</dt>
            <dd className="num">{metrics.graph.linked_customers.toLocaleString()}</dd>
            <dt>Links</dt>
            <dd className="num">{metrics.graph.n_edges.toLocaleString()}</dd>
            <dt>Connected groups</dt>
            <dd className="num">{metrics.ring_detection.n_candidates.toLocaleString()}</dd>
            <dt>Suspected rings</dt>
            <dd className="num">{metrics.ring_detection.n_suspected.toLocaleString()}</dd>
            {metrics.graph.label_mix && (
              <>
                <dt>Links between known-legit customers</dt>
                <dd className="num">{metrics.graph.label_mix.legit_legit.toLocaleString()}</dd>
                <dt>Links between known-fraud customers</dt>
                <dd className="num">{metrics.graph.label_mix.fraud_fraud.toLocaleString()}</dd>
                <dt>Mixed fraud–legit links</dt>
                <dd className="num">{metrics.graph.label_mix.mixed.toLocaleString()}</dd>
              </>
            )}
          </dl>
          {metrics.ring_detection.truth && (
            <>
              <div className="divider" />
              <dl className="kv">
                <dt>Suspected rings that are mostly fraud</dt>
                <dd className="num">{pct(metrics.ring_detection.truth.precision, 1)}</dd>
                <dt>Fraud customers inside a suspected ring</dt>
                <dd className="num">{pct(metrics.ring_detection.truth.member_recall, 1)}</dd>
                {metrics.ring_detection.truth.ring_recall !== null && (
                  <>
                    <dt>Known rings recovered</dt>
                    <dd className="num">
                      {pct(metrics.ring_detection.truth.ring_recall, 1)} of {metrics.ring_detection.truth.n_true_rings}
                    </dd>
                  </>
                )}
              </dl>
            </>
          )}
          <div className="divider" />
          <BarList
            rows={Object.entries(metrics.graph.edges_by_type).map(([kind, count]) => ({ key: kind, label: `${attributeLabel(kind)} links`, value: count }))}
          />
        </div>
      </div>

      <div className="card flush">
        <div className="card-head" style={{ padding: "16px 16px 0" }}>
          <h2>Model versions &amp; feedback loop</h2>
          <span className="hint">Each retrain adds analyst decisions as labels. Ring IDs stay stable across versions.</span>
        </div>
        <VersionTable history={data.history} />
      </div>

      {metrics.notes.length > 0 && (
        <div className="card stack tight">
          <h2>Notes from the pipeline</h2>
          <ul style={{ margin: 0, paddingLeft: 18 }} className="text-2">
            {metrics.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
