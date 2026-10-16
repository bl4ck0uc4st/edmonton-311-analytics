"""Command-line entry point: ``yeg311 <command>``.

yeg311 sample    [--rows N] [--seed S]       synthetic bronze partitions (offline demo / CI)
yeg311 extract   [--mode full|incremental]   pull real data from data.edmonton.ca
yeg311 build                                 bronze -> silver -> gold in DuckDB
yeg311 quality                               run data-quality checks (exit 1 on critical failure)
yeg311 export    [--no-csv]                  write gold tables to data/exports (Parquet + CSV)
yeg311 run       [--mode ...] [--sample]     extract/sample -> build -> quality -> export
yeg311 stats                                 headline numbers for the README
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from . import __version__
from .config import Settings


def _settings_from_args(args: argparse.Namespace) -> Settings:
    kwargs = {}
    if getattr(args, "data_dir", None):
        kwargs["data_dir"] = args.data_dir
    s = Settings(**kwargs)
    s.ensure_dirs()
    return s


def cmd_sample(args: argparse.Namespace) -> int:
    from .sample import write_sample

    s = _settings_from_args(args)
    counts = write_sample(
        s, n_rows=args.rows, seed=args.seed, today=date.fromisoformat(args.today) if args.today else None
    )
    print(
        f"Synthetic sample written to {s.raw_dir}: {sum(counts.values()):,} rows in {len(counts)} partitions"
    )
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    from .extract import run_extract

    s = _settings_from_args(args)
    if args.lookback_months:
        s.lookback_months = args.lookback_months
    results = run_extract(s, mode=args.mode)
    total = sum(results.values())
    print(f"Extracted {total:,} rows across {len(results)} month partitions -> {s.raw_dir}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from .warehouse import build_warehouse

    s = _settings_from_args(args)
    summary = build_warehouse(s)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_quality(args: argparse.Namespace) -> int:
    from .quality import format_report, run_quality

    s = _settings_from_args(args)
    report = run_quality(s)
    print(format_report(report))
    return 1 if report["status"] == "FAIL" else 0


def cmd_export(args: argparse.Namespace) -> int:
    from .export import export_gold

    s = _settings_from_args(args)
    meta = export_gold(s, csv=not args.no_csv)
    print(f"Exported {len(meta['files'])} tables to {s.export_dir}")
    return 0


def cmd_charts(args: argparse.Namespace) -> int:
    from .charts import render_charts

    s = _settings_from_args(args)
    paths = render_charts(s, out_dir=args.out)
    print(f"Rendered {len(paths)} charts to {paths[0].parent}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    from .stats import format_stats, headline_stats

    s = _settings_from_args(args)
    print(format_stats(headline_stats(s)))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .export import export_gold
    from .quality import format_report, run_quality
    from .warehouse import build_warehouse

    s = _settings_from_args(args)
    if args.sample:
        from .sample import write_sample

        write_sample(s, n_rows=args.rows, seed=args.seed)
    else:
        from .extract import run_extract

        if args.lookback_months:
            s.lookback_months = args.lookback_months
        run_extract(s, mode=args.mode)
    summary = build_warehouse(s)
    print(json.dumps(summary, indent=2))
    report = run_quality(s)
    print(format_report(report))
    if report["status"] == "FAIL":
        print("Critical data-quality failures: export skipped.", file=sys.stderr)
        return 1
    export_gold(s, csv=not args.no_csv)
    print(f"Exports written to {s.export_dir}")
    if not args.no_charts:
        from .charts import render_charts

        paths = render_charts(s)
        print(f"Charts written to {paths[0].parent}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yeg311", description="Edmonton 311 analytics pipeline")
    p.add_argument("--version", action="version", version=f"yeg311 {__version__}")
    p.add_argument("--data-dir", help="override the data directory (default: ./data)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("sample", help="generate synthetic bronze partitions")
    sp.add_argument("--rows", type=int, default=25_000)
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--today", help="pin the 'current date' (YYYY-MM-DD) for reproducible samples")
    sp.set_defaults(func=cmd_sample)

    ep = sub.add_parser("extract", help="download data from the Edmonton Open Data Portal")
    ep.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    ep.add_argument("--lookback-months", type=int, default=None)
    ep.set_defaults(func=cmd_extract)

    sub.add_parser("build", help="build the DuckDB warehouse").set_defaults(func=cmd_build)
    sub.add_parser("quality", help="run data-quality checks").set_defaults(func=cmd_quality)

    xp = sub.add_parser("export", help="export gold tables for Power BI")
    xp.add_argument("--no-csv", action="store_true")
    xp.set_defaults(func=cmd_export)

    sub.add_parser("stats", help="print headline statistics").set_defaults(func=cmd_stats)

    cp = sub.add_parser("charts", help="render preview charts from the warehouse")
    cp.add_argument("--out", help="output directory (default: data/exports/charts)")
    cp.set_defaults(func=cmd_charts)

    rp = sub.add_parser("run", help="end-to-end pipeline")
    rp.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    rp.add_argument("--lookback-months", type=int, default=None)
    rp.add_argument("--sample", action="store_true", help="use synthetic data instead of the API")
    rp.add_argument("--rows", type=int, default=25_000)
    rp.add_argument("--seed", type=int, default=42)
    rp.add_argument("--no-csv", action="store_true")
    rp.add_argument("--no-charts", action="store_true", help="skip rendering preview charts")
    rp.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
