"""
SlopLens API v4 — Three-Layer Hybrid Detection Engine
Layer 1: Heuristic  (instant, free, deterministic, pure Python)
Layer 2: Semantic   (TF-IDF cosine similarity vs 61-sentence corpus)
Layer 3: LLM        (Groq — FREE tier, llama-3.1-8b-instant)

Free API key: https://console.groq.com (no credit card required)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import json, re, math, hashlib, os, asyncio
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SlopLens API", version="4.0.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# Lazy-initialised so tests run without a key
_groq_client = None
def get_groq_client():
    global _groq_client
    if _groq_client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY not set. Get a free key at https://console.groq.com")
        _groq_client = Groq(api_key=key)
    return _groq_client

# ── Signal dictionaries ────────────────────────────────────────────────────────

FILLER_PHRASES = [
    "it goes without saying","in today's world","at the end of the day",
    "moving forward","think outside the box","circle back","best-in-class",
    "cutting-edge","revolutionize","game-changer","paradigm shift",
    "in conclusion","it is important to note","needless to say","going forward",
    "due to the fact that","it should be noted","as we all know","low-hanging fruit",
    "move the needle","value-add","deep dive","bandwidth","scalable solution",
    "in today's fast-paced","it is what it is","when all is said and done",
    "the fact of the matter is","for all intents and purposes","in the final analysis",
    "first and foremost","last but not least","in this day and age",
    "the bottom line is","without further ado","long story short",
    "at this point in time","it is worth noting",
]
HEDGE_WORDS = [
    "basically","literally","honestly","actually","essentially","generally",
    "somewhat","rather","fairly","quite","perhaps","maybe","possibly",
    "arguably","seemingly","apparently","presumably",
]
PASSIVE_RE = re.compile(r'\b(is|are|was|were|been|be|being)\s+\w+ed\b', re.IGNORECASE)

_cache: dict = {}


# ── Layer 1: Heuristic ─────────────────────────────────────────────────────────

def heuristic_score(text: str) -> dict:
    if not text.strip():
        return {"filler_ratio":50,"information_density":50,"naturalness":50,
                "passive_density":50,"h_confidence":0,"flagged_phrases":[]}
    lower = text.lower()
    words = re.findall(r'\b\w+\b', lower)
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 8]
    n_sent = max(len(sentences), 1)

    filler_hits = [p for p in FILLER_PHRASES if p in lower]
    hedge_hits  = sum(1 for w in HEDGE_WORDS if re.search(rf'\b{w}\b', lower))
    filler_ratio = min(100, int((len(filler_hits)*14 + hedge_hits*5) / n_sent * 8))

    window = words[:200]
    ttr = len(set(window)) / len(window) if window else 0.5
    information_density = min(100, int(ttr * 125))

    naturalness = 50
    if len(sentences) >= 3:
        lengths = [len(s.split()) for s in sentences]
        mean = sum(lengths) / len(lengths)
        std  = math.sqrt(sum((l-mean)**2 for l in lengths) / len(lengths))
        cv   = std / mean if mean > 0 else 0
        naturalness = min(100, int(cv * 190))

    passive_count   = len(PASSIVE_RE.findall(text))
    passive_density = min(100, int(passive_count / n_sent * 60))
    short_penalty   = int(sum(1 for s in sentences if len(s.split()) < 6) / n_sent * 35)
    confidence = min(100, len(filler_hits)*20 + hedge_hits*8 + passive_count*10 + 15)

    return {
        "filler_ratio":        min(100, filler_ratio + short_penalty),
        "information_density": information_density,
        "naturalness":         max(0, naturalness - short_penalty//2),
        "passive_density":     passive_density,
        "flagged_phrases":     filler_hits[:5],
        "h_confidence":        confidence,
    }


# ── Layer 2: Semantic (sentence-transformers + TF-IDF hybrid) ───────────────

SLOP_CORPUS = [
    # Marketing fluff
    "It goes without saying that leveraging cutting-edge AI solutions is paramount for driving meaningful outcomes.",
    "Moving forward, our team will synergize cross-functional capabilities to deliver best-in-class experiences.",
    "At the end of the day, we need to think outside the box and circle back on our core competencies.",
    "This comprehensive solution will revolutionize the way we interact with technology going forward.",
    "In today's fast-paced digital landscape, best-in-class synergies are essential for value creation.",
    "We need to leverage our bandwidth and move the needle to achieve sustainable growth and engagement.",
    "Our cutting-edge platform delivers paradigm-shifting results through innovative cross-functional teamwork.",
    "Going forward, we will double down on our core competencies to drive meaningful engagement outcomes.",
    "It should be noted that our scalable solutions empower stakeholders at every level of the organization.",
    "Due to the fact that the market is evolving rapidly, we must adapt our go-to-market strategy accordingly.",
    "Needless to say, our best-in-class approach ensures that we remain at the forefront of innovation.",
    "When all is said and done, the bottom line is that we need to think outside the box to move the needle.",
    # Corporate buzzwords
    "Our holistic approach to digital transformation enables us to deliver value across the entire ecosystem.",
    "By fostering a culture of innovation, we empower our teams to ideate and execute at scale.",
    "We are excited to announce that our platform is disrupting the space and redefining what is possible.",
    "Our mission-driven organization is laser-focused on delivering impactful solutions to our valued customers.",
    "This initiative represents a unique opportunity to align our strategic pillars with market opportunities.",
    "We are committed to being proactive in our approach as we navigate the complexities of the landscape.",
    "Our robust and scalable infrastructure positions us well to capitalize on emerging trends going forward.",
    "By leveraging data-driven insights, we can unlock new value streams and monetize our core competencies.",
    # AI filler
    "Certainly! I would be happy to help you explore this fascinating and multifaceted topic in detail.",
    "It is important to note that this is a complex issue with many dimensions worth considering carefully.",
    "In conclusion, I hope this comprehensive overview has provided valuable insights into the subject matter.",
    "Absolutely, this is a great question that deserves a thorough and nuanced exploration of the key factors.",
    "As an AI language model, I can provide a balanced perspective on this multifaceted and nuanced topic.",
    "It goes without saying that we must consider all stakeholders as we navigate this challenging environment.",
    "I completely understand your perspective, and I think it is important to validate your feelings on this.",
    # SEO stuffing
    "Best practices for leveraging synergies in today's dynamic and rapidly evolving business environment.",
    "Top strategies for driving meaningful outcomes through innovative and cutting-edge digital solutions.",
    "How to revolutionize your workflow with best-in-class tools that move the needle and add real value.",
    "Ultimate guide to unlocking the full potential of your core competencies in a competitive landscape.",
]

CLEAN_CORPUS = [
    # Engineering commits / PRs
    "Fixed race condition in auth middleware where concurrent requests read stale session tokens.",
    "Added Redis SETNX lock with 200ms TTL; fallback to DB read after 3 retries. Closes #1847.",
    "Reduced p99 latency from 340ms to 42ms by replacing synchronous DB calls with connection pooling.",
    "CPU spiked to 94% during the 09:15 deployment; rolled back at 09:22. Root cause: N+1 query in user loader.",
    "Benchmarked three approaches: naive O(n²) sort, quicksort, and radix sort on 10 million integers.",
    "Memory leak in WebSocket handler: buffer not freed on disconnect. Added explicit cleanup in onClose.",
    "Migrated from REST to GraphQL; reduced overfetch by 67% and cut mobile data usage by 2.1MB per session.",
    "Test coverage increased from 43% to 89% after adding integration tests for the payment processing module.",
    "Compilation time dropped from 4.2s to 0.8s after switching from webpack to esbuild with tree-shaking.",
    "Replaced O(n²) deduplication loop with a hash-set lookup; list processing dropped from 4.1s to 0.03s.",
    "The segfault traced to a use-after-free in the parser when input exceeded 64KB; added bounds check.",
    "Dockerfile layer order fixed: copy requirements first, then source, so pip cache survives code changes.",
    # Scientific / factual writing
    "The study recruited 847 participants aged 18-65 with diagnosed hypertension; 423 received treatment.",
    "Neural network achieved 94.3% accuracy on WESAD test set using a CNN-RNN hybrid architecture.",
    "The volcano erupted at 14:32 local time, sending ash columns 12km into the atmosphere.",
    "Rainfall totaled 43mm in 6 hours, exceeding the 1-in-50-year threshold for the catchment area.",
    "The enzyme operates optimally at pH 7.4 and 37°C; activity drops 80% below pH 6.0.",
    "Subjects who slept fewer than 6 hours showed a 23% increase in cortisol levels by day 3.",
    "The alloy failed at 312 MPa, 18% below the manufacturer specification of 380 MPa.",
    # Technical documentation
    "Set the timeout to 30s; connections idle longer than this are closed and removed from the pool.",
    "Pass --dry-run to preview changes without writing to disk; omit the flag to apply them.",
    "The queue processes messages in FIFO order; dead-lettered items are retried after a 5-minute backoff.",
    "Token refresh happens automatically 60 seconds before expiry; no client-side handling required.",
    "Logs rotate daily and are retained for 14 days; older files are compressed and moved to cold storage.",
    "The API returns 429 with a Retry-After header when rate limits are exceeded; back off exponentially.",
    # Journalism / concrete reporting
    "The company laid off 340 employees, 12% of its workforce, effective the last Friday of the month.",
    "The bill passed 54-46, with three senators crossing party lines to support the amendment.",
    "Temperatures reached 41°C in the city center, the highest recorded since measurements began in 1893.",
    "The defendant was sentenced to 7 years after being convicted on two counts of wire fraud.",
    "The satellite launched at 03:47 UTC and reached its target orbit 94 minutes after liftoff.",
]

# Sentence-transformers model — loaded lazily to avoid cold-start issues
_st_model = None
def get_st_model():
    global _st_model
    if _st_model is None:
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model

# Pre-compute corpus centroids at startup
_st_slop_centroid  = None
_st_clean_centroid = None

def _init_centroids():
    global _st_slop_centroid, _st_clean_centroid
    if _st_slop_centroid is not None:
        return
    model = get_st_model()
    slop_embs  = model.encode(SLOP_CORPUS,  convert_to_numpy=True, show_progress_bar=False)
    clean_embs = model.encode(CLEAN_CORPUS, convert_to_numpy=True, show_progress_bar=False)
    _st_slop_centroid  = slop_embs.mean(axis=0)
    _st_clean_centroid = clean_embs.mean(axis=0)

# Also keep TF-IDF as fast fallback
_vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
_vec.fit(SLOP_CORPUS + CLEAN_CORPUS)
_tfidf_slop_centroid  = np.asarray(_vec.transform(SLOP_CORPUS).mean(axis=0))
_tfidf_clean_centroid = np.asarray(_vec.transform(CLEAN_CORPUS).mean(axis=0))


def semantic_score(text: str, use_embeddings: bool = True) -> dict:
    """
    Semantic slop scoring using sentence-transformers cosine similarity.
    Falls back to TF-IDF if embeddings unavailable.
    """
    text_trunc = text[:2000]

    # Primary: sentence-transformers (all-MiniLM-L6-v2)
    if use_embeddings:
        try:
            _init_centroids()
            model    = get_st_model()
            emb      = model.encode([text_trunc], convert_to_numpy=True, show_progress_bar=False)[0]
            slop_sim  = float(np.dot(emb, _st_slop_centroid)  / (np.linalg.norm(emb) * np.linalg.norm(_st_slop_centroid)  + 1e-9))
            clean_sim = float(np.dot(emb, _st_clean_centroid) / (np.linalg.norm(emb) * np.linalg.norm(_st_clean_centroid) + 1e-9))
            total = slop_sim + clean_sim
            score = int((slop_sim / total) * 100) if total > 0.001 else 50
            return {
                "semantic_slop_score": score,
                "slop_similarity":     round(slop_sim,  4),
                "clean_similarity":    round(clean_sim, 4),
                "semantic_method":     "sentence-transformers/all-MiniLM-L6-v2",
            }
        except Exception:
            pass  # fall through to TF-IDF

    # Fallback: TF-IDF
    vec       = _vec.transform([text_trunc])
    slop_sim  = float(cosine_similarity(vec, _tfidf_slop_centroid)[0][0])
    clean_sim = float(cosine_similarity(vec, _tfidf_clean_centroid)[0][0])
    total = slop_sim + clean_sim
    score = int((slop_sim / total) * 100) if total > 0.001 else 50
    return {
        "semantic_slop_score": score,
        "slop_similarity":     round(slop_sim,  4),
        "clean_similarity":    round(clean_sim, 4),
        "semantic_method":     "tfidf-fallback",
    }


# ── Reading time ───────────────────────────────────────────────────────────────

def calculate_times(text: str, info_density: int) -> dict:
    words = len(re.findall(r'\b\w+\b', text))
    reading_time = round(words / 238, 1)
    info_time    = round(reading_time * (info_density / 100), 1)
    fluff_pct    = max(0, int((1 - info_density / 100) * 100))
    return {
        "reading_time_min": reading_time,
        "info_time_min":    info_time,
        "fluff_percent":    fluff_pct,
        "word_count":       words,
    }


# ── Layer 3: LLM (Groq — free tier) ──────────────────────────────────────────

LLM_PROMPT = """Analyze this text for slop — low-quality, filler-heavy, low-information content.
Return ONLY valid JSON, no markdown fences, no explanation:
{{
  "overall_slop_score": <integer 0-100, 100=pure slop>,
  "information_density": <integer 0-100>,
  "filler_ratio": <integer 0-100>,
  "specificity": <integer 0-100>,
  "naturalness": <integer 0-100>,
  "slop_category": <one of: "marketing_fluff"|"corporate_buzzwords"|"ai_filler"|"seo_stuffing"|"repetition"|"empty_conclusions"|"clean">,
  "verdict": "<one punchy honest sentence, max 15 words>",
  "roast": "<one witty devastating sentence, max 20 words>",
  "flagged_phrases": ["exact phrase1","exact phrase2","exact phrase3"],
  "fix": "<one specific actionable improvement, max 20 words>"
}}
Text: \"\"\"{text}\"\"\""""


