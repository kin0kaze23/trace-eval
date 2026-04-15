"""CLI entrypoint for trace-eval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trace_eval.loader import load_trace_with_report
from trace_eval.scoring import compute_scorecard, DEFAULT_PROFILE, REQUIRED_JUDGES
from trace_eval.report import format_text, format_json
from trace_eval.judges.reliability import judge_reliability
from trace_eval.judges.efficiency import judge_efficiency
from trace_eval.judges.retrieval import judge_retrieval
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.judges.context import judge_context

JUDGES = {
    "reliability": judge_reliability,
    "efficiency": judge_efficiency,
    "retrieval": judge_retrieval,
    "tool_discipline": judge_tool_discipline,
    "context": judge_context,
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.trace)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    trace, report = load_trace_with_report(path)

    # Basic schema validation
    errors: list[str] = []
    if not trace.events:
        errors.append("No events in trace")

    indices = [e.event_index for e in trace.events]
    if indices != sorted(indices):
        errors.append("Events are not in order by event_index")

    unknown_types = [
        e.event_index for e in trace.events if e.event_type is None
    ]
    if unknown_types:
        errors.append(f"Unknown event types at indices: {unknown_types}")

    # Field coverage
    from trace_eval.schema import FieldCoverage
    coverage = FieldCoverage.compute(trace.events)

    if errors:
        print(f"Schema validation FAILED for {path}:")
        for err in errors:
            print(f"  X {err}")
        return 1
    else:
        print(f"Schema validation PASSED for {path}")
        print(f"  Events: {len(trace.events)}")

    print("\nField coverage:")
    # Only show fields with non-100% coverage to keep output clean
    for field_name, entry in sorted(coverage.fields.items()):
        pct = entry.coverage_pct
        if pct < 100:
            bar = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
            print(f"  {field_name:30s} {pct:5.0f}% [{bar}]")
        else:
            print(f"  {field_name:30s} {pct:5.0f}% [####################]")

    print("\nAdapter capability report:")
    for key, val in report.items():
        print(f"  {key}: {val}")

    return 0


def cmd_run(args: argparse.Namespace) -> int:
    path = Path(args.trace)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    trace, adapter_report = load_trace_with_report(path)

    judge_results = {name: fn(trace.events) for name, fn in JUDGES.items()}
    card = compute_scorecard(judge_results)

    if args.format == "json":
        print(format_json(card, adapter_report=adapter_report))
    else:
        print(format_text(card, adapter_report=adapter_report))

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    before_path = Path(args.before)
    after_path = Path(args.after)

    if not before_path.exists():
        print(f"Error: file not found: {before_path}", file=sys.stderr)
        return 1
    if not after_path.exists():
        print(f"Error: file not found: {after_path}", file=sys.stderr)
        return 1

    before_trace, before_report = load_trace_with_report(before_path)
    after_trace, after_report = load_trace_with_report(after_path)

    before_results = {name: fn(before_trace.events) for name, fn in JUDGES.items()}
    after_results = {name: fn(after_trace.events) for name, fn in JUDGES.items()}

    before_card = compute_scorecard(before_results)
    after_card = compute_scorecard(after_results)

    # --- Text comparison (default) ---
    if args.format != "json":
        print("COMPARISON: before vs after")
        print("=" * 55)
        print(f"  Total score: {before_card.total_score:6.1f} -> {after_card.total_score:6.1f}")
        total_delta = after_card.total_score - before_card.total_score
        if total_delta > 0:
            print(f"  Change:      +{total_delta:.1f} (improved)")
        elif total_delta < 0:
            print(f"  Change:      {total_delta:.1f} (regressed)")
        else:
            print(f"  Change:      0.0 (no change)")
        print()

        for dim in before_card.dimension_scores:
            b = before_card.dimension_scores[dim]
            a = after_card.dimension_scores[dim]
            b_str = f"{b:.1f}" if b is not None else "N/A"
            a_str = f"{a:.1f}" if a is not None else "N/A"
            if b is not None and a is not None:
                delta = a - b
                if delta > 0:
                    delta_str = f"+{delta:.1f}"
                    indicator = "^"
                elif delta < 0:
                    delta_str = f"{delta:.1f}"
                    indicator = "v"
                else:
                    delta_str = " 0.0"
                    indicator = "="
            else:
                delta_str = "---"
                indicator = " "

            print(f"  {dim:20s} {b_str:>6s} -> {a_str:>6s}  {indicator} {delta_str}")

        # Flag comparison
        before_flags = before_card.all_flags
        after_flags = after_card.all_flags
        before_flag_ids = {f.id for f in before_flags}
        after_flag_ids = {f.id for f in after_flags}

        resolved = before_flag_ids - after_flag_ids
        new_flags = after_flag_ids - before_flag_ids

        if resolved or new_flags:
            print()
            print("  FLAG CHANGES:")
            for fid in sorted(resolved):
                print(f"    [RESOLVED] {fid}")
            for fid in sorted(new_flags):
                flag = next(f for f in after_flags if f.id == fid)
                print(f"    [NEW] [{flag.severity.upper():8s}] {fid}")

        print()
        return 0

    # --- JSON comparison ---
    before_flag_ids_j = {f.id for f in before_card.all_flags}
    after_flag_ids_j = {f.id for f in after_card.all_flags}

    output = {
        "before": {
            "total_score": before_card.total_score,
            "dimension_scores": before_card.dimension_scores,
        },
        "after": {
            "total_score": after_card.total_score,
            "dimension_scores": after_card.dimension_scores,
        },
        "delta": {},
        "flag_changes": {
            "resolved": sorted(before_flag_ids_j - after_flag_ids_j),
            "new": sorted(after_flag_ids_j - before_flag_ids_j),
        },
    }

    for dim in before_card.dimension_scores:
        b = before_card.dimension_scores.get(dim)
        a = after_card.dimension_scores.get(dim)
        if b is not None and a is not None:
            output["delta"][dim] = round(a - b, 2)
        else:
            output["delta"][dim] = None

    print(json.dumps(output, indent=2, sort_keys=False))
    return 0


def cmd_ci(args: argparse.Namespace) -> int:
    path = Path(args.trace)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    min_score = args.min_score
    allow_partial = args.allow_partial
    use_json = args.format == "json"

    trace, adapter_report = load_trace_with_report(path)
    judge_results = {name: fn(trace.events) for name, fn in JUDGES.items()}
    card = compute_scorecard(judge_results)

    # Collect structured failure reasons
    failed_thresholds: list[dict] = []
    failure_lines: list[str] = []

    # Check required judges
    if card.missing_required_judges and not allow_partial:
        for dim in card.missing_required_judges:
            failed_thresholds.append({"type": "judge_not_scorable", "dimension": dim})
            failure_lines.append(f"required judge '{dim}' is not scorable")

    # Check total score threshold
    if card.total_score < min_score:
        failed_thresholds.append({
            "type": "total_score_below_threshold",
            "threshold": min_score,
            "actual": card.total_score,
        })
        failure_lines.append(f"total score {card.total_score:.1f} < minimum {min_score}")

    # Check per-dimension thresholds
    if args.min_dimension:
        for dim_threshold in args.min_dimension:
            dim, threshold = dim_threshold.split("=", 1)
            threshold = float(threshold)
            actual = card.dimension_scores.get(dim)
            if actual is not None and actual < threshold:
                failed_thresholds.append({
                    "type": "dimension_below_threshold",
                    "dimension": dim,
                    "threshold": threshold,
                    "actual": actual,
                })
                failure_lines.append(f"{dim} score {actual:.1f} < minimum {threshold}")

    # Always output scorecard on stdout
    if use_json:
        output = json.loads(format_json(card, adapter_report=adapter_report, failed_thresholds=failed_thresholds))
        print(json.dumps(output, indent=2))
    else:
        print(format_text(card, adapter_report=adapter_report))

    # If any failures, compact summary to stderr and exit 1
    if failed_thresholds:
        print("FAIL: " + "; ".join(failure_lines), file=sys.stderr)
        return 1

    print("PASS", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="trace-eval",
        description="Tell you why this agent run went wrong and what to change next.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = sub.add_parser("validate", help="Schema validation + field coverage + adapter capabilities")
    p_validate.add_argument("trace", help="Path to trace file (.jsonl or .db)")

    # run
    p_run = sub.add_parser("run", help="Full scorecard")
    p_run.add_argument("trace", help="Path to trace file")
    p_run.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")

    # compare
    p_compare = sub.add_parser("compare", help="Delta between two traces")
    p_compare.add_argument("before", help="Path to before trace")
    p_compare.add_argument("after", help="Path to after trace")
    p_compare.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")

    # ci
    p_ci = sub.add_parser("ci", help="CI gate -- exits non-zero below threshold")
    p_ci.add_argument("trace", help="Path to trace file")
    p_ci.add_argument("--min-score", type=float, default=80, help="Minimum total score (default: 80)")
    p_ci.add_argument("--min-dimension", action="append", help="Per-dimension threshold (e.g., reliability=90)")
    p_ci.add_argument("--allow-partial", action="store_true", help="Allow unscorable judges")
    p_ci.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")

    args = parser.parse_args()

    commands = {
        "validate": cmd_validate,
        "run": cmd_run,
        "compare": cmd_compare,
        "ci": cmd_ci,
    }

    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
