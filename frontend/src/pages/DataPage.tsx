import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import SyntheticForm from "../components/SyntheticForm";
import UploadWizard from "../components/UploadWizard";
import { ErrorBox, Loading, PageHead } from "../components/ui";
import { useApp } from "../context";
import { dateTime, modeLabel } from "../format";
import { useApi } from "../hooks";

export default function DataPage() {
  const { datasets, datasetsError, reloadDatasets } = useApp();
  const jobs = useApi(() => api.jobs(), [datasets]);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const remove = async (id: string, name: string) => {
    if (!window.confirm(`Delete "${name}" and all of its reviews? This cannot be undone.`)) return;
    setDeleting(id);
    setError(null);
    try {
      await api.deleteDataset(id);
      reloadDatasets();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="stack">
      <PageHead
        title="Datasets & uploads"
        subtitle="Bring your own customer data or generate a synthetic population. Every dataset runs through the same pipeline: identity graph, features, model, explanations, ring detection."
      />
      <div className="card stack">
        <div className="card-head">
          <h2>Upload your own data</h2>
          <span className="hint">CSV / TSV · up to 200 MB</span>
        </div>
        <UploadWizard />
      </div>
      <div className="card stack">
        <div className="card-head">
          <h2>Generate a synthetic dataset</h2>
          <span className="hint">Known fraud rings, useful for demos and for measuring the model</span>
        </div>
        <SyntheticForm />
      </div>
      <div className="card flush">
        <div className="card-head" style={{ padding: "16px 16px 0" }}>
          <h2>Your datasets</h2>
        </div>
        {error && (
          <div style={{ padding: "0 16px" }}>
            <ErrorBox message={error} />
          </div>
        )}
        {datasetsError && <ErrorBox message={datasetsError} onRetry={reloadDatasets} />}
        {!datasets ? (
          <Loading />
        ) : datasets.length === 0 ? (
          <p className="empty">No datasets yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Source</th>
                  <th className="right">Customers</th>
                  <th>Model</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {datasets.map((dataset) => (
                  <tr key={dataset.id}>
                    <td>
                      <Link to={`/d/${dataset.id}`}>
                        <strong>{dataset.name}</strong>
                      </Link>
                    </td>
                    <td>{dataset.source === "synthetic" ? "Synthetic" : "Upload"}</td>
                    <td className="right num">{dataset.summary?.n_customers?.toLocaleString() ?? "–"}</td>
                    <td className="small">
                      {dataset.summary ? `${modeLabel(dataset.summary.mode)} · v${dataset.active_version}` : "–"}
                    </td>
                    <td>
                      {dataset.active_job ? (
                        <span className="row small" style={{ gap: 6 }}>
                          <span className="spinner" /> {Math.round(dataset.active_job.progress * 100)}%
                        </span>
                      ) : dataset.status === "failed" ? (
                        <span className="badge confirmed" title={dataset.error ?? ""}>
                          Failed
                        </span>
                      ) : (
                        <span className="badge dismissed">Ready</span>
                      )}
                    </td>
                    <td className="small muted">{dateTime(dataset.created_at)}</td>
                    <td className="right">
                      <button
                        className="btn small ghost"
                        disabled={deleting === dataset.id || Boolean(dataset.active_job)}
                        onClick={() => remove(dataset.id, dataset.name)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {jobs.data && jobs.data.length > 0 && (
        <div className="card flush">
          <div className="card-head" style={{ padding: "16px 16px 0" }}>
            <h2>Recent jobs</h2>
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Dataset</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.slice(0, 10).map((job) => {
                  const dataset = datasets?.find((item) => item.id === job.dataset_id);
                  return (
                    <tr key={job.id}>
                      <td>{job.kind === "retrain" ? "Retrain with feedback" : job.kind === "synthetic" ? "Generate + analyse" : "Analyse upload"}</td>
                      <td>{dataset ? <Link to={`/d/${dataset.id}`}>{dataset.name}</Link> : <span className="muted">deleted</span>}</td>
                      <td>
                        {job.status === "completed" ? (
                          <span className="badge dismissed">Completed</span>
                        ) : job.status === "failed" ? (
                          <span className="badge confirmed">Failed</span>
                        ) : (
                          <span className="badge info">
                            {job.status} {Math.round(job.progress * 100)}%
                          </span>
                        )}
                      </td>
                      <td className="small muted">{dateTime(job.started_at ?? job.created_at)}</td>
                      <td className="small text-2 truncate" style={{ maxWidth: 360 }}>
                        {job.error ?? (job.result ? `Model version ${job.result.version} (${job.result.mode})` : job.message)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
