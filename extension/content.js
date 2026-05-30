/**
 * SlopLens Content Script v5
 * Heatmap: overlay divs (no innerHTML modification)
 */

const DEFAULT_BACKEND = (typeof SLOPLENS_BACKEND !== "undefined" ? SLOPLENS_BACKEND : "");
let badge = null, panel = null, scanning = false, lastResult = null;
let heatmapActive = false;
let backendUrl = DEFAULT_BACKEND;

chrome.storage.local.get(["backendUrl","autoScan"], r => {
  if (r.backendUrl) backendUrl = r.backendUrl;
  if (r.autoScan) setTimeout(triggerScan, 2000);
});

// ── Sentence scorer ───────────────────────────────────────────────────────────
const FILLERS = ["it goes without saying","in today's world","at the end of the day","moving forward","think outside the box","circle back","best-in-class","cutting-edge","revolutionize","game-changer","needless to say","going forward","low-hanging fruit","move the needle","in conclusion","first and foremost","last but not least","when all is said and done"];
const HEDGES  = ["basically","literally","honestly","essentially","generally","somewhat","arguably"];

function scoreText(text) {
  const lower = text.toLowerCase();
  const words = (text.match(/\b\w+\b/g) || []);
  if (words.length < 5) return "neutral";
  const hasFiller = FILLERS.some(f => lower.includes(f));
  const hedgeCount = HEDGES.filter(h => new RegExp("\\b"+h+"\\b").test(lower)).length;
  const uniqueRatio = new Set(words.map(w=>w.toLowerCase())).size / words.length;
  const hasPassive = /\b(is|are|was|were|been)\s+\w+ed\b/i.test(text);
  if (hasFiller || hedgeCount >= 2 || (hasPassive && uniqueRatio < 0.55)) return "red";
  if (hedgeCount >= 1 || uniqueRatio < 0.6) return "yellow";
  if (uniqueRatio >= 0.65 && words.length >= 8) return "green";
  return "neutral";
}

// ── Heatmap (overlay approach — no innerHTML change) ──────────────────────────
const OVERLAY_COLORS = {
  red:    "rgba(239,68,68,0.18)",
  yellow: "rgba(245,158,11,0.15)",
  green:  "rgba(34,197,94,0.15)",
};

function applyHeatmap() {
  removeHeatmap();

  // Inject style
  const style = document.createElement("style");
  style.id = "sl-heatmap-style";
  style.textContent = ".sl-hl{position:relative!important;border-radius:2px;transition:background .3s}";
  document.head.appendChild(style);

  let count = 0;
  const SKIP = new Set(["SCRIPT","STYLE","NAV","FOOTER","HEADER","CODE","PRE","BUTTON","INPUT","TEXTAREA","SELECT","ASIDE","NOSCRIPT","A"]);

  // Walk all elements
  document.body.querySelectorAll("p, li, h1, h2, h3, h4, blockquote, td, div").forEach(el => {
    if (SKIP.has(el.tagName)) return;
    if (el.closest("nav, footer, header, aside")) return;
    if (el.children.length > 2) return; // skip containers

    const text = el.innerText?.trim() || "";
    if (text.length < 40 || text.length > 2000) return;

    const grade = scoreText(text);
    if (grade === "neutral") return;

    // Apply background color directly to element style
    el.dataset.slOrigBg = el.style.backgroundColor || "";
    el.style.backgroundColor = OVERLAY_COLORS[grade];
    el.style.borderRadius = "2px";
    el.dataset.slHighlighted = "1";
    count++;
  });

  // Show legend
  showLegend(count);
}

function removeHeatmap() {
  // Remove background from all highlighted elements
  document.querySelectorAll("[data-sl-highlighted]").forEach(el => {
    el.style.backgroundColor = el.dataset.slOrigBg || "";
    el.style.borderRadius = "";
    delete el.dataset.slOrigBg;
    delete el.dataset.slHighlighted;
  });
  document.getElementById("sl-heatmap-style")?.remove();
  removeLegend();
}

