# Project Assessment

*Prepared by inspecting the repository directly — reading source files, running `git log`/`git status`, checking installed dependencies, and reading (not just skimming) the backend pipeline, the FastAPI surface, the React frontend, and the test suite. Where a claim in `README.md` or `PROJECT_STATUS.md` could be checked against code, it was. Where it couldn't (mainly: actually executing the test suite and the frontend build in this environment — see §9 and §14), that is stated explicitly rather than assumed.*

## 1. Executive Summary

**What is it?** A tool that detects "synthetic identity fraud rings" — groups of fake accounts that share phone numbers, emails, addresses or devices. It ships with (a) a synthetic-data generator that creates a realistic fake bank population with injected fraud rings, (b) a machine-learning pipeline that links customers into an identity graph and scores each one for risk, and (c) a web application ("analyst console") where a fraud analyst can upload their own CSV, see suspected rings, read a plain-English explanation for every risk score, confirm or dismiss rings, and retrain the model on their feedback.

**Who is it for?** A fraud-operations analyst or a team evaluating a fraud-detection approach — someone who wants to see suspected rings and act on them, not someone who wants to write Python. It also functions as a research/experimentation harness (the original script-based pipeline under `src/` and `data_generation/` still runs standalone and produces a reproducible experiment table).

**What is already built?** All of it, in the sense that every feature named in the README maps to real, working code: CSV ingestion with automatic column-role detection for foreign schemas, identity-graph construction, network + behavioural feature engineering, a supervised **and** a "transfer" (label-free) scoring mode, Shapley-based explanations, ring detection and an analyst review workflow, a feedback-driven retraining loop with before/after metrics, live per-stage job progress over Server-Sent Events, and a full React console covering all of it. An optional graph-contrastive-learning (GNN) bolt-on is also implemented and evaluated, though not wired into the app.

**How complete is it?** Very complete for a single-analyst, single-machine tool. It is **not** complete as a multi-user, hosted, production system: there is no authentication, no deployment tooling (no Dockerfile, no CI), one background worker processes one job at a time, and the graph/features are computed over the whole dataset at once rather than at a point in time (explicitly called out as future work by the authors themselves).

**Current maturity:** Advanced MVP, bordering on Beta, for local/single-analyst use. See §23–25.

**Biggest problems:** (1) No automated verification was possible in *this* environment — no Python virtual environment or `pytest` installed, no `node_modules` — so the claimed "18 tests pass" and "typecheck passes" could not be independently re-run, only read and judged for quality (they read as genuine, specific, evidence-producing tests, not placeholders). (2) The system is transductive/static by design — it can find rings in a snapshot, but cannot yet say "we would have caught this ring 10 days before the bust-out." (3) Nothing here is production-hardened: no auth, no deployment automation, no CI, one job at a time.

**What should happen next?** Nothing is broken or half-built, so the right next step is not "finish features," it's (a) get the test suite actually running in CI so the well-written tests provide continuous evidence rather than one-time developer claims, and (b) tackle the deliberately deferred temporal/point-in-time modelling, which is the one place where the product's real-world claims (`catches fraud`) are weaker than its snapshot-accuracy claims.

---

## 2. Project at a Glance

| | |
|---|---|
| **Project name** | Synthetic Identity Fraud Detection (analyst console: "Fraud Ring Console") |
| **Problem solved** | Detecting rings of fake identities that share contact/device details across many accounts |
| **Target users** | Fraud analysts / investigators; secondarily, ML researchers evaluating the approach |
| **Core value proposition** | Turns a raw customer export (any column names) into a scored, explained, reviewable list of suspected fraud rings, and improves with analyst feedback |
| **Current maturity** | Advanced MVP / early Beta (single-user, local) |
| **Estimated completion** | **78%** (methodology in §9) — weighted toward implementation maturity, not line count |
| **Demo readiness** | 9/10 |
| **MVP readiness** | 8/10 |
| **Production readiness** | 3/10 |

---

## 3. What the Project Does

Two things live side by side in this repository:

1. **A research pipeline** (`data_generation/`, `src/data/`, `src/models/`) that generates a synthetic bank population with injected fraud rings, builds an identity graph, engineers network and behavioural features, and trains/evaluates Random Forest and HistGradientBoosting classifiers. This is the original "Week 1–3" project and still runs standalone (`python -m data_generation.run_all`, etc.).
2. **A web application** (`backend/`, `frontend/`) built on top of it, which is the actual deliverable a non-technical stakeholder would look at: upload a CSV (or generate a synthetic demo), watch a live progress bar while it's analysed, then browse an overview dashboard, a fraud-ring review queue, an interactive network graph, a searchable customer list, per-customer detail pages with plain-English explanations, and a model-metrics page. Analyst decisions (confirm/dismiss a ring) become training labels for the next model version.

The two halves are genuinely connected, not just adjacent: the app's pipeline (`backend/pipeline/`) imports and reuses the research pipeline's feature and split code (`src/data/build_customer_graph.py`, `src/data/generate_red_flag_features.py`, `src/data/split_data.py`), and the app reproduces the exact research experiment table live for any labelled dataset (verified in `tests/test_app.py::test_synthetic_job_reproduces_the_research_experiments`, which asserts specific ROC-AUC and confusion-matrix numbers).

## 4. Current User Journey

```
Visitor → Choose "Generate & analyse" or "Upload a CSV" → (upload: map columns) →
Live progress (per-stage) → Overview dashboard → Fraud-ring review (confirm/dismiss) →
Network graph / Customer detail (drill down) → Model & metrics → Retrain with feedback →
Version 2 with before/after comparison
```

