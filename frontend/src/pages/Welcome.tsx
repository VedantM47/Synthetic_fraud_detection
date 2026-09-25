import { Link } from "react-router-dom";
import SyntheticForm from "../components/SyntheticForm";

export default function Welcome() {
  return (
    <div className="stack" style={{ maxWidth: 980 }}>
      <div className="page-head">
        <div className="titles">
          <h1>Find synthetic-identity fraud rings</h1>
          <p>
            Fraud rings reuse phone numbers, emails, addresses and devices across many fake identities. This console
            links customers that share identity details, scores every customer with a model, explains each score in
            plain English, and puts suspected rings in front of an analyst to confirm or dismiss. Analyst decisions
            are fed back into the model.
          </p>
        </div>
      </div>
      <div className="pipeline" aria-label="Pipeline">
        {["Upload or generate data", "Build identity graph", "Network + behaviour features", "Train & score", "Explain", "Detect rings", "Analyst review", "Retrain"].map(
          (step, index, all) => (
            <span key={step} className="row" style={{ gap: 6 }}>
              <span className="step">{step}</span>
              {index < all.length - 1 && <span aria-hidden="true">→</span>}
            </span>
          ),
        )}
      </div>
      <div className="grid two">
        <div className="card stack">
          <h2>Start with the synthetic demo</h2>
          <p className="text-2">
            Generates 8,000 legitimate customers and 800 fraud-ring members with realistic noise (households, shared
            contact phones, sparse rings), then runs the full pipeline. Takes about a minute.
          </p>
          <SyntheticForm compact />
        </div>
        <div className="card stack">
          <h2>Use your own data</h2>
          <p className="text-2">
            Upload a CSV with one row per customer. Columns such as phone, email, address, device or IP are detected
            automatically and you can adjust the mapping. Labels are optional: without them the app scores customers
            with a reference model and still surfaces the rings.
          </p>
          <div>
            <Link to="/data" className="btn primary">
              Upload a CSV
            </Link>
          </div>
          <p className="small muted">Sample files in a different format are available on the upload page.</p>
        </div>
      </div>
    </div>
  );
}
