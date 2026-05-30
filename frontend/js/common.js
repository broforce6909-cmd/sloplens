// ── SlopLens Common JS ────────────────────────────────────────────────────────

let backendUrl = localStorage.getItem("sloplens_backend") || "";

// ── Backend bar ───────────────────────────────────────────────────────────────

function initBackendBar() {
  const input = document.getElementById("bbInput");
  if (!input) return;
  if (backendUrl) input.value = backendUrl;

  // Auto-detect: if served from FastAPI on port 8000
  if (window.location.port === "8000") {
    backendUrl = window.location.origin;
    localStorage.setItem("sloplens_backend", backendUrl);
    input.value = backendUrl;
    updateBackendStatus("connected", "✓ Auto-connected");
    return;
  }
  updateBackendStatus(backendUrl ? "connected" : "off", backendUrl ? "✓ Backend set" : "Not connected");
}

function setBackend() {
  const val = document.getElementById("bbInput").value.trim().replace(/\/+$/, "");
  backendUrl = val;
  if (val) {
    localStorage.setItem("sloplens_backend", val);
    updateBackendStatus("connected", "✓ Set — click Test");
  } else {
    localStorage.removeItem("sloplens_backend");
    updateBackendStatus("off", "Not connected");
  }
}

function useLocalhost() {
  document.getElementById("bbInput").value = "http://localhost:8000";
  backendUrl = "http://localhost:8000";
  localStorage.setItem("sloplens_backend", backendUrl);
  updateBackendStatus("connected", "Testing...");
  testBackend();
}

async function testBackend() {
  const url = (document.getElementById("bbInput").value || backendUrl || "").trim().replace(/\/+$/, "");
  if (!url) { alert("Enter a backend URL or click 'Use localhost'"); return; }
  backendUrl = url;
  localStorage.setItem("sloplens_backend", url);
  updateBackendStatus("connecting", "Testing...");
  try {
    const r = await fetch(url + "/health");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    updateBackendStatus("connected", "✓ " + d.service + " v" + d.version);
  } catch (e) {
    updateBackendStatus("error", "✗ " + e.message);
    alert("✗ Cannot connect: " + e.message + "\n\nMake sure backend is running:\npython run.py");
  }
}

function updateBackendStatus(state, text) {
  const el = document.getElementById("bbStatus");
  if (!el) return;
  el.textContent = text;
  el.className = state === "connected" ? "connected" : state === "error" ? "error" : "";
}

// ── Theme helpers ─────────────────────────────────────────────────────────────

function theme(s) {
  if (s >= 65) return { c: "var(--red)",   bg: "var(--red-bg)",   b: "var(--red-d)",   label: "HIGH SLOP" };
  if (s >= 35) return { c: "var(--amber)", bg: "var(--amber-bg)", b: "var(--amber-d)", label: "MEDIUM SLOP" };
  return             { c: "var(--green)", bg: "var(--green-bg)", b: "var(--green-d)",  label: "CLEAN" };
}

function bc(v, h) {
  const bad = h ? 100 - v : v;
  return bad >= 65 ? "var(--red)" : bad >= 35 ? "var(--amber)" : "var(--green)";
}

// ── HTML helpers ──────────────────────────────────────────────────────────────

function escH(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function buildHl(text, phrases) {
  let out = escH(text);
  (phrases || []).forEach(p => {
    const safe = escH(p).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(safe, "gi"), m => `<mark class="slop">${m}</mark>`);
  });
  return out;
}