| Stage | Status | Evidence |
|---|---|---|
| Landing / choose synthetic or upload | ✅ Working | `frontend/src/pages/Welcome.tsx`, `DataPage.tsx` |
| Upload + column mapping | ✅ Working | `UploadWizard.tsx` (451 lines) talks to `/api/uploads` and `/api/roles`; column-role auto-detection is unit-tested against a deliberately foreign schema (`tests/test_app.py::test_column_roles_are_detected_for_a_foreign_schema`) |
| Live progress | ✅ Working | SSE endpoint `/api/jobs/{id}/stream` in `backend/main.py`, consumed with a polling fallback in `frontend/src/hooks.ts::useJobStream` |
| Overview dashboard | ✅ Working | `/api/datasets/{id}/overview`, `Overview.tsx` |
| Fraud-ring review, confirm/dismiss | ✅ Working | `/api/datasets/{id}/rings/{ring_id}/review`, `Rings.tsx` — end-to-end tested including the retrain that follows it |
| Network graph | ✅ Working | Cytoscape.js-based `GraphView.tsx`, `/api/datasets/{id}/graph` |
| Customer detail / explanation | ✅ Working | `/api/datasets/{id}/customers/{id}`, explanation sentences generated by `backend/pipeline/explain.py` and unit-tested for correctness |
| Retrain with feedback → version 2 | ✅ Working | `/api/datasets/{id}/retrain`; tested end to end including stable ring IDs across versions |
| Model & metrics, version history | ✅ Working | `Metrics.tsx`, `/api/datasets/{id}/metrics` |

A real user can go start to finish without hitting a dead end. The weakest link in the journey is not a missing screen, it's that for a **new, unlabeled dataset** the risk scores come from a model trained on synthetic reference data (see §7, "transfer mode") — the UI is honest about this (it shows the mode and a note), but a first-time user could still misread "94.8% ROC-AUC" as ground truth about their own bank's fraud rather than a transfer estimate.

## 5. Repository / System Overview

```
backend/              FastAPI app, background job runner, SQLite layer, CLI        (~4,600 lines)
  pipeline/           ingest, graph/features, modeling, explanations, rings, reference model, runner
data_generation/       synthetic data generator (customers, identities, rings, events)  (~700 lines)
src/data/              graph, feature, split, validation scripts (research pipeline)     (~700 lines)
src/models/            baseline experiment runner + contrastive-pretraining bolt-on       (~470 lines)
frontend/              React 19 + TypeScript + Vite analyst console                     (~4,500 lines)
sample_data/           "bring your own data" example in a deliberately different format
scripts/               regenerates the sample data
tests/                 pytest suite (data generation, contrastive, app end-to-end)
docs/screenshots/      real screenshots referenced from the README
notebooks/             one exploratory notebook (see §8 — explicitly not further developed)
```

Total hand-written source is roughly 12,300 lines (backend + frontend + research pipeline; excludes generated data, `package-lock.json`, notebook JSON). This is a substantial, coherent codebase for what it is, not a thin wrapper.

## 6. Technical Architecture — Simplified

- **Frontend (React + TypeScript, Vite)** — the part an analyst clicks around in. Built with Cytoscape.js for the interactive graph and hand-built SVG for charts (no charting library dependency). Talks to the backend only through a single typed API client (`frontend/src/api.ts`), which mirrors every backend route.
- **Backend (FastAPI)** — a single Python process that serves both the REST API and the built frontend files. It has no separate "backend for frontend" layer; `backend/main.py` is the whole HTTP surface.
- **Background job runner** — a one-worker thread pool (`backend/jobs.py`) that runs the actual data-science pipeline (ingest → graph → features → model → rings → explanations → save) so uploads don't block the HTTP request. Progress is written to the database stage by stage and streamed to the browser.
- **Database (SQLite)** — one file (`backend/db.py`), storing datasets, jobs, model run metrics, per-customer scores/explanations, graph edges, rings, and the audit trail of analyst reviews. This is a deliberate, reasonable choice for a single-user local tool; it does not scale to concurrent multi-analyst use (see §17).
- **The ML pipeline** — not a single model call, but a small system: a graph built from shared attributes, hand-engineered network and behavioural features, a class-balanced gradient-boosting classifier, out-of-fold cross-validated scoring for labelled data (`StratifiedGroupKFold`, keeping connected customers together so the model is never evaluated on data it effectively saw), and a "transfer" model trained on a synthetic reference population when a new dataset has no usable labels.
- **Explanations** — not a black box. Every risk score is decomposed into per-feature contributions using a baseline Shapley approximation (permutation sampling with antithetic orders), and those contributions are turned into English sentences. This is genuinely more rigorous than most "explainable AI" bolted onto hackathon projects: the tests assert the contributions sum exactly to the score (`test_shapley_contributions_add_up_to_the_score`).
- **AI/ML bolt-on (optional)** — `src/models/contrastive_pretraining.py` implements a real GRACE-style graph contrastive learner (a 2-layer GCN encoder, NT-Xent loss over edge-dropped/feature-masked graph views) that produces label-free embeddings. **Correction from an earlier draft of this report:** the encoder is hand-written directly on top of plain PyTorch sparse-tensor operations (`torch.sparse.mm`, a custom `normalized_adjacency` function) — it does **not** use the `torch_geometric` library, which isn't even listed in `requirements-contrastive.txt` (only `torch>=2.2` is). It is evaluated with real metrics and is *not* used by the app — kept as a documented experiment. This is a case where the docs correctly say "optional, not used in the app," which they get right.

## 7. Feature-by-Feature Implementation Status

