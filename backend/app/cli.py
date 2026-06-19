"""Small CLI for operating the agent without the web layer.

Usage::

    python -m app.cli run-pipeline          # full pipeline (no email)
    python -m app.cli run-pipeline --email  # full pipeline + send emails
    python -m app.cli init                   # seed superuser + sources
    python -m app.cli collect                # only collect news
"""

from __future__ import annotations

import argparse
import json

from app.ai.graph import run_pipeline
from app.db.init_db import init_db
from app.db.session import session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="AI News Intelligence Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run-pipeline", help="Run the full agent pipeline")
    p_run.add_argument("--email", action="store_true", help="Also send the brief + digests")

    sub.add_parser("init", help="Seed superuser and default sources")
    sub.add_parser("collect", help="Run only the collector agent")
    sub.add_parser("send-brief", help="Re-generate latest report and email the PDF brief")

    args = parser.parse_args()

    if args.command == "init":
        with session_scope() as db:
            init_db(db)
        print("Initialized database (superuser + sources).")
    elif args.command == "collect":
        from app.agents import collector

        with session_scope() as db:
            print(json.dumps(collector.collect(db), indent=2))
    elif args.command == "run-pipeline":
        with session_scope() as db:
            init_db(db)
            stats = run_pipeline(db, send_email=args.email)
        print(json.dumps(stats, indent=2, default=str))
    elif args.command == "send-brief":
        from app.agents import email as email_agent
        from app.agents import report as report_agent

        with session_scope() as db:
            report = report_agent.generate(db, kind="daily")
            result = email_agent.send_daily_brief(db, report)
            print(json.dumps({"report_id": report.id, "pdf": report.pdf_path, **result},
                             indent=2, default=str))


if __name__ == "__main__":
    main()
