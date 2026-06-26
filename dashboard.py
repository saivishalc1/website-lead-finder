#!/usr/bin/env python3
"""
Lead Finder -- Web Dashboard builder
====================================

Turns leads into a single, self-contained HTML page you can open in any browser
(no server, no internet, no installs). It has a search box, niche + state
filters, sortable lead-score badges, and click-to-call phone links.

USAGE
-----
  python3 dashboard.py                         # build from free SAMPLE data, then open it
  python3 dashboard.py --states "NJ,NY"        # sample data, just those states
  python3 dashboard.py --csv us_website_leads.csv   # build from your REAL results
  python3 dashboard.py --no-open               # build dashboard.html but don't open it

It writes "dashboard.html" next to this script.
"""

import argparse
import csv
import datetime
import html
import json
import os
import sys


# -----------------------------------------------------------------------------
# Get the leads (either from a CSV, or generate free sample data)
# -----------------------------------------------------------------------------

def load_leads_from_csv(path):
    """Read leads from a CSV produced by find_leads.py."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def generate_sample_leads(states_arg=None):
    """
    Reuse find_leads.py's demo generator to make realistic SAMPLE leads
    (invented data -- 555 phone numbers). Optionally limit to some states.
    """
    import find_leads as f  # stdlib-only to import now that 'requests' is lazy

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
# Build the HTML page
# -----------------------------------------------------------------------------

# The whole page is one template with a few __TOKENS__ we replace below.
# (Plain string -- NOT an f-string -- so the CSS/JS braces need no escaping.)
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lead Finder Dashboard</title>
<style>
  :root { --bg:#f5f6f8; --card:#fff; --ink:#1f2430; --muted:#6b7280; --line:#e5e7eb; --brand:#2563eb; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--ink); }
  .wrap { max-width:1120px; margin:0 auto; padding:24px 16px 64px; }
  h1 { font-size:24px; margin:0 0 4px; }
  .sub { color:var(--muted); margin:0 0 18px; font-size:13px; }
  .demo-banner { background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; padding:11px 14px; border-radius:10px; font-size:13px; margin:0 0 18px; }
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:0 0 18px; }
  .stat { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  .stat .n { font-size:24px; font-weight:700; }
  .stat .l { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
  .controls { display:flex; flex-wrap:wrap; gap:10px; margin:0 0 14px; }
  .controls input, .controls select { padding:9px 11px; border:1px solid var(--line); border-radius:9px; font-size:14px; background:#fff; color:var(--ink); }
  .controls input[type=search] { flex:1 1 240px; min-width:180px; }
  .count { color:var(--muted); font-size:13px; margin:0 0 8px; }
  table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
  thead th { text-align:left; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; padding:11px 12px; border-bottom:1px solid var(--line); background:#fafafa; }
  tbody td { padding:11px 12px; border-bottom:1px solid var(--line); font-size:14px; vertical-align:middle; }
  tbody tr:last-child td { border-bottom:none; }
  tbody tr:hover { background:#f9fafb; }
  .badge { display:inline-block; min-width:30px; text-align:center; font-weight:700; padding:3px 8px; border-radius:999px; color:#fff; font-size:13px; }
  .s4 { background:#16a34a; } .s3 { background:#65a30d; } .s2 { background:#d97706; } .s1 { background:#9ca3af; }
  .name { font-weight:600; }
  .niche { color:var(--muted); font-size:12px; text-transform:capitalize; }
  a { color:var(--brand); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .foot { color:var(--muted); font-size:12px; margin-top:18px; line-height:1.5; }
  @media (max-width:680px){ .stats{grid-template-columns:repeat(2,1fr);} .hide-sm{display:none;} }
</style>
</head>
<body>
<div class="wrap">
  <h1>Lead Finder &mdash; Businesses With No Website</h1>
  <p class="sub">__SOURCE__ &middot; generated __DATE__</p>
  __BANNER__
  <div class="stats" id="stats"></div>
  <div class="controls">
    <input type="search" id="q" placeholder="Search name, phone, or city...">
    <select id="niche"><option value="">All niches</option></select>
    <select id="state"><option value="">All states</option></select>
    <select id="minScore">
      <option value="0">Any score</option>
      <option value="9">Score 9+</option>
      <option value="8">Score 8+</option>
      <option value="7">Score 7+</option>
      <option value="5">Score 5+</option>
    </select>
    <select id="sort">
      <option value="score">Sort: best score</option>
      <option value="reviews">Sort: most reviews</option>
      <option value="rating">Sort: highest rating</option>
      <option value="name">Sort: name A-Z</option>
    </select>
  </div>
  <p class="count" id="count"></p>
  <table>
    <thead><tr>
      <th>Score</th><th>Business</th><th>Location</th>
      <th class="hide-sm">Rating</th><th class="hide-sm">Reviews</th>
      <th>Phone</th><th>Map</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <p class="foot">Lead score 1-10 = no website (+4) + reviews + rating + phone + niche. Higher = better prospect. __FOOTNOTE__</p>
  __ATTRIBUTION__
</div>
<script>
const LEADS = __DATA__;
function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function num(x){ const n = parseFloat(x); return isNaN(n) ? 0 : n; }
function stateOf(loc){ const p = String(loc||"").split(","); return p.length>1 ? p[p.length-1].trim() : ""; }
function bucket(s){ if(s>=9) return 4; if(s>=7) return 3; if(s>=5) return 2; return 1; }
function card(n,l){ return `<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`; }

// Fill the niche/state dropdowns and the stat cards from the data.
(function(){
  const niches = [...new Set(LEADS.map(l=>l.niche).filter(Boolean))].sort();
  const states = [...new Set(LEADS.map(l=>stateOf(l.loc)).filter(Boolean))].sort();
  const ns = document.getElementById('niche'), ss = document.getElementById('state');
  niches.forEach(n => { const o=document.createElement('option'); o.value=n; o.textContent=n; ns.appendChild(o); });
  states.forEach(s => { const o=document.createElement('option'); o.value=s; o.textContent=s; ss.appendChild(o); });
  const avg = LEADS.length ? LEADS.reduce((a,l)=>a+num(l.score),0)/LEADS.length : 0;
  document.getElementById('stats').innerHTML =
    card(LEADS.length.toLocaleString(),'Leads') + card(states.length,'States') +
    card(niches.length,'Niches') + card(avg.toFixed(1),'Avg score');
})();

function rowHtml(l){
  const s = num(l.score), b = bucket(s);
  const tel = String(l.phone||"").replace(/[^0-9+]/g,"");
  const phone = l.phone ? `<a href="tel:${esc(tel)}">${esc(l.phone)}</a>` : "&mdash;";
  const map = l.maps ? `<a href="${esc(l.maps)}" target="_blank" rel="noopener">Open</a>` : "&mdash;";
  const rating = (l.rating==="" || l.rating==null) ? "&mdash;" : esc(l.rating);
  return `<tr>
    <td><span class="badge s${b}">${s}</span></td>
    <td><div class="name">${esc(l.name)}</div><div class="niche">${esc(l.niche)}</div></td>
    <td>${esc(l.loc)}</td>
    <td class="hide-sm">${rating}</td>
    <td class="hide-sm">${esc(l.reviews)}</td>
    <td>${phone}</td>
    <td>${map}</td>
  </tr>`;
}

function render(){
  const q = document.getElementById('q').value.trim().toLowerCase();
  const niche = document.getElementById('niche').value;
  const state = document.getElementById('state').value;
  const minS = num(document.getElementById('minScore').value);
  const sort = document.getElementById('sort').value;

  let rows = LEADS.filter(l => {
    if (niche && l.niche !== niche) return false;
    if (state && stateOf(l.loc) !== state) return false;
    if (num(l.score) < minS) return false;
    if (q) { const hay = (l.name+" "+l.phone+" "+l.loc).toLowerCase(); if (!hay.includes(q)) return false; }
    return true;
  });
  rows.sort((a,b) => {
    if (sort === 'name') return String(a.name).localeCompare(String(b.name));
    const k = sort==='reviews' ? 'reviews' : sort==='rating' ? 'rating' : 'score';
    return num(b[k]) - num(a[k]);
  });

  document.getElementById('count').textContent =
    `Showing ${rows.length.toLocaleString()} of ${LEADS.length.toLocaleString()} leads`;
  document.getElementById('rows').innerHTML =
    rows.map(rowHtml).join('') ||
    `<tr><td colspan="7" style="padding:24px;text-align:center;color:#6b7280">No matches.</td></tr>`;
}

['q','niche','state','minScore','sort'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('input', render);
  el.addEventListener('change', render);
});
render();
</script>
</body>
</html>
"""