| Feature | Intended purpose | Status | Evidence | Main gap |
|---|---|---|---|---|
| Synthetic data generation | Realistic fake bank population with fraud rings | ✅ COMPLETE, VERIFIED | `data_generation/*`, `tests/test_data_generation.py` (determinism, leakage, ring-size bounds all asserted) | None significant |
| CSV upload with auto column-role detection | Work on "your own data" without a fixed schema | ✅ COMPLETE, VERIFIED | `backend/pipeline/ingest.py` (1,010 lines), tested against a deliberately foreign schema and messy values | Column-role heuristics are name/value-based; very unusual schemas may still need manual correction (the UI supports this) |
| Identity graph construction | Link customers via shared phone/email/address/device | ✅ COMPLETE, VERIFIED | `src/data/build_customer_graph.py`, reused by `backend/pipeline/features.py`; hub-value suppression (>50 shares) verified in `test_unlabeled_upload_finds_rings_and_learns_from_feedback` | Transductive: built once from the whole dataset, not point-in-time (disclosed by the authors) |
| Network + behavioural feature engineering | Turn the graph and event history into model inputs | ✅ COMPLETE, VERIFIED | `src/data/generate_red_flag_features.py`, `generate_temporal_features.py`; vectorised version tested bit-identical to the original per-customer loop | None significant |
| Supervised scoring (labelled data) | Ring-aware, leakage-safe cross-validated risk scores | ✅ COMPLETE, VERIFIED | `backend/pipeline/modeling.py::run_supervised`, `StratifiedGroupKFold`; E2E-tested (`test_labeled_upload_trains_on_its_own_labels`) | None significant |
| Transfer scoring (unlabeled data) | Score a new, label-free dataset using a reference model | ✅ COMPLETE, VERIFIED | `backend/pipeline/reference.py`, `run_transfer`; E2E-tested against a hidden-label sample (`roc_auc > 0.85` asserted) | Quality depends on how similar the real data's sharing patterns are to the synthetic generator's; the docs are candid about this |
| Shapley-based explanations | Plain-English, additive risk explanations | ✅ COMPLETE, VERIFIED | `backend/pipeline/explain.py`; unit-tested that contributions sum to the score and that the written summary matches the largest factor | None significant |
| Ring detection | Group linked customers into suspected fraud rings | ✅ COMPLETE, VERIFIED | `backend/pipeline/rings.py` (connected components + Louvain split for large groups); precision/recall against known labels reported and tested | Rings above 30 members are split by community detection, which can fracture one real large ring (disclosed) |
| Analyst review / audit trail | Confirm or dismiss rings/customers with notes | ✅ COMPLETE, VERIFIED | `/api/.../review` endpoints, `reviews` table, full history shown in `Rings.tsx`; E2E-tested | None significant |
| Feedback-driven retraining | Analyst decisions become labels; version history compares fairly | ✅ COMPLETE, VERIFIED | `backend/pipeline/runner.py::_previous_version_metrics`, `_changes`; E2E-tested including "reviewed customers excluded from evaluation" fairness rule | None significant |
| Live job progress | Stage-by-stage progress while a job runs | ✅ COMPLETE, VERIFIED | SSE stream + polling fallback; tested that the stream replays the finished job | Single worker processes one job at a time system-wide (disclosed; a real scale limitation, not a bug) |
| Interactive network graph UI | Explore rings visually, filter, drill down | ✅ COMPLETE | `GraphView.tsx` (412 lines, Cytoscape.js, fcose/packed layouts) | Not independently exercised in a browser during this review (see §14) |
| Model & metrics page | ROC/PR curves, confusion matrix, feature importance, version history | ✅ COMPLETE | `Metrics.tsx` (395 lines) maps 1:1 onto `/api/datasets/{id}/metrics` | None significant |
| CSV export of scores | Hand results to another tool | ✅ COMPLETE, VERIFIED | `/api/datasets/{id}/export/customers.csv`, asserted in tests | None |
| Contrastive pretraining (GNN) bolt-on | Label-free embeddings as an optional feature source | ✅ COMPLETE (optional, not integrated into the app) | `src/models/contrastive_pretraining.py`, `tests/test_contrastive.py` | Correctly scoped as "not a clear win" by the authors' own numbers |
| Temporal / point-in-time modelling | Detect fraud *before* bust-out, not just in a snapshot | 🔴 NOT IMPLEMENTED (explicitly deferred) | README §"Future work: temporal modelling (deferred)" | This is the single largest scoped gap in the whole project, and the docs are upfront about it |
| Authentication / multi-user access | Restrict or separate who can see/edit data | 🔴 NOT IMPLEMENTED | No auth code anywhere in `backend/`; disclosed in `PROJECT_STATUS.md` under "Known Limitations" | Fine for a local single-analyst tool, not for shared/hosted use |
| Deployment automation (CI/CD, Docker) | Repeatable builds/deploys | 🔴 NOT IMPLEMENTED | No `.github/`, no Dockerfile, no `docker-compose.yml` found anywhere in the repo | Everything is currently "run it on your own machine" |

## 8. Documentation vs Reality

This is the section where projects usually lose credibility — overstated READMEs are the norm. Here, the opposite pattern shows up: the documentation is unusually candid, and where it makes a claim, the claim generally checks out.

- **Matches:** every page listed in the README's "What the console does" table exists and wires to a real, working API route (verified by reading `frontend/src/pages/*.tsx` against `backend/main.py`). The specific research numbers quoted in the README (e.g., Random Forest "Tabular + Network" ROC-AUC 0.9153) are reproduced by an actual test (`test_synthetic_job_reproduces_the_research_experiments`), not just asserted in prose.
- **Self-disclosed limitations, verified as real:** "The web app is single-user: no login, and one background worker runs jobs one at a time" — confirmed (`ThreadPoolExecutor(max_workers=1)` in `backend/jobs.py`). "The notebook is still a basic exploration notebook" — confirmed (6 cells, titled "Week 1 Data Exploration").
- **One place to read carefully, not a contradiction but a nuance:** the "Results" table's headline metrics (ROC-AUC 0.957 etc.) are for the *synthetic* demo dataset. For a real, unlabeled dataset the app uses transfer learning from that same synthetic population — a materially different, weaker guarantee. The README does explain this, but a stakeholder skimming only the metrics table could walk away thinking the numbers describe real-world performance in general.
- **Nothing found that was "documented but not implemented."** This is worth stating plainly because it's the opposite of the default assumption for this kind of audit: no feature named in the README was missing from the code, and no code path was found that silently did less than documented.

## 9. Completion Analysis

### Completion Methodology

Scored 0–10 per category, weighted by how much each contributes to a *usable, credible product* (not lines of code), then converted to a percentage.

### Weighted Score Breakdown

