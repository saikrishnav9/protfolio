from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from pulse.config import ROOT, get_settings
from pulse.ingest.run import ingest_bronze
from pulse.pipeline import run_pipeline
from pulse.site_build import assemble_site


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pulse", description="Pulse public-signal lakehouse")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pipe = sub.add_parser("pipeline", help="ingest → test → enrich → export dashboard")
    pipe.add_argument("--offline", action="store_true", help="use committed fixtures instead of live APIs")
    pipe.add_argument("--no-dbt", action="store_true", help="run Python contracts only")

    sub.add_parser("ingest", help="land bronze parquet")
    sub.add_parser("serve", help="serve the portfolio + Pulse demo locally")
    sub.add_parser("assemble-site", help="copy Pulse under site/pulse for GitHub Pages")

    args = parser.parse_args(argv)
    settings = get_settings()

    if args.cmd == "ingest":
        counts = ingest_bronze(settings)
        print(json.dumps(counts, indent=2))
        return 0

    if args.cmd == "pipeline":
        if args.offline:
            os.environ["PULSE_OFFLINE"] = "1"
        run = run_pipeline(offline=args.offline or None, use_dbt=not args.no_dbt)
        print(json.dumps(run.to_public_dict(), indent=2))
        return 0 if run.status == "success" else 2

    if args.cmd == "assemble-site":
        root = assemble_site()
        print(str(root / "pulse"))
        return 0

    if args.cmd == "serve":
        assemble_site()
        site = ROOT / "site"
        os.chdir(site)
        port = int(os.environ.get("PORT", "8080"))

        class NoCacheHandler(SimpleHTTPRequestHandler):
            def end_headers(self) -> None:
                self.send_header("Cache-Control", "no-store")
                super().end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", port), NoCacheHandler)
        print(f"Portfolio http://127.0.0.1:{port}", flush=True)
        print(f"Pulse     http://127.0.0.1:{port}/pulse/", flush=True)
        server.serve_forever()
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
