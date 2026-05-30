# SlopLens v4

> **Not "is this AI?" — how much of this is actually worth reading?**

SlopLens is a three-layer hybrid slop detection engine that scores any text for information density, filler, and naturalness. It ships as a web application, Chrome extension, REST API, and CLI — all free to run using Groq's free tier.

[![CI](https://github.com/broforce6909-cmd/sloplens/actions/workflows/ci.yml/badge.svg)](https://github.com/broforce6909-cmd/sloplens/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-34%20passing-green)](tests/)
[![F1 Score](https://img.shields.io/badge/F1-0.897-blue)](dataset/benchmark_results.json)

**SLOP SCAN 2026 — UX Track (primary) + Detection Track + Track A + CI/CD Bonus**

---

## Live Demo

**[sloplens.onrender.com](https://sloplens.onrender.com)** — no setup needed. Open and scan.

> First load may take 30 seconds — free tier cold start.

---

## Table of Contents

- [What is Slop?](#what-is-slop)
- [The Insight](#the-insight)
- [Features](#features)
- [Architecture](#architecture)
- [Benchmark](#benchmark)
- [Quick Start](#quick-start)
- [All Pages](#all-pages)
- [Chrome Extension](#chrome-extension)
- [CLI](#cli)
- [Pre-commit Hook](#pre-commit-hook)
- [GitHub Actions](#github-actions)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Cost](#cost)
- [Limitations](#limitations)
- [Tests](#tests)

---

## What is Slop?

Slop is low-quality, low-information writing that takes a long time to read but delivers almost nothing:

- PR descriptions that restate the diff in prose
- Blog posts that spend 800 words saying what fits in a sentence
- READMEs full of buzzwords with zero specifics
- Commit messages like "fix things" or "update files"

SlopLens asks not **"is this AI?"** but **"did a human actually think, or did they just fill space?"**

---

## The Insight

Most text quality tools either count words or call an LLM. Both approaches have problems:

- **Word count** tells you nothing about information density
- **LLM-only detection** is opaque, expensive, non-reproducible

SlopLens uses three independent layers:

1. **Heuristic layer** — 37 filler phrases, vocabulary diversity (TTR), sentence variance, passive voice, hedge words. Instant. Free. Deterministic.
2. **Semantic layer** — TF-IDF cosine similarity to 61-sentence slop/clean corpus centroids (sklearn). No model download needed.
3. **LLM layer** — Groq llama-3.3-70b scores specificity, naturalness, slop category. Generates roast + fix. MD5 cached.

Scores fused with confidence gating — stronger heuristic signal = narrower confidence interval.

---

## Features

### Web Analyzer
- Paste any text — works instantly in browser without backend
- Full 3-layer LLM scoring when backend connected
- Skeleton loader, animated score ring, confidence interval (`73 ± 6`)
- Reading time vs signal time: "5.2min read → 1.1min useful · 79% fluff"
- Phrase highlighting, roast, slop category, verdict, fix
- Remove fluff — LLM rewrites text removing all slop
- Copy share card to clipboard

### Compare Mode
- Before vs after, side by side
- Parallel async scoring
- Delta score, time saved, signal gained

### Repo Scanner
- Any public GitHub repo — `owner/repo` or full URL
- README + last 20 PRs + last 30 commits scanned in parallel
- Per-section scores + distribution (clean/medium/slop) + worst PR quoted
- No token needed (60 req/hr); add token for 5000 req/hr

### URL Ranker
- Paste up to 5 URLs
- Fetches, extracts text, ranks by slop score
- Quick-fill: Tech blogs / Docs sites / News sites

### Badge & Leaderboard
- Live SVG badge for README embed:
```markdown
[![SlopLens](https://sloplens.onrender.com/badge/owner/repo.svg)](https://sloplens.onrender.com)
```
- Top 20 sloppiest repos scanned (in-memory, updates on every scan)

### Chrome Extension
- Badge on every webpage automatically
- Score panel: reading time, roast, flagged phrases, fix
- Heatmap overlay: green/yellow/red on page elements
- Auto-scan toggle — every page scored on load
- Backend URL auto-detected — no manual config

### CLI (8 commands)
- `scan` — text, file, URL, pipe, CI threshold mode
- `repo` — GitHub repo scanner
- `compare` — before/after files
- `condense` — rewrite removing slop
- `batch` — rank multiple files
- `init` — install pre-commit hook + GitHub Action in one command
- `config` — set/show backend URL
- `doctor` — health check

### Pre-commit Hook
- Pure Python, zero dependencies, no API key
- Checks staged `.md`/`.txt`/`.rst` before every commit
- Blocks if slop score exceeds threshold (default: 70)
- Configurable: `SLOPLENS_THRESHOLD=65 git commit -m "..."`

### GitHub Actions
- `ci.yml` — 34 tests on every push
- `slop-gate.yml` — slop-gates PRs + all markdown files

---

## Architecture

```
Browser / CLI / Extension
          |
          v  POST /scan
  ┌─────────────────────────────┐
  │      FastAPI Backend         │
  │                              │
  │  Layer 1: Heuristic          │  ← instant, free, deterministic
  │  ├── 37 filler phrases       │
  │  ├── TTR-200 (vocabulary)    │
  │  ├── Sentence CV score       │
  │  ├── Passive voice regex     │
  │  └── Hedge word frequency    │
  │                              │
  │  Layer 2: Semantic (TF-IDF)  │  ← 61-sentence corpus
  │  ├── Slop corpus centroid    │
  │  └── Clean corpus centroid   │
  │                              │
  │  Layer 3: Groq LLM           │  ← free tier, llama-3.3-70b
  │  ├── Specificity scoring     │
  │  ├── 6-category classify     │
  │  ├── Roast + fix generation  │
  │  └── MD5 response cache      │
  │                              │
  │  Confidence-gated fusion     │
  │  → Score 0-100 ± CI         │
  └─────────────────────────────┘
```

**Fusion formula:**
```
hw = min(0.35, heuristic_confidence / 100 × 0.35)
sw = 0.20
lw = 1 - hw - sw

blended_slop = l.slop × 0.75 + sem.score × 0.25
confidence_interval = max(3, 15 - h.confidence // 10)
```

---

## Benchmark

**60 manually labeled texts — 30 slop + 30 clean**

| Metric | Score |
|---|---|
| **F1** | **0.897** |
| Precision | 0.929 |
| Recall | 0.867 |
| Accuracy | 0.900 |
| Threshold | 20 |

Method: heuristic + TF-IDF layers (deterministic). LLM excluded — non-deterministic.

Full dataset: `dataset/labeled_dataset.jsonl` · Results: `dataset/benchmark_results.json` · Limitations: `dataset/limitations.md`

---

## Quick Start

### Run locally

```bash
git clone https://github.com/broforce6909-cmd/sloplens
cd sloplens

python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate     # Mac/Linux

pip install -r backend/requirements.txt
cp .env.example .env
# Add GROQ_API_KEY=gsk_... (free from console.groq.com)

python run.py
```

Open **http://localhost:8000** — backend bar auto-connects.

### Get free Groq API key

1. Go to https://console.groq.com
2. Sign up (no credit card)
3. Create API key → add to `.env`

### Optional: GitHub token

```bash
# Increases repo scanner from 60 → 5000 req/hr
GITHUB_TOKEN=ghp_...
```

---

## All Pages

| Page | Live URL | Local URL |
|---|---|---|
| Home | https://sloplens.onrender.com | http://localhost:8000 |
| Analyzer | https://sloplens.onrender.com/pages/analyzer.html | http://localhost:8000/pages/analyzer.html |
| Compare | https://sloplens.onrender.com/pages/compare.html | http://localhost:8000/pages/compare.html |
| Repo Scanner | https://sloplens.onrender.com/pages/repo.html | http://localhost:8000/pages/repo.html |
| URL Ranker | https://sloplens.onrender.com/pages/urls.html | http://localhost:8000/pages/urls.html |
| Badge | https://sloplens.onrender.com/pages/badge.html | http://localhost:8000/pages/badge.html |
| Extension Guide | https://sloplens.onrender.com/pages/extension.html | http://localhost:8000/pages/extension.html |
| CLI Guide | https://sloplens.onrender.com/pages/cli.html | http://localhost:8000/pages/cli.html |
| API Reference | https://sloplens.onrender.com/pages/api.html | http://localhost:8000/pages/api.html |
| Swagger UI | https://sloplens.onrender.com/docs | http://localhost:8000/docs |

Backend URL auto-detected on every page — no manual config needed.

---

## Chrome Extension

### Install (3 steps)

1. Download ZIP from GitHub:
```
https://github.com/broforce6909-cmd/sloplens/archive/refs/heads/main.zip
```

2. Extract → `chrome://extensions` → Developer Mode ON → Load unpacked → select `sloplens-main/extension/`

3. Done — badge appears on every page. Backend URL pre-configured to `https://sloplens.onrender.com`.

### Usage

- **Badge** → click → scan page
- **Panel** → score, reading time, roast, fix
- **Show Heatmap** → green/yellow/red on page elements
- **Auto-scan** → extension icon → toggle ON

---

## CLI

```bash
pip install -e .

sloplens scan "your text here"
sloplens scan --file README.md
sloplens scan --file README.md --threshold 60    # CI mode
sloplens scan --url https://example.com/blog
sloplens repo microsoft/vscode
sloplens compare before.md after.md
sloplens condense --file bloated.md --output clean.md
sloplens batch docs/*.md --threshold 70
sloplens config --backend https://sloplens.onrender.com
sloplens doctor

cat README.md | sloplens scan                   # pipe
```

---

## Pre-commit Hook

```bash
# Install via CLI
sloplens init

# Or manually
cp pre-commit-hook/sloplens-check.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Output on blocked commit:
```
🔍 SlopLens pre-commit check
   82 ±6  README.md  [going ahead, advanced]

✗ BLOCKED — score 82 exceeds threshold 70
    Remove: going ahead, advanced
```

---

## GitHub Actions

**`ci.yml`** — every push:
- 34 unit tests, no API key needed

**`slop-gate.yml`** — every PR:
- Scans all `.md` files for filler phrases
- Checks PR title and description

---

## API Reference

Base URL: `https://sloplens.onrender.com`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/scan` | 3-layer hybrid scan |
| POST | `/scan/compare` | Compare two texts |
| POST | `/scan/repo` | GitHub repo scanner |
| POST | `/scan/condense` | Rewrite removing slop |
| POST | `/scan/urls` | Rank up to 5 URLs |
| POST | `/scan/heuristic` | Heuristic + TF-IDF only (free, instant) |
| POST | `/scan/batch` | Batch up to 10 texts |
| GET | `/badge/{owner}/{repo}.svg` | Live SVG badge |
| GET | `/leaderboard` | Top 20 sloppiest repos |
| GET | `/health` | Status check |

Interactive docs: **https://sloplens.onrender.com/docs**

---

## Project Structure

```
sloplens/
├── run.py                      ← python run.py → everything starts
├── cli.py                      ← CLI (8 commands)
├── setup.py                    ← pip install -e .
├── .env.example                ← GROQ_API_KEY + GITHUB_TOKEN
├── .gitignore
├── LICENSE                     ← MIT
├── DEMO.md                     ← 7-minute video demo script
├── SUBMISSION.md               ← Hackathon submission description
├── docker-compose.yml
│
├── frontend/
│   ├── index.html              ← Landing page
│   ├── css/style.css           ← Shared dark theme
│   ├── js/common.js            ← Shared JS + auto-detect backend
│   └── pages/
│       ├── analyzer.html       ← Text scanner
│       ├── compare.html        ← Before/after
│       ├── repo.html           ← GitHub repo scanner
│       ├── urls.html           ← URL ranker
│       ├── badge.html          ← Badge + leaderboard
│       ├── extension.html      ← Extension install guide
│       ├── cli.html            ← CLI reference
│       └── api.html            ← API docs
│
├── backend/
│   ├── main.py                 ← FastAPI (frontend + API + serving)
│   ├── requirements.txt
│   └── Dockerfile
│
├── extension/                  ← Chrome Extension MV3
│   ├── config.js               ← Backend URL (pre-set to Render)
│   ├── content.js              ← Badge + heatmap + panel
│   ├── manifest.json
│   ├── background.js
│   ├── icons/
│   └── popup/
│
├── tests/
│   └── test_main.py            ← 34 tests, no API key needed
│
├── dataset/
│   ├── labeled_dataset.jsonl   ← 60 labeled texts
│   ├── benchmark_results.json  ← F1=0.897
│   ├── dataset_statistics.json
│   └── limitations.md
│
├── pre-commit-hook/
│   └── sloplens-check.py       ← Zero deps, pure Python
│
└── .github/workflows/
    ├── ci.yml                  ← Tests on every push
    └── slop-gate.yml           ← Slop-gates PRs
```

---

## Deployment

### Render (live)

```
https://sloplens.onrender.com
```

### Local

```bash
python run.py
# http://localhost:8000
```

### Docker

```bash
cp .env.example .env
docker-compose up
```

---

## Cost

| Service | Cost | Limit |
|---|---|---|
| Groq API | Free forever | 30 req/min |
| GitHub API (no token) | Free | 60 req/hr |
| GitHub API (with token) | Free | 5000 req/hr |
| Render | Free tier | 750 hr/month |

**Total: Zero.**

---

## Limitations

- **Short texts (<30 words):** heuristic signals unreliable
- **Non-English:** dictionary and corpus English-only
- **Technical jargon:** may score as slop
- **Satire:** intentional buzzwords score high correctly
- **LLM non-determinism:** use `/scan/heuristic` for reproducible results

Full details: `dataset/limitations.md`

---

## Tests

```bash
pytest tests/ -v
# 34 passed
```

No API key needed. Covers heuristic, semantic, reading time, fusion, repo parser, CLI, confidence interval, pre-commit hook.

---

## Why SlopLens

1. **Works without any API key** — JS heuristic in browser, instant
2. **Three independent layers** — each catches different patterns
3. **Lives in the browser** — extension scores every page automatically
4. **Fixes slop** — `/scan/condense` rewrites with LLM
5. **Covers 4 tracks** — UX, Detection, Track A, CI/CD
6. **Free** — Groq free tier, Render free tier, no credit card

---

## License

MIT — see [LICENSE](LICENSE)