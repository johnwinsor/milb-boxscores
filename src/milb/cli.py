"""Command-line interface.

Every flag the original single-file script accepted still works, so existing
muscle memory and shell history keep functioning:

    milb 7                          milb 7 --format csv --out lines.csv
    milb --days 3 --season 2026     milb 7 --team Zebras
    milb --lookup "Name"            milb --lookup-id 829045

New subcommands split the fetch from the render, which is what lets the GitHub
Action refresh data without rendering anything:

    milb ingest                     fetch game logs into data/milb.sqlite
    milb export                     write static JSON for the web app
"""

import argparse
import os
import sys
from datetime import datetime

from . import db, query, render
from .config import DB_PATH


def _report_args(p):
    p.add_argument("days", type=int, nargs="?", default=7,
                   help="number of days to look back (default: 7)")
    p.add_argument("--days", dest="days_opt", type=int, default=None,
                   help="alternate spelling of the positional days argument")
    p.add_argument("--season", type=int, default=datetime.now().year,
                   help="season year to query (default: current year)")
    p.add_argument("--format", choices=["text", "csv", "json"], default="text",
                   help="output format (default: text)")
    p.add_argument("--out", default=None,
                   help="output file path (required for csv/json; text defaults to stdout)")
    p.add_argument("--team", default=None, metavar="TEAM",
                   help="only report one fantasy roster (case-insensitive), e.g. --team Zebras")
    p.add_argument("--plain", action="store_true",
                   help="disable Rich colorized tables; plain-text output")
    return p


def build_parser():
    parser = argparse.ArgumentParser(
        prog="milb",
        description="Daily box-score lines for a roster of MLB/MiLB prospects.")
    parser.add_argument("--db", default=str(DB_PATH), help=f"SQLite path (default: {DB_PATH})")
    parser.add_argument("--debug", action="store_true",
                        help="print search/game-log diagnostics to stderr")
    parser.add_argument("--lookup", default=None, metavar="NAME",
                        help="print raw search results for NAME and exit")
    parser.add_argument("--lookup-id", default=None, type=int, metavar="PERSON_ID",
                        help="print the full person record for PERSON_ID and exit")
    # Accepted for backwards compatibility with the JSON-cache era.
    parser.add_argument("--no-cache", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--clear-cache", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cache-file", default=None, help=argparse.SUPPRESS)

    subs = parser.add_subparsers(dest="command")
    rep = subs.add_parser("report", help="render a box-score report (default)")
    _report_args(rep)
    rep.add_argument("--db", default=None, help=argparse.SUPPRESS)
    rep.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    rep.add_argument("--no-cache", action="store_true", help=argparse.SUPPRESS)
    rep.add_argument("--clear-cache", action="store_true", help=argparse.SUPPRESS)
    rep.add_argument("--cache-file", default=None, help=argparse.SUPPRESS)

    ing = subs.add_parser("ingest", help="fetch game logs into SQLite")
    ing.add_argument("--season", type=int, default=datetime.now().year)
    ing.add_argument("--workers", type=int, default=6)

    exp = subs.add_parser("export", help="write static JSON for the web app")
    exp.add_argument("--season", type=int, default=datetime.now().year)
    exp.add_argument("--out-dir", default=None)

    subs.add_parser("migrate-cache", help="seed SQLite from a legacy milb_cache.json"
                    ).add_argument("path", nargs="?", default="milb_cache.json")

    return parser


SUBCOMMANDS = {"report", "ingest", "export", "migrate-cache"}


def _normalize_argv(argv):
    """`milb 7` and `milb --team Zebras` are shorthand for `milb report ...`.

    A positional `days` on the top-level parser would be ambiguous with the
    subcommand name, so insert the implied subcommand instead of declaring the
    argument twice.
    """
    argv = list(argv)
    for i, tok in enumerate(argv):
        if tok in SUBCOMMANDS:
            return argv
        if tok in ("-h", "--help", "--lookup", "--lookup-id"):
            return argv
        if tok.startswith("-"):
            continue
        # first bare token that is not a flag value
        if i == 0 or not argv[i - 1] in ("--db", "--out", "--team", "--format",
                                         "--season", "--cache-file"):
            break
    return ["report"] + argv


def main(argv=None):
    import sys as _sys
    argv = _normalize_argv(_sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.lookup_id or args.lookup:
        from .statsapi import StatsAPI
        api = StatsAPI(debug=args.debug)
        if args.lookup_id:
            person = api.get_person(args.lookup_id)
            if not person:
                print(f"No person found for id={args.lookup_id}")
                return 1
            team = (person.get("currentTeam") or {}).get("name", "?")
            print(f"id={person['id']}")
            print(f"fullName={person.get('fullName', '?')}")
            print(f"currentTeam={team}")
            print(f"primaryPosition={(person.get('primaryPosition') or {}).get('abbreviation','?')}")
            print(f"birthDate={person.get('birthDate', '?')}")
            print(f"active={person.get('active', '?')}")
            return 0
        people = api.search_people(args.lookup)
        if not people:
            print(f"No matches for '{args.lookup}'")
            return 1
        for p in people:
            team = (p.get("currentTeam") or {}).get("name", "?")
            print(f"id={p['id']:<8} fullName={p.get('fullName','?'):<25} currentTeam={team}")
        return 0

    if args.command == "ingest":
        from . import ingest
        r = ingest.run(season=args.season, db_path=args.db,
                       workers=args.workers, debug=args.debug)
        print(f"ingested {r['rows']} rows for {r['resolved']}/{r['players']} players "
              f"in {r['requests']} requests", file=sys.stderr)
        for key, msg in r["errors"].items():
            print(f"  unresolved: {key}: {msg}", file=sys.stderr)
        return 0

    if args.command == "export":
        from . import export
        written = export.run(season=args.season, db_path=args.db, out_dir=args.out_dir)
        print(f"wrote {written} JSON files", file=sys.stderr)
        return 0

    if args.command == "migrate-cache":
        from . import migrate
        n = migrate.from_json_cache(args.path, db_path=args.db)
        print(f"seeded {n} game-log rows from {args.path}", file=sys.stderr)
        return 0

    # -- default: report ---------------------------------------------------
    db_path = args.db or str(DB_PATH)
    days = args.days_opt if getattr(args, "days_opt", None) is not None else args.days
    if args.format in ("csv", "json") and not args.out:
        parser.error(f"--out is required when --format={args.format}")
    if not os.path.exists(db_path):
        parser.error(f"no database at {db_path} -- run `milb ingest` first")

    conn = db.connect(db_path, readonly=True)
    reports = query.report(conn, days, args.season, team=args.team)
    if args.team and not reports:
        teams = [r[0] for r in conn.execute("SELECT name FROM fantasy_team ORDER BY ord")]
        parser.error(f"no players found for team '{args.team}'. Known teams: {', '.join(teams)}")

    if args.format == "text":
        if args.out:
            with open(args.out, "w") as f:
                render.write_text(reports, days, args.season, f)
        elif render.RICH_AVAILABLE and not args.plain:
            render.write_rich(reports, days, args.season)
        else:
            render.write_text(reports, days, args.season)
    else:
        records = query.flat_records(reports)
        writer = render.write_csv if args.format == "csv" else render.write_json
        writer(records, args.out)
        print(f"Wrote {len(records)} rows to {args.out}", file=sys.stderr)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