| Area | Weight | Score /10 | Contribution | Evidence / Reasoning |
|---|---:|---:|---:|---|
| Core functionality (ingest → graph → model → rings → explain → feedback) | 30% | 9.0 | 27.0% | Every stage implemented and covered by a real E2E test that exercises the actual API (§7) |
| UX / frontend | 15% | 8.0 | 12.0% | All pages implemented, sensible loading/error/empty states, theming, keyboard-accessible controls, audit-trail UI (§13); no automated frontend test suite |
| Backend / APIs | 15% | 8.5 | 12.75% | Full REST surface, parameterised SQL throughout, upload-size/type validation, SSE streaming, sensible error codes | 
| Database / data layer | 10% | 7.0 | 7.0% | Reasonable SQLite schema with indices (§17); no migration tooling, single-file DB is a scale ceiling, not a defect |
| AI / ML | 10% | 9.0 | 9.0% | Real, tested Shapley explanations; leakage-aware CV; documented, honestly-scoped contrastive bolt-on |
| Testing / reliability | 10% | 6.5 | 6.5% | Test code itself is genuine and specific (§14), but this reviewer could not execute it in this environment (no `pytest`/venv present) and there is no CI to make "tests pass" a continuously-checked fact rather than a developer claim |
| Security | 5% | 5.0 | 2.5% | No secrets found, parameterised SQL, upload limits; but no auth, no rate limiting, no dependency scanning, and an unsanitised CSV export (§15) |
| Deployment / DevOps / observability | 5% | 2.5 | 1.25% | No CI, no Dockerfile, no structured logging/monitoring; "run it on your machine" only |

### Overall Completion Percentage

**≈ 78%**

This reflects a project whose *implemented* scope is unusually solid and well-tested-in-principle, held back mainly by the absence of production/operational scaffolding (deployment, CI, auth) rather than by missing product features.

### Confidence Level

**Medium-High confidence.** High confidence on "what exists and how it's wired," because the code was read directly and cross-checked against every documentation claim. Medium (not High) on "does it actually run correctly end-to-end today," because this environment had no working Python virtual environment (`pytest` not installed, `python -m pytest` failed with `No module named pytest`) and no `frontend/node_modules`, so the test suite and the frontend build could not be executed here — see §14 for exactly what that means and doesn't mean.

## 10. Project Scorecard

| Category | Score /10 | Evidence | Explanation |
|---|---:|---|---|
| Product completeness | 8 | §7 feature table | Every documented feature is implemented; the one deliberately missing piece (temporal modelling) is scoped, not hidden |
| Core functionality | 9 | `backend/pipeline/*`, `tests/test_app.py` | End-to-end pipeline works and is exercised by tests that assert real numbers, not just "no exception raised" |
| Feature completeness | 8 | §7 | Nothing found that was claimed but absent |
| User experience | 8 | `frontend/src/pages/*.tsx` | Loading/empty/error states everywhere reviewed, audit trail, theming, live progress; not personally exercised in a live browser here |
| Technical architecture | 8 | §6 | Clean separation (ingest/graph/features/model/explain/rings/runner); reused research code rather than duplicated |
| Code quality | 7 | `backend/main.py`, `backend/pipeline/*` | Consistently typed, docstring-explained "why," parameterised SQL; a few very large files (`main.py` 986 lines, `ingest.py` 1,010 lines) that would benefit from splitting |
| Testing | 6.5 | `tests/*.py` | Tests are genuinely good (specific numeric assertions, real E2E flows); could not be executed in this environment, and there's no CI enforcing them — same reasoning and score as the weighted "Testing / reliability" row in §9 |
| Reliability | 7 | `backend/db.py::fail_interrupted_jobs`, `jobs.py` | Interrupted-job recovery is implemented and tested; single-worker queue is a real bottleneck under any concurrent load |
| Security | 5 | §15 | No secrets, parameterised queries, upload limits; but no auth, no rate limiting, and one real finding — the CSV export doesn't sanitise formula-injection characters (§15) |
| Scalability | 4 | §16, §6 | Single SQLite file, single background worker — fine for one analyst, not for a team or a large recurring dataset |
| Documentation | 9 | README.md, PROJECT_STATUS.md | Unusually accurate and self-critical; explains architecture, results methodology, and its own limitations |
| Deployment readiness | 2 | §21, §25 | No Dockerfile, no CI, no environment templates found |
| Maintainability | 7 | Module boundaries in `backend/pipeline/` | Good separation of concerns overall; a couple of oversized modules |
| Performance readiness | 7 | PROJECT_STATUS.md "Bugs found and fixed" | Feature computation is explicitly vectorised (16s → 0.6s per the changelog) and covered by an equivalence test; no load-testing evidence |
| Overall product maturity | 7 | Whole report | Advanced MVP for a single analyst; not yet a hosted product |

## 11. Core Functionality Assessment

The core loop — upload or generate data, build the identity graph, score every customer, detect rings, explain scores, let an analyst act, retrain — is real and internally consistent. The most convincing piece of evidence is `tests/test_app.py::test_unlabeled_upload_finds_rings_and_learns_from_feedback`, a single test that drives the *entire* product surface through the actual HTTP API: upload → column mapping → job completion → overview stats → ring detail → customer explanation (asserting the Shapley contributions really do sum to the displayed score) → confirm one ring, dismiss another → retrain → verify version 2 exists with the right feedback count and that ring IDs stayed stable → replay the SSE stream → export CSV. That is not a superficial smoke test; it is a real product-acceptance test.

The one structural caveat, disclosed by the authors and confirmed by reading `backend/pipeline/runner.py::split_groups`/`build_graph`, is that the identity graph and features are computed over the *entire* dataset at once (transductive), which is appropriate for "find rings in what we have" but overstates how early, in real time, fraud could be caught.

## 12. UX Assessment

Reading `frontend/src/pages/Rings.tsx`, `App.tsx`, and `hooks.ts` in full:

