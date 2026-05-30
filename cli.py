#!/usr/bin/env python3
"""
SlopLens CLI — slop detection in your terminal
Usage:
  sloplens scan "your text here"
  sloplens scan --file README.md
  sloplens scan --url https://example.com/blog
  sloplens repo owner/repo
  sloplens compare before.txt after.txt
  sloplens batch file1.txt file2.txt file3.txt
  sloplens config --backend https://your-api.railway.app

Get a free Groq API key at https://console.groq.com
"""
import click
import json
import os
import sys
import httpx
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box

console = Console()

# ── Config ─────────────────────────────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".sloplens" / "config.json"
DEFAULT_BACKEND = "http://localhost:8000"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_backend() -> str:
    cfg = load_config()
    return cfg.get("backend", os.getenv("SLOPLENS_BACKEND", DEFAULT_BACKEND))


# ── Display helpers ────────────────────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 65: return "red"
    if score >= 35: return "yellow"
    return "green"


def score_label(score: int) -> str:
    if score >= 65: return "HIGH SLOP"
    if score >= 35: return "MEDIUM SLOP"
    return "CLEAN"


def score_bar(value: int, width: int = 20, higher_is_better: bool = False) -> Text:
    bad = (100 - value) if higher_is_better else value
    color = "red" if bad >= 65 else "yellow" if bad >= 35 else "green"
    filled = int(value / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return Text(bar, style=color)


def print_result(r: dict, title: str = "SlopLens"):
    score    = r.get("overall_slop_score", 0)
    color    = score_color(score)
    label    = score_label(score)

    console.print()

    # Score header
    console.print(Panel(
        f"[bold {color}]{score}[/bold {color}] / 100  [{color}]{label}[/{color}]"
        + (f"\n[dim]method: {r.get('scoring_method','?')}[/dim]" if r.get('scoring_method') else ""),
        title=f"[bold]{title}[/bold]",
        border_style=color,
        padding=(0, 2),
    ))

    # Reading time
    if r.get("reading_time_min") is not None:
        rt, it, fp = r["reading_time_min"], r["info_time_min"], r["fluff_percent"]
        console.print(
            f"  [dim]Read:[/dim] {rt}min  →  "
            f"[{color}]Useful: {it}min[/{color}]  "
            f"[{color}]Fluff: {fp}%[/{color}]"
        )
        console.print()

    # Metrics table
    t = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    t.add_column("Metric", style="dim", width=22)
    t.add_column("Bar", width=22)
    t.add_column("Val", justify="right", width=5)

    metrics = [
        ("Information density", r.get("information_density", 0), True),
        ("Filler ratio",        r.get("filler_ratio", 0),        False),
        ("Specificity",         r.get("specificity", 0),         True),
        ("Naturalness",         r.get("naturalness", 0),         True),
        ("Passive density",     r.get("passive_density", 0),     False),
    ]
    if r.get("semantic_slop_score") is not None:
        metrics.append(("Semantic slop",  r["semantic_slop_score"], False))

    for name, val, hib in metrics:
        bad = (100 - val) if hib else val
        c   = "red" if bad >= 65 else "yellow" if bad >= 35 else "green"
        t.add_row(name, score_bar(val, 20, hib), f"[{c}]{val}[/{c}]")
    console.print(t)

    # Roast
    if r.get("roast"):
        console.print(Panel(
            f'[italic]{r["roast"]}[/italic]',
            title="[bold yellow]ROAST[/bold yellow]",
            border_style="yellow", padding=(0,2)
        ))

    # Slop category
    if r.get("slop_category") and r["slop_category"] != "clean":
        console.print(f"  [dim]Category:[/dim] [{color}]{r['slop_category'].replace('_',' ')}[/{color}]")

    # Verdict
    if r.get("verdict"):
        console.print(f'\n  [dim italic]"{r["verdict"]}"[/dim italic]')

    # Flagged phrases
    if r.get("flagged_phrases"):
        console.print(f"\n  [dim]Flagged:[/dim] " +
                      "  ".join(f"[yellow]{p}[/yellow]" for p in r["flagged_phrases"]))

    # Fix
    if r.get("fix"):
        console.print(Panel(
            r["fix"],
            title="[bold green]Fix[/bold green]",
            border_style="green", padding=(0,2)
        ))
    console.print()


def make_request(endpoint: str, payload: dict, backend: str, fast: bool = False) -> dict:
    payload["fast"] = fast
    try:
        r = httpx.post(
            f"{backend.rstrip('/')}/{endpoint.lstrip('/')}",
            json=payload, timeout=30,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        console.print(f"[red]✗ Cannot connect to backend at {backend}[/red]")
        console.print("[dim]  → Start backend:  cd backend && uvicorn main:app --reload[/dim]")
        console.print("[dim]  → Set backend:    sloplens config --backend https://your-api.railway.app[/dim]")
        console.print("[dim]  → Check status:   sloplens doctor[/dim]")
        sys.exit(1)
    except httpx.TimeoutException:
        console.print(f"[red]✗ Request timed out — backend may be slow or overloaded[/red]")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", e.response.text[:200])
        except Exception:
            detail = e.response.text[:200]
        console.print(f"[red]✗ API error {e.response.status_code}:[/red] {detail}")
        sys.exit(1)


# ── CLI ────────────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("4.0.0", prog_name="sloplens", message="%(prog)s v%(version)s")
def cli():
    """SlopLens — detect slop in text, files, URLs, and GitHub repos."""
    pass


@cli.command()
@click.argument("text", required=False)
@click.option("--file", "-f",  type=click.Path(exists=True), help="Scan a text file")
@click.option("--url",  "-u",  help="Fetch and scan a URL")
@click.option("--fast", is_flag=True, help="Use fast LLM mode (Haiku)")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--threshold", "-t", type=int, default=None,
              help="Exit code 1 if slop score exceeds threshold (good for CI)")
def scan(text, file, url, fast, as_json, threshold):
    """Scan text, a file, or a URL for slop.

    \b
    Examples:
      sloplens scan "Moving forward, we will leverage synergies..."
      sloplens scan --file README.md
      sloplens scan --url https://example.com/blog-post
      sloplens scan --file README.md --threshold 60
    """
    backend = get_backend()

    # Get input text
    if file:
        content = Path(file).read_text(errors="ignore")
        source  = str(file)
    elif url:
        with Progress(SpinnerColumn(), TextColumn("[dim]Fetching URL..."), transient=True) as p:
            p.add_task("fetch")
            try:
                resp = httpx.get(url, timeout=10, follow_redirects=True,
                                 headers={"User-Agent":"SlopLens-CLI/4.0"})
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["nav","footer","header","script","style"]):
                    tag.decompose()
                main = soup.find("main") or soup.find("article") or soup.body
                content = main.get_text(separator=" ", strip=True)[:4000] if main else ""
            except Exception as e:
                console.print(f"[red]Failed to fetch URL: {e}[/red]")
                sys.exit(1)
        source = url
    elif text:
        content = text
        source  = "stdin"
    else:
        # Read from stdin if piped
        if not sys.stdin.isatty():
            content = sys.stdin.read()
            source  = "stdin"
        else:
            console.print("[red]Provide text, --file, or --url[/red]")
            sys.exit(1)

    if len(content.strip()) < 20:
        console.print("[red]Text too short (min 20 chars)[/red]")
        sys.exit(1)

    with Progress(SpinnerColumn(), TextColumn("[dim]Scanning..."), transient=True) as p:
        p.add_task("scan")
        result = make_request("scan", {"text": content[:8000]}, backend, fast)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    print_result(result, title=f"Scan: {Path(source).name if file else source[:50]}")

    if threshold is not None:
        score = result.get("overall_slop_score", 0)
        if score > threshold:
            console.print(f"[red]FAIL[/red] — slop score {score} exceeds threshold {threshold}")
            sys.exit(1)
        else:
            console.print(f"[green]PASS[/green] — slop score {score} within threshold {threshold}")


