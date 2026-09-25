import { useState } from "react";
import { api, type FeedbackSummary } from "../api";
import { useDataset } from "../context";

/** Prompts the analyst to feed new review decisions back into the model. */
export default function RetrainBanner({ feedback, compact = false }: { feedback: FeedbackSummary; compact?: boolean }) {
  const { dataset, startJob } = useDataset();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const running = Boolean(dataset.active_job);

  const retrain = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.retrain(dataset.id);
      startJob(result.job_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  if (!feedback.retrain_recommended && compact) return null;
  return (
    <div className={`notice ${feedback.retrain_recommended ? "info" : ""}`} style={{ alignItems: "center", flexWrap: "wrap" }}>
      <div style={{ flex: 1, minWidth: 240 }}>
        {feedback.retrain_recommended ? (
          <>
            <strong>
              {feedback.reviews_since_model} new review decision{feedback.reviews_since_model === 1 ? "" : "s"}
            </strong>{" "}
            since model v{dataset.active_version}. Analysts have labelled {feedback.fraud} account
            {feedback.fraud === 1 ? "" : "s"} as fraud and {feedback.legit} as legitimate. Retrain to feed these decisions
            back into the model; ring IDs stay the same.
          </>
        ) : feedback.n_reviews === 0 ? (
          <>
            No analyst decisions yet. Confirm or dismiss rings in the review screen; each decision becomes a training label
            and a “Retrain with feedback” button appears here.
          </>
        ) : (
          <>
            Model v{dataset.active_version} already includes all {feedback.labels_in_model} analyst label
            {feedback.labels_in_model === 1 ? "" : "s"}. Review more rings to improve it further.
          </>
        )}
        {error && <div className="small" style={{ color: "var(--critical-ink)" }}>{error}</div>}
      </div>
      {feedback.retrain_recommended && (
        <button className="btn primary" onClick={retrain} disabled={busy || running}>
          {running ? "Job running…" : busy ? "Starting…" : "Retrain with feedback"}
        </button>
      )}
    </div>
  );
}