- Every data-fetching page has a distinct loading state (`Loading`), error state (`ErrorBox` with retry), and empty state (`Empty`, e.g. "Nothing left to review here. 🎉" when the review queue is clear) — this is the kind of polish that's easy to skip and wasn't skipped here.
- Live job progress uses Server-Sent Events with an automatic fallback to polling if SSE is unavailable (`useJobStream` in `hooks.ts`), which is a thoughtful touch for a tool that might sit behind a buffering proxy.
- The ring-review workflow keeps an audit note, remembers "suggested" members (medium/high risk pre-ticked), auto-advances the queue after a decision, and shows full review history per ring — this is real workflow design, not a form.
- Accessibility touches are present (`aria-label`s on the search boxes and checkboxes) though not exhaustively audited.
- Nothing was found suggesting broken links, dead buttons, or lorem-ipsum placeholder text.

**What could not be verified:** this review did not launch the app in a browser (no `node_modules`, no running backend session), so first-hand claims about "no console errors in light and dark mode" in `PROJECT_STATUS.md` are read as a developer claim, not independently reconfirmed here.

## 13. Code Quality Assessment

Strengths, with evidence:
- Consistent typing throughout (Python type hints everywhere in `backend/`; TypeScript `interface`s in `frontend/src/api.ts` mirror the backend's JSON shapes almost field-for-field).
- Docstrings explain *why*, not *what* (e.g. `backend/pipeline/rings.py`'s module docstring explains why ring IDs are structural rather than model-derived — a genuinely non-obvious design decision worth documenting).
- No `TODO`/`FIXME`/`XXX`/"placeholder"/"not implemented" markers found anywhere in `backend/`, `src/`, `data_generation/`, or `frontend/src/` (a repo-wide search came back empty of stub markers; the few "placeholder" hits found are legitimate references to *data* placeholders like `"N/A"` phone numbers, not unfinished code).
- SQL is parameterised everywhere reviewed in `backend/db.py` and `backend/main.py`; the one place a column name is interpolated into a query (`ORDER BY {column}` in `list_customers`) is safe because `column` is selected from a hardcoded whitelist dict, not user input directly.

Weaknesses:
- `backend/main.py` (986 lines) and `backend/pipeline/ingest.py` (1,010 lines) are large single modules doing many things; not unreadable, but due for a split as the project grows.
- Git history is very coarse: 4 commits total across the whole project (`d777752` "first commit", `22774d0` "week 2-3 pipeline updates", `7029d12` "frontend work and dataset uploads section work completed", plus a merge). Each of the later commits changes 300–2,700+ lines. This means the repository itself provides very little incremental review trail — large amounts of work landed in a few big pushes rather than reviewable increments.
- No repo-wide linter/formatter config found (no `.eslintrc`, no `ruff`/`black` config) — code style is consistent by discipline, not by tooling.

## 14. Testing & Reliability

**What exists:** `tests/test_app.py` (326 lines), `tests/test_data_generation.py` (145 lines), `tests/test_contrastive.py` (49 lines). These are real tests: they assert specific numbers (e.g. `roc_auc == pytest.approx(0.9457, abs=5e-5)`), specific behaviours (ring IDs staying stable across a retrain, reviewed customers being excluded from post-retrain evaluation to avoid overstating improvement), and specific edge cases (a 60-person shared office address correctly being treated as a non-ring "hub," a bad file upload being rejected with a 400).

**What could not be verified here:** this execution environment has no Python virtual environment matching `requirements.txt` (`python -m pytest` failed with `No module named pytest`; the only `pip` on `PATH` belongs to an unrelated global Python install with a large, unrelated package list — `celery`, `aiohttp`, etc. — and no `pytest`, `fastapi`, or `torch`). Similarly, `frontend/node_modules` does not exist, so `npm run typecheck` could not be run. Per the task's own ground rules ("do not install dependencies merely for the purpose of this analysis"), no attempt was made to `pip install`/`npm install` to force a run.

**Consequence for this assessment:** the claim "18 tests pass" and "`npm run typecheck` passes with strict TypeScript" (both in `PROJECT_STATUS.md`) are treated as **plausible but not independently reproduced** in this session — the test code itself is high quality and internally consistent (it wouldn't type-check or import correctly if the referenced functions didn't exist with matching signatures, which was spot-checked by reading the referenced modules), but "the code looks right and the tests look meaningful" is not the same as "a test run just now returned green." This is the single biggest reason completion/confidence isn't scored higher.

**Reliability details actually verified by reading code:** interrupted jobs (e.g., the process was killed mid-job) are marked `failed` on restart (`Database.fail_interrupted_jobs`, tested in `test_interrupted_jobs_are_marked_failed_on_restart`); a failed retrain leaves the previous version's results intact rather than corrupting the dataset (`_fail` in `jobs.py` only marks the dataset `failed` if it has no prior successful version).

## 15. Security Assessment

Confirmed positives:
- No hardcoded secrets, API keys, or credentials found anywhere in the codebase.
- SQL is parameterised throughout; the one dynamic-`ORDER BY` case is guarded by a hardcoded column whitelist, not raw user input.
- File uploads are size-capped (`MAX_UPLOAD_BYTES = 200MB`) and rejected outright for non-CSV extensions (`.xlsx`, `.parquet`, `.json`, etc.) before parsing.
- Upload/dataset IDs used in filesystem paths are validated against a strict regex (`SAFE_ID = ^[a-f0-9]{8,32}$`) before being used to build a directory path, which appears to close an obvious path-traversal angle for that endpoint.

Gaps (all consistent with the project's own "single-user" framing, but real gaps if this were exposed beyond one trusted user's machine):
- No authentication or authorization anywhere — every API route is open to anyone who can reach the port.
- No rate limiting — the synthetic-generation and upload endpoints could be hit repeatedly with no throttling.
- No CORS restriction is set up, but this appears intentional: the backend serves the built frontend from the same origin (`backend/main.py`'s catch-all `/{rest:path}` route), so a browser same-origin policy already applies; this becomes a real question only if the API is ever exposed to a different frontend origin.
- No dependency-vulnerability scanning configured (no `pip-audit`/`npm audit` step, no Dependabot config found).
- **CSV/formula-injection risk in the score export (added in this second-pass audit):** `backend/main.py::export_customers` (the `/api/datasets/{id}/export/customers.csv` route) writes each customer's `name` and explanation text straight into the CSV with no check for a leading `=`, `+`, `-`, or `@` character. Since the customer `name` field can come directly from an uploaded, potentially untrusted CSV (`backend/pipeline/ingest.py`), a maliciously crafted upload could plant a spreadsheet-formula payload in a name field that later executes if an analyst opens the exported CSV in Excel/Sheets. This is a **potential risk**, not a confirmed exploit — it was not tested end-to-end here — but it is a known, well-documented class of vulnerability (CSV/formula injection) and costs little to fix (prefixing risky leading characters with a single quote or tab on export).

None of this rises to a confirmed, demonstrated vulnerability for the tool's stated use case (a trusted analyst running it locally on data they generated or trust); the CSV-export item is the one place where an untrusted *upload* could plausibly turn into a downstream risk for whoever later opens the exported file. This is a real gap to close before treating uploads as coming from anyone other than the analyst's own trusted sources.

## 16. Performance & Scalability

- The project's own changelog (`PROJECT_STATUS.md`, "Bugs found and fixed") documents a real performance fix: temporal feature computation went from a 16-second per-customer loop to a 0.6-second vectorised version for 8,800 customers, and a test (`test_vectorised_temporal_features_match_a_per_customer_loop`) locks in that the fast version matches the slow one exactly. This is a credible, verifiable performance claim, not a vague assertion.
- No load-testing evidence exists (no k6/locust scripts, no benchmark results), so actual requests-per-second or maximum-dataset-size capacity cannot be established from the repository alone.
- Scalability ceiling is architectural rather than algorithmic: one SQLite file and one single-threaded background worker (`ThreadPoolExecutor(max_workers=1)`) mean exactly one analysis job runs at a time system-wide, and one process serves all HTTP traffic. For a single analyst this is a non-issue; for a shared team tool it is the first thing that would need to change.
- **Correction from an earlier draft of this report:** the earlier version of this section wrongly implied the app only uses a fully vectorised feature path. Checking `backend/pipeline/features.py::build_graph` shows it actually calls the *same* `build_edge_records` function from `src/data/build_customer_graph.py` that the standalone research script uses — and that function is a Python-level loop (a `groupby` per attribute value, then `itertools.combinations` over each group's members) to turn shared attribute values into graph edges. What *is* confirmed vectorised (via a single pandas `groupby`, read directly in `src/data/generate_red_flag_features.py::compute_features`) is the separate, later step that aggregates those edges into per-customer network features — that's the step PROJECT_STATUS.md's "bug fix" changelog refers to. In production, the edge-building loop is bounded by `MAX_ATTRIBUTE_GROUP_SIZE = 50` (`backend/settings.py`), which caps any single shared value at at most C(50,2) = 1,225 pairs, so it stayed practical at the scales this project has actually tested (thousands of customers) — but it is a real, unbounded-by-default loop in the standalone research script (`src/data/build_customer_graph.py::main`, which calls `build_edge_records` with no size cap at all), and it is a legitimate scalability question — not yet a demonstrated problem — for much larger uploaded datasets with many large shared-value groups.

## 17. Database / Data Layer

`backend/db.py` defines a straightforward SQLite schema: `datasets`, `jobs`, `model_runs`, `customers`, `edges`, `rings`, plus (from later code, not fully quoted above) reviews/events tables. Indices exist on the columns actually queried by risk (`customers_by_risk`) and by ring/edge lookups (`customers_by_ring`, `edges_by_source`, `edges_by_target`) — this is a deliberately-designed schema, not an afterthought. Several columns store JSON blobs (`explanation_json`, `metrics_json`, `features_json`) rather than fully normalized tables, which is a reasonable trade-off for a single-file app database holding heterogeneous per-customer payloads, but it does mean there's no schema-level guarantee on those payloads' shape — only whatever the Python code writes.

There is no migration tool (Alembic or similar) — the schema is created idempotently with `CREATE TABLE IF NOT EXISTS` on startup, which works today but would not gracefully handle a future schema change against an existing `storage/app.db` with real data in it.

## 18. AI / ML Assessment

This is a genuine, working ML system, not an imported model wrapped in a nice UI:

- **Trained models, not placeholders:** `HistGradientBoostingClassifier` (class-balanced) is fit fresh per dataset/version in `backend/pipeline/modeling.py`; the standalone research pipeline (`src/models/random_forest_baseline.py`) also trains a Random Forest for comparison. Nothing is a hardcoded score or a rule dressed up as "AI."
- **Evaluation methodology is leakage-aware:** `StratifiedGroupKFold` keeps whole connected components (or known rings) together across folds so no customer's label leaks into its own out-of-fold prediction — verified by reading `run_supervised` and by the leakage assertions in `test_week3_pipeline_leakage_reproducibility_and_outputs`.
- **Explanations are a real attribution method, not string templates dressed up:** baseline Shapley values via permutation sampling (`shapley_contributions`), tested to sum exactly to the model's own predicted probability.
- **Transfer learning is a deliberate, tested design, not a stub:** when a new dataset has no usable labels, a model trained on the synthetic reference population (with the same feature *definitions* the new dataset can actually provide) scores it, and analyst feedback is folded back in with a 5× sample weight.
- **The optional contrastive-pretraining bolt-on is real, not decorative:** `src/models/contrastive_pretraining.py` implements an actual 2-layer GCN with an NT-Xent loss over graph augmentations (edge dropping + feature masking), evaluated across 3 seeds with mean±std reported. The authors' own conclusion — "not a clear win, kept as an optional experiment" — is honest and matches what a skeptical reader would conclude from their own numbers (label-free embeddings alone reach ~98% of the hand-engineered features' ROC-AUC, but combining them doesn't clearly help).
- **Explainability distinguishes fact from causation carefully:** `backend/pipeline/explain.py`'s `clause()` function deliberately returns `None` rather than writing a nonsensical sentence when a feature's direction doesn't support a natural-language claim (e.g., "doesn't share an email" can't be *why* a score went up) — a small but telling sign of care.

Nothing labeled "AI" here turned out to be a lookup table or a mocked response.

## 19. Git / Development Health

- 4 commits total on `main`, spanning 2026-08-30 to 2026-09-25 (about 4 weeks), from two contributors (`Mahi-0809`, `Vedant Mishra`/`VedantM47`), merged via a single PR (`#1`, branch `mahi` → `main`).
- Commit granularity is coarse: the largest commit alone adds essentially the entire `backend/` and `frontend/` trees (2,700+ line diff). This means the repository's own history cannot be used to reconstruct how the design evolved — it was evidently developed elsewhere (locally, or on another branch) and pushed in a few large batches.
- No secrets, credentials, or accidentally-committed environment files were found in the tracked history.
- The one untracked file at the time of this review, `Synthetic Identity Fraud Project.pdf`, sits in the repo root and is not part of the analysed codebase; it was not opened as part of this audit (out of scope — this report is a code/product audit, and the PDF was left untouched).
- `.gitignore` is sensible and specific (excludes `venv/`, `data/raw/*.csv`, generated `outputs/**`, `storage/`, `frontend/node_modules/`, `frontend/dist/`), explaining why several directories (`data/raw`, `outputs/models/rf_baseline`, `storage/`) were empty or absent in this checkout — that is expected, not a sign of missing work.

## 20. Strengths

- **The documentation is honest.** This is rare enough to call out as a genuine strength: the README and `PROJECT_STATUS.md` disclose real bugs that were found and fixed (a CSV float-parsing bug that silently changed results, a 16-second-per-customer performance bug), state exact test counts, and scope out what's deliberately *not* done (temporal modelling) instead of quietly omitting it.
- **The explanation system is mathematically grounded**, not templated guesswork — contributions provably sum to the score, and this is enforced by a test, not just claimed.
- **The evaluation methodology is unusually rigorous for this kind of project**: ring-aware group cross-validation, "reviewed customers excluded from post-retrain evaluation" to avoid an easy self-serving metric, and a like-for-like previous-vs-current-version comparison on identical customers.
- **The frontend and backend are fully in sync** — every backend route has a corresponding, correctly-typed frontend consumer; nothing found was "backend exists but the UI never calls it" or vice versa.
- **The synthetic data generator itself is a real research artifact**, not a toy: it deliberately makes legitimate customers share some attributes too (households, contact pairs), makes fraud rings imperfectly dense, and makes only 60% of fraud accounts show the "obvious" bust-out behaviour — specifically so the detection problem isn't artificially easy. This is evidenced by the generator code and locked in by tests.

## 21. Weaknesses

- **No production operational layer at all**: no CI, no Docker, no deployment scripts, no structured logging/monitoring beyond basic Python `logging` calls in `jobs.py`.
- **No authentication** — acceptable for the stated single-analyst/local use case, a real gap for anything shared.
- **Single-worker job queue** is a hard architectural ceiling on throughput; fine for a demo, not for a team.
- **Test execution could not be independently reproduced in this environment** (missing `pytest`/venv, missing `node_modules`) — the tests themselves read as high quality, but "high quality test code" and "verified passing right now" are different claims, and this report is careful not to conflate them.
- **Coarse git history** (4 commits) limits how much confidence an external reviewer can place in incremental review/code-review practice, even though the end result reads as carefully built.
- **Transductive, whole-dataset graph and features** — the one gap the authors themselves flag as the most important next step, and this review agrees it's the correct priority.

## 22. Critical Gaps

**CRITICAL**
- None found that block the core product from working today. (This is a genuinely rare finding for an audit of this kind, and it is stated because it's true, not because it's expected.)

**HIGH**
- No independently-reproducible test execution in a clean environment / no CI — the difference between "well-written tests" and "verified passing" matters a lot before this is trusted for any real decision-making.
- No authentication — blocks any use beyond a single trusted local user.
- No deployment automation — blocks handing this to anyone who isn't comfortable running `python -m backend` themselves.

**MEDIUM**
- Temporal/point-in-time modelling is deferred — real-world fraud-catching claims are weaker than snapshot-accuracy claims until this exists.
- Single background worker — a real bottleneck for team use, not for solo use.
- No schema migration tooling for the SQLite database.

**LOW**
- A couple of oversized modules (`main.py`, `ingest.py`) that would benefit from splitting.
- No linter/formatter configuration checked into the repo.
- The untracked PDF in the repo root should either be committed intentionally or removed/ignored, for repo hygiene.
- CSV export doesn't neutralise formula-injection characters in customer names (§15) — low likelihood (requires a malicious upload *and* someone opening the export in a spreadsheet program) but cheap to fix.

## 23. Demo Readiness

**Demo Readiness: 9/10.**

The README's own 7-minute demo script (Overview → Model & metrics → Fraud-ring review → Customer detail → upload your own data → rings without labels → feedback loop) maps exactly onto features that were confirmed to exist and be wired correctly. What would demo well: the whole flow, especially the plain-English explanations and the "shows rings even without labels" transfer-mode capability, which is a genuinely distinctive feature for this kind of tool. What could break a demo: anything relying on `storage/` already being populated (it must be generated or uploaded fresh — there is no seeded demo data shipped, by design, since `storage/` is gitignored) and, unverified in this review, whatever a live browser session would actually render (see §14).

## 24. MVP Readiness

**MVP Readiness: 8/10.**

A real user (an analyst) could use this today to upload their own export, get scored rings with explanations, and make decisions that improve the model — that is the definition of a working MVP for this product's stated purpose. What's missing before calling it a *credible* MVP for a real fraud team: nothing on the product-feature side; the gaps are trust-and-operations gaps (verified test execution / CI, and some way to run it as more than one analyst's local process).

## 25. Production Readiness

**Production Readiness: 3/10.**

"It runs on my machine" (or in this case, "it's clearly built to run correctly on one machine") is not production readiness. To get there: authentication and authorization, a deployment story (container image + environment config, since none exists today), a multi-worker or queue-based job runner instead of one thread, database migration tooling, structured logging/monitoring, and a CI pipeline that actually executes `pytest` and `npm run typecheck` on every change instead of those being one-time developer-run claims. None of this is unusual to be missing at this stage of a project — it is simply the honest distance between "complete feature set" and "production system."

## 26. What Should Be Done Next

### Quick Wins
1. **Add a CI workflow** (GitHub Actions) that installs `requirements.txt`, runs `pytest -q`, installs frontend deps, and runs `npm run typecheck`. *Why:* turns "18 tests pass" from a developer claim into a continuously-verified fact. *Impact:* High. *Effort:* Low.
2. **Commit or remove the stray `Synthetic Identity Fraud Project.pdf`** at the repo root. *Why:* repo hygiene; an untracked file of unclear provenance next to a very clean `.gitignore` stands out. *Impact:* Low. *Effort:* Low.
3. **Add a `requirements-dev.txt` or document the exact venv setup** so a fresh clone can run tests without guesswork (this review had to discover, via trial and error, that no working Python environment existed in this checkout). *Impact:* Medium. *Effort:* Low.
4. **Split `backend/main.py` and `backend/pipeline/ingest.py`** into smaller modules (e.g., routers by resource). *Impact:* Medium (maintainability). *Effort:* Low-Medium.
5. **Add a minimal Dockerfile** for the backend (frontend build + `python -m backend`). *Impact:* High (unlocks "hand this to someone else to run"). *Effort:* Low.
6. **Add basic rate limiting** to the upload/synthetic-generation endpoints. *Impact:* Medium. *Effort:* Low.

### Priority 1 (next sprint-sized effort)
- **Verified, CI-enforced test execution** (see Quick Win #1, but treat getting it green in CI, not just locally, as the real milestone).
- **Basic authentication** (even a single shared password/token gate) before this is shared with more than one person.
- **Replace the single-worker queue** with a small multi-worker or process-pool design so two analysts (or one analyst plus a retrain) don't block each other.

### Priority 2
- **Begin the temporal/point-in-time modelling roadmap** the authors already scoped in the README (timestamped links → point-in-time graph snapshots → point-in-time behaviour features → forward-in-time evaluation). This is the single highest-value technical improvement available, and it's already been thought through by the team — it just hasn't been started.
- **Database migration tooling** (Alembic or a simple versioned-migrations approach) before `storage/app.db` accumulates real, hard-to-lose data.

### Future Enhancements
- Richer benign-entity modelling (employers, IP ranges, shared student housing) as suggested in the team's own "Week 4 Recommendations."
- A calibration/threshold-selection workflow tied to actual analyst investigation capacity, not just F1-optimal.
- Automated frontend tests (component or E2E, e.g. Playwright) to complement the strong backend test suite.

## 27. 7-Day Action Plan

**What I would do in the next 7 days**, prioritized to move this from "well-built local tool" toward "trustworthy to hand to someone else":

1. Get a clean environment set up and actually run `pytest -q` and `npm run typecheck` to confirm the documented results for real (this is the single highest-value 30 minutes available, since it converts the biggest open question in this report from "plausible" to "confirmed").
2. Stand up a CI workflow that does the same on every push/PR.
3. Add a Dockerfile and a one-command "make it run" path.
4. Decide on and implement a minimal auth gate (even HTTP basic auth) if this will ever be shown to more than one trusted person.
5. Clean up the repo root (the untracked PDF) and split the two oversized backend modules.

## 28. 30-Day Action Plan

Building on the 7-day plan:

- **Completeness:** start the temporal/point-in-time modelling work (timestamped links first — the generator already has account-open dates, so this is an additive change, not a rewrite).
- **Reliability:** move the job runner from a single thread to a small worker pool; add structured logging (request IDs, job IDs) instead of print/basic logging.
- **Quality:** add an automated frontend test (even a handful of Playwright smoke tests covering the upload → review → retrain path) so the frontend has the same kind of confidence the backend already does.
- **UX:** make the "transfer mode" distinction between "scored against reference data" and "scored against your own trained labels" more visually prominent on the Overview page, so the difference in evidentiary strength is unmissable, not just present in a note.
- **Security:** add basic auth and rate limiting; run a dependency-vulnerability scan and address anything flagged.
- **Deployment:** ship a Dockerfile and a short deployment guide (even "run this container behind your own reverse proxy" is enough for the intended single-team use case).
- **Differentiation:** if time allows, revisit whether the contrastive-pretraining embeddings could help specifically in the *transfer* (unlabeled) scenario, where the team's own numbers suggest label-free signal might matter more than in the fully-labelled case they tested it on.

## 29. Final PM Assessment

**What exists today?** A genuinely complete, internally consistent fraud-ring-detection tool: synthetic data generation, a real identity-graph-plus-ML pipeline, mathematically grounded explanations, a full analyst review and feedback loop, and a React console that covers all of it — all connected end to end, not a collection of disconnected demos.

**What is genuinely working?** Everything the documentation claims about the *product*. This review could not find a single feature that was documented but not implemented, which is unusual and worth taking at face value as a real strength.

**What is still incomplete?** The operational/production layer (auth, deployment, CI, multi-worker execution) and the deliberately-deferred temporal modelling. Both are clearly identified by the project's own authors, which is itself a good sign about how this team thinks about its own work.

**What is holding the project back?** Not the product — the surrounding scaffolding that turns a well-built local tool into something that can be trusted and used by more than its own authors: continuously-verified tests (this review could read the tests but not run them here), a deployment story, and basic access control.

**What would make the biggest difference next?** Getting the existing, well-written test suite running in CI. It costs almost nothing relative to the rest of the work already done, and it is the one thing that would convert this report's "Medium-High confidence" into "High confidence" — for this reviewer and for anyone else who picks this repository up next.
