const DEFAULT = (typeof SLOPLENS_BACKEND !== "undefined" ? SLOPLENS_BACKEND : "");
const input   = document.getElementById("backendIn");
const autoChk = document.getElementById("autoScan");
const scanBtn = document.getElementById("scanBtn");

// Load settings
chrome.storage.local.get(["backendUrl","autoScan"], r => {
  input.value   = r.backendUrl  || DEFAULT;
  autoChk.checked = r.autoScan || false;
});
input.addEventListener("change",  () => chrome.storage.local.set({backendUrl:  input.value.trim()}));
autoChk.addEventListener("change", () => chrome.storage.local.set({autoScan: autoChk.checked}));

function scoreColor(s){return s>=65?"#dc2626":s>=35?"#d97706":"#16a34a";}

scanBtn.addEventListener("click", async () => {
  scanBtn.textContent = "Scanning...";
  scanBtn.disabled    = true;
  const backendUrl = input.value.trim() || DEFAULT;
  try {
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    const [{result:text}] = await chrome.scripting.executeScript({
      target:{tabId:tab.id},
      func: () => {
        for (const sel of ["main","article","[role='main']",".content","#content"]){
          const el=document.querySelector(sel);
          if(el?.innerText?.length>100) return el.innerText.slice(0,3000);
        }
        return document.body.innerText.slice(0,3000);
      },
    });
    const res  = await fetch(`${backendUrl}/scan`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,fast:true})});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const c    = scoreColor(data.overall_slop_score);
    document.getElementById("scoreNum").textContent = data.overall_slop_score;
    document.getElementById("scoreNum").style.color = c;
    document.getElementById("verdict").textContent  = `"${data.verdict}"`;
    if (data.semantic_slop_score != null)
      document.getElementById("semRow").textContent = `semantic: ${data.semantic_slop_score} · method: ${data.scoring_method}`;
    document.getElementById("result").style.display = "block";
  } catch(e) {
    document.getElementById("verdict").textContent  = `Error: ${e.message}`;
    document.getElementById("result").style.display = "block";
  }
  scanBtn.textContent = "Scan again";
  scanBtn.disabled    = false;
});
