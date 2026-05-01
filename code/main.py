from __future__ import annotations

import argparse
from pathlib import Path

from triage_agent import SupportTriageAgent, run_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Terminal support-triage agent for HackerRank Orchestrate."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("support_tickets/support_tickets.csv"),
        help="Path to input CSV containing Issue, Subject, Company.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("support_tickets/output.csv"),
        help="Path to write predictions CSV.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory that contains local support corpus markdown files.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of evidence snippets to use in responses.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = SupportTriageAgent(data_dir=args.data_dir)
    run_batch(
        agent=agent,
        input_csv=args.input,
        output_csv=args.output,
        top_k=args.top_k,
    )
    print(f"Wrote triage output to: {args.output}")


if __name__ == "__main__":
    main()