def render_html(leads, is_demo, source_label, attribution_html=""):
    """Turn the leads into the final HTML string."""
    # Keep only the fields the page needs, with short keys (smaller file).
    slim = [{
        "name": r.get("business_name", ""),
        "niche": r.get("niche", ""),
        "loc": r.get("search_area", "") or r.get("address", ""),
        "phone": r.get("phone", ""),
        "rating": r.get("rating", ""),
        "reviews": r.get("review_count", 0),
        "score": r.get("lead_score", 0),
        "maps": r.get("google_maps_url", ""),
    } for r in leads]

    # json.dumps safely escapes the data; the "</" guard prevents a stray
    # "</script>" inside any value from breaking out of the <script> tag.
    data_json = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")

    if is_demo:
        banner = ('<div class="demo-banner">&#9888; <b>Sample data</b> &mdash; these are '
                  'invented businesses with fake 555 phone numbers, shown so you can see the '
                  'layout. Real, callable leads require a live run with a Google API key.</div>')
        footnote = "Showing SAMPLE data &mdash; not real businesses."
    else:
        banner = ""
        footnote = "Tip: verify each business actually has no website before contacting them."

    page = PAGE_TEMPLATE
    page = page.replace("__DATA__", data_json)
    page = page.replace("__BANNER__", banner)
    page = page.replace("__FOOTNOTE__", footnote)
    page = page.replace("__SOURCE__", html.escape(source_label))
    page = page.replace("__DATE__", datetime.date.today().isoformat())
    page = page.replace("__ATTRIBUTION__", attribution_html)
    return page


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build a single-file web dashboard from your leads.")
    parser.add_argument("--csv", help="Load leads from this CSV (e.g. us_website_leads.csv). "
                                       "Default: generate free sample data.")
    parser.add_argument("--states", help='Sample data only: limit to these states, e.g. "NJ,NY".')
    parser.add_argument("--out", default="dashboard.html", help="Output HTML file (default dashboard.html).")
    parser.add_argument("--no-open", action="store_true", help="Build the file but don't open a browser.")
    args = parser.parse_args()

    # Decide where the leads come from.
    if args.csv:
        if not os.path.exists(args.csv):
            print(f"ERROR: CSV not found: {args.csv}")
            sys.exit(1)
        leads = load_leads_from_csv(args.csv)
        is_demo = "demo" in os.path.basename(args.csv).lower()
        source = f"{len(leads)} leads from {os.path.basename(args.csv)}"
    else:
        leads = generate_sample_leads(args.states)
        is_demo = True
        source = f"{len(leads)} sample leads (demo data)"

    # Best leads first.
    leads.sort(key=lambda r: (int(float(r.get("lead_score") or 0)),
                              int(float(r.get("review_count") or 0))), reverse=True)

    # OpenStreetMap data must be credited (ODbL license) when published.
    attribution = ""
    if args.csv and "osm" in os.path.basename(args.csv).lower():
        attribution = ('<p class="foot">Business data &copy; '
                       '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">'
                       'OpenStreetMap</a> contributors, licensed under '
                       '<a href="https://opendatacommons.org/licenses/odbl/" target="_blank" rel="noopener">ODbL</a>.</p>')

    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(render_html(leads, is_demo, source, attribution))

    path = os.path.abspath(args.out)
    print(f"Built dashboard with {len(leads)} leads -> {path}")

    if not args.no_open:
        try:
            import webbrowser
            webbrowser.open("file://" + path)
            print("Opening it in your browser...")
        except Exception:
            print("Open that file in your browser to view it.")


if __name__ == "__main__":
    main()