@cli.command()
@click.argument("repo")
@click.option("--fast", is_flag=True, help="Use fast LLM mode")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def repo(repo, fast, as_json):
    """Scan a GitHub repo — README, PRs, and commit messages.

    \b
    Examples:
      sloplens repo torvalds/linux
      sloplens repo https://github.com/openai/openai-python
    """
    backend = get_backend()

    with Progress(SpinnerColumn(), TextColumn("[dim]Scanning repo (README + PRs + commits)..."), transient=True) as p:
        p.add_task("scan")
        result = make_request("scan/repo", {"repo": repo}, backend, fast)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    score = result.get("overall_slop_score", 0)
    color = score_color(score)
    label = score_label(score)

    console.print()
    console.print(Panel(
        f"[bold {color}]{score}[/bold {color}] / 100  [{color}]{label}[/{color}]\n"
        f"[dim]{result.get('repo','')}[/dim]  [dim]★ {result.get('star_count',0):,}[/dim]",
        title="[bold]Repo Slop Score[/bold]",
        border_style=color, padding=(0,2),
    ))

    if result.get("verdict"):
        console.print(f'\n  [dim italic]"{result["verdict"]}"[/dim italic]\n')

    # Section breakdown
    t = Table(title="Section Breakdown", box=box.ROUNDED, border_style="dim")
    t.add_column("Section",      style="bold")
    t.add_column("Slop Score",   justify="center")
    t.add_column("Bar",          width=20)
    t.add_column("Details",      style="dim")

    for sec in result.get("sections", []):
        sc = sec["slop_score"]
        c  = score_color(sc)
        details = ""
        if sec.get("pr_count"):
            d = sec.get("score_distribution", {})
            details = f"{sec['pr_count']} PRs — {d.get('clean',0)}✓ {d.get('medium',0)}~ {d.get('slop',0)}✗"
        elif sec.get("commit_count"):
            details = f"{sec['commit_count']} commits"
        elif sec.get("word_count"):
            details = f"{sec['word_count']} words"
        t.add_row(
            sec["section"],
            f"[{c}]{sc}[/{c}]",
            score_bar(sc, 20),
            details,
        )
    console.print(t)

    # Worst samples
    for sec in result.get("sections", []):
        worst = sec.get("worst_sample") or sec.get("worst_message")
        if worst:
            console.print(Panel(
                f'[dim italic]"{worst[:200]}"[/dim italic]',
                title=f"[dim]Worst {sec['section']} sample[/dim]",
                border_style="dim", padding=(0,1),
            ))

    if result.get("cleanest_section"):
        console.print(f"  [green]Cleanest:[/green]  {result['cleanest_section']}")
    if result.get("sloppiest_section"):
        console.print(f"  [red]Sloppiest:[/red] {result['sloppiest_section']}")
    console.print()


