# SlopLens Pre-commit Hook

Blocks commits with sloppy documentation.

## Quick install (2 commands)

```bash
cp pre-commit-hook/sloplens-check.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Configure threshold

```bash
# Default: fail if slop score > 70
SLOPLENS_THRESHOLD=60 git commit -m "..."

# Or export permanently
export SLOPLENS_THRESHOLD=65
```

## What it checks

Staged `.md`, `.txt`, `.rst` files only. Pure Python, no dependencies, no API key.

## Output

```
🔍 SlopLens pre-commit check
   82 ±8  README.md  [moving forward, cutting-edge]
   34 ±12 CHANGELOG.md

✗ BLOCKED — 1 file(s) exceed slop threshold (70)
  README.md: score 82
    Remove: moving forward, cutting-edge
```