async def llm_score(text: str, fast: bool = False) -> dict:
    key = hashlib.md5((text[:500] + str(fast)).encode()).hexdigest()
    if key in _cache:
        return _cache[key]

    # Groq free tier models:
    # llama-3.1-8b-instant  — fastest, great for fast=True
    # llama-3.3-70b-versatile — best quality, for fast=False
    model = "llama-3.1-8b-instant" if fast else "llama-3.3-70b-versatile"

    response = get_groq_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": LLM_PROMPT.format(text=text[:2500])}],
        temperature=0.1,
        max_tokens=500,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    result = json.loads(raw)
    _cache[key] = result
    return result


# ── Fusion ────────────────────────────────────────────────────────────────────

def fuse(h: dict, l: dict, text: str) -> dict:
    sem = semantic_score(text)
    hw  = min(0.35, h["h_confidence"] / 100 * 0.35)
    sw  = 0.20
    lw  = 1 - hw - sw

    fused_density = int(
        h["information_density"] * hw +
        (100 - sem["semantic_slop_score"]) * sw +
        l["information_density"] * lw
    )
    fused_filler  = int(h["filler_ratio"] * hw + sem["semantic_slop_score"] * sw + l["filler_ratio"] * lw)
    fused_natural = int(h["naturalness"] * hw + l["naturalness"] * (lw + sw))
    blended_slop  = int(l["overall_slop_score"] * 0.75 + sem["semantic_slop_score"] * 0.25)
    flagged = list(dict.fromkeys(h.get("flagged_phrases",[]) + l.get("flagged_phrases",[])))[:6]
    times   = calculate_times(text, fused_density)

    return {
        "overall_slop_score":   min(100, blended_slop),
        "information_density":  min(100, fused_density),
        "filler_ratio":         min(100, fused_filler),
        "specificity":          l.get("specificity", 50),
        "naturalness":          min(100, fused_natural),
        "passive_density":      h["passive_density"],
        "semantic_slop_score":  sem["semantic_slop_score"],
        "slop_similarity":      sem["slop_similarity"],
        "clean_similarity":     sem["clean_similarity"],
        "slop_category":        l.get("slop_category", "unknown"),
        "verdict":              l.get("verdict", ""),
        "roast":                l.get("roast", ""),
        "flagged_phrases":      flagged,
        "fix":                  l.get("fix", ""),
        **times,
        "scoring_method":       "hybrid_v4_3layer",
        "heuristic_confidence": h["h_confidence"],
        "llm_model":            "groq/llama-3.3-70b-versatile",
        "confidence_interval":  max(3, 15 - h["h_confidence"] // 10),
    }


# ── Request models ─────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    text: str
    fast: bool = False

class BatchRequest(BaseModel):
    texts: list[str]
    fast:  bool = True

class CompareRequest(BaseModel):
    text_a: str
    text_b: str
    fast:   bool = False

class URLBatchRequest(BaseModel):
    urls: list[str]
    fast: bool = True


# ── Core scan ─────────────────────────────────────────────────────────────────

async def _scan_one(text: str, fast: bool) -> dict:
    h = heuristic_score(text)
    l = await llm_score(text, fast)
    return fuse(h, l, text)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/scan", summary="Full 3-layer hybrid scan",
           description="Scores text using heuristic + TF-IDF semantic + Groq LLM. Returns slop score, reading time, roast, category, fix, and confidence interval.")
