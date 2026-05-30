# SlopLens v4

> **Not "is this AI?" — how much of this is actually worth reading?**

SlopLens is a three-layer hybrid slop detection engine that scores any text for information density, filler, and naturalness. It ships as a web application, Chrome extension, REST API, and CLI — all free to run using Groq's free tier.

[![CI](https://github.com/your-org/sloplens/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/sloplens/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-34%20passing-green)](tests/)
[![F1 Score](https://img.shields.io/badge/F1-0.897-blue)](dataset/benchmark_results.json)

**SLOP SCAN 2026 — UX Track (primary) + Detection Track + Track A + CI/CD Bonus**

---

## Table of Contents

- [What is Slop?](#what-is-slop)
- [The Insight](#the-insight)
- [Live Demo](#live-demo)
- [Features](#features)
- [Architecture](#architecture)
- [Benchmark](#benchmark)
- [Quick Start](#quick-start)
- [Web UI — All Pages](#web-ui--all-pages)
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
- [License](#license)

---

## What is Slop?

Slop is low-quality, low-information writing that takes a long time to read but delivers almost nothing. It shows up everywhere:

- PR descriptions that restate the diff in prose
- Blog posts that spend 800 words saying what fits in a sentence
- READMEs built entirely from buzzwords
- Documentation that uses jargon instead of examples
- Commit messages like "fix things" or "update files"

Slop is not the same as AI-generated content. Humans write slop too. The question SlopLens asks is not **"is this AI?"** but **"did a human actually think, or did they just fill space?"**

---

## The Insight

Most text quality tools either count words or call an LLM and ask it to rate the text. Both approaches have problems:

- **Word count** tells you nothing about information density
- **LLM-only detection** is opaque, expensive, and non-reproducible

SlopLens uses three independent layers that each catch different slop patterns:

1. **Heuristic layer** — 37 known filler phrases, vocabulary diversity, sentence length variance, passive voice density, hedge word frequency. Instant. Free. Deterministic.

2. **Semantic layer** — cosine similarity to pre-computed slop/clean corpus centroids using sentence-transformers `all-MiniLM-L6-v2`. Real embeddings. No model download at runtime (cached at Docker build time).

3. **LLM layer** — Groq llama-3.3-70b-versatile scores specificity, naturalness, and slop category. Generates a roast and a targeted fix. MD5 cached to avoid duplicate API calls.

The three scores are fused with confidence gating: the stronger the heuristic signal, the narrower the confidence interval on the final score.

---

## Live Demo

```bash
git clone https://github.com/you/sloplens
cd sloplens
cp .env.example .env        # add GROQ_API_KEY
pip install -r backend/requirements.txt
python run.py
```

Open **http://localhost:8000** — everything runs from one command.

---

## Features

### Web Analyzer
- Paste any text — PR description, blog post, commit message, README, documentation
- Heuristic mode works instantly in browser with zero backend or API key
- Full 3-layer LLM scoring when backend is connected
- **Skeleton loader** — animated placeholder while scoring
- **Score ring** — animates from 0 to final score
- **Reading time vs signal time** — "5.2min read → 1.1min useful · 79% fluff"
- **Confidence interval** — score shown as `73 ± 6`
- **Phrase highlighting** — flagged phrases highlighted amber directly in the text
- **Roast** — one devastating sentence summarising what is wrong
- **Slop category** — classified into one of 6 types
- **Verdict** — one sentence assessment
- **Suggested fix** — one specific actionable improvement
- **Remove fluff** — rewrites the text removing all slop via LLM
- **Copy share card** — copies a formatted score card to clipboard

### Compare Mode
- Paste two versions of the same text side by side
- Scores both in parallel (async)
- Shows delta score, time saved, and signal gained
- Roast shown for the "before" version
- "Still needs" fix shown for the "after" version

### Repo Scanner
- Paste any public GitHub repo URL (`owner/repo` or full URL)
- Scans three sections in parallel:
  - **README** — strips code blocks and links, scores prose quality
  - **Last 20 PR descriptions** — per-PR scores, distribution (clean/medium/slop), worst PR quoted verbatim
  - **Last 30 commit messages** — aggregated score, worst message flagged
- Returns overall repo slop score (README 40% + PRs 40% + commits 20%)
- Shows cleanest vs sloppiest section
- Works without GitHub token (60 req/hr free); add token for 5000 req/hr

### URL Ranker
- Paste up to 5 URLs (one per line)
- Backend fetches, extracts readable text (BeautifulSoup), scores each
- Returns ranked table: slop score, fluff%, read time, slop category
- Quick-fill buttons: Tech blogs, Docs sites, News sites

### Badge & Leaderboard
- After scanning a repo, embed a live SVG badge in your README:
```markdown
[![SlopLens](https://your-api.railway.app/badge/owner/repo.svg)](https://sloplens.dev)
```
- Badge auto-updates on every `/scan/repo` call
- Leaderboard: top 20 sloppiest repos scanned (in-memory, no database needed)

### Chrome Extension
- Badge appears automatically on every webpage
- Click badge → detail panel with score, reading time, roast, fix
- **Show Heatmap** — applies green/yellow/red background colors to page elements:
  - 🟢 Green = useful, high information density
  - 🟡 Yellow = filler, hedging language
  - 🔴 Red = likely slop, filler phrases detected
- Auto-scan toggle — scores every page on load automatically
- Configurable backend URL saved to localStorage

### CLI
- 8 commands with rich terminal output (colors, bars, panels)
- Pipe support: `cat README.md | sloplens scan`
- CI mode: `sloplens scan --file docs/PR_TEMPLATE.md --threshold 60`
- Full repo scanning: `sloplens repo torvalds/linux`
- Before/after comparison: `sloplens compare before.md after.md`
- Rewrite: `sloplens condense --file bloated.md --output clean.md`
- One-command setup: `sloplens init` installs pre-commit hook + GitHub Action

### Pre-commit Hook
- Pure Python, zero dependencies, no API key required
- Checks staged `.md`, `.txt`, `.rst` files before every commit
- Blocks commit if slop score exceeds threshold (default: 70)
- Shows flagged phrases and specific fix
- Configurable: `SLOPLENS_THRESHOLD=65 git commit -m "..."`

### GitHub Actions
Two workflows included:

**`ci.yml`** — Runs on every push and PR:
- 34 unit tests (no API key needed)
- Ruff linter on backend
- Slop-gates README.md

**`slop-gate.yml`** — Runs on every PR:
- Scans all staged `.md` files for filler phrases
- Checks PR title and description for slop
- Fails CI if slop detected

---

## Architecture

```
Browser / CLI / Extension
          |
          v  POST /scan
  ┌───────────────────────────┐
  │      FastAPI Backend       │
  │                            │
  │  Layer 1: Heuristic        │  ← instant, free, deterministic
  │  ├── 37 filler phrases     │
  │  ├── TTR-200 (vocabulary)  │
  │  ├── Sentence CV score     │
  │  ├── Passive voice regex   │
  │  └── Hedge word frequency  │
  │                            │
  │  Layer 2: Semantic         │  ← all-MiniLM-L6-v2 embeddings
  │  ├── TF-IDF + ST hybrid    │
  │  ├── Slop corpus centroid  │
  │  └── Clean corpus centroid │
  │       (61-sentence corpus) │
  │                            │
  │  Layer 3: Groq LLM         │  ← free tier, llama-3.3-70b
  │  ├── Specificity scoring   │
  │  ├── Naturalness scoring   │
  │  ├── 6-category classify   │
  │  ├── Roast generation      │
  │  ├── Fix generation        │
  │  └── MD5 response cache    │
  │                            │
  │  Confidence-gated fusion   │
  │  → Score 0-100 + CI ± N   │
  └───────────────────────────┘
```

### Scoring formula (fusion)

```
hw = min(0.35, heuristic_confidence / 100 × 0.35)   # heuristic weight
sw = 0.20                                             # semantic weight
lw = 1 - hw - sw                                      # LLM weight

fused_density  = h.density  × hw + (100 - sem.score) × sw + l.density  × lw
fused_filler   = h.filler   × hw + sem.score          × sw + l.filler   × lw
blended_slop   = l.slop × 0.75 + sem.score × 0.25

confidence_interval = max(3, 15 - h.confidence // 10)
```

Higher heuristic confidence (more filler phrases detected) → lower CI range → more trustworthy score.

---

## Benchmark

**Dataset: 60 manually labeled texts (30 slop + 30 clean)**

Categories covered:
- **Slop:** marketing fluff, corporate buzzwords, AI filler, SEO stuffing, vague commits, hedge-heavy writing
- **Clean:** engineering commits, scientific writing, technical documentation, concrete journalism

| Metric | Score |
|--------|-------|
| **F1** | **0.897** |
| Precision | 0.929 |
| Recall | 0.867 |
| Accuracy | 0.900 |
| Optimal threshold | 20 |

Method: heuristic + sentence-transformers layers only (deterministic). LLM layer excluded from benchmark — non-deterministic.

Full dataset: `dataset/labeled_dataset.jsonl`
Results: `dataset/benchmark_results.json`
Limitations: `dataset/limitations.md`

---

## Quick Start

### Requirements
- Python 3.10+
- A free Groq API key (https://console.groq.com — no credit card)

### Installation

```bash
# Clone
git clone https://github.com/you/sloplens
cd sloplens

# Virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r backend/requirements.txt

# Configure
cp .env.example .env
# Open .env and add:
# GROQ_API_KEY=gsk_...
# GITHUB_TOKEN=ghp_...  (optional, for higher GitHub rate limits)

# Run
python run.py
```

Open **http://localhost:8000**

### What `python run.py` does

- Starts FastAPI on port 8000
- Serves the frontend from `frontend/` folder
- Serves all API endpoints under `/scan/...`
- Serves Swagger UI at `/docs`
- No npm, no Node.js, no build step required

---

## Web UI — All Pages

| Page | URL | Requires backend? |
|------|-----|-------------------|
| Home | http://localhost:8000 | No |
| Analyzer | http://localhost:8000/pages/analyzer.html | Optional (heuristic works without) |
| Compare | http://localhost:8000/pages/compare.html | Optional |
| Repo Scanner | http://localhost:8000/pages/repo.html | **Yes** |
| URL Ranker | http://localhost:8000/pages/urls.html | **Yes** |
| Badge | http://localhost:8000/pages/badge.html | Optional |
| API Docs | http://localhost:8000/docs | **Yes** |

**Setting backend URL:**
Every page has a backend bar at the top. Click **"Use localhost"** to connect automatically. The URL is saved to localStorage — only needs to be set once.

---

## Chrome Extension

### Install

1. Open `extension/config.js` and set your backend URL:
```js
const SLOPLENS_BACKEND = "http://localhost:8000";
```

2. Open Chrome → `chrome://extensions`
3. Enable **Developer Mode** (top right toggle)
4. Click **Load unpacked** → select the `extension/` folder
5. SlopLens appears in your extensions

### Usage

- **Any webpage** → SlopLens badge appears bottom-right
- **Click badge** → score + detail panel opens
- **Show Heatmap** → green/yellow/red overlaid on page elements
- **Auto-scan** → click extension icon → toggle "Auto-scan on page load"

### How heatmap works

The heatmap runs entirely client-side with no API call. It uses the JavaScript heuristic scorer to classify each visible element (`p`, `h1-h4`, `li`, `div`, `blockquote`) and applies background colors:
- Green: TTR ≥ 0.65, no filler, no hedging
- Yellow: hedge words present, or TTR < 0.6
- Red: filler phrase detected, or passive voice + low TTR

---

## CLI

### Install

```bash
pip install -e .
```

### Commands

```bash
# Scan text directly
sloplens scan "Moving forward we will leverage synergies"

# Scan a file
sloplens scan --file README.md

# Scan a URL (fetches and extracts text)
sloplens scan --url https://example.com/blog-post

# CI mode — exits with code 1 if slop score > threshold
sloplens scan --file docs/README.md --threshold 60

# Scan a GitHub repo
sloplens repo microsoft/vscode
sloplens repo https://github.com/torvalds/linux

# Compare two files
sloplens compare before.md after.md

# Rewrite removing slop
sloplens condense --file bloated.md
sloplens condense --file bloated.md --output clean.md

# Batch scan multiple files
sloplens batch docs/*.md
sloplens batch *.txt --threshold 70

# Configure backend URL
sloplens config --backend http://localhost:8000
sloplens config --show
sloplens config --reset

# Health check
sloplens doctor

# Pipe support
cat README.md | sloplens scan
git log --format="%s" | sloplens scan --threshold 50

# JSON output (for scripting)
sloplens scan --file README.md --json
sloplens repo owner/repo --json
```

---

## Pre-commit Hook

### Quick install

```bash
# Option 1 — via CLI (recommended)
sloplens init

# Option 2 — manual
cp pre-commit-hook/sloplens-check.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit   # Mac/Linux only
```

### How it works

On every `git commit`, the hook:
1. Finds all staged `.md`, `.txt`, `.rst` files
2. Runs the heuristic scorer (no API call, zero deps)
3. Blocks the commit if any file scores above threshold

```
🔍 SlopLens pre-commit check
   82 ±6  README.md  [moving forward, cutting-edge]
   23 ±12 CHANGELOG.md

✗ BLOCKED — 1 file(s) exceed slop threshold (70)
  README.md: score 82
    Remove: moving forward, cutting-edge

Fix slop or: SLOPLENS_THRESHOLD=80 git commit ...
```

### Configuration

```bash
# Change threshold
export SLOPLENS_THRESHOLD=65   # default: 70

# Per-commit override
SLOPLENS_THRESHOLD=80 git commit -m "your message"

# Disable for one commit
git commit -m "your message" --no-verify
```

---

## GitHub Actions

### CI workflow (`ci.yml`)

Runs on every push to `main`/`dev` and every PR:

```yaml
jobs:
  test:    # 34 unit tests, no API key needed
  lint:    # ruff check on backend/
  slop-gate:  # scans README.md for filler phrases
```

### Slop gate workflow (`slop-gate.yml`)

Runs on every PR:
- Scans all `.md` files in the repo
- Checks PR title and description for filler phrases
- Fails if slop detected — forces authors to write clear PRs

---

## API Reference

Base URL: `http://localhost:8000` (local) or your Railway URL

### POST /scan

Full 3-layer hybrid scan.

**Request:**
```json
{
  "text": "your text here",
  "fast": false
}
```

`fast: true` uses `llama-3.1-8b-instant` instead of `llama-3.3-70b-versatile`.

**Response:**
```json
{
  "overall_slop_score": 78,
  "information_density": 22,
  "filler_ratio": 85,
  "specificity": 18,
  "naturalness": 30,
  "passive_density": 12,
  "semantic_slop_score": 71,
  "slop_similarity": 0.4821,
  "clean_similarity": 0.1923,
  "slop_category": "corporate_buzzwords",
  "verdict": "Pure jargon dressed as strategy.",
  "roast": "This paragraph used 80 words to say absolutely nothing specific.",
  "flagged_phrases": ["moving forward", "best-in-class", "circle back"],
  "fix": "Replace 'moving forward' with the specific action and date.",
  "reading_time_min": 2.1,
  "info_time_min": 0.4,
  "fluff_percent": 79,
  "word_count": 512,
  "confidence_interval": 6,
  "scoring_method": "hybrid_v4_3layer",
  "heuristic_confidence": 88,
  "llm_model": "groq/llama-3.3-70b-versatile"
}
```

### POST /scan/compare

Compare two texts in parallel.

**Request:**
```json
{
  "text_a": "before text",
  "text_b": "after text",
  "fast": false
}
```

**Response:**
```json
{
  "before": { ... full scan result ... },
  "after":  { ... full scan result ... },
  "improvement": 47,
  "time_saved": 1.8,
  "signal_gained": 0.9,
  "summary": "Slop cut by 47 pts · 1.8min saved · 0.9min more signal"
}
```

### POST /scan/repo

Scan a public GitHub repository.

**Request:**
```json
{
  "repo": "microsoft/vscode",
  "fast": true
}
```

**Response:**
```json
{
  "repo": "microsoft/vscode",
  "overall_slop_score": 34,
  "star_count": 165000,
  "description": "Visual Studio Code",
  "sections": [
    {
      "section": "README",
      "slop_score": 28,
      "word_count": 1240,
      "flagged_phrases": []
    },
    {
      "section": "PR Descriptions",
      "slop_score": 41,
      "pr_count": 20,
      "worst_score": 72,
      "worst_sample": "This PR fixes the thing ...",
      "score_distribution": { "clean": 12, "medium": 6, "slop": 2 }
    },
    {
      "section": "Commit Messages",
      "slop_score": 33,
      "commit_count": 30,
      "worst_message": "fix stuff"
    }
  ],
  "cleanest_section": "README",
  "sloppiest_section": "PR Descriptions",
  "verdict": "Generally clean repo with some sloppy PR descriptions."
}
```

### POST /scan/urls

Fetch and rank up to 5 URLs.

**Request:**
```json
{
  "urls": ["https://example.com/blog", "https://docs.example.com"],
  "fast": true
}
```

### POST /scan/condense

Rewrite text removing all slop.

**Request:**
```json
{ "text": "In today's fast-paced world..." }
```

**Response:**
```json
{
  "original": "...",
  "condensed": "...",
  "words_before": 120,
  "words_after": 48,
  "words_cut": 72,
  "percent_cut": 60,
  "slop_before": 81,
  "slop_after": 22,
  "time_saved": 0.3
}
```

### POST /scan/heuristic

Heuristic + semantic layers only. No LLM, no API cost, instant.

### POST /scan/batch

Batch scan up to 10 texts.

**Request:**
```json
{
  "texts": ["text1", "text2", "text3"],
  "fast": true
}
```

### GET /badge/{owner}/{repo}.svg

Returns a live SVG badge. Embed in README:
```markdown
[![SlopLens](https://your-api.railway.app/badge/owner/repo.svg)](https://sloplens.dev)
```

### GET /leaderboard

Returns top 20 sloppiest repos scanned (updates in real time).

### GET /health

```json
{
  "status": "ok",
  "service": "SlopLens API",
  "version": "4.0.0",
  "llm_provider": "groq (free)",
  "layers": 3,
  "cache_entries": 42,
  "github_token": "set (5000 req/hr)",
  "semantic_model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

---

## Project Structure

```
sloplens/
│
├── run.py                        ← One command startup (python run.py)
├── cli.py                        ← CLI — 8 commands
├── setup.py                      ← pip install -e .
├── .env.example                  ← GROQ_API_KEY + GITHUB_TOKEN template
├── .gitignore
├── LICENSE                       ← MIT
├── DEMO.md                       ← 5-minute video demo script
├── SUBMISSION.md                 ← Hackathon submission description
├── railway.json                  ← One-click Railway deploy config
├── docker-compose.yml            ← Docker deployment
│
├── frontend/                     ← Pure HTML/CSS/JS (no framework)
│   ├── index.html                ← Landing page with feature overview
│   ├── css/
│   │   └── style.css             ← Shared dark theme styles
│   ├── js/
│   │   └── common.js             ← Shared JS: scoring, API, helpers
│   └── pages/
│       ├── analyzer.html         ← Text scanner + condense + share card
│       ├── compare.html          ← Before/after comparison
│       ├── repo.html             ← GitHub repo scanner
│       ├── urls.html             ← URL ranker
│       └── badge.html            ← Badge embed + leaderboard
│
├── backend/
│   ├── main.py                   ← FastAPI app (serves frontend + all API)
│   ├── requirements.txt
│   └── Dockerfile
│
├── extension/                    ← Chrome Extension Manifest V3
│   ├── config.js                 ← Set SLOPLENS_BACKEND URL here
│   ├── content.js                ← Page badge + heatmap + detail panel
│   ├── manifest.json             ← Extension config
│   ├── background.js
│   ├── icons/                    ← 16/32/48/128px PNG icons
│   └── popup/
│       ├── popup.html            ← Extension popup with auto-scan toggle
│       └── popup.js
│
├── tests/
│   └── test_main.py              ← 34 tests (no API key needed)
│
├── dataset/
│   ├── labeled_dataset.jsonl     ← 60 labeled texts (30 slop + 30 clean)
│   ├── benchmark_results.json    ← F1=0.897, precision, recall, accuracy
│   ├── dataset_statistics.json   ← Category distribution
│   └── limitations.md            ← Honest failure modes
│
├── pre-commit-hook/
│   ├── sloplens-check.py         ← Pre-commit hook (zero deps, pure Python)
│   ├── .pre-commit-config.yaml   ← pre-commit framework config
│   └── README.md
│
└── .github/
    └── workflows/
        ├── ci.yml                ← Tests + lint + README slop-gate
        └── slop-gate.yml         ← Slop-gates PRs + all markdown files
```

---

## Deployment

### Local (recommended for development)

```bash
python run.py
# http://localhost:8000
```

### Docker

```bash
cp .env.example .env
# Add GROQ_API_KEY
docker-compose up
# http://localhost:8000
```

### Railway (recommended for production)

```bash
npm i -g @railway/cli
railway login
railway up
# Set GROQ_API_KEY and GITHUB_TOKEN in Railway dashboard
# Copy Railway URL → extension/config.js
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | **Yes** | Free from https://console.groq.com |
| `GITHUB_TOKEN` | No | Increases GitHub API from 60 → 5000 req/hr |
| `ALLOWED_ORIGINS` | No | CORS origins (default: `*`) |

---

## Cost

**Zero.** Everything uses free tiers:

| Service | Cost | Limit |
|---------|------|-------|
| Groq API | Free forever | 30 req/min |
| GitHub API (no token) | Free | 60 req/hr |
| GitHub API (with token) | Free | 5000 req/hr |
| Railway deploy | Free tier | 500 hours/month |

---

## Limitations

See `dataset/limitations.md` for full details. Key limitations:

- **Short texts (<30 words):** heuristic signals unreliable
- **Non-English:** filler dictionary and corpus are English-only
- **Technical jargon:** dense domain-specific text may score as slop
- **Satire:** intentional corporate-speak will score high (correctly detecting surface patterns, incorrectly labeling intent)
- **Kernel-style commits:** terse writing (Linus Torvalds style) may score low naturalness due to uniform sentence lengths
- **LLM non-determinism:** Layer 3 scores may vary slightly between runs — use `/scan/heuristic` for reproducible results

---

## Tests

```bash
# Run all tests (no API key needed)
pytest tests/ -v

# Expected output
34 passed in X.Xs
```

Tests cover:
- Heuristic scorer (7 tests)
- Semantic scorer (4 tests)
- Reading time calculator (5 tests)
- Fusion logic (7 tests)
- Repo URL parser (5 tests)
- CLI importability (3 tests)
- New features: confidence interval, pre-commit hook, condense endpoint (5 tests)

---

## Why SlopLens Wins

Most slop detection entries are a single LLM API call wrapped in a web form. SlopLens is different:

1. **Works without any API key** — heuristic mode runs in pure JavaScript in the browser
2. **Three independent layers** — each catches different patterns; together they're more robust
3. **Lives in the browser** — the Chrome extension scores every page without any user action
4. **Fixes slop, not just detects it** — `/scan/condense` rewrites text with the LLM
5. **Covers 4 tracks** — UX, Detection, Track A (repo scanning), CI/CD
6. **Free to run** — Groq free tier, no credit card, no expiry

---

## License

MIT — see [LICENSE](LICENSE)
