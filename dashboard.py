#!/usr/bin/env python3
"""
Lead Finder -- Web Dashboard builder
====================================

Turns leads into a single, self-contained HTML page (no server, no internet, no
installs). Features:

  * search + niche / state / status / score filters, sortable columns
  * Table view AND a Card view (toggle)
  * light / dark theme (remembered)
  * drag-and-drop CSV upload -- view your REAL results in the browser with no
    Python re-run; the uploaded file is remembered between visits
  * an outreach PIPELINE per lead: status (new / contacted / follow-up / won /
    lost), a free-text note, and an auto last-contacted date -- all saved in the
    browser (localStorage) so you can work the list over days
  * Export the current (filtered) view to CSV -- including your pipeline -- so
    your progress is portable between browsers and machines

USAGE
-----
  python3 dashboard.py                              # free SAMPLE data, opens it
  python3 dashboard.py --states "NJ,NY"             # sample data, those states
  python3 dashboard.py --csv us_website_leads.csv   # your REAL results
  python3 dashboard.py --no-open                    # build only, don't open
"""

import argparse
import csv
import datetime
import html
import json
import os
import re
import sys
import urllib.parse


# -----------------------------------------------------------------------------
# Get the leads (from a CSV, or generate free sample data)
# -----------------------------------------------------------------------------

def load_leads_from_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def generate_sample_leads(states_arg=None):
    import find_leads as f  # stdlib-only now that 'requests' is lazy
    if states_arg:
        matched, unknown = f.resolve_states(states_arg)
        if unknown:
            print(f"Warning: ignoring unrecognized state(s): {', '.join(unknown)}")
        if matched:
            f.STATES_TO_SEARCH = matched
    locations = f.build_locations()
    triples = f.generate_demo_places(locations)
    leads, _ = f.collect_leads_from_places(triples)
    return leads


# -----------------------------------------------------------------------------
# Page template  (plain string with __TOKENS__ -- not an f-string, so the CSS
# and JS braces are safe). Tokens are filled in by render_html() with .replace.
# -----------------------------------------------------------------------------

PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lead Finder</title>
<style>
  :root{
    --bg:#f5f6fb; --bg2:#eef1f8; --panel:#ffffff; --panel2:#fbfcfe;
    --ink:#0f172a; --muted:#64748b; --line:#e6e9f2; --line2:#eef1f7;
    --brand:#4f46e5; --brand2:#7c3aed; --ring:rgba(79,70,229,.18);
    --shadow:0 8px 30px rgba(15,23,42,.07); --shadow-sm:0 4px 14px rgba(15,23,42,.05);
    --st-new:#64748b; --st-contacted:#2563eb; --st-follow:#d97706; --st-won:#16a34a; --st-lost:#dc2626;
  }
  html[data-theme="dark"]{
    --bg:#0b1020; --bg2:#0e1426; --panel:#131b30; --panel2:#101829;
    --ink:#e8edf9; --muted:#93a1bd; --line:#243150; --line2:#1b2740;
    --brand:#8b5cf6; --brand2:#6366f1; --ring:rgba(139,92,246,.28);
    --shadow:0 12px 36px rgba(0,0,0,.45); --shadow-sm:0 4px 14px rgba(0,0,0,.35);
    --st-new:#94a3b8; --st-contacted:#60a5fa; --st-follow:#fbbf24; --st-won:#4ade80; --st-lost:#f87171;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:linear-gradient(180deg,var(--bg2),var(--bg));min-height:100vh;color:var(--ink);
       -webkit-font-smoothing:antialiased;font-size:14px}
  a{color:var(--brand);text-decoration:none}
  a:hover{text-decoration:underline}
  button{font-family:inherit}

  /* ---- top app bar ---- */
  .bar{position:sticky;top:0;z-index:30;background:var(--panel);border-bottom:1px solid var(--line);
       box-shadow:var(--shadow-sm)}
  .bar-in{max-width:1280px;margin:0 auto;padding:12px 18px;display:flex;align-items:center;gap:14px}
  .logo{display:flex;align-items:center;gap:11px;min-width:0}
  .mark{width:38px;height:38px;border-radius:11px;flex:0 0 auto;
        background:linear-gradient(135deg,var(--brand),var(--brand2));display:grid;place-items:center;
        color:#fff;box-shadow:0 6px 16px var(--ring)}
  .brand-t{min-width:0}
  .brand-t h1{margin:0;font-size:17px;font-weight:800;letter-spacing:-.02em;line-height:1.1}
  .brand-t p{margin:1px 0 0;font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .bar-actions{margin-left:auto;display:flex;align-items:center;gap:8px}
  .btn{display:inline-flex;align-items:center;gap:7px;padding:9px 13px;border:1px solid var(--line);
       border-radius:10px;background:var(--panel2);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;
       transition:border-color .15s, background .15s, transform .05s}
  .btn:hover{border-color:var(--brand);background:var(--panel)}
  .btn:active{transform:translateY(1px)}
  .btn.primary{background:linear-gradient(135deg,var(--brand),var(--brand2));border-color:transparent;color:#fff}
  .btn.icon{padding:9px;width:38px;justify-content:center}
  .btn svg{width:16px;height:16px;flex:0 0 auto}

  .wrap{max-width:1280px;margin:0 auto;padding:20px 18px 70px}

  /* ---- KPI cards ---- */
  .stats{display:grid;grid-template-columns:repeat(5,1fr);gap:13px;margin-bottom:16px}
  .stat{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:15px 17px;box-shadow:var(--shadow-sm)}
  .stat .n{font-size:25px;font-weight:800;line-height:1;letter-spacing:-.02em}
  .stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:7px}
  .stat.accent .n{color:var(--brand)}
  .stat.good .n{color:var(--st-won)}
  .stat .sub{font-size:11px;color:var(--muted);margin-top:3px}

  /* ---- dropzone ---- */
  .drop{margin-bottom:16px;border:1.5px dashed var(--line);border-radius:14px;background:var(--panel);
        padding:14px 16px;display:flex;align-items:center;gap:14px;color:var(--muted);font-size:13px;
        transition:border-color .15s, background .15s;cursor:pointer}
  .drop:hover{border-color:var(--brand)}
  .drop.drag{border-color:var(--brand);background:var(--panel2);color:var(--ink)}
  .drop .dz-ic{width:40px;height:40px;border-radius:11px;background:var(--bg2);display:grid;place-items:center;color:var(--brand);flex:0 0 auto}
  .drop b{color:var(--ink)}
  .drop .dz-grow{flex:1 1 auto;min-width:0}
  .drop .pill{display:inline-flex;align-items:center;gap:6px;background:var(--bg2);border:1px solid var(--line);
              border-radius:999px;padding:4px 10px;font-size:12px;color:var(--ink);font-weight:600}
  .linkbtn{background:none;border:none;color:var(--brand);font-weight:600;cursor:pointer;font-size:13px;padding:0}
  .linkbtn:hover{text-decoration:underline}

  .note{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;padding:10px 14px;border-radius:12px;font-size:13px;margin-bottom:14px}
  html[data-theme="dark"] .note{background:#3a2a14;border-color:#7c4a1e;color:#fcd9b6}

  /* ---- panel + toolbar ---- */
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);overflow:hidden}
  .toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:13px;border-bottom:1px solid var(--line);background:var(--panel)}
  .search{position:relative;flex:1 1 240px;min-width:170px}
  .search input{width:100%;padding:10px 12px 10px 36px;border:1px solid var(--line);border-radius:11px;font-size:14px;
                background:var(--panel2);color:var(--ink)}
  .search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.5;width:16px;height:16px}
  select,.toggle{padding:10px 12px;border:1px solid var(--line);border-radius:11px;font-size:13px;background:var(--panel2);color:var(--ink)}
  input:focus,select:focus,textarea:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 4px var(--ring)}
  .toggle{display:inline-flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
  .toggle input{width:16px;height:16px;accent-color:var(--brand)}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:11px;overflow:hidden;background:var(--panel2)}
  .seg button{border:none;background:transparent;color:var(--muted);padding:9px 13px;font-size:13px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
  .seg button.on{background:var(--brand);color:#fff}

  .meta{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;
        padding:10px 16px;color:var(--muted);font-size:13px;border-bottom:1px solid var(--line);background:var(--panel2)}
  .chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:3px 9px;border-radius:999px;
        border:1px solid var(--line);background:var(--panel)}
  .chip .dot{width:8px;height:8px;border-radius:50%}
  .barwrap{display:flex;align-items:center;gap:8px}
  .bar2{height:7px;width:150px;background:var(--bg2);border-radius:999px;overflow:hidden}
  .bar2>i{display:block;height:100%;background:linear-gradient(90deg,var(--st-won),#22c55e);width:0;transition:width .2s}

  /* ---- table ---- */
  .tablewrap{max-height:74vh;overflow:auto}
  table{width:100%;border-collapse:collapse}
  thead th{position:sticky;top:0;background:var(--panel2);text-align:left;font-size:11px;color:var(--muted);
           text-transform:uppercase;letter-spacing:.05em;padding:11px 14px;border-bottom:1px solid var(--line);z-index:2;white-space:nowrap}
  tbody td{padding:11px 14px;border-bottom:1px solid var(--line2);vertical-align:top}
  tbody tr:hover{background:var(--panel2)}
  tr.closed{opacity:.55}
  tr.closed .name{text-decoration:line-through}

  .badge{display:inline-block;min-width:30px;text-align:center;font-weight:800;padding:4px 9px;border-radius:999px;color:#fff;font-size:13px}
  .b9{background:#059669}.b7{background:#16a34a}.b5{background:#d97706}.b3{background:#64748b}
  .name{font-weight:700}
  .sub{color:var(--muted);font-size:12px;margin-top:2px;text-transform:capitalize}
  .rev{color:#b45309;font-size:12px;margin-top:2px}
  html[data-theme="dark"] .rev{color:#fbbf24}
  .contact a{display:block;font-size:13px;margin-bottom:2px;white-space:nowrap}
  .open{display:inline-block;padding:6px 11px;border:1px solid var(--line);border-radius:9px;font-weight:600;font-size:13px;background:var(--panel2);color:var(--ink)}
  .open:hover{border-color:var(--brand);text-decoration:none}
  .when{font-size:11px;color:var(--muted);margin-top:5px}

  /* status select, colour-coded by current value */
  .stsel{font-weight:700;border-radius:9px;padding:7px 9px;border:1px solid var(--line);background:var(--panel2);cursor:pointer;font-size:13px}
  .stsel[data-v="new"]{color:var(--st-new)}
  .stsel[data-v="contacted"]{color:var(--st-contacted);border-color:var(--st-contacted)}
  .stsel[data-v="follow_up"]{color:var(--st-follow);border-color:var(--st-follow)}
  .stsel[data-v="won"]{color:var(--st-won);border-color:var(--st-won)}
  .stsel[data-v="lost"]{color:var(--st-lost);border-color:var(--st-lost)}

  .noteinput{width:100%;min-width:150px;resize:vertical;min-height:34px;max-height:120px;padding:7px 9px;
             border:1px solid var(--line);border-radius:9px;font-size:12px;background:var(--panel2);color:var(--ink);font-family:inherit}
  .noteinput::placeholder{color:var(--muted)}
  .sitewrap{display:flex;flex-direction:column;gap:5px;min-width:140px}
  .siteinput{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:9px;font-size:12px;background:var(--panel2);color:var(--ink);font-family:inherit}
  .siteinput::placeholder{color:var(--muted)}

  /* ---- card view ---- */
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px;padding:16px}
  .lcard{border:1px solid var(--line);border-radius:15px;background:var(--panel);padding:14px;box-shadow:var(--shadow-sm);display:flex;flex-direction:column;gap:9px}
  .lcard.closed{opacity:.6}
  .lc-top{display:flex;align-items:flex-start;gap:10px}
  .lc-top .name{font-size:15px}
  .lc-loc{color:var(--muted);font-size:12px}
  .lc-contact{display:flex;flex-direction:column;gap:3px}
  .lc-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto;padding-top:4px}

  .empty{padding:44px 20px;text-align:center;color:var(--muted)}
  .empty svg{width:34px;height:34px;opacity:.4;margin-bottom:10px}
  .foot{color:var(--muted);font-size:12px;margin:16px 4px;line-height:1.65}

  @media (max-width:820px){
    .stats{grid-template-columns:repeat(2,1fr)}
    .hide-sm{display:none}
    .brand-t p{display:none}
    .btn .lbl{display:none}
    .btn{padding:9px}
  }
</style>
</head>
<body>
<div class="bar"><div class="bar-in">
  <div class="logo">
    <div class="mark"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg></div>
    <div class="brand-t"><h1>Lead Finder</h1><p>__SOURCE__ &middot; generated __DATE__</p></div>
  </div>
  <div class="bar-actions">
    <button class="btn" id="uploadBtn" title="Load your own leads CSV"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg><span class="lbl">Upload CSV</span></button>
    <button class="btn" id="exportBtn" title="Export the current view (with your pipeline) to CSV"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg><span class="lbl">Export</span></button>
    <button class="btn icon" id="themeBtn" title="Toggle light / dark"><svg id="themeIc" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button>
  </div>
</div></div>

<input type="file" id="fileInput" accept=".csv,text/csv" style="display:none">

<div class="wrap">
  __BANNER__
  __CAPNOTE__

  <div class="drop" id="drop">
    <div class="dz-ic"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg></div>
    <div class="dz-grow" id="dropText"><b>Drop your leads CSV here</b> or click to browse &mdash; view your own results, no Python re-run needed. Your file is remembered on this device.</div>
  </div>

  <div class="stats" id="stats"></div>

  <div class="panel">
    <div class="toolbar">
      <div class="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
        <input type="search" id="q" placeholder="Search name, phone, email, city... (press /)">
      </div>
      <select id="niche"><option value="">All niches</option></select>
      <select id="state"><option value="">All states</option></select>
      <select id="status">
        <option value="">All statuses</option>
        <option value="new">New</option><option value="contacted">Contacted</option>
        <option value="follow_up">Follow-up</option><option value="won">Won</option><option value="lost">Lost</option>
      </select>
      <select id="minScore">
        <option value="0">Any score</option><option value="9">Score 9+</option>
        <option value="8">Score 8+</option><option value="7">Score 7+</option><option value="5">Score 5+</option>
      </select>
      <select id="sort">
        <option value="score">Best score</option><option value="reviews">Most reviews</option>
        <option value="rating">Highest rating</option><option value="recent">Recently worked</option>
        <option value="name">Name A-Z</option>
      </select>
      <label class="toggle"><input type="checkbox" id="hideClosed"> Hide won/lost</label>
      <label class="toggle"><input type="checkbox" id="hasSite"> Has website</label>
      <div class="seg" role="group" aria-label="View">
        <button id="viewTable" class="on"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>Table</button>
        <button id="viewCards"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>Cards</button>
      </div>
    </div>

    <div class="meta">
      <span id="count"></span>
      <div class="chips" id="pipeline"></div>
      <span class="barwrap"><span id="progressText"></span><span class="bar2"><i id="progressBar"></i></span></span>
    </div>

    <div id="tableView">
      <div class="tablewrap">
        <table>
          <thead><tr>
            <th>Status</th><th>Score</th><th>Business</th><th class="hide-sm">Location</th>
            <th>Contact</th><th class="hide-sm">Website</th><th>Map</th>
          </tr></thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </div>
    <div id="cardView" style="display:none"><div class="cards" id="cards"></div></div>
  </div>

  <p class="foot">Lead score 1-10 favors: no website, a public email, reviews, rating, and a phone. Your
  <b>pipeline</b> (status, notes, last-contacted) is saved in <i>this browser</i> only &mdash; use
  <b>Export</b> to keep a portable copy or move it to another machine. __FOOTNOTE__</p>
  __ATTRIBUTION__
</div>

<script>
"use strict";
const BAKED = __DATA__;

/* ---------------- status model ---------------- */
const STATUSES = [
  {k:"new",       label:"New"},
  {k:"contacted", label:"Contacted"},
  {k:"follow_up", label:"Follow-up"},
  {k:"won",       label:"Won"},
  {k:"lost",      label:"Lost"},
];
const ST_LABEL = Object.fromEntries(STATUSES.map(s=>[s.k,s.label]));
const ST_COLORVAR = {new:"--st-new",contacted:"--st-contacted",follow_up:"--st-follow",won:"--st-won",lost:"--st-lost"};

/* ---------------- persistence ---------------- */
const OUT_KEY="leadfinder_outreach_v2", OLD_KEY="leadfinder_contacted_v1",
      DATA_KEY="leadfinder_dataset_v1", THEME_KEY="leadfinder_theme", VIEW_KEY="leadfinder_view";

let outreach = loadOutreach();          // id -> {status, note, ts}
function loadOutreach(){
  let o={};
  try{ o = JSON.parse(localStorage.getItem(OUT_KEY)||"{}") || {}; }catch(e){ o={}; }
  // migrate the old simple "contacted" checkbox set, once.
  try{
    const old = JSON.parse(localStorage.getItem(OLD_KEY)||"[]");
    if(Array.isArray(old) && old.length){
      old.forEach(id=>{ if(!o[id]) o[id]={status:"contacted",note:"",ts:""}; });
      localStorage.removeItem(OLD_KEY);
      saveOutreach(o);
    }
  }catch(e){}
  return o;
}
let saveT=null;
function saveOutreach(o){ o=o||outreach; try{localStorage.setItem(OUT_KEY,JSON.stringify(o));}catch(e){} }
function saveSoon(){ clearTimeout(saveT); saveT=setTimeout(()=>saveOutreach(),250); }
function recOf(id){ return outreach[id] || {status:"new",note:"",ts:"",site:""}; }
function setRec(id,patch){
  const r=Object.assign({status:"new",note:"",ts:"",site:""}, outreach[id]||{}, patch);
  if(r.status==="new" && !r.note && !r.site){ delete outreach[id]; } else { outreach[id]=r; }
}

/* ---------------- helpers ---------------- */
const $=id=>document.getElementById(id);
function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function num(x){ const n=parseFloat(x); return isNaN(n)?0:n; }
function stateOf(loc){ const p=String(loc||"").split(","); return p.length>1?p[p.length-1].trim():""; }
function bucket(s){ if(s>=9)return 9; if(s>=7)return 7; if(s>=5)return 5; return 3; }
function today(){ return new Date().toISOString().slice(0,10); }
function fmtDate(s){ return s? s : ""; }

/* ---------------- dataset (baked sample OR uploaded CSV) ---------------- */
let LEADS = BAKED.slice();
let sourceLabel = null;          // filename when uploaded
(function restoreDataset(){
  try{
    const saved=JSON.parse(localStorage.getItem(DATA_KEY)||"null");
    if(saved && Array.isArray(saved.rows) && saved.rows.length){
      LEADS = saved.rows; sourceLabel = saved.name || "your CSV";
    }
  }catch(e){}
})();

/* ---------------- CSV parsing (RFC-4180-ish, handles quotes/newlines) ---- */
function parseCSV(text){
  text = String(text).replace(/^\uFEFF/,"");
  const rows=[]; let row=[], field="", inQ=false, i=0;
  while(i<text.length){
    const c=text[i];
    if(inQ){
      if(c==='"'){ if(text[i+1]==='"'){field+='"';i+=2;continue;} inQ=false;i++;continue; }
      field+=c;i++;continue;
    }
    if(c==='"'){ inQ=true;i++;continue; }
    if(c===','){ row.push(field);field="";i++;continue; }
    if(c==='\r'){ i++;continue; }
    if(c==='\n'){ row.push(field);rows.push(row);row=[];field="";i++;continue; }
    field+=c;i++;
  }
  if(field.length || row.length){ row.push(field); rows.push(row); }
  return rows.filter(r=>r.some(v=>String(v).trim()!==""));
}
function reMaps(name,loc,url){
  const coords=/query=-?\d+\.\d+(,|%2C)-?\d+\.\d+/;
  if(name && (!url || coords.test(url)))
    return "https://www.google.com/maps/search/?api=1&query="+encodeURIComponent(name+", "+loc);
  return url||"";
}
function normStatus(s){
  s=String(s||"").trim().toLowerCase().replace(/[\s-]+/g,"_");
  if(s==="called"||s==="emailed"||s==="contacted") return "contacted";
  if(s==="follow_up"||s==="followup"||s==="follow") return "follow_up";
  if(s==="won"||s==="lost"||s==="new") return s;
  return "";
}
function rowsToLeads(rows){
  if(!rows.length) return [];
  const head=rows[0].map(h=>h.trim().toLowerCase().replace(/\s+/g,"_"));
  const idx=n=>head.indexOf(n);
  const pick=(r,...names)=>{ for(const n of names){ const k=idx(n); if(k>=0 && r[k]!=null && r[k]!=="") return r[k]; } return ""; };
  const out=[];
  for(let i=1;i<rows.length;i++){
    const r=rows[i];
    const name=pick(r,"business_name","name","business");
    const phone=pick(r,"phone","phone_number","telephone");
    if(!name && !phone) continue;
    const loc=pick(r,"search_area","location","city","address");
    const id=pick(r,"place_id","id") || (name+"|"+phone);
    const site=pick(r,"website_url","website","site","built_site");
    out.push({
      id:id, name:name, niche:pick(r,"niche","category","industry"),
      loc:loc, phone:phone, email:pick(r,"email"),
      rating:pick(r,"rating","stars"), reviews:pick(r,"review_count","reviews","ratings"),
      score:pick(r,"lead_score","score"), site:site,
      maps:reMaps(name,loc,pick(r,"google_maps_url","maps","map","maps_url")),
    });
    // round-trip our own exported pipeline columns, if present
    const st=normStatus(pick(r,"status"));
    const nt=pick(r,"note","notes"), lc=pick(r,"last_contacted","contacted_on","date");
    if(st || nt || site){ setRec(id,{status:st||"new",note:nt||"",ts:lc||"",site:site||""}); }
  }
  saveOutreach();
  return out;
}
function loadCsvText(text,fname){
  let leads;
  try{ leads=rowsToLeads(parseCSV(text)); }
  catch(e){ alert("Could not read that CSV: "+e.message); return; }
  if(!leads.length){ alert("No usable rows found. Expected columns like business_name, phone, niche, lead_score..."); return; }
  LEADS=leads; sourceLabel=fname||"your CSV";
  try{ localStorage.setItem(DATA_KEY, JSON.stringify({name:sourceLabel,rows:leads})); }
  catch(e){ /* too big to persist; still usable this session */ }
  buildFilters(); renderStats(); render(); updateDropText();
  window.scrollTo({top:0,behavior:"smooth"});
}
function resetDataset(){
  localStorage.removeItem(DATA_KEY);
  LEADS=BAKED.slice(); sourceLabel=null;
  buildFilters(); renderStats(); render(); updateDropText();
}

/* ---------------- KPI cards + pipeline ---------------- */
function card(n,l,cls,sub){ return `<div class="stat ${cls||''}"><div class="n">${n}</div><div class="l">${l}</div>${sub?`<div class="sub">${sub}</div>`:''}</div>`; }
function worked(l){ const r=recOf(l.id); return r.status && r.status!=="new"; }
function renderStats(){
  const states=[...new Set(LEADS.map(l=>stateOf(l.loc)).filter(Boolean))];
  const niches=[...new Set(LEADS.map(l=>l.niche).filter(Boolean))];
  const avg=LEADS.length?(LEADS.reduce((a,l)=>a+num(l.score),0)/LEADS.length):0;
  const w=LEADS.filter(worked).length;
  const won=LEADS.filter(l=>recOf(l.id).status==="won").length;
  const pct=LEADS.length?Math.round(100*w/LEADS.length):0;
  $('stats').innerHTML =
    card(LEADS.length.toLocaleString(),"Leads","accent") +
    card(avg.toFixed(1),"Avg score") +
    card(states.length,"States",null,niches.length+" niches") +
    card(pct+"%","Worked",null,w.toLocaleString()+" of "+LEADS.length.toLocaleString()) +
    card(won.toLocaleString(),"Won","good");
}

/* ---------------- status <select> ---------------- */
function statusSelect(id){
  const cur=recOf(id).status||"new";
  const opts=STATUSES.map(s=>`<option value="${s.k}" ${s.k===cur?'selected':''}>${s.label}</option>`).join("");
  return `<select class="stsel" data-id="${esc(id)}" data-v="${cur}">${opts}</select>`;
}
function whenLine(id){ const ts=recOf(id).ts; return ts?`<div class="when">last: ${esc(fmtDate(ts))}</div>`:""; }

/* ---------------- row / card markup ---------------- */
function contactHtml(l){
  const tel=String(l.phone||"").replace(/[^0-9+]/g,"");
  const phone=l.phone?`<a href="tel:${esc(tel)}">&#128222; ${esc(l.phone)}</a>`:"";
  const email=l.email?`<a href="mailto:${esc(l.email)}">&#9993; ${esc(l.email)}</a>`:"";
  return (phone+email)||"&mdash;";
}
function ratingHtml(l){
  return (l.rating!=="" && l.rating!=null && num(l.rating)>0)
    ? `<div class="rev">&#9733; ${esc(l.rating)}${l.reviews?` (${esc(l.reviews)})`:''}</div>` : "";
}
function noteInput(id){ return `<textarea class="noteinput" data-id="${esc(id)}" placeholder="Notes...">${esc(recOf(id).note||"")}</textarea>`; }
function siteOf(l){ return recOf(l.id).site || l.site || ""; }
function siteInput(l){
  const v=siteOf(l);
  const open=v?`<a class="open" href="${esc(v)}" target="_blank" rel="noopener">Open &#8599;</a>`:"";
  return `<div class="sitewrap"><input class="siteinput" data-id="${esc(l.id)}" type="url" placeholder="Paste site URL" value="${esc(v)}">${open}</div>`;
}

function rowHtml(l){
  const s=num(l.score), b=bucket(s), st=recOf(l.id).status||"new";
  const map=l.maps?`<a class="open" href="${esc(l.maps)}" target="_blank" rel="noopener">Open</a>`:"&mdash;";
  const closed=(st==="won"||st==="lost");
  return `<tr class="${closed?'closed':''}" data-id="${esc(l.id)}">
    <td>${statusSelect(l.id)}${whenLine(l.id)}</td>
    <td><span class="badge b${b}">${s}</span></td>
    <td><div class="name">${esc(l.name)}</div><div class="sub">${esc(l.niche)}</div>${ratingHtml(l)}</td>
    <td class="hide-sm">${esc(l.loc)}</td>
    <td class="contact">${contactHtml(l)}</td>
    <td class="hide-sm">${siteInput(l)}</td>
    <td>${map}</td>
  </tr>`;
}
function cardHtml(l){
  const s=num(l.score), b=bucket(s), st=recOf(l.id).status||"new";
  const closed=(st==="won"||st==="lost");
  const map=l.maps?`<a class="open" href="${esc(l.maps)}" target="_blank" rel="noopener">Map</a>`:"";
  return `<div class="lcard ${closed?'closed':''}" data-id="${esc(l.id)}">
    <div class="lc-top">
      <span class="badge b${b}">${s}</span>
      <div style="flex:1;min-width:0">
        <div class="name">${esc(l.name)}</div>
        <div class="sub">${esc(l.niche)}</div>
      </div>
    </div>
    <div class="lc-loc">${esc(l.loc)}</div>
    ${ratingHtml(l)}
    <div class="lc-contact">${contactHtml(l)}</div>
    ${noteInput(l.id)}
    ${siteInput(l)}
    <div class="lc-foot">
      <span>${statusSelect(l.id)}${whenLine(l.id)}</span>
      ${map}
    </div>
  </div>`;
}

/* ---------------- filtering + sorting ---------------- */
function currentRows(){
  const q=$('q').value.trim().toLowerCase(), niche=$('niche').value, state=$('state').value,
        statusF=$('status').value, minS=num($('minScore').value), sort=$('sort').value,
        hide=$('hideClosed').checked, hasSite=$('hasSite').checked;
  let r=LEADS.filter(l=>{
    if(niche && l.niche!==niche) return false;
    if(state && stateOf(l.loc)!==state) return false;
    const st=recOf(l.id).status||"new";
    if(statusF && st!==statusF) return false;
    if(hide && (st==="won"||st==="lost")) return false;
    if(hasSite && !siteOf(l)) return false;
    if(num(l.score)<minS) return false;
    if(q){ const hay=(l.name+" "+l.phone+" "+(l.email||"")+" "+l.loc+" "+(recOf(l.id).note||"")+" "+siteOf(l)).toLowerCase(); if(!hay.includes(q)) return false; }
    return true;
  });
  r.sort((a,b)=>{
    if(sort==='name') return String(a.name).localeCompare(String(b.name));
    if(sort==='recent') return String(recOf(b.id).ts||"").localeCompare(String(recOf(a.id).ts||""));
    const k=sort==='reviews'?'reviews':sort==='rating'?'rating':'score';
    return num(b[k])-num(a[k]);
  });
  return r;
}

/* ---------------- pipeline chips + progress ---------------- */
function renderPipeline(){
  const counts={new:0,contacted:0,follow_up:0,won:0,lost:0};
  LEADS.forEach(l=>{ counts[recOf(l.id).status||"new"]++; });
  $('pipeline').innerHTML = STATUSES.map(s=>
    `<span class="chip"><span class="dot" style="background:var(${ST_COLORVAR[s.k]})"></span>${s.label} ${counts[s.k].toLocaleString()}</span>`).join("");
  const w=LEADS.filter(worked).length;
  $('progressText').textContent=`${w.toLocaleString()} / ${LEADS.length.toLocaleString()} worked`;
  $('progressBar').style.width=(LEADS.length?100*w/LEADS.length:0)+'%';
}

/* ---------------- main render ---------------- */
let view = (localStorage.getItem(VIEW_KEY)==="cards") ? "cards" : "table";
function render(){
  const r=currentRows();
  $('count').textContent=`Showing ${r.length.toLocaleString()} of ${LEADS.length.toLocaleString()} leads`;
  if(view==="cards"){
    $('tableView').style.display="none"; $('cardView').style.display="";
    $('cards').innerHTML = r.length ? r.map(cardHtml).join("")
      : `<div class="empty" style="grid-column:1/-1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg><div>No matches. Try clearing a filter.</div></div>`;
  }else{
    $('cardView').style.display="none"; $('tableView').style.display="";
    $('rows').innerHTML = r.length ? r.map(rowHtml).join("")
      : `<tr><td colspan="7" class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg><div>No matches. Try clearing a filter.</div></td></tr>`;
  }
  renderPipeline();
}

/* ---------------- filter <select> population ---------------- */
function buildFilters(){
  const niches=[...new Set(LEADS.map(l=>l.niche).filter(Boolean))].sort();
  const states=[...new Set(LEADS.map(l=>stateOf(l.loc)).filter(Boolean))].sort();
  $('niche').innerHTML='<option value="">All niches</option>'+niches.map(n=>`<option value="${esc(n)}">${esc(n)}</option>`).join("");
  $('state').innerHTML='<option value="">All states</option>'+states.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join("");
}

/* ---------------- live edits (status + notes), event-delegated ---------- */
document.addEventListener('change', e=>{
  if(e.target.classList.contains('stsel')){
    const id=e.target.getAttribute('data-id'), v=e.target.value, prev=recOf(id);
    const ts=(v==="new")?"":(prev.ts||today());   // stamp first time it leaves "new"
    setRec(id,{status:v,ts:ts});
    saveSoon();
    renderStats();
    render();   // keeps the "last:" date, closed styling, pipeline + any status filter in sync
  } else if(e.target.classList.contains('siteinput')){
    setRec(e.target.getAttribute('data-id'),{site:e.target.value.trim()});
    saveSoon();
    render();   // refresh the "Open" link once they finish editing
  }
});
document.addEventListener('input', e=>{
  if(e.target.classList.contains('noteinput')){
    setRec(e.target.getAttribute('data-id'),{note:e.target.value});
    saveSoon();
  } else if(e.target.classList.contains('siteinput')){
    setRec(e.target.getAttribute('data-id'),{site:e.target.value.trim()});
    saveSoon();
  }
});

/* ---------------- toolbar wiring ---------------- */
['q','niche','state','status','minScore','sort','hideClosed','hasSite'].forEach(id=>{
  $(id).addEventListener('input',render); $(id).addEventListener('change',render);
});
function setView(v){
  view=v; localStorage.setItem(VIEW_KEY,v);
  $('viewTable').classList.toggle('on',v==="table");
  $('viewCards').classList.toggle('on',v==="cards");
  render();
}
$('viewTable').addEventListener('click',()=>setView("table"));
$('viewCards').addEventListener('click',()=>setView("cards"));

/* ---------------- theme ---------------- */
function setTheme(t){
  document.documentElement.setAttribute('data-theme',t);
  localStorage.setItem(THEME_KEY,t);
  $('themeIc').innerHTML = (t==="dark")
    ? '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'
    : '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
}
setTheme(localStorage.getItem(THEME_KEY)==="dark"?"dark":"light");
$('themeBtn').addEventListener('click',()=>setTheme(document.documentElement.getAttribute('data-theme')==="dark"?"light":"dark"));

/* ---------------- CSV upload (button + drag/drop) ---------------- */
function updateDropText(){
  if(sourceLabel){
    $('dropText').innerHTML = `<span class="pill">&#128196; ${esc(sourceLabel)} &middot; ${LEADS.length.toLocaleString()} leads</span> &nbsp; <button class="linkbtn" id="resetBtn">Reset to sample data</button> &nbsp;&middot;&nbsp; drop another CSV to replace`;
    const rb=$('resetBtn'); if(rb) rb.addEventListener('click',resetDataset);
  }else{
    $('dropText').innerHTML = `<b>Drop your leads CSV here</b> or click to browse &mdash; view your own results, no Python re-run needed. Your file is remembered on this device.`;
  }
}
function handleFile(file){
  if(!file) return;
  const rd=new FileReader();
  rd.onload=()=>loadCsvText(rd.result,file.name);
  rd.onerror=()=>alert("Could not read that file.");
  rd.readAsText(file);
}
$('uploadBtn').addEventListener('click',()=>$('fileInput').click());
$('drop').addEventListener('click',e=>{ if(e.target.id!=='resetBtn') $('fileInput').click(); });
$('fileInput').addEventListener('change',e=>{ if(e.target.files[0]) handleFile(e.target.files[0]); e.target.value=""; });
['dragenter','dragover'].forEach(ev=>$('drop').addEventListener(ev,e=>{e.preventDefault();$('drop').classList.add('drag');}));
['dragleave','drop'].forEach(ev=>$('drop').addEventListener(ev,e=>{e.preventDefault();$('drop').classList.remove('drag');}));
$('drop').addEventListener('drop',e=>{ const f=e.dataTransfer.files[0]; if(f) handleFile(f); });
// allow dropping anywhere on the page too
window.addEventListener('dragover',e=>e.preventDefault());
window.addEventListener('drop',e=>{ e.preventDefault(); if(e.target.closest('#drop')) return; const f=e.dataTransfer.files[0]; if(f) handleFile(f); });

/* ---------------- CSV export (current filtered view + pipeline) -------- */
function csvCell(v){ v=String(v==null?"":v); return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v; }
$('exportBtn').addEventListener('click',()=>{
  const rows=currentRows();
  const cols=["business_name","niche","phone","email","location","rating","review_count","lead_score","status","note","last_contacted","website_url","google_maps_url"];
  const lines=[cols.join(",")];
  rows.forEach(l=>{ const r=recOf(l.id);
    lines.push([l.name,l.niche,l.phone,l.email,l.loc,l.rating,l.reviews,l.score,
                ST_LABEL[r.status||"new"],r.note||"",r.ts||"",siteOf(l),l.maps].map(csvCell).join(","));
  });
  const blob=new Blob([lines.join("\n")],{type:"text/csv;charset=utf-8"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  a.download="leads_export_"+today()+".csv";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
});

/* ---------------- keyboard: "/" focuses search ---------------- */
document.addEventListener('keydown',e=>{
  if(e.key==='/' && document.activeElement.tagName!=='INPUT' && document.activeElement.tagName!=='TEXTAREA' && document.activeElement.tagName!=='SELECT'){
    e.preventDefault(); $('q').focus();
  }
});

/* ---------------- boot ---------------- */
buildFilters(); renderStats(); setView(view); updateDropText();
</script>
</body>
</html>
"""


def render_html(leads, is_demo, source_label, attribution_html="", total_count=None):
    """Turn the leads into the final HTML string."""

    def maps_link(r):
        url = r.get("google_maps_url", "")
        name = r.get("business_name", "")
        loc = r.get("address", "") or r.get("search_area", "")
        if name and (not url or re.search(r"query=-?\d+\.\d+(%2C|,)-?\d+\.\d+", url)):
            return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(f"{name}, {loc}")
        return url

    slim = [{
        "id": r.get("place_id", "") or (r.get("business_name", "") + "|" + r.get("phone", "")),
        "name": r.get("business_name", ""),
        "niche": r.get("niche", ""),
        "loc": r.get("search_area", "") or r.get("address", ""),
        "phone": r.get("phone", ""),
        "email": r.get("email", ""),
        "rating": r.get("rating", ""),
        "reviews": r.get("review_count", 0),
        "score": r.get("lead_score", 0),
        "site": r.get("website_url", "") or r.get("website", ""),
        "maps": maps_link(r),
    } for r in leads]

    data_json = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")

    if is_demo:
        banner = ('<div class="note">&#9888; <b>Sample data</b> &mdash; invented businesses with fake 555 '
                  'numbers, shown so you can see the layout. Drop in your own CSV above, or do a live run for real leads.</div>')
        footnote = "Showing SAMPLE data &mdash; not real businesses."
    else:
        banner = ""
        footnote = "Verify a business actually has no website before pitching it."

    capnote = ""
    if total_count and total_count > len(leads):
        capnote = (f'<div class="note">Showing the top <b>{len(leads):,}</b> highest-scoring leads of '
                   f'<b>{total_count:,}</b> total &mdash; the full list is in the CSV.</div>')

    page = PAGE_TEMPLATE
    page = page.replace("__DATA__", data_json)
    page = page.replace("__BANNER__", banner)
    page = page.replace("__CAPNOTE__", capnote)
    page = page.replace("__FOOTNOTE__", footnote)
    page = page.replace("__SOURCE__", html.escape(source_label))
    page = page.replace("__DATE__", datetime.date.today().isoformat())
    page = page.replace("__ATTRIBUTION__", attribution_html)
    return page


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build a single-file web dashboard from your leads.")
    parser.add_argument("--csv", help="Load leads from this CSV. Default: generate free sample data.")
    parser.add_argument("--states", help='Sample data only: limit to these states, e.g. "NJ,NY".')
    parser.add_argument("--out", default="dashboard.html", help="Output HTML file (default dashboard.html).")
    parser.add_argument("--no-open", action="store_true", help="Build the file but don't open a browser.")
    parser.add_argument("--max-rows", type=int, default=2000,
                        help="Max leads to embed in the page (top by score; default 2000).")
    args = parser.parse_args()

    if args.csv:
        if not os.path.exists(args.csv):
            print(f"ERROR: CSV not found: {args.csv}")
            sys.exit(1)
        leads = load_leads_from_csv(args.csv)
        is_demo = "demo" in os.path.basename(args.csv).lower()
        source = f"{len(leads):,} leads from {os.path.basename(args.csv)}"
    else:
        leads = generate_sample_leads(args.states)
        is_demo = True
        source = f"{len(leads):,} sample leads (demo data)"

    leads.sort(key=lambda r: (int(float(r.get("lead_score") or 0)),
                              int(float(r.get("review_count") or 0))), reverse=True)
    total_count = len(leads)
    if total_count > args.max_rows:        # keep the page fast for huge datasets
        leads = leads[:args.max_rows]

    attribution = ""
    if args.csv and "osm" in os.path.basename(args.csv).lower():
        attribution = ('<p class="foot">Business data &copy; '
                       '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">'
                       'OpenStreetMap</a> contributors, licensed under '
                       '<a href="https://opendatacommons.org/licenses/odbl/" target="_blank" rel="noopener">ODbL</a>.</p>')

    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(render_html(leads, is_demo, source, attribution, total_count))

    path = os.path.abspath(args.out)
    print(f"Built dashboard ({len(leads):,} of {total_count:,} leads shown) -> {path}")
    if not args.no_open:
        try:
            import webbrowser
            webbrowser.open("file://" + path)
            print("Opening it in your browser...")
        except Exception:
            print("Open that file in your browser to view it.")


if __name__ == "__main__":
    main()