function showLegend(count) {
  removeLegend();
  const leg = document.createElement("div");
  leg.id = "sl-legend";
  leg.style.cssText = "position:fixed;top:20px;right:20px;z-index:2147483646;background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 14px;font-family:-apple-system,sans-serif;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);line-height:1.9;min-width:180px;";
  leg.innerHTML =
    '<div style="font-weight:600;font-size:13px;margin-bottom:6px;display:flex;justify-content:space-between">SlopLens Heatmap <span id="sl-close-leg" style="cursor:pointer;color:#aaa">&#x2715;</span></div>'+
    '<div><span style="display:inline-block;width:14px;height:14px;background:rgba(34,197,94,.4);border-radius:2px;vertical-align:middle;margin-right:6px"></span>Useful</div>'+
    '<div><span style="display:inline-block;width:14px;height:14px;background:rgba(245,158,11,.4);border-radius:2px;vertical-align:middle;margin-right:6px"></span>Filler</div>'+
    '<div><span style="display:inline-block;width:14px;height:14px;background:rgba(239,68,68,.4);border-radius:2px;vertical-align:middle;margin-right:6px"></span>Slop</div>'+
    '<div style="font-size:10px;color:#aaa;margin-top:5px">'+count+' elements</div>';
  document.body.appendChild(leg);
  document.getElementById("sl-close-leg").addEventListener("click", () => { removeLegend(); });
}

function removeLegend() {
  document.getElementById("sl-legend")?.remove();
}

function toggleHeatmap() {
  heatmapActive = !heatmapActive;
  if (heatmapActive) applyHeatmap();
  else removeHeatmap();
  updateHeatmapBtn();
}

function updateHeatmapBtn() {
  const btn = document.getElementById("sl-heatmap-btn");
  if (!btn) return;
  btn.textContent = heatmapActive ? "Hide Heatmap" : "Show Heatmap";
  btn.style.background = heatmapActive ? "#111" : "#f5f5f5";
  btn.style.color = heatmapActive ? "#F59E0B" : "#333";
}

// ── Badge ─────────────────────────────────────────────────────────────────────
function mkBadge() {
  const el = document.createElement("div");
  el.id = "sl-badge";
  el.style.cssText = "position:fixed;bottom:20px;right:20px;z-index:2147483647;cursor:pointer;user-select:none;display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:10px;background:#111;color:#fff;border:2px solid #333;box-shadow:0 2px 16px rgba(0,0,0,.2);font-family:'Courier New',monospace;min-width:130px;";
  el.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span style="font-size:12px">Scan page</span>';
  el.addEventListener("click", () => lastResult ? togglePanel() : triggerScan());
  document.body.appendChild(el);
  return el;
}

function setBadgeLoading() {
  badge.style.background="#111"; badge.style.borderColor="#555"; badge.style.color="#fff";
  badge.innerHTML = '<span style="font-size:12px">Scanning&#8230;</span>';
}

function setBadgeScore(s) {
  const t = getTheme(s);
  badge.style.background="#fff"; badge.style.borderColor=t.border; badge.style.color="#111";
  badge.innerHTML = '<span style="font-size:22px;font-weight:700;color:'+t.c+'">'+s+'</span><div style="line-height:1.3"><div style="font-size:10px;font-weight:700;color:'+t.c+'">SLOP</div><div style="font-size:10px;color:#888">'+t.label+'</div></div>';
}

