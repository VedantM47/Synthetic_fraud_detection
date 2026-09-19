import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, sampleUrl, type FilePreview, type SampleFile, type UploadResponse } from "../api";
import { useApp } from "../context";
import { useApi } from "../hooks";

type FileKind = "customers" | "events" | "links";

const ROLE_OPTIONS: { value: string; label: string; group: string }[] = [
  { value: "ignore", label: "Ignore", group: "General" },
  { value: "customer_id", label: "Customer ID", group: "General" },
  { value: "name", label: "Name", group: "General" },
  { value: "open_date", label: "Account open date", group: "General" },
  { value: "feature", label: "Numeric feature", group: "General" },
  { value: "label", label: "Fraud label (1/0, yes/no)", group: "Labels" },
  { value: "ring", label: "Known ring ID (evaluation only)", group: "Labels" },
  { value: "phone", label: "Phone number", group: "Shared identity details" },
  { value: "email", label: "Email address", group: "Shared identity details" },
  { value: "address", label: "Address (several columns are combined)", group: "Shared identity details" },
  { value: "device", label: "Device ID / fingerprint", group: "Shared identity details" },
  { value: "ip", label: "IP address", group: "Shared identity details" },
  { value: "national_id", label: "National ID / SSN (hashed)", group: "Shared identity details" },
  { value: "bank_account", label: "Bank account / card (hashed)", group: "Shared identity details" },
  { value: "identifier", label: "Other shared identifier", group: "Shared identity details" },
];
const IDENTITY = new Set(["phone", "email", "address", "device", "ip", "national_id", "bank_account", "identifier"]);
const SINGLE = ["customer_id", "label", "ring", "open_date"];

const EVENT_FIELDS: { key: string; label: string; required?: boolean }[] = [
  { key: "customer_id", label: "Customer ID", required: true },
  { key: "event_date", label: "Date", required: true },
  { key: "event_type", label: "Event type" },
  { key: "utilization", label: "Credit utilization" },
  { key: "credit_limit", label: "Credit limit" },
];
const LINK_FIELDS: { key: string; label: string; required?: boolean }[] = [
  { key: "customer_id", label: "Customer ID", required: true },
  { key: "attribute_type", label: "Attribute type (phone, email, …)", required: true },
  { key: "attribute_value", label: "Attribute value", required: true },
];

function sizeText(bytes: number): string {
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function FilePicker({
  kind,
  title,
  hint,
  file,
  onFile,
}: {
  kind: FileKind;
  title: string;
  hint: string;
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div
      className={`dropzone${drag ? " drag" : ""}`}
      onClick={() => input.current?.click()}
      onDragOver={(event) => {
        event.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDrag(false);
        if (event.dataTransfer.files[0]) onFile(event.dataTransfer.files[0]);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") input.current?.click();
      }}
      aria-label={`Choose the ${kind} file`}
    >
      <input
        ref={input}
        type="file"
        accept=".csv,.tsv,.txt,text/csv"
        onChange={(event) => onFile(event.target.files?.[0] ?? null)}
      />
      <strong>{title}</strong>
      {file ? (
        <div className="row between">
          <span>
            {file.name} <span className="muted small">({sizeText(file.size)})</span>
          </span>
          <button
            className="btn small ghost"
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onFile(null);
              if (input.current) input.current.value = "";
            }}
          >
            Remove
          </button>
        </div>
      ) : (
        <span className="small muted">{hint}</span>
      )}
    </div>
  );
}

