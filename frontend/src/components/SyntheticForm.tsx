import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../context";

export default function SyntheticForm({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate();
  const { reloadDatasets } = useApp();
  const [seed, setSeed] = useState(42);
  const [legit, setLegit] = useState(8000);
  const [fraud, setFraud] = useState(800);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.createSynthetic({
        seed,
        n_legitimate: legit,
        n_fraud: fraud,
        name: name.trim() || undefined,
      });
      reloadDatasets();
      navigate(`/d/${result.dataset_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setBusy(false);
    }
  };

  return (
    <form className="stack" onSubmit={submit}>
      {!compact && (
        <div className="field">
          <label htmlFor="syn-name">Name (optional)</label>
          <input id="syn-name" className="input" value={name} onChange={(event) => setName(event.target.value)} placeholder="Synthetic demo" />
        </div>
      )}
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field">
          <label htmlFor="syn-legit">Legitimate customers</label>
          <input
            id="syn-legit"
            className="input num"
            type="number"
            min={200}
            max={50000}
            step={100}
            value={legit}
            onChange={(event) => setLegit(Number(event.target.value))}
            style={{ width: 130 }}
          />
        </div>
        <div className="field">
          <label htmlFor="syn-fraud">Fraud-ring customers</label>
          <input
            id="syn-fraud"
            className="input num"
            type="number"
            min={20}
            max={10000}
            step={10}
            value={fraud}
            onChange={(event) => setFraud(Number(event.target.value))}
            style={{ width: 130 }}
          />
        </div>
        <div className="field">
          <label htmlFor="syn-seed">Random seed</label>
          <input
            id="syn-seed"
            className="input num"
            type="number"
            min={0}
            value={seed}
            onChange={(event) => setSeed(Number(event.target.value))}
            style={{ width: 100 }}
          />
        </div>
      </div>
      {error && <div className="notice error">{error}</div>}
      <div>
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? "Starting…" : "Generate and analyse"}
        </button>
      </div>
      <p className="small muted">Seed 42 with the default sizes reproduces the research dataset and its published metrics.</p>
    </form>
  );
}