// ── Panel ─────────────────────────────────────────────────────────────────────
function togglePanel() {
  if (panel) { panel.remove(); panel=null; return; }
  if (!lastResult) return;
  const r = lastResult, t = getTheme(r.overall_slop_score);

  panel = document.createElement("div");
  panel.id = "sl-panel";
  panel.style.cssText = "position:fixed;bottom:74px;right:20px;z-index:2147483646;width:300px;background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:16px;font-family:-apple-system,sans-serif;font-size:13px;color:#111;box-shadow:0 8px 32px rgba(0,0,0,.12);";

  panel.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'+
      '<span style="font-weight:700;font-size:15px">SlopLens</span>'+
      '<span style="font-size:11px;padding:3px 10px;border-radius:4px;font-weight:600;background:'+t.bg+';color:'+t.c+'">'+t.label+'</span>'+
    '</div>'+
    '<div style="font-size:40px;font-weight:700;font-family:\'Courier New\',monospace;color:'+t.c+';line-height:1;margin-bottom:10px">'+r.overall_slop_score+' <span style="font-size:12px;color:#999">/ 100</span></div>'+
    (r.reading_time_min!=null?
      '<div style="display:flex;align-items:center;gap:8px;padding:8px;background:#f8f8f8;border-radius:6px;margin-bottom:10px;font-family:\'Courier New\',monospace;font-size:13px">'+
        r.reading_time_min+'min read &#8594; <span style="color:'+t.c+'">'+r.info_time_min+'min useful</span> &mdash; <span style="color:'+t.c+'">'+r.fluff_percent+'% fluff</span>'+
      '</div>':'')+
    (r.roast?'<div style="padding:8px;background:#111;border-radius:6px;margin-bottom:8px;font-size:12px;color:#F59E0B;font-style:italic">"'+r.roast+'"</div>':'')+
    '<div style="font-style:italic;color:#555;font-size:12px;margin-bottom:8px">"'+(r.verdict||'')+'"</div>'+
    (r.fix?'<div style="padding:8px;background:#f0fdf4;border-radius:6px;font-size:12px;color:#166534;margin-bottom:10px">'+r.fix+'</div>':'')+
    '<button id="sl-heatmap-btn" style="width:100%;padding:9px;background:'+(heatmapActive?'#111':'#f5f5f5')+';color:'+(heatmapActive?'#F59E0B':'#333')+';border:1px solid #ddd;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;font-family:-apple-system,sans-serif">'+
      (heatmapActive?'Hide Heatmap':'Show Heatmap')+
    '</button>';

  document.body.appendChild(panel);

  document.getElementById("sl-heatmap-btn").addEventListener("click", e => {
    e.stopPropagation();
    toggleHeatmap();
  });

  setTimeout(() => {
    document.addEventListener("click", function fn(e) {
      if (!panel?.contains(e.target) && e.target !== badge) {
        panel?.remove(); panel=null;
        document.removeEventListener("click", fn);
      }
    });
  }, 150);
}

// ── Scan ──────────────────────────────────────────────────────────────────────
function getPageText() {
  for (const s of ["main","article","[role='main']",".content","#content",".post"]) {
    const el = document.querySelector(s);
    if (el?.innerText?.length > 100) return el.innerText.slice(0,3000);
  }
  const c = document.body.cloneNode(true);
  ["nav","footer","header","script","style","aside"].forEach(t=>c.querySelectorAll(t).forEach(e=>e.remove()));
  return c.innerText.slice(0,3000);
}

async function triggerScan() {
  if (scanning) return;
  scanning=true;
  if (panel){panel.remove();panel=null;}
  setBadgeLoading();
  const text = getPageText();
  if (text.trim().length < 20) {
    badge.innerHTML='<span style="font-size:12px;color:#aaa">No text</span>';
    scanning=false; return;
  }
  try {
    const url = (backendUrl||DEFAULT_BACKEND).replace(/\/+$/,"");
    const res = await fetch(url+"/scan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,fast:true})});
    if(!res.ok) throw new Error("HTTP "+res.status);
    lastResult = await res.json();
    setBadgeScore(lastResult.overall_slop_score);
  } catch(e) {
    badge.style.cssText="position:fixed;bottom:20px;right:20px;z-index:2147483647;padding:10px 14px;border-radius:10px;background:#fff;border:2px solid #ef4444;box-shadow:0 2px 16px rgba(0,0,0,.2);cursor:pointer;font-family:'Courier New',monospace;font-size:11px;color:#ef4444;";
    badge.textContent="Error — retry";
    badge.addEventListener("click",()=>{lastResult=null;scanning=false;triggerScan();},{once:true});
  }
  scanning=false;
}

function getTheme(s) {
  if(s>=65) return{c:"#dc2626",bg:"#fee2e2",border:"#fca5a5",label:"High slop"};
  if(s>=35) return{c:"#d97706",bg:"#fef3c7",border:"#fcd34d",label:"Medium slop"};
  return{c:"#16a34a",bg:"#dcfce7",border:"#86efac",label:"Clean"};
}

// ── Init ──────────────────────────────────────────────────────────────────────
if(document.readyState==="loading")
  document.addEventListener("DOMContentLoaded",()=>{badge=mkBadge();});
else badge=mkBadge();
