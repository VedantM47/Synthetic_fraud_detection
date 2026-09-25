import type { Job } from "../api";
import { useJobStream } from "../hooks";

const KIND_LABELS: Record<string, string> = {
  synthetic: "Generating and analysing a synthetic dataset",
  analyze: "Analysing your data",
  retrain: "Retraining with analyst feedback",
};

function elapsed(job: Job): string {
  if (!job.started_at) return "";
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(job.started_at).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function JobStages({ job }: { job: Job }) {
  return (
    <ol className="stages">
      {job.stages.map((stage) => (
        <li key={stage.key}>
          <span className={`stage-icon ${stage.status}`} aria-hidden="true">
            {stage.status === "done" ? "✓" : stage.status === "failed" ? "!" : ""}
          </span>
          <div>
            <div className="stage-name">{stage.label}</div>
            {stage.message && <div className="stage-msg">{stage.message}</div>}
          </div>
          <span className="small muted num">
            {stage.status === "running" ? `${Math.round(stage.progress * 100)}%` : stage.status === "done" ? "done" : ""}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Live progress for one job (Server-Sent Events with polling fallback). */
export default function JobProgress({ jobId, onFinish }: { jobId: string; onFinish?: (job: Job) => void }) {
  const job = useJobStream(jobId, onFinish);
  if (!job) {
    return (
      <div className="loading">
        <span className="spinner" /> Connecting to the job…
      </div>
    );
  }
  const percent = Math.round(job.progress * 100);
  return (
    <div className="stack" aria-live="polite">
      <div className="row between">
        <strong>{KIND_LABELS[job.kind] ?? job.kind}</strong>
        <span className="small muted num">
          {job.status === "completed" ? "Finished" : job.status === "failed" ? "Failed" : `${percent}%`} · {elapsed(job)}
        </span>
      </div>
      <div className="progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${job.status === "completed" ? 100 : percent}%` }} />
      </div>
      {job.status === "failed" && job.error && <div className="notice error">{job.error}</div>}
      <JobStages job={job} />
    </div>
  );
}
