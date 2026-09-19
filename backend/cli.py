"""Command-line helpers that run jobs without the web server.

    python -m backend.cli demo                     # generate + analyse the synthetic demo dataset
    python -m backend.cli analyze customers.csv    # analyse your own CSV with auto-detected columns
    python -m backend.cli list                     # list datasets in storage/
"""

from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path

from backend import settings
from backend.db import Database
from backend.jobs import JobManager
from backend.pipeline.ingest import preview_file


def _setup() -> tuple[Database, JobManager, dict[str, Path]]:
    paths = settings.storage_paths()
    for key in ["base", "uploads", "datasets", "reference"]:
        paths[key].mkdir(parents=True, exist_ok=True)
    db = Database(paths["db"])
    return db, JobManager(db, paths), paths


def _run(jobs: JobManager, kind: str, dataset_id: str, params: dict | None = None) -> int:
    job_id = jobs.submit(kind, dataset_id, params)
    job = jobs.wait(job_id)
    for stage in job["stages"]:
        print(f"  [{stage['status']:>7}] {stage['label']}: {stage['message']}")
    if job["status"] != "completed":
        print(f"FAILED: {job['error']}")
        return 1
    print(f"Done. Dataset {dataset_id} is ready (model version {job['result']['version']}, {job['result']['mode']} mode).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate and analyse a synthetic dataset.")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--legitimate", type=int, default=8000)
    demo.add_argument("--fraud", type=int, default=800)
    analyze = commands.add_parser("analyze", help="Analyse a customers CSV using auto-detected column roles.")
    analyze.add_argument("customers", type=Path)
    analyze.add_argument("--events", type=Path, default=None)
    analyze.add_argument("--name", default=None)
    analyze.add_argument("--evaluate-only", action="store_true", help="Hide the label column from the model.")
    commands.add_parser("list", help="List datasets.")
    args = parser.parse_args(argv)

    db, jobs, paths = _setup()
    try:
        if args.command == "list":
            for dataset in db.list_datasets():
                summary = dataset["summary"] or {}
                print(
                    f"{dataset['id']}  {dataset['status']:<10} v{dataset['active_version']}  "
                    f"{summary.get('n_customers', '?'):>6} customers  {dataset['name']}"
                )
            return 0
        if args.command == "demo":
            dataset_id = uuid.uuid4().hex[:10]
            params = {"seed": args.seed, "n_legitimate": args.legitimate, "n_fraud": args.fraud}
            db.create_dataset(dataset_id, f"Synthetic demo (seed {args.seed})", "synthetic", {"synthetic": params}, None)
            return _run(jobs, "synthetic", dataset_id, params)

        dataset_id = uuid.uuid4().hex[:10]
        folder = paths["datasets"] / dataset_id / "uploads"
        folder.mkdir(parents=True)
        files = {"customers": str(folder / "customers.csv")}
        shutil.copy2(args.customers, files["customers"])
        preview = preview_file(Path(files["customers"]), "customers")
        mapping: dict = {
            "customers": {"roles": preview["suggested_roles"], "label_mode": "evaluate" if args.evaluate_only else "train"}
        }
        if args.events:
            files["events"] = str(folder / "events.csv")
            shutil.copy2(args.events, files["events"])
            mapping["events"] = preview_file(Path(files["events"]), "events")["suggested_fields"]
        print("Detected column roles:")
        for column, role in preview["suggested_roles"].items():
            print(f"  {column:<28} -> {role}")
        db.create_dataset(dataset_id, args.name or args.customers.stem, "upload", mapping, files)
        return _run(jobs, "analyze", dataset_id)
    finally:
        jobs.shutdown()


if __name__ == "__main__":
    sys.exit(main())
