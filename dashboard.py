#!/usr/bin/env python3
"""
Lead Finder -- Web Dashboard builder
====================================

Turns leads into a single, self-contained HTML page (no server, no internet, no
installs). Features: search, niche/state/score filters, sortable lead scores,
click-to-call / click-to-email, and a "contacted" checkbox that PERSISTS in the
browser (localStorage) so you can tick off businesses as you reach out.

USAGE
-----
  python3 dashboard.py                              # free SAMPLE data, opens it
  python3 dashboard.py --states "NJ,NY"             # sample data, those states
  python3 dashboard.py --csv us_website_leads_osm.csv   # your REAL results
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
# Page template  (plain string with __TOKENS__ -- not an f-string)
# -----------------------------------------------------------------------------

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lead Finder</title>
<style>
  :root{
    --bg:#eef1f6; --card:#ffffff; --ink:#0f172a; --muted:#64748b; --line:#e7eaf0;
    --brand:#4f46e5; --brand2:#7c3aed; --ring:rgba(79,70,229,.15);
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
  a{color:var(--brand);text-decoration:none}
  a:hover{text-decoration:underline}

  .hero{background:linear-gradient(120deg,var(--brand),var(--brand2));color:#fff;padding:28px 20px 64px}
  .hero-in{max-width:1200px;margin:0 auto}
  .hero h1{margin:0;font-size:26px;font-weight:800;letter-spacing:-.02em}
  .hero p{margin:6px 0 0;opacity:.9;font-size:14px}

  .wrap{max-width:1200px;margin:-40px auto 60px;padding:0 16px}

  .stats{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:18px}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px;
        box-shadow:0 6px 20px rgba(15,23,42,.05)}
  .stat .n{font-size:26px;font-weight:800;line-height:1}
  .stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:6px}
  .stat.accent .n{color:var(--brand)}
  .stat.good .n{color:#16a34a}

  .note{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;padding:10px 14px;border-radius:12px;
        font-size:13px;margin-bottom:16px}

  .panel{background:var(--card);border:1px solid var(--line);border-radius:18px;
         box-shadow:0 8px 30px rgba(15,23,42,.06);overflow:hidden}
  .toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:14px;border-bottom:1px solid var(--line);
           position:sticky;top:0;background:var(--card);z-index:5}
  .search{position:relative;flex:1 1 260px;min-width:180px}
  .search input{width:100%;padding:11px 12px 11px 36px;border:1px solid var(--line);border-radius:11px;font-size:14px;background:#fff}
  .search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.5}
  select,.toggle{padding:11px 12px;border:1px solid var(--line);border-radius:11px;font-size:14px;background:#fff;color:var(--ink)}
  input:focus,select:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 4px var(--ring)}
  .toggle{display:inline-flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
  .toggle input{width:16px;height:16px;accent-color:var(--brand)}

  .meta{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;color:var(--muted);font-size:13px;
        border-bottom:1px solid var(--line);background:#fbfcfe}
  .bar{height:6px;width:160px;background:#eef1f6;border-radius:999px;overflow:hidden}
  .bar>i{display:block;height:100%;background:#16a34a;width:0}

  .tablewrap{max-height:72vh;overflow:auto}
  table{width:100%;border-collapse:collapse}
  thead th{position:sticky;top:0;background:#fbfcfe;text-align:left;font-size:11px;color:var(--muted);
           text-transform:uppercase;letter-spacing:.05em;padding:12px 14px;border-bottom:1px solid var(--line);z-index:2}
  tbody td{padding:12px 14px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:middle}
  tbody tr:hover{background:#f8faff}
  tr.done{opacity:.5}
  tr.done .name{text-decoration:line-through}

  .cb input{width:18px;height:18px;accent-color:#16a34a;cursor:pointer}
  .badge{display:inline-block;min-width:30px;text-align:center;font-weight:800;padding:4px 9px;border-radius:999px;color:#fff;font-size:13px}
  .b9{background:#059669}.b7{background:#16a34a}.b5{background:#d97706}.b3{background:#64748b}
  .name{font-weight:700}
  .sub{color:var(--muted);font-size:12px;margin-top:2px;text-transform:capitalize}
  .rev{color:#b45309;font-size:12px;margin-top:2px}
  .contact a{display:block;font-size:13px}
  .open{display:inline-block;padding:7px 12px;border:1px solid var(--line);border-radius:10px;font-weight:600;font-size:13px;background:#fff}
  .open:hover{border-color:var(--brand);text-decoration:none;background:#f5f5ff}
  .empty{padding:34px;text-align:center;color:var(--muted)}
  .foot{color:var(--muted);font-size:12px;margin:16px 4px;line-height:1.6}

  @media (max-width:820px){
    .stats{grid-template-columns:repeat(2,1fr)}
    .hide-sm{display:none}
  }
</style>
</head>
<body>
<div class="hero"><div class="hero-in">
  <h1>Lead Finder</h1>
  <p>__SOURCE__ &middot; generated __DATE__ &middot; tick off businesses as you contact them</p>
</div></div>

<div class="wrap">
  __BANNER__
  __CAPNOTE__
  <div class="stats" id="stats"></div>

  <div class="panel">
    <div class="toolbar">
      <div class="search">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
        <input type="search" id="q" placeholder="Search name, phone, email, city...">
      </div>
      <select id="niche"><option value="">All niches</option></select>
      <select id="state"><option value="">All states</option></select>
      <select id="minScore">
        <option value="0">Any score</option><option value="9">Score 9+</option>
        <option value="8">Score 8+</option><option value="7">Score 7+</option><option value="5">Score 5+</option>
      </select>
      <select id="sort">
        <option value="score">Best score</option><option value="reviews">Most reviews</option>
        <option value="rating">Highest rating</option><option value="name">Name A-Z</option>
      </select>
      <label class="toggle"><input type="checkbox" id="hideDone"> Hide contacted</label>
    </div>

    <div class="meta">
      <span id="count"></span>
      <span style="display:flex;align-items:center;gap:8px">
        <span id="progressText"></span><span class="bar"><i id="progressBar"></i></span>
      </span>
    </div>

    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>Done</th><th>Score</th><th>Business</th><th class="hide-sm">Location</th>
          <th>Contact</th><th>Map</th>
        </tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </div>

  <p class="foot">Lead score 1-10 favors: no website, a public email, reviews, rating, and a phone. The
  <b>Contacted</b> checkmarks are saved in <i>this browser</i> only. __FOOTNOTE__</p>
  __ATTRIBUTION__
</div>

<script>
const LEADS = __DATA__;
const KEY = 'leadfinder_contacted_v1';
let contacted = (function(){ try{return new Set(JSON.parse(localStorage.getItem(KEY)||'[]'));}catch(e){return new Set();} })();
function saveContacted(){ try{localStorage.setItem(KEY, JSON.stringify([...contacted]));}catch(e){} }

function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function num(x){ const n=parseFloat(x); return isNaN(n)?0:n; }
function stateOf(loc){ const p=String(loc||"").split(","); return p.length>1?p[p.length-1].trim():""; }
function bucket(s){ if(s>=9)return 9; if(s>=7)return 7; if(s>=5)return 5; return 3; }
function card(n,l,cls){ return `<div class="stat ${cls||''}"><div class="n">${n}</div><div class="l">${l}</div></div>`; }

const $=id=>document.getElementById(id);

(function setup(){
  const niches=[...new Set(LEADS.map(l=>l.niche).filter(Boolean))].sort();
  const states=[...new Set(LEADS.map(l=>stateOf(l.loc)).filter(Boolean))].sort();
  niches.forEach(n=>$('niche').appendChild(new Option(n,n)));
  states.forEach(s=>$('state').appendChild(new Option(s,s)));
  const avg=LEADS.length?LEADS.reduce((a,l)=>a+num(l.score),0)/LEADS.length:0;
  const withEmail=LEADS.filter(l=>l.email).length;
  $('stats').innerHTML =
    card(LEADS.length.toLocaleString(),'Leads shown','accent') +
    card(states.length,'States') +
    card(niches.length,'Niches') +
    card(withEmail.toLocaleString(),'With email') +
    card('<span id="doneN">0</span>','Contacted','good');
})();

function rowHtml(l){
  const s=num(l.score), b=bucket(s), done=contacted.has(l.id);
  const tel=String(l.phone||"").replace(/[^0-9+]/g,"");
  const phone=l.phone?`<a href="tel:${esc(tel)}">&#128222; ${esc(l.phone)}</a>`:"";
  const email=l.email?`<a href="mailto:${esc(l.email)}">&#9993; ${esc(l.email)}</a>`:"";
  const contact=(phone+email)||"&mdash;";
  const rev=(l.rating!=="" && l.rating!=null && num(l.rating)>0)
      ? `<div class="rev">&#9733; ${esc(l.rating)}${l.reviews?` (${esc(l.reviews)})`:''}</div>` : "";
  const map=l.maps?`<a class="open" href="${esc(l.maps)}" target="_blank" rel="noopener">Open</a>`:"&mdash;";
  return `<tr class="${done?'done':''}" data-id="${esc(l.id)}">
    <td class="cb"><input type="checkbox" class="done-cb" ${done?'checked':''}></td>
    <td><span class="badge b${b}">${s}</span></td>
    <td><div class="name">${esc(l.name)}</div><div class="sub">${esc(l.niche)}</div>${rev}</td>
    <td class="hide-sm">${esc(l.loc)}</td>
    <td class="contact">${contact}</td>
    <td>${map}</td>
  </tr>`;
}

function currentRows(){
  const q=$('q').value.trim().toLowerCase(), niche=$('niche').value, state=$('state').value,
        minS=num($('minScore').value), sort=$('sort').value, hide=$('hideDone').checked;
  let r=LEADS.filter(l=>{
    if(niche&&l.niche!==niche) return false;
    if(state&&stateOf(l.loc)!==state) return false;
    if(num(l.score)<minS) return false;
    if(hide&&contacted.has(l.id)) return false;
    if(q){ const hay=(l.name+" "+l.phone+" "+(l.email||"")+" "+l.loc).toLowerCase(); if(!hay.includes(q)) return false; }
    return true;
  });
  r.sort((a,b)=>{ if(sort==='name')return String(a.name).localeCompare(String(b.name));
    const k=sort==='reviews'?'reviews':sort==='rating'?'rating':'score'; return num(b[k])-num(a[k]); });
  return r;
}

function updateProgress(){
  const done=LEADS.filter(l=>contacted.has(l.id)).length;
  $('doneN').textContent=done.toLocaleString();
  $('progressText').textContent=`${done.toLocaleString()} / ${LEADS.length.toLocaleString()} contacted`;
  $('progressBar').style.width=(LEADS.length?100*done/LEADS.length:0)+'%';
}

function render(){
  const r=currentRows();
  $('count').textContent=`Showing ${r.length.toLocaleString()} of ${LEADS.length.toLocaleString()} leads`;
  $('rows').innerHTML = r.length ? r.map(rowHtml).join('') : `<tr><td colspan="6" class="empty">No matches.</td></tr>`;
  updateProgress();
}

// One delegated handler for all the contacted checkboxes.
$('rows').addEventListener('change', e=>{
  if(!e.target.classList.contains('done-cb')) return;
  const tr=e.target.closest('tr'), id=tr.getAttribute('data-id');
  if(e.target.checked) contacted.add(id); else contacted.delete(id);
  saveContacted();
  if($('hideDone').checked) render(); else { tr.classList.toggle('done', e.target.checked); updateProgress(); }
});

['q','niche','state','minScore','sort','hideDone'].forEach(id=>{
  $(id).addEventListener('input',render); $(id).addEventListener('change',render);
});
render();
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
        "maps": maps_link(r),
    } for r in leads]

    data_json = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")

    if is_demo:
        banner = ('<div class="note">&#9888; <b>Sample data</b> &mdash; invented businesses with fake 555 '
                  'numbers, shown so you can see the layout. Real leads come from a live run.</div>')
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
