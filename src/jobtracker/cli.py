"""Command line entry point: jobtracker ui | sync | doctor | seed | stats | reset."""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_settings


def cmd_ui(args, settings) -> int:
    from .desktop import run_ui

    run_ui(settings, browser=args.browser, port=args.port)
    return 0


def cmd_sync(args, settings) -> int:
    from .pipeline import sync

    def progress(p):
        if p.get("phase") in ("fetching", "extracting"):
            model = f" · {p['model']}" if p.get("model") else ""
            print(f"\r{p['phase'].capitalize()} {p['current']}/{p['total']}{model}   ", end="", flush=True)
        elif p.get("message"):
            print(p["message"])

    result = sync(settings, progress, dry_run=args.dry_run, full=args.full)
    print()
    if args.dry_run:
        print(f"Query: {result['query']}")
        print(f"{result['matched']} matched, {result['new']} not processed yet "
              f"({result['own_replies']} of them your own replies, stored without analysis):\n")
        for e in result["emails"]:
            mark = "keep" if e["keep"] else "drop"
            kind = " (your outreach)" if e["kind"] == "outreach" else ""
            print(f"  [{mark}] {e['date'][:10]}  {e['subject'][:90]}{kind}")
    else:
        print(f"{result['matched']} matched, {result['new']} new "
              f"({result['followed']} found by following {result['domains']} company domains)")
        print(f"Results: {result['counts']}")
    return 0


def cmd_doctor(args, settings) -> int:
    from .doctor import run_doctor

    return run_doctor(settings)


def cmd_seed(args, settings) -> int:
    from sqlmodel import Session

    from .db import get_engine
    from .seed import seed

    with Session(get_engine(settings.db_path)) as session:
        n = seed(session, force=args.force)
    print(f"Seeded {n} sample applications." if n else "Already seeded (use --force to add more).")
    return 0


def cmd_stats(args, settings) -> int:
    from sqlmodel import Session

    from .db import get_engine
    from .filters import Filters, load_rows
    from .stats import compute_stats

    with Session(get_engine(settings.db_path)) as session:
        rows = load_rows(session, Filters(range=args.range), settings)
    print(json.dumps(compute_stats(rows), indent=2))
    return 0


def cmd_reset(args, settings) -> int:
    from .db import dispose_engine

    targets = [settings.db_path, settings.db_path.with_name("jobs.db-wal"),
               settings.db_path.with_name("jobs.db-shm"), settings.token_path]
    existing = [p for p in targets if p.exists()]
    if not existing:
        print("Nothing to delete.")
        return 0
    if not args.yes:
        print("This deletes:\n  " + "\n  ".join(map(str, existing)))
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            print("Aborted.")
            return 1
    dispose_engine(settings.db_path)
    for p in existing:
        p.unlink()
    print("Reset complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobtracker", description="Local job application tracker.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ui", help="open the app (native window, or --browser)")
    p.add_argument("--browser", action="store_true", help="open a browser tab instead of a window")
    p.add_argument("--port", type=int, help="port to bind on 127.0.0.1 (default: a free one)")
    p.set_defaults(func=cmd_ui)

    p = sub.add_parser("sync", help="fetch Gmail and extract application events")
    p.add_argument("--dry-run", action="store_true", help="list fetched subjects; no LLM, no writes")
    p.add_argument("--full", action="store_true", help="ignore the last sync time and backfill again")
    p.set_defaults(func=cmd_sync)

    sub.add_parser("doctor", help="check Ollama, the model and GPU use").set_defaults(func=cmd_doctor)

    p = sub.add_parser("seed", help="add sample data for trying the UI")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("stats", help="print funnel stats")
    p.add_argument("--range", default="all", choices=["30d", "90d", "180d", "all"])
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("reset", help="delete the database and Gmail token")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(func=cmd_reset)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args, load_settings())


if __name__ == "__main__":
    sys.exit(main())