async def scan(req: ScanRequest):
    text = req.text.strip()
    if len(text) < 20:    raise HTTPException(400, "Text too short (min 20 chars)")
    if len(text) > 10000: raise HTTPException(400, "Text too long (max 10,000 chars)")
    try:
        return await _scan_one(text, req.fast)
    except json.JSONDecodeError:
        raise HTTPException(502, "LLM returned malformed JSON — retry or use fast=true")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Internal error: {type(e).__name__}")


@app.post("/scan/compare", summary="Compare two texts",
           description="Scores both texts in parallel. Returns before/after scores, improvement delta, time saved, and signal gained.")
async def compare(req: CompareRequest):
    a, b = req.text_a.strip(), req.text_b.strip()
    if len(a) < 20 or len(b) < 20:
        raise HTTPException(400, "Both texts must be at least 20 chars")
    try:
        ra, rb = await asyncio.gather(_scan_one(a, req.fast), _scan_one(b, req.fast))
        improvement   = ra["overall_slop_score"] - rb["overall_slop_score"]
        time_saved    = round(max(0, ra["reading_time_min"] - rb["reading_time_min"]), 1)
        signal_gained = round(max(0, rb["info_time_min"]    - ra["info_time_min"]),    1)
        return {
            "before": ra, "after": rb,
            "improvement":   improvement,
            "time_saved":    time_saved,
            "signal_gained": signal_gained,
            "summary": f"Slop cut by {improvement} pts · {time_saved}min saved · {signal_gained}min more signal",
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/scan/urls", summary="Rank URLs by slop score",
           description="Fetches up to 5 URLs, extracts text, scores each with fast LLM mode. Returns ranked table.")