@cli.command()
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
@click.option("--fast", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def compare(file_a, file_b, fast, as_json):
    """Compare two files — before vs after.

    \b
    Examples:
      sloplens compare before.md after.md
      sloplens compare v1.txt v2.txt
    """
    backend  = get_backend()
    text_a   = Path(file_a).read_text(errors="ignore")
    text_b   = Path(file_b).read_text(errors="ignore")

    with Progress(SpinnerColumn(), TextColumn("[dim]Comparing..."), transient=True) as p:
        p.add_task("scan")
        result = make_request("scan/compare", {"text_a": text_a[:8000], "text_b": text_b[:8000]}, backend, fast)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    ra, rb = result["before"], result["after"]
    imp    = result.get("improvement", 0)
    saved  = result.get("time_saved", 0)
    gained = result.get("signal_gained", 0)
    color  = "green" if imp > 0 else "red"
    sign   = "-" if imp > 0 else "+"

    console.print()
    # Side-by-side summary
    t = Table(box=box.ROUNDED, border_style="dim", title="Compare Results")
    t.add_column("",         style="dim", width=22)
    t.add_column(f"Before ({Path(file_a).name})", justify="center")
    t.add_column(f"After ({Path(file_b).name})",  justify="center")
    t.add_column("Change",   justify="center")

    ca, cb = score_color(ra["overall_slop_score"]), score_color(rb["overall_slop_score"])

    t.add_row("Slop score",
              f"[{ca}]{ra['overall_slop_score']}[/{ca}]",
              f"[{cb}]{rb['overall_slop_score']}[/{cb}]",
              f"[{color}]{sign}{abs(imp)}[/{color}]")

    if ra.get("reading_time_min") is not None:
        t.add_row("Reading time",
                  f"{ra['reading_time_min']}min",
                  f"{rb['reading_time_min']}min",
                  f"[{color}]{'-' if saved>0 else '+'}{abs(saved)}min[/{color}]" if saved else "—")
        t.add_row("Fluff %",
                  f"[{ca}]{ra['fluff_percent']}%[/{ca}]",
                  f"[{cb}]{rb['fluff_percent']}%[/{cb}]",
                  "")

    t.add_row("Verdict",
              f"[dim italic]{ra.get('verdict','')[:40]}[/dim italic]",
              f"[dim italic]{rb.get('verdict','')[:40]}[/dim italic]",
              "")
    console.print(t)

    if imp > 0:
        console.print(f"\n  [green]✓ Slop cut by {imp} pts"
                      + (f" · {saved}min saved" if saved > 0 else "")
                      + (f" · +{gained}min signal" if gained > 0 else "")
                      + "[/green]")
    else:
        console.print(f"\n  [red]✗ Slop increased by {abs(imp)} pts[/red]")

    if rb.get("fix"):
        console.print(Panel(rb["fix"], title="[bold green]Still needs[/bold green]",
                            border_style="green", padding=(0,2)))
    console.print()


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--fast", is_flag=True, default=True)
@click.option("--threshold", "-t", type=int, default=None, help="Exit 1 if any file exceeds threshold")
@click.option("--json", "as_json", is_flag=True)
def batch(files, fast, threshold, as_json):
    """Scan multiple files and rank by slop score.

    \b
    Examples:
      sloplens batch *.md
      sloplens batch docs/*.txt --threshold 70
    """
    backend = get_backend()
    results = []

    with Progress(SpinnerColumn(), TextColumn("[dim]Scanning {task.description}"), transient=True) as p:
        task = p.add_task("files", total=len(files))
        for f in files:
            p.update(task, description=f)
            content = Path(f).read_text(errors="ignore")
            if len(content.strip()) < 20:
                results.append({"file": f, "error": "Too short"})
            else:
                r = make_request("scan/heuristic", {"text": content[:8000]}, backend, fast)
                results.append({**r, "file": f})
            p.advance(task)

    # Sort by slop score descending
    results.sort(key=lambda x: x.get("overall_slop_score", 0), reverse=True)

    if as_json:
        click.echo(json.dumps(results, indent=2))
        return

    t = Table(title="Batch Scan Results", box=box.ROUNDED, border_style="dim")
    t.add_column("Rank",      width=5,  justify="right")
    t.add_column("File",      style="dim")
    t.add_column("Slop",      width=6,  justify="center")
    t.add_column("Bar",       width=20)
    t.add_column("Fluff%",    width=8,  justify="center")
    t.add_column("Read",      width=8,  justify="center")
    t.add_column("Status",    width=12)

    failed = False
    for i, r in enumerate(results, 1):
        if "error" in r:
            t.add_row(str(i), r["file"], "—", "", "—", "—", "[dim]skip[/dim]")
            continue
        sc = r.get("overall_slop_score", 0)
        c  = score_color(sc)
        over = threshold is not None and sc > threshold
        if over: failed = True
        t.add_row(
            str(i),
            Path(r["file"]).name,
            f"[{c}]{sc}[/{c}]",
            score_bar(sc, 20),
            f"[{c}]{r.get('fluff_percent','?')}%[/{c}]",
            f"{r.get('reading_time_min','?')}min",
            f"[red]FAIL >{threshold}[/red]" if over else "[green]PASS[/green]" if threshold else "",
        )

    console.print()
    console.print(t)

    if threshold and failed:
        console.print(f"\n[red]FAIL — one or more files exceed threshold {threshold}[/red]")
        sys.exit(1)
    console.print()



@cli.command()
@click.argument("text", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="File to condense")
@click.option("--output", "-o", type=click.Path(), help="Write condensed text to file")
@click.option("--json", "as_json", is_flag=True)
def condense(text, file, output, as_json):
    """Remove fluff — rewrite text removing all slop.

    \b
    Examples:
      sloplens condense --file bloated.md
      sloplens condense --file bloated.md --output clean.md
      cat README.md | sloplens condense
    """
    backend = get_backend()

    if file:
        content_text = Path(file).read_text(errors="ignore")
    elif text:
        content_text = text
    elif not sys.stdin.isatty():
        content_text = sys.stdin.read()
    else:
        console.print("[red]Provide text, --file, or pipe input[/red]")
        sys.exit(1)

    with Progress(SpinnerColumn(), TextColumn("[dim]Condensing..."), transient=True) as p:
        p.add_task("condense")
        result = make_request("scan/condense", {"text": content_text[:5000]}, backend)

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    console.print()
    console.print(Panel(
        result["condensed"],
        title="[bold green]Condensed[/bold green]",
        border_style="green", padding=(1, 2),
    ))
    console.print(
        f"  [green]Words:[/green] {result['words_before']} → {result['words_after']} "
        f"([green]-{result['words_cut']} ({result['percent_cut']}% cut)[/green])  "
        f"[green]-{result['time_saved']}min read time[/green]  "
        f"Slop: {result['slop_before']} → [green]{result['slop_after']}[/green]"
    )
    console.print()

    if output:
        Path(output).write_text(result["condensed"])
        console.print(f"[dim]Written to {output}[/dim]")


@cli.command()
@click.option("--backend", help="Set backend URL (e.g. https://your-api.railway.app)")
@click.option("--show",    is_flag=True, help="Show current config")
@click.option("--reset",   is_flag=True, help="Reset config to defaults")
def config(backend, show, reset):
    """Configure SlopLens CLI settings.

    \b
    Examples:
      sloplens config --backend https://your-api.railway.app
      sloplens config --show
    """
    if reset:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        console.print("[green]Config reset[/green]")
        return

    if show:
        cfg = load_config()
        console.print(Panel(
            json.dumps(cfg or {"backend": DEFAULT_BACKEND + " (default)"}, indent=2),
            title="Current Config",
            border_style="dim"
        ))
        return

    if backend:
        cfg = load_config()
        cfg["backend"] = backend.rstrip("/")
        save_config(cfg)
        console.print(f"[green]Backend set to:[/green] {cfg['backend']}")

        # Quick health check
        try:
            r = httpx.get(f"{cfg['backend']}/health", timeout=5)
            d = r.json()
            console.print(f"[green]✓ Backend online[/green] — {d.get('service','?')} v{d.get('version','?')}")
        except Exception:
            console.print("[yellow]⚠ Could not reach backend — check the URL[/yellow]")



@cli.command()
@click.option("--threshold", "-t", default=70, help="Slop threshold for pre-commit hook")
@click.option("--no-action", is_flag=True, help="Skip GitHub Action setup")
def init(threshold, no_action):
    """Set up SlopLens in the current repo (pre-commit + GitHub Action).

    \b
    Run from your repo root:
      sloplens init
      sloplens init --threshold 60
    """
    import shutil, stat

    cwd = Path.cwd()

    # Check git repo
    if not (cwd / ".git").exists():
        console.print("[red]Not a git repo. Run from repo root.[/red]")
        sys.exit(1)

    console.print(f"\n[bold]SlopLens init[/bold] in [dim]{cwd}[/dim]\n")

    # 1. Pre-commit hook
    hook_src = Path(__file__).parent / "pre-commit-hook" / "sloplens-check.py"
    hook_dst = cwd / ".git" / "hooks" / "pre-commit"

    if hook_src.exists():
        shutil.copy(hook_src, hook_dst)
        hook_dst.chmod(hook_dst.stat().st_mode | stat.S_IEXEC)
        console.print(f"  [green]✓ Pre-commit hook installed[/green] — threshold: {threshold}")
        console.print(f"  [dim]  Set env: SLOPLENS_THRESHOLD={threshold}[/dim]")
    else:
        console.print(f"  [yellow]⚠ Pre-commit hook source not found[/yellow]")

    # 2. GitHub Action
    if not no_action:
        action_dir = cwd / ".github" / "workflows"
        action_dir.mkdir(parents=True, exist_ok=True)
        action_dst = action_dir / "slop-gate.yml"

        if not action_dst.exists():
            action_src = Path(__file__).parent / ".github" / "workflows" / "slop-gate.yml"
            if action_src.exists():
                shutil.copy(action_src, action_dst)
                console.print(f"  [green]✓ GitHub Action installed[/green] → .github/workflows/slop-gate.yml")
            else:
                console.print(f"  [yellow]⚠ slop-gate.yml source not found[/yellow]")
        else:
            console.print(f"  [dim]  GitHub Action already exists — skipped[/dim]")

    console.print()
    console.print("[green]Done.[/green] SlopLens will now check staged markdown files before each commit.")
    console.print(f"[dim]Override threshold: SLOPLENS_THRESHOLD={threshold} git commit ...[/dim]\n")


@cli.command()
def doctor():
    """Check if SlopLens is properly configured."""
    backend = get_backend()
    console.print(f"\n[bold]SlopLens Doctor[/bold]\n")
    console.print(f"  Backend: [dim]{backend}[/dim]")

    # Check backend
    try:
        r = httpx.get(f"{backend}/health", timeout=5)
        d = r.json()
        console.print(f"  [green]✓ Backend online[/green] — {d.get('service')} v{d.get('version')} · {d.get('layers',0)} layers · {d.get('cache_entries',0)} cached")
    except Exception as e:
        console.print(f"  [red]✗ Backend offline:[/red] {e}")
        console.print(f"  [dim]Start: cd backend && uvicorn main:app --reload[/dim]")

    # Check GROQ key (local only)
    if os.getenv("GROQ_API_KEY"):
        console.print(f"  [green]✓ GROQ_API_KEY set[/green]")
    else:
        console.print(f"  [yellow]⚠ GROQ_API_KEY not in env (needed by backend, not CLI)[/yellow]")

    console.print()


if __name__ == "__main__":
    cli()