function FieldMapping({
  preview,
  fields,
  mapping,
  onChange,
}: {
  preview: FilePreview;
  fields: { key: string; label: string; required?: boolean }[];
  mapping: Record<string, string | null>;
  onChange: (next: Record<string, string | null>) => void;
}) {
  return (
    <div className="grid two" style={{ gap: 10 }}>
      {fields.map((field) => (
        <div className="field" key={field.key}>
          <label>
            {field.label}
            {field.required ? " *" : ""}
          </label>
          <select
            className="input"
            value={mapping[field.key] ?? ""}
            onChange={(event) => onChange({ ...mapping, [field.key]: event.target.value || null })}
          >
            <option value="">{field.required ? "Choose a column…" : "Not available"}</option>
            {preview.columns.map((column) => (
              <option key={column.name} value={column.name}>
                {column.name}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}

export default function UploadWizard() {
  const navigate = useNavigate();
  const { reloadDatasets } = useApp();
  const samples = useApi<SampleFile[]>(() => api.samples(), []);
  const [files, setFiles] = useState<Record<FileKind, File | null>>({ customers: null, events: null, links: null });
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [labelMode, setLabelMode] = useState<"train" | "evaluate">("train");
  const [eventMap, setEventMap] = useState<Record<string, string | null>>({});
  const [linkMap, setLinkMap] = useState<Record<string, string | null>>({});
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const setFile = (kind: FileKind, file: File | null) => {
    setFiles((current) => ({ ...current, [kind]: file }));
    setUpload(null);
    setError(null);
    if (kind === "customers" && file && !name) setName(file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
  };

  const loadSample = async (customers: string, events?: string) => {
    setBusy("Loading sample…");
    setError(null);
    try {
      const fetchFile = async (fileName: string) => {
        const response = await fetch(sampleUrl(fileName));
        if (!response.ok) throw new Error(`Could not load ${fileName}`);
        return new File([await response.blob()], fileName, { type: "text/csv" });
      };
      const next = { customers: await fetchFile(customers), events: events ? await fetchFile(events) : null, links: null };
      setFiles(next);
      setUpload(null);
      setName(customers.replace(/\.csv$/, "").replace(/_/g, " "));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const doUpload = async () => {
    if (!files.customers) return;
    setBusy("Uploading and detecting columns…");
    setError(null);
    try {
      const result = await api.upload({ customers: files.customers, events: files.events, links: files.links });
      setUpload(result);
      setRoles(result.files.customers?.suggested_roles ?? {});
      setEventMap((result.files.events?.suggested_fields as Record<string, string | null>) ?? {});
      setLinkMap((result.files.links?.suggested_fields as Record<string, string | null>) ?? {});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const customersPreview = upload?.files.customers;
  const problems = useMemo(() => {
    const list: string[] = [];
    if (!upload) return list;
    for (const role of SINGLE) {
      const count = Object.values(roles).filter((value) => value === role).length;
      if (count > 1) list.push(`Only one column can be the ${ROLE_OPTIONS.find((option) => option.value === role)?.label}.`);
    }
    const identity = Object.values(roles).some((value) => IDENTITY.has(value));
    const hasLinks = Boolean(upload.files.links && linkMap.customer_id && linkMap.attribute_type && linkMap.attribute_value);
    const hasEvents = Boolean(upload.files.events && eventMap.customer_id && eventMap.event_date);
    const hasLabel = Object.values(roles).includes("label");
    const hasFeatures = Object.values(roles).some((value) => value === "feature" || value === "open_date");
    if (!identity && !hasLinks && !hasEvents && !(hasLabel && hasFeatures)) {
      list.push("Map at least one shared identity detail (phone, email, address, device, …) so rings can be found.");
    }
    if (upload.files.events && !(eventMap.customer_id && eventMap.event_date)) {
      list.push("Events file: choose the customer ID and date columns (or remove the file).");
    }
    if (upload.files.links && !hasLinks) list.push("Identity links file: choose all three columns.");
    if (!name.trim()) list.push("Give the dataset a name.");
    return list;
  }, [upload, roles, eventMap, linkMap, name]);

  const identityCount = Object.values(roles).filter((value) => IDENTITY.has(value)).length;
  const identityTypes = Object.entries(
    Object.values(roles)
      .filter((value) => IDENTITY.has(value))
      .reduce<Record<string, number>>((counts, value) => ({ ...counts, [value]: (counts[value] ?? 0) + 1 }), {}),
  );
  const hasLabel = Object.values(roles).includes("label");

  const submit = async () => {
    if (!upload || problems.length) return;
    setBusy("Starting analysis…");
    setError(null);
    try {
      const mapping: Record<string, unknown> = { customers: { roles, label_mode: labelMode } };
      if (upload.files.events) mapping.events = eventMap;
      if (upload.files.links) mapping.links = linkMap;
      const result = await api.createDataset({ upload_id: upload.upload_id, name: name.trim(), mapping });
      reloadDatasets();
      navigate(`/d/${result.dataset_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setBusy(null);
    }
  };

  return (
    <div className="stack">
      <div className="grid three">
        <FilePicker
          kind="customers"
          title="1. Customers file (required)"
          hint="CSV, one row per customer. Drop it here or click to choose."
          file={files.customers}
          onFile={(file) => setFile("customers", file)}
        />
        <FilePicker
          kind="events"
          title="Account events (optional)"
          hint="Customer ID + date per row; type, utilization and limit if you have them."
          file={files.events}
          onFile={(file) => setFile("events", file)}
        />
        <FilePicker
          kind="links"
          title="Identity links (optional)"
          hint="Long format: customer ID, attribute type, attribute value."
          file={files.links}
          onFile={(file) => setFile("links", file)}
        />
      </div>
      {samples.data && samples.data.length > 0 && (
        <div className="notice info" style={{ flexWrap: "wrap" }}>
          <span>
            <strong>No data at hand?</strong> Try the sample bank export (different column names, messy phone formats,
            split addresses):
          </span>
          <div className="row">
            <button className="btn small" type="button" onClick={() => loadSample("bank_customers_labeled.csv", "bank_account_events.csv")}>
              Labeled sample + events
            </button>
            <button className="btn small" type="button" onClick={() => loadSample("bank_customers_unlabeled.csv")}>
              Unlabeled sample
            </button>
            {samples.data.map((sample) => (
              <a key={sample.name} className="small" href={sampleUrl(sample.name)} title={sample.description} download>
                {sample.name}
              </a>
            ))}
          </div>
        </div>
      )}
      {!upload && (
        <div className="row">
          <button className="btn primary" disabled={!files.customers || Boolean(busy)} onClick={doUpload}>
            {busy ?? "Upload and detect columns"}
          </button>
        </div>
      )}
      {error && <div className="notice error">{error}</div>}

      {upload && customersPreview && (
        <div className="stack">
          <div className="divider" />
          <div className="row between">
            <h2>2. Check the detected columns</h2>
            <span className="small muted">
              {customersPreview.n_rows.toLocaleString()} rows in {customersPreview.filename}
            </span>
          </div>
          <p className="text-2 small">
            Each column was given a role automatically. Change anything that looks wrong. Columns marked as shared identity
            details are how customers get linked into rings; values are normalised (phone formats, letter case, placeholders
            like "N/A") before matching.
          </p>
          <div className="card flush">
            <div className="table-wrap">
              <table className="data mapping-table">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Examples</th>
                    <th className="right">Distinct</th>
                    <th>Role</th>
                  </tr>
                </thead>
                <tbody>
                  {customersPreview.columns.map((column) => (
                    <tr key={column.name}>
                      <td>
                        <strong>{column.name}</strong>
                      </td>
                      <td className="small text-2">
                        <div className="truncate" style={{ maxWidth: 320 }}>
                          {column.examples.join(" · ") || <span className="muted">(empty)</span>}
                        </div>
                      </td>
                      <td className="right num small">{column.n_unique.toLocaleString()}</td>
                      <td>
                        <select
                          className="input"
                          aria-label={`Role for ${column.name}`}
                          value={roles[column.name] ?? "ignore"}
                          onChange={(event) => setRoles({ ...roles, [column.name]: event.target.value })}
                        >
                          {["General", "Labels", "Shared identity details"].map((group) => (
                            <optgroup key={group} label={group}>
                              {ROLE_OPTIONS.filter((option) => option.group === group).map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="small text-2">
            {identityCount === 0
              ? "No shared identity details mapped yet"
              : `Customers will be linked through: ${identityTypes
                  .map(([kind, count]) =>
                    `${ROLE_OPTIONS.find((option) => option.value === kind)?.label.split(" (")[0].toLowerCase()}${
                      count > 1 ? (kind === "address" ? ` (${count} columns combined)` : ` (${count} columns)`) : ""
                    }`,
                  )
                  .join(", ")}`}
            {Object.values(roles).includes("customer_id") ? "" : " · no ID column: row numbers will be used"}
          </div>

          {hasLabel && (
            <div className="card stack tight">
              <strong>How should the fraud label be used?</strong>
              <label className="check">
                <input type="radio" name="label-mode" checked={labelMode === "train"} onChange={() => setLabelMode("train")} />
                Train a model on my labels (scores come from cross-validation, so no customer is scored by a model that saw
                its own label)
              </label>
              <label className="check">
                <input
                  type="radio"
                  name="label-mode"
                  checked={labelMode === "evaluate"}
                  onChange={() => setLabelMode("evaluate")}
                />
                Evaluate only: hide the labels from the model, score with the reference model, and report how well it did
              </label>
            </div>
          )}
          {!hasLabel && (
            <div className="notice">
              No fraud label mapped: customers will be scored by the reference model trained on the synthetic dataset,
              using only the kinds of data your file has. Analyst reviews later become labels for retraining.
            </div>
          )}

          {upload.files.events && (
            <div className="card stack">
              <strong>Events file columns ({upload.files.events.n_rows.toLocaleString()} rows)</strong>
              <FieldMapping preview={upload.files.events} fields={EVENT_FIELDS} mapping={eventMap} onChange={setEventMap} />
            </div>
          )}
          {upload.files.links && (
            <div className="card stack">
              <strong>Identity links file columns ({upload.files.links.n_rows.toLocaleString()} rows)</strong>
              <FieldMapping preview={upload.files.links} fields={LINK_FIELDS} mapping={linkMap} onChange={setLinkMap} />
            </div>
          )}

          <div className="field" style={{ maxWidth: 420 }}>
            <label htmlFor="dataset-name">3. Dataset name</label>
            <input id="dataset-name" className="input" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          {problems.length > 0 && (
            <div className="notice error">
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="row">
            <button className="btn primary" disabled={problems.length > 0 || Boolean(busy)} onClick={submit}>
              {busy ?? "Run the analysis"}
            </button>
            <button className="btn ghost" onClick={() => setUpload(null)} disabled={Boolean(busy)}>
              Start over
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