async def scan_urls(req: URLBatchRequest):
    if len(req.urls) > 5: raise HTTPException(400, "Max 5 URLs per request")
    import httpx
    from bs4 import BeautifulSoup
    results = []
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as http:
        for url in req.urls:
            url = url.strip()
            if not url.startswith(("http://","https://")): url = "https://" + url
            try:
                r    = await http.get(url, headers={"User-Agent":"SlopLens/4.0"})
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["nav","footer","header","script","style","aside","form"]):
                    tag.decompose()
                main = (soup.find("main") or soup.find("article") or
                        soup.find(id="content") or soup.find(class_="content") or soup.body)
                text = main.get_text(separator=" ", strip=True)[:3000] if main else ""
                if len(text.strip()) < 50:
                    results.append({"url":url,"error":"No readable content found"}); continue
                s = await _scan_one(text, fast=True)
                results.append({
                    "url":                url,
                    "overall_slop_score": s["overall_slop_score"],
                    "reading_time_min":   s["reading_time_min"],
                    "fluff_percent":      s["fluff_percent"],
                    "slop_category":      s.get("slop_category","unknown"),
                    "verdict":            s["verdict"],
                    "roast":              s.get("roast",""),
                })
            except Exception as e:
                results.append({"url":url,"error":str(e)[:120]})

    valid  = sorted([r for r in results if "error" not in r],
                    key=lambda x: x["overall_slop_score"], reverse=True)
    errors = [r for r in results if "error"     in r]
    return {"results": valid + errors, "ranked_count": len(valid)}