function ringHtml(score, t, sz = 130) {
  const r = (sz - 14) / 2, cx = sz / 2, cy = sz / 2;
  const circ = (2 * Math.PI * r).toFixed(2);
  return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--border)" stroke-width="8"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${t.c}" stroke-width="8"
      stroke-dasharray="${circ}" stroke-dashoffset="${circ}" class="rarc"
      stroke-linecap="round" transform="rotate(-90 ${cx} ${cy})"
      style="transition:stroke-dashoffset 1.1s cubic-bezier(.16,1,.3,1)"/>
    <text x="${cx}" y="${cy - 6}" text-anchor="middle"
      style="font-size:${Math.round(sz * .22)}px;font-weight:700;font-family:'Courier New',monospace;fill:${t.c}">${score}</text>
    <text x="${cx}" y="${cy + 12}" text-anchor="middle" style="font-size:10px;fill:var(--ink3)">slop</text>
  </svg>`;
}

function animRings() {
  document.querySelectorAll(".rarc").forEach(arc => {
    const circ = parseFloat(arc.getAttribute("stroke-dasharray"));
    const score = parseInt(arc.closest("svg").querySelector("text").textContent);
    if (!isNaN(score) && !isNaN(circ)) {
      arc.style.strokeDashoffset = (circ - score / 100 * circ).toFixed(2);
    }
  });
}

function animBars() {
  document.querySelectorAll(".bf[data-w]").forEach(b => {
    b.style.width = b.dataset.w + "%";
  });
}

function mrow(label, val, hib) {
  const c = bc(val, hib);
  const id = "bf" + label.replace(/\s/g, "");
  return `<div class="mrow" style="margin-bottom:12px">
    <div class="mh"><span class="ml">${label}</span><span class="mv" style="color:${c}">${val}</span></div>
    <div class="bt"><div class="bf" id="${id}" data-w="${val}" style="background:${c}"></div></div>
  </div>`;
}

const CAT_MAP = {
  marketing_fluff:    { c: "var(--red)",   bg: "var(--red-bg)"   },
  corporate_buzzwords:{ c: "var(--amber)", bg: "var(--amber-bg)" },
  ai_filler:          { c: "var(--red)",   bg: "var(--red-bg)"   },
  seo_stuffing:       { c: "var(--amber)", bg: "var(--amber-bg)" },
  repetition:         { c: "var(--amber)", bg: "var(--amber-bg)" },
  empty_conclusions:  { c: "var(--amber)", bg: "var(--amber-bg)" },
  clean:              { c: "var(--green)", bg: "var(--green-bg)" },
};

function catTag(cat) {
  const cc = CAT_MAP[cat] || { c: "var(--ink3)", bg: "var(--surface2)" };
  return `<span class="cat-tag" style="background:${cc.bg};color:${cc.c};border:1px solid ${cc.c}">${(cat || "unknown").replace(/_/g, " ")}</span>`;
}

function buildResultHtml(r) {
  const t = theme(r.overall_slop_score);
  const metrics = [
    ["Information density", r.information_density, true],
    ["Filler ratio",        r.filler_ratio,        false],
    ["Specificity",         r.specificity,         true],
    ["Naturalness",         r.naturalness,         true],
  ];
  if (r.passive_density != null) metrics.push(["Passive density", r.passive_density, false]);

  return `
    <div class="results-top">
      <div class="score-col">
        ${ringHtml(r.overall_slop_score, t)}
        <span class="vc-pill" style="background:${t.bg};color:${t.c};border:1px solid ${t.b}">${t.label}</span>
        ${r.confidence_interval != null ? `<span class="ci-badge">±${r.confidence_interval}</span>` : ""}
      </div>
      <div class="metrics-col">${metrics.map(([l, v, h]) => mrow(l, v, h)).join("")}</div>
    </div>
    ${r.reading_time_min != null ? `
    <div class="time-strip">
      <div class="tblk"><span class="tnum">${r.reading_time_min}</span><span class="tlbl">Min to read</span></div>
      <div class="tarr">→</div>
      <div class="tblk"><span class="tnum" style="color:${t.c}">${r.info_time_min}</span><span class="tlbl">Min useful</span></div>
      <div class="tblk" style="border-left:1px solid var(--border)"><span class="tnum" style="color:${t.c}">${r.fluff_percent}%</span><span class="tlbl">Fluff</span></div>
    </div>` : ""}
    ${r.roast ? `<div class="roast-box"><span class="roast-tag">ROAST</span><span class="roast-txt">"${escH(r.roast)}"</span></div>` : ""}
    ${r.slop_category ? catTag(r.slop_category) : ""}
    ${r.semantic_slop_score != null ? `<div class="sem-row"><span>semantic: ${r.semantic_slop_score}</span><span>method: ${r.scoring_method || ""}</span></div>` : ""}
    <div class="verdict-q">"${escH(r.verdict || "")}"</div>
    ${r.flagged_phrases?.length ? `
      <div class="flags-lbl">Flagged phrases — highlighted above</div>
      <div class="flags-row">${r.flagged_phrases.map(p => `<span class="flag-chip">${escH(p)}</span>`).join("")}</div>` : ""}
    <div class="fix-box"><div class="fix-lbl">Suggested fix</div><div class="fix-body">${escH(r.fix || "")}</div></div>
  `;
}

// ── API call ──────────────────────────────────────────────────────────────────

async function apiCall(endpoint, body) {
  if (!backendUrl) throw new Error("No backend URL set — click 'Use localhost' at the top");
  const url = backendUrl.replace(/\/+$/, "") + "/" + endpoint.replace(/^\//, "");
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = "HTTP " + r.status;
    try { detail = (await r.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return r.json();
}

// ── Share card ────────────────────────────────────────────────────────────────

function copyShareCard(r) {
  if (!r) return;
  const emoji = r.overall_slop_score >= 65 ? "🔴" : r.overall_slop_score >= 35 ? "🟡" : "🟢";
  const lines = [
    `Slop score: ${r.overall_slop_score}/100 ${emoji}`,
    r.reading_time_min != null ? `${r.reading_time_min}min read → ${r.info_time_min}min useful (${r.fluff_percent}% fluff)` : "",
    r.roast ? `"${r.roast}"` : "",
    r.confidence_interval != null ? `Confidence: ±${r.confidence_interval}` : "",
    "",
    "via SlopLens",
  ].filter(Boolean).join("\n");
  navigator.clipboard.writeText(lines).then(() => {
    const btn = document.getElementById("shareBtn");
    if (btn) { const o = btn.textContent; btn.textContent = "Copied!"; setTimeout(() => btn.textContent = o, 1500); }
  });
}

// ── Heuristic JS scorer (no backend needed) ───────────────────────────────────

const FILLERS_JS = [
  "it goes without saying","in today's world","at the end of the day","moving forward",
  "think outside the box","circle back","best-in-class","cutting-edge","revolutionize",
  "game-changer","paradigm shift","in conclusion","it is important to note","needless to say",
  "going forward","due to the fact that","it should be noted","as we all know",
  "low-hanging fruit","move the needle","value-add","deep dive","bandwidth","scalable solution",
  "in today's fast-paced","when all is said and done","the fact of the matter is",
  "for all intents and purposes","first and foremost","last but not least",
  "without further ado","long story short","at this point in time",
];
const HEDGES_JS = ["basically","literally","honestly","actually","essentially","generally",
  "somewhat","rather","fairly","quite","perhaps","maybe","possibly","arguably","seemingly"];
const PASSIVE_JS = /\b(is|are|was|were|been|be|being)\s+\w+ed\b/gi;

function jsScore(text) {
  if (!text.trim()) return null;
  const lower = text.toLowerCase();
  const words = text.match(/\b\w+\b/g) || [];
  const sents = text.split(/[.!?]+/).map(s => s.trim()).filter(s => s.length > 8);
  const n = Math.max(sents.length, 1);

  const fillerHits = FILLERS_JS.filter(f => lower.includes(f));
  const hedgeHits  = HEDGES_JS.filter(h => new RegExp(`\\b${h}\\b`).test(lower)).length;
  const fr = Math.min(100, Math.round((fillerHits.length * 14 + hedgeHits * 5) / n * 8));

  const win = words.slice(0, 200);
  const ttr = win.length ? new Set(win.map(w => w.toLowerCase())).size / win.length : 0.5;
  const density = Math.min(100, Math.round(ttr * 125));

  let nat = 50;
  if (sents.length >= 3) {
    const lens = sents.map(s => s.split(/\s+/).length);
    const mean = lens.reduce((a, b) => a + b, 0) / lens.length;
    const std  = Math.sqrt(lens.reduce((a, l) => a + (l - mean) ** 2, 0) / lens.length);
    nat = Math.min(100, Math.round((mean > 0 ? std / mean : 0) * 190));
  }

  const pc = (text.match(PASSIVE_JS) || []).length;
  const pd = Math.min(100, Math.round(pc / n * 60));
  const sp = Math.round(sents.filter(s => s.split(/\s+/).length < 6).length / n * 35);
  const frf = Math.min(100, fr + sp);
  const natf = Math.max(0, nat - Math.round(sp / 2));
  const slop = Math.min(100, Math.round(frf * 0.40 + (100 - density) * 0.30 + (100 - natf) * 0.20 + pd * 0.10));

  const wc = words.length;
  const rt = Math.round(wc / 238 * 10) / 10;
  const it = Math.round(rt * (density / 100) * 10) / 10;
  const fp = Math.max(0, Math.round((1 - density / 100) * 100));

  const verdicts = slop >= 65
    ? ["Heavy on buzzwords, light on substance.", "Filler-to-signal ratio is alarming.", "Could be one sentence."]
    : slop >= 35
    ? ["Some useful content buried in noise.", "Decent signal but hedged heavily.", "Could be tighter."]
    : ["Specific and concrete.", "High signal density.", "Gets to the point."];

  return {
    overall_slop_score: slop,
    information_density: density,
    filler_ratio: frf,
    specificity: Math.max(0, density - 10),
    naturalness: natf,
    passive_density: pd,
    flagged_phrases: fillerHits.slice(0, 5),
    verdict: verdicts[Math.floor(Math.random() * verdicts.length)],
    roast: null,
    slop_category: slop >= 65 ? (fillerHits.length > 3 ? "corporate_buzzwords" : "ai_filler") : "clean",
    fix: fillerHits.length ? `Replace "${fillerHits[0]}" with a concrete, specific statement.` : "Add specific numbers, names, or technical details.",
    reading_time_min: rt,
    info_time_min: it,
    fluff_percent: fp,
    word_count: wc,
    confidence_interval: Math.max(5, 15),
    scoring_method: "heuristic_js",
  };
}

// ── Shared nav active link ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;
  document.querySelectorAll(".nav-links a").forEach(a => {
    if (a.getAttribute("href") && path.endsWith(a.getAttribute("href"))) {
      a.classList.add("active");
    }
  });
  initBackendBar();
});
