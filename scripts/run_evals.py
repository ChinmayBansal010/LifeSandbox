#!/usr/bin/env python3
"""CLI utility to execute LLM evaluation and regression suites.

Supports running Promptfoo-based evals, Pytest-based regression suites,
and exporting structured regression summaries over time.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_promptfoo(output_path: Path | None = None, mode: str = "mock") -> int:
    promptfoo_bin = ROOT / "node_modules" / ".bin" / "promptfoo"
    if not promptfoo_bin.exists():
        print(
            "promptfoo binary not found in node_modules. Run 'npm install' first.",
            file=sys.stderr,
        )
        return 1

    cmd = [str(promptfoo_bin), "eval", "--no-progress-bar"]
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-o", str(output_path)])

    print(f"Running Promptfoo evaluation harness (mode={mode})...")
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def run_pytest_evals() -> int:
    print("Running Pytest-based LLM regression suite (tests/test_llm_eval_regression.py)...")
    cmd = ["uv", "run", "pytest", "tests/test_llm_eval_regression.py", "-v"]
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def run_speech_harness() -> int:
    print("Running Speech (STT/TTS) evaluation harness (scripts/run_speech_harness.py)...")
    cmd = ["uv", "run", "python", "scripts/run_speech_harness.py", "--suite", "all"]
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LLM evaluation and regression harness.")
    parser.add_argument(
        "--suite",
        choices=["promptfoo", "pytest", "speech", "all"],
        default="all",
        help="Evaluation suite to execute (default: all)",
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "nebius", "openrouter"],
        default="mock",
        help="LLM provider mode to test (default: mock)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evals" / "reports" / "latest.json",
        help="Path to save evaluation output (default: evals/reports/latest.json)",
    )

    args = parser.parse_args()

    exit_code = 0
    if args.suite in ("promptfoo", "all"):
        pf_code = run_promptfoo(output_path=args.output, mode=args.mode)
        if pf_code != 0:
            print(f"Promptfoo evaluation failed with code {pf_code}", file=sys.stderr)
            exit_code = pf_code
        elif args.output and args.output.exists():
            try:
                with args.output.open() as f:
                    data = json.load(f)
                stats = data.get("results", {}).get("stats", {})
                print(
                    f"Promptfoo Eval Summary: {stats.get('successes', 0)} passed, "
                    f"{stats.get('failures', 0)} failed, {stats.get('errors', 0)} errors."
                )
            except Exception as e:
                print(f"Could not parse eval output stats: {e}")

    if args.suite in ("pytest", "all"):
        pt_code = run_pytest_evals()
        if pt_code != 0:
            print(f"Pytest evaluation failed with code {pt_code}", file=sys.stderr)
            exit_code = pt_code

    if args.suite in ("speech", "all"):
        sp_code = run_speech_harness()
        if sp_code != 0:
            print(f"Speech harness evaluation failed with code {sp_code}", file=sys.stderr)
            exit_code = sp_code

    if exit_code == 0:
        print("All evaluation suites passed cleanly without regression.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