@app.post("/scan/batch", summary="Batch scan up to 10 texts",
           description="Scans up to 10 texts using fast LLM mode. Returns array of results.")
async def scan_batch(req: BatchRequest):
    if len(req.texts) > 10: raise HTTPException(400, "Max 10 texts")
    results = []
    for text in req.texts:
        try:    results.append(await _scan_one(text.strip(), True))
        except Exception as e: results.append({"error": str(e)})
    return {"results": results}


@app.post("/scan/heuristic", summary="Heuristic + semantic scan (free)",
           description="Runs heuristic and TF-IDF layers only. No LLM, no API cost, instant response.")
async def scan_heuristic_only(req: ScanRequest):
    text = req.text.strip()
    if len(text) < 20: raise HTTPException(400, "Text too short")
    h   = heuristic_score(text)
    sem = semantic_score(text)
    slop = int(h["filler_ratio"]*0.35 + (100-h["information_density"])*0.25
               + (100-h["naturalness"])*0.20 + h["passive_density"]*0.10
               + sem["semantic_slop_score"]*0.10)
    times = calculate_times(text, h["information_density"])
    return {**h,**sem,**times,"overall_slop_score":min(100,slop),
            "scoring_method":"heuristic_semantic_v4",
            "confidence_interval": max(3, 15 - h["h_confidence"] // 10)}




# ── Badge + Leaderboard ───────────────────────────────────────────────────────

from fastapi.responses import Response
from collections import deque
import time

# In-memory leaderboard (top 20 repos scanned)
_leaderboard: list = []
_recent_scans: deque = deque(maxlen=100)


def _update_leaderboard(repo: str, score: int, verdict: str):
    global _leaderboard
    # Update or insert
    for entry in _leaderboard:
        if entry["repo"] == repo:
            entry["score"] = score
            entry["verdict"] = verdict
            entry["updated"] = int(time.time())
            _leaderboard.sort(key=lambda x: x["score"], reverse=True)
            return
    _leaderboard.append({
        "repo": repo, "score": score,
        "verdict": verdict, "updated": int(time.time())
    })
    _leaderboard.sort(key=lambda x: x["score"], reverse=True)
    _leaderboard = _leaderboard[:20]  # keep top 20


def _score_to_color(score: int) -> str:
    if score >= 65: return "#EF4444"
    if score >= 35: return "#F59E0B"
    return "#22C55E"


def _score_to_label(score: int) -> str:
    if score >= 65: return "High Slop"
    if score >= 35: return "Medium Slop"
    return "Clean"


@app.get("/badge/{owner}/{repo_name}.svg",
         summary="SVG badge for a repo's slop score",
         description="Returns an SVG badge showing the repo's slop score. Embed in README.")
async def badge(owner: str, repo_name: str):
    repo = f"{owner}/{repo_name}"
    # Find in leaderboard cache
    cached = next((e for e in _leaderboard if e["repo"] == repo), None)
    if cached:
        score = cached["score"]
    else:
        score = 50  # unknown — prompt to scan

    color = _score_to_color(score)
    label = _score_to_label(score) if cached else "not scanned"
    text  = f"slop: {score}" if cached else "slop: ?"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="20">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="120" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="70" height="20" fill="#555"/>
    <rect x="70" width="50" height="20" fill="{color}"/>
    <rect width="120" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="35" y="15" fill="#010101" fill-opacity=".3">SlopLens</text>
    <text x="35" y="14">SlopLens</text>
    <text x="95" y="15" fill="#010101" fill-opacity=".3">{score}</text>
    <text x="95" y="14">{score}</text>
  </g>
</svg>"""

    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "max-age=3600"})


@app.get("/leaderboard",
         summary="Top 20 sloppiest repos scanned",
         description="Returns the 20 highest slop-scoring repos that have been scanned via /scan/repo.")
async def leaderboard():
    return {
        "leaderboard": _leaderboard,
        "total_scanned": len(_leaderboard),
        "updated": int(time.time()),
    }


@app.get("/health", summary="Health check",
           description="Returns service status, version, LLM provider, layer count, and response cache size.")
async def health():
    github_token = os.getenv("GITHUB_TOKEN")
    return {
        "status":        "ok",
        "service":       "SlopLens API",
        "version":       "4.0.0",
        "llm_provider":  "groq (free)",
        "layers":        3,
        "cache_entries": len(_cache),
        "github_token":  "set (5000 req/hr)" if github_token else "not set (60 req/hr — add GITHUB_TOKEN to .env)",
        "semantic_model": "sentence-transformers/all-MiniLM-L6-v2",
    }


# ── Repo Scanner ──────────────────────────────────────────────────────────────

class RepoRequest(BaseModel):
    repo: str          # "owner/repo" or full github URL
    fast: bool = True


def parse_repo(repo: str) -> str:
    """Extract owner/repo from URL or plain string."""
    repo = repo.strip().rstrip("/")
    repo = re.sub(r'^https?://(www\.)?github\.com/', '', repo)
    repo = re.sub(r'\.git$', '', repo)
    return repo


async def fetch_github(path: str, http: "httpx.AsyncClient") -> dict | list | None:
    url = f"https://api.github.com/{path}"
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = await http.get(url, headers=headers, timeout=10)
    if r.status_code == 404:
        return None
    if r.status_code == 403:
        remaining = r.headers.get("X-RateLimit-Remaining", "?")
        reset_ts   = r.headers.get("X-RateLimit-Reset", "?")
        if remaining == "0":
            raise HTTPException(429,
                f"GitHub rate limit exceeded. "
                f"{'Add GITHUB_TOKEN to .env for 5000 req/hr.' if not token else 'Token rate limit hit — wait or use a different token.'} "
                f"Resets at Unix timestamp {reset_ts}.")
        raise HTTPException(403, "GitHub API forbidden — check your GITHUB_TOKEN if set.")
    if r.status_code == 401:
        raise HTTPException(401, "Invalid GITHUB_TOKEN — check your token in .env.")
    r.raise_for_status()
    return r.json()


@app.post("/scan/repo", summary="Scan a GitHub repository",
           description="Scans README, last 20 PR descriptions, and last 30 commit messages in parallel. Returns per-section breakdown and overall repo slop score.")
async def scan_repo(req: RepoRequest):
    """
    Scan a public GitHub repo for slop.
    Scores: README, last 20 PR descriptions, last 30 commit messages.
    Returns per-section scores + overall repo slop score.
    """
    import httpx

    repo = parse_repo(req.repo)
    if not re.match(r'^[\w.-]+/[\w.-]+$', repo):
        raise HTTPException(400, "Invalid repo format. Use: owner/repo")

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as http:
        # 1. Verify repo exists
        meta = await fetch_github(f"repos/{repo}", http)
        if not meta:
            raise HTTPException(404, f"Repo '{repo}' not found or is private")

        results = {"repo": repo, "sections": [], "overall_slop_score": 0,
                   "star_count": meta.get("stargazers_count", 0),
                   "description": meta.get("description", "")}

        tasks = []

        # 2. README
        async def scan_readme():
            try:
                import base64
                data = await fetch_github(f"repos/{repo}/readme", http)
                if data and data.get("content"):
                    text = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
                    text = re.sub(r'```[\s\S]*?```', '', text)   # strip code blocks
                    text = re.sub(r'`[^`]+`', '', text)          # strip inline code
                    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # strip images
                    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # strip links
                    text = text.strip()
                    if len(text) > 50:
                        s = heuristic_score(text)
                        sem = semantic_score(text)
                        slop = int(s["filler_ratio"]*0.40 + (100-s["information_density"])*0.30
                                   + (100-s["naturalness"])*0.20 + sem["semantic_slop_score"]*0.10)
                        return {
                            "section": "README",
                            "slop_score": min(100, slop),
                            "word_count": len(text.split()),
                            "flagged_phrases": s["flagged_phrases"][:3],
                            "sample": text[:200].replace("\n", " "),
                        }
            except Exception:
                pass
            return None

        # 3. PR descriptions (last 20 closed PRs)
        async def scan_prs():
            try:
                prs = await fetch_github(
                    f"repos/{repo}/pulls?state=closed&per_page=20&sort=updated", http)
                if not prs:
                    return None
                bodies = [(pr.get("title","") + " " + (pr.get("body") or "")).strip()
                          for pr in prs if pr.get("title")]
                bodies = [b for b in bodies if len(b) > 30][:20]
                if not bodies:
                    return None
                scores = []
                worst_body, worst_score = "", 0
                for body in bodies:
                    s   = heuristic_score(body)
                    sem = semantic_score(body)
                    sc  = int(s["filler_ratio"]*0.40 + (100-s["information_density"])*0.30
                              + (100-s["naturalness"])*0.20 + sem["semantic_slop_score"]*0.10)
                    sc  = min(100, sc)
                    scores.append(sc)
                    if sc > worst_score:
                        worst_score = sc
                        worst_body  = body[:150]
                avg = int(sum(scores) / len(scores))
                return {
                    "section":      "PR Descriptions",
                    "slop_score":   avg,
                    "pr_count":     len(scores),
                    "worst_score":  worst_score,
                    "worst_sample": worst_body,
                    "score_distribution": {
                        "clean":  sum(1 for s in scores if s < 35),
                        "medium": sum(1 for s in scores if 35 <= s < 65),
                        "slop":   sum(1 for s in scores if s >= 65),
                    },
                }
            except Exception:
                pass
            return None

        # 4. Commit messages (last 30)
        async def scan_commits():
            try:
                commits = await fetch_github(
                    f"repos/{repo}/commits?per_page=30", http)
                if not commits:
                    return None
                messages = [c["commit"]["message"].split("\n")[0]
                            for c in commits if c.get("commit",{}).get("message")]
                messages = [m for m in messages if len(m) > 10][:30]
                if not messages:
                    return None
                full_text = ". ".join(messages)
                s   = heuristic_score(full_text)
                sem = semantic_score(full_text)
                slop = int(s["filler_ratio"]*0.40 + (100-s["information_density"])*0.30
                           + (100-s["naturalness"])*0.20 + sem["semantic_slop_score"]*0.10)
                worst = max(messages, key=lambda m: len([f for f in FILLER_PHRASES if f in m.lower()]))
                return {
                    "section":       "Commit Messages",
                    "slop_score":    min(100, slop),
                    "commit_count":  len(messages),
                    "worst_message": worst,
                    "flagged_phrases": s["flagged_phrases"][:3],
                }
            except Exception:
                pass
            return None

        # Run all three in parallel
        readme_r, prs_r, commits_r = await asyncio.gather(
            scan_readme(), scan_prs(), scan_commits()
        )

        sections = [r for r in [readme_r, prs_r, commits_r] if r is not None]
        results["sections"] = sections

        if sections:
            # Weighted overall: README 40%, PRs 40%, commits 20%
            weights = {"README": 0.40, "PR Descriptions": 0.40, "Commit Messages": 0.20}
            total_w, total_s = 0, 0
            for sec in sections:
                w = weights.get(sec["section"], 0.33)
                total_s += sec["slop_score"] * w
                total_w += w
            results["overall_slop_score"] = int(total_s / total_w) if total_w else 50

            # Best + worst section
            results["cleanest_section"] = min(sections, key=lambda s: s["slop_score"])["section"]
            results["sloppiest_section"] = max(sections, key=lambda s: s["slop_score"])["section"]
            # Update leaderboard
            _update_leaderboard(repo, results["overall_slop_score"], results.get("verdict",""))

            # Verdict
            score = results["overall_slop_score"]
            if score >= 65:
                results["verdict"] = f"This repo's documentation is high slop. PRs and README need serious work."
            elif score >= 35:
                results["verdict"] = f"Medium slop. Some sections are clear, others lean on filler."
            else:
                results["verdict"] = f"Clean repo. Documentation is specific and informative."

        return results


# ── Condense endpoint ─────────────────────────────────────────────────────────

CONDENSE_PROMPT = """You are a ruthless editor. Rewrite this text removing all filler, buzzwords, hedge words, and empty phrases. Keep only concrete information. Be brutal. Cut length by at least 40%.

Rules:
- Remove ALL filler phrases ("it goes without saying", "moving forward", etc.)
- Replace vague abstractions with specific claims
- Cut passive voice where possible
- No "certainly", "absolutely", "I hope this helps"
- Output ONLY the rewritten text, nothing else

Original text:
\"\"\"{text}\"\"\""""


class CondenseRequest(BaseModel):
    text: str


@app.post("/scan/condense", summary="Rewrite text removing slop",
           description="Uses Groq LLM to rewrite text, removing filler, buzzwords and passive voice. Returns original, condensed, and stats.")
async def condense(req: CondenseRequest):
    """Rewrite sloppy text into clean, dense prose."""
    text = req.text.strip()
    if len(text) < 20:  raise HTTPException(400, "Text too short")
    if len(text) > 5000: raise HTTPException(400, "Text too long (max 5000 chars)")

    before = heuristic_score(text)
    before_times = calculate_times(text, before["information_density"])

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": CONDENSE_PROMPT.format(text=text[:4000])}],
        temperature=0.3,
        max_tokens=1500,
    )
    condensed = response.choices[0].message.content.strip()

    after = heuristic_score(condensed)
    after_times = calculate_times(condensed, after["information_density"])

    words_cut = before_times["word_count"] - after_times["word_count"]
    pct_cut   = int(words_cut / max(before_times["word_count"], 1) * 100)

    return {
        "original":       text,
        "condensed":      condensed,
        "words_before":   before_times["word_count"],
        "words_after":    after_times["word_count"],
        "words_cut":      words_cut,
        "percent_cut":    pct_cut,
        "slop_before":    min(100, int(before["filler_ratio"]*0.40 + (100-before["information_density"])*0.30 + (100-before["naturalness"])*0.30)),
        "slop_after":     min(100, int(after["filler_ratio"]*0.40 + (100-after["information_density"])*0.30 + (100-after["naturalness"])*0.30)),
        "time_saved":     round(before_times["reading_time_min"] - after_times["reading_time_min"], 1),
    }


# ── Serve frontend ─────────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

_root     = pathlib.Path(__file__).parent.parent
_frontend = _root / "frontend"

@app.get("/", include_in_schema=False)
async def serve_index():
    idx = _frontend / "index.html"
    return FileResponse(str(idx)) if idx.exists() else {"error": "Frontend not found"}

if _frontend.exists():
    app.mount("/css",   StaticFiles(directory=str(_frontend / "css")),   name="css")
    app.mount("/js",    StaticFiles(directory=str(_frontend / "js")),     name="js")
    app.mount("/pages", StaticFiles(directory=str(_frontend / "pages")), name="pages")