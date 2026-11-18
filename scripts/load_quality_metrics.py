"""Turn CI history, test reports and the bug list into SQL for the quality dashboard.

The script prints SQL; psql inside the Postgres container runs it. That keeps the project free of a
database driver dependency. Typical use, from the repository root:

    uv run python scripts/load_quality_metrics.py --fetch \\
        | docker compose -f compose.metrics.yaml exec -T postgres psql -q -U quality -d quality

--fetch downloads the latest CI runs and their JUnit reports with the GitHub CLI (`gh`) into
observability/data/ci/. Without it, the script uses what was downloaded before.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "observability" / "data" / "ci"
RUNS_FILE = DATA_DIR / "runs.json"
BUGS_FILE = ROOT / "observability" / "bugs.csv"
REPORT_ARTIFACT = "test-reports"  # the artifact name used in .github/workflows/ci.yml
RUN_FIELDS = "databaseId,headBranch,event,conclusion,headSha,displayTitle,createdAt,updatedAt"


def fetch(limit: int) -> None:
    """Download the run list and each run's test reports. Runs without reports are skipped."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    runs = subprocess.run(
        ["gh", "run", "list", "--limit", str(limit), "--json", RUN_FIELDS],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    RUNS_FILE.write_text(runs)
    for run in json.loads(runs):
        target = DATA_DIR / str(run["databaseId"])
        if target.exists() or run["conclusion"] not in ("success", "failure"):
            continue  # already downloaded, or still running / cancelled
        subprocess.run(
            ["gh", "run", "download", str(run["databaseId"]), "-n", REPORT_ARTIFACT, "-D", target],
            check=False,  # an old run may have no report artifact
            capture_output=True,
        )


def sql_text(value: Any) -> str:
    """A SQL literal. Only for this trusted, local data; real code would use bound parameters."""
    if value is None or value == "":
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def outcome_of(case: ET.Element) -> tuple[str, str | None]:
    """Map a JUnit <testcase> to one outcome and an optional one-line message."""
    for tag, outcome in (("failure", "failed"), ("error", "error")):
        node = case.find(tag)
        if node is not None:
            return outcome, (node.get("message") or "").splitlines()[0][:300] or None
    skipped = case.find("skipped")
    if skipped is not None:
        outcome = "xfailed" if skipped.get("type") == "pytest.xfail" else "skipped"
        return outcome, (skipped.get("message") or "")[:300] or None
    return "passed", None


def test_rows(run_id: int) -> Iterator[str]:
    for report in sorted((DATA_DIR / str(run_id)).glob("*.xml")):
        stage = report.stem  # fast.xml -> fast, smoke.xml -> smoke, live.xml -> live
        for case in ET.parse(report).iter("testcase"):
            test_id = f"{case.get('classname')}::{case.get('name')}"
            outcome, message = outcome_of(case)
            duration = float(case.get("time") or 0)
            values = [run_id, stage, test_id, outcome, duration, message]
            yield "(" + ", ".join(sql_text(v) for v in values) + ")"


def build_sql() -> str:
    if not RUNS_FILE.exists():
        sys.exit("No CI data yet. Run once with --fetch (needs the GitHub CLI, `gh`).")
    all_runs = json.loads(RUNS_FILE.read_text())
    runs = [r for r in all_runs if (DATA_DIR / str(r["databaseId"])).is_dir()]

    lines = ["BEGIN;", "TRUNCATE test_results, ci_runs, bugs;"]
    for run in runs:
        values = [
            run["databaseId"],
            run["headBranch"],
            run["event"],
            run["conclusion"],
            run["headSha"][:7],
            run["displayTitle"],
            run["createdAt"],
            run["updatedAt"],
        ]
        lines.append(f"INSERT INTO ci_runs VALUES ({', '.join(sql_text(v) for v in values)});")
        rows = list(test_rows(run["databaseId"]))
        if rows:
            lines.append("INSERT INTO test_results VALUES\n  " + ",\n  ".join(rows) + ";")

    with BUGS_FILE.open(newline="") as handle:
        for bug in csv.DictReader(handle):
            fields: list[Any] = list(bug.values())
            fields[7] = bug["escaped_to_production"] == "true"  # CSV text -> SQL boolean
            lines.append(f"INSERT INTO bugs VALUES ({', '.join(sql_text(v) for v in fields)});")

    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="download CI runs and reports first")
    parser.add_argument("--limit", type=int, default=30, help="how many recent CI runs to fetch")
    args = parser.parse_args()
    if args.fetch:
        fetch(args.limit)
    sys.stdout.write(build_sql())


if __name__ == "__main__":
    main()
