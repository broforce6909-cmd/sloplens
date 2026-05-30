#!/usr/bin/env python3
"""
SlopLens pre-commit hook
Checks staged markdown/text files for slop before commit.

Install:
  cp pre-commit-hook/sloplens-check.py .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit

Or with pre-commit framework:
  # .pre-commit-config.yaml
  repos:
  - repo: local
    hooks:
    - id: sloplens
      name: SlopLens slop check
      entry: python pre-commit-hook/sloplens-check.py
      language: python
      types: [markdown, text]
      additional_dependencies: []
"""
import sys, os, re, subprocess, math

# ── Config (edit these) ────────────────────────────────────────────────────────
THRESHOLD     = int(os.getenv("SLOPLENS_THRESHOLD", "70"))   # fail if score > this
EXTENSIONS    = {".md", ".txt", ".rst"}                       # file types to check
CHECK_COMMITS = os.getenv("SLOPLENS_CHECK_COMMITS", "1") == "1"

# ── Heuristic scorer (no API, no deps) ────────────────────────────────────────
FILLERS = [
    "it goes without saying","in today's world","at the end of the day",
    "moving forward","think outside the box","circle back","best-in-class",
    "cutting-edge","revolutionize","game-changer","paradigm shift","in conclusion",
    "it is important to note","needless to say","going forward","low-hanging fruit",
    "move the needle","value-add","deep dive","scalable solution","when all is said",
    "the fact of the matter","for all intents","first and foremost","last but not least",
    "without further ado","long story short","at this point in time",
]
HEDGES   = ["basically","literally","honestly","actually","essentially",
            "generally","somewhat","rather","fairly","quite","perhaps",
            "maybe","possibly","arguably","seemingly"]
PASSIVE  = re.compile(r'\b(is|are|was|were|been|be|being)\s+\w+ed\b', re.I)


def score(text: str) -> tuple[int, list, int]:
    """Returns (slop_score 0-100, flagged_phrases, confidence)."""
    if not text.strip():
        return 0, [], 0
    lower = text.lower()
    words = re.findall(r'\b\w+\b', lower)
    sents = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 8]
    n     = max(len(sents), 1)

    hits  = [p for p in FILLERS if p in lower]
    hedgn = sum(1 for h in HEDGES if re.search(rf'\b{h}\b', lower))
    filler_ratio = min(100, int((len(hits)*14 + hedgn*5) / n * 8))

    window = words[:200]
    ttr    = len(set(window)) / len(window) if window else 0.5
    density = min(100, int(ttr * 125))

    natural = 50
    if len(sents) >= 3:
        lens   = [len(s.split()) for s in sents]
        mean   = sum(lens) / len(lens)
        std    = math.sqrt(sum((l-mean)**2 for l in lens) / len(lens))
        cv     = std / mean if mean > 0 else 0
        natural = min(100, int(cv * 190))

    passive = len(PASSIVE.findall(text))
    pd      = min(100, int(passive / n * 60))
    sp      = int(sum(1 for s in sents if len(s.split()) < 6) / n * 35)

    fr  = min(100, filler_ratio + sp)
    nat = max(0, natural - sp//2)
    slop = int(fr*0.40 + (100-density)*0.30 + (100-nat)*0.20 + pd*0.10)
    conf = min(100, len(hits)*20 + hedgn*8 + passive*10 + 15)

    return min(100, slop), hits[:3], conf


def get_staged_files() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return [f for f in out.splitlines() if f]
    except Exception:
        return []


def get_staged_content(filepath: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f":{filepath}"],
            stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
    except Exception:
        return ""


def color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    codes = {"red": "\033[31m", "yellow": "\033[33m", "green": "\033[32m",
             "bold": "\033[1m", "dim": "\033[2m", "reset": "\033[0m"}
    return codes.get(code, "") + text + codes["reset"]


def main():
    files   = get_staged_files()
    checked = [f for f in files if os.path.splitext(f)[1].lower() in EXTENSIONS]

    if not checked:
        sys.exit(0)

    print(color("\n🔍 SlopLens pre-commit check", "bold"))
    failures = []

    for filepath in checked:
        content = get_staged_content(filepath)
        if len(content.strip()) < 30:
            continue

        s, hits, conf = score(content)
        c = "red" if s >= 65 else "yellow" if s >= 35 else "green"
        status = color(f"{s:3d}", c)
        conf_str = color(f"±{max(5, 15 - conf//10)}", "dim")

        print(f"  {status} {conf_str}  {filepath}", end="")
        if hits:
            print(color(f"  [{', '.join(hits[:2])}]", "dim"), end="")
        print()

        if s > THRESHOLD:
            failures.append((filepath, s, hits))

    if failures:
        print(color(f"\n✗ BLOCKED — {len(failures)} file(s) exceed slop threshold ({THRESHOLD})", "red"))
        for f, s, hits in failures:
            print(color(f"  {f}: score {s}", "red"))
            if hits:
                print(color(f"    Remove: {', '.join(hits)}", "dim"))
        print(color("\nFix slop or raise threshold: SLOPLENS_THRESHOLD=80 git commit ...", "dim"))
        print()
        sys.exit(1)

    print(color(f"\n✓ All {len(checked)} file(s) within threshold ({THRESHOLD})\n", "green"))
    sys.exit(0)


if __name__ == "__main__":
    main()
