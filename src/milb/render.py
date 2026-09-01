"""Terminal renderers. Output is intentionally identical to the original CLI."""

import csv
import json
import sys

try:
    from rich import box as rich_box
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

CSV_FIELDS = [
    "fantasy_team", "date", "player", "org", "level", "pos", "type", "team", "opponent",
    "PA", "AB", "H", "R", "RBI", "2B", "HR", "SB", "CS", "BB", "K",
    "IP", "ER", "is_total",
]

HITTER_COLUMNS = ["Date", "Team", "Opp", "PA", "AB", "H", "R", "RBI", "2B", "HR", "SB", "CS", "BB", "K"]
PITCHER_COLUMNS = ["Date", "Team", "Opp", "IP", "H", "R", "ER", "BB", "K", "HR"]


def format_hitting_line(rec):
    prefix = "TOTAL" if rec.get("is_total") else f"{rec['date']}  {rec['team']} vs {rec['opponent']}:"
    return (f"{prefix} "
            f"{rec['PA']} PA {rec['AB']} AB {rec['H']} H {rec['R']} R "
            f"{rec['RBI']} RBI {rec['2B']} 2B {rec['HR']} HR {rec['SB']} SB "
            f"{rec['CS']} CS {rec['BB']} BB {rec['K']} K")


def format_pitching_line(rec):
    prefix = "TOTAL" if rec.get("is_total") else f"{rec['date']}  {rec['team']} vs {rec['opponent']}:"
    return (f"{prefix} "
            f"{rec['IP']} IP {rec['H']} H {rec['R']} R {rec['ER']} ER "
            f"{rec['BB']} BB {rec['K']} K {rec['HR']} HR")


def _stat_cell(col, value, rec, pitcher):
    """Highlight standout lines. The web app mirrors these thresholds in CSS."""
    text = str(value)
    if col == "HR" and isinstance(value, int) and value > 0:
        return f"[bold green]{text}[/bold green]"
    if col == "H" and not pitcher and isinstance(value, int) and value >= 3:
        return f"[bold green]{text}[/bold green]"
    if col == "K" and pitcher and isinstance(value, int) and value >= 8:
        return f"[bold cyan]{text}[/bold cyan]"
    if col == "ER" and pitcher and rec.get("IP") not in (None, "0.0") and isinstance(value, int) and value == 0:
        return f"[bold green]{text}[/bold green]"
    if col == "SB" and not pitcher and isinstance(value, int) and value > 0:
        return f"[cyan]{text}[/cyan]"
    return text


def write_rich(reports, days, season, plain_console=False):
    console = Console(no_color=plain_console, width=None)
    if not console.is_terminal:
        console.width = max(console.width, 100)
    console.print(f"\n[bold]Box scores for the last {days} day(s), season {season}[/bold]\n")

    current_team = object()  # sentinel guarantees the first heading always prints
    for rep in reports:
        if rep.fantasy_team != current_team:
            console.print(Rule(f"[bold]{rep.fantasy_team}[/bold]", style="bright_black"))
            current_team = rep.fantasy_team

        title = f"{rep.name}  ·  {rep.org} {rep.level} {rep.pos}"
        if rep.error:
            console.print(Panel(f"[dim]{rep.error}[/dim]", title=title, title_align="left",
                                border_style="yellow", box=rich_box.ROUNDED))
            continue
        if not rep.records:
            console.print(Panel(f"[dim]no games played in the last {days} day(s)[/dim]",
                                title=title, title_align="left", border_style="dim",
                                box=rich_box.ROUNDED))
            continue

        pitcher = rep.is_pitcher
        columns = PITCHER_COLUMNS if pitcher else HITTER_COLUMNS
        table = Table(box=rich_box.SIMPLE_HEAVY, show_edge=False, header_style="bold")
        for col in columns:
            table.add_column(col, justify="left" if col in ("Date", "Team", "Opp") else "right",
                             no_wrap=True, overflow="ellipsis")
        for rec in rep.records:
            row = [rec["date"], rec["team"], rec["opponent"]]
            row += [_stat_cell(c, rec.get(c, ""), rec, pitcher) for c in columns[3:]]
            table.add_row(*row)
        if rep.total:
            table.add_section()
            table.add_row("[bold]TOTAL[/bold]", "", "",
                          *[f"[bold]{rep.total.get(c, '')}[/bold]" for c in columns[3:]])

        console.print(Panel(table, title=title, title_align="left",
                            border_style="red" if pitcher else "blue",
                            box=rich_box.ROUNDED, padding=(0, 1)))
    console.print()


def write_text(reports, days, season, out=None):
    stream = out or sys.stdout
    print(f"Box scores for the last {days} day(s), season {season}\n", file=stream)
    current_team = object()
    for rep in reports:
        if rep.fantasy_team != current_team:
            print(f"=== {rep.fantasy_team} ===\n", file=stream)
            current_team = rep.fantasy_team
        print(f"{rep.name} ({rep.org} {rep.level} {rep.pos}):", file=stream)
        if rep.error:
            print(f"  {rep.error}", file=stream)
        elif not rep.records:
            print(f"  no games played in the last {days} day(s)", file=stream)
        else:
            fmt = format_pitching_line if rep.is_pitcher else format_hitting_line
            for rec in rep.records:
                print(f"  {fmt(rec)}", file=stream)
            if rep.total:
                print(file=stream)
                print(f"  {fmt(rep.total)}", file=stream)
        print(file=stream)


def write_csv(records, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def write_json(records, path):
    keys = set(CSV_FIELDS) | {"game_pk", "summary", "is_home", "is_win"}
    with open(path, "w") as f:
        json.dump([{k: v for k, v in r.items() if k in keys} for r in records], f, indent=2)
