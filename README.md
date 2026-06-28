# US Website Lead Finder (all 50 states + DC)

A beginner-friendly Python script that uses the **official Google Places API**
(not Google scraping) to find local service businesses **anywhere in the US that
have no website listed** — strong leads if you sell websites / online presence.

It saves the results to a CSV with a 1–10 **lead score** so you can work the
best opportunities first, plus a `search_area` column so you can filter by state.

---

## ⚡ Try it free right now (no setup, no key, no cost)

Want to see exactly what the output looks like before signing up for anything?
Run the built-in **demo mode** — it uses realistic *sample* data (no API key,
no internet, no charges):

```bash
python3 find_leads.py --demo
```

This writes **`us_website_leads_demo.csv`** with ~890 sample leads spread across
all 51 states/territories and prints the top 5. The sample data is invented
(phone numbers use the `555-01xx` "fiction" range) but flows through the *exact
same* filtering and lead-scoring code as a real run — so it's a true preview.
A portion of the sample is deliberately given a website / too few reviews /
"closed" status so you can see the filters working.

> The demo is for previewing only. For **real** leads, follow the Google setup
> below and run without `--demo`.

---

## 🖥️ See it as a website

Turn the results into a clean, single-file web dashboard — and actually **work
the list** from it. The dashboard is one self-contained `dashboard.html` file
(no server, no internet, no installs) with:

- **Drag-and-drop CSV upload** — drop your own `us_website_leads.csv` straight
  onto the page to view it. No need to re-run Python, and the file is remembered
  on that device for next time.
- **An outreach pipeline per lead** — set a status (New → Contacted → Follow-up
  → Won / Lost), jot **notes**, and the **last-contacted date** is stamped
  automatically. Everything is saved in your browser, so you can chip away at the
  list over days.
- **Table _and_ Card views**, search, niche / state / **status** / score filters,
  sortable columns, click-to-call / click-to-email, and live pipeline KPIs.
- **Export** the current (filtered) view — pipeline included — back to a CSV, so
  your progress is portable between browsers and machines.
- A **light / dark** theme that's remembered.

```bash
python3 dashboard.py                                # sample data, opens in your browser
python3 dashboard.py --states "NJ,NY"               # sample data, just those states
python3 dashboard.py --csv us_website_leads.csv     # use your REAL results
python3 dashboard.py --no-open                      # build dashboard.html without opening
```

It writes the self-contained `dashboard.html` and opens it automatically — or,
once built, just **double-click the file** (or drag a CSV onto it) any time.
Works with zero installs.

---

## What it finds

Businesses in these niches (edit `NICHE_SEARCHES` in `find_leads.py`):
junk removal · pressure washing · mobile car detailing · cleaning services ·
handyman services · landscaping · painting contractors · towing companies ·
roofing · plumbing · electrician · HVAC · tree service · fencing ·
pest control · moving services

Each niche is searched with **several phrasings** (e.g. "junk removal", "junk
hauling", "debris removal"). Different phrasings surface different businesses and
duplicates are merged automatically — so you get more distinct leads per city.

It **only keeps** a business if it:
- has **no website** listed on Google,
- **has a phone number**,
- has **at least 5 reviews**,
- is **not permanently closed**.

### How the nationwide coverage works
A single "junk removal in Texas" search only returns ~60 results — nowhere near
enough for a whole state. So the script searches **city by city**: it has a
built-in list of the biggest cities in every state (`STATE_CITIES`) and runs
each niche against each city. You control how deep it goes with two settings:

- `STATES_TO_SEARCH` — `"ALL"` (whole country) or a list like `["New Jersey", "New York"]`.
- `MAX_CITIES_PER_STATE` — how many of each state's biggest cities to use (default 3).

---

## 1. Requirements

- **Python 3.8+** — check with `python3 --version`
- A **Google Cloud account** with **billing enabled** (a card on file is
  required even though there's a free monthly usage tier).
- The **Places API (New)** enabled on your Google Cloud project.

---

## 2. Get a Google Maps API key (one-time setup)

1. Go to <https://console.cloud.google.com/> and sign in.
2. Create a project (top bar → *Select a project* → *New Project*).
3. **Enable billing**: menu → *Billing* → link a billing account.
4. **Enable the API**: menu → *APIs & Services* → *Library* → search
   **“Places API (New)”** → click it → **Enable**.
5. **Create the key**: *APIs & Services* → *Credentials* → *Create credentials*
   → *API key*. Copy it.
6. *(Recommended)* Click the new key → under *API restrictions*, restrict it to
   **Places API (New)**.

---

## 3. Install the dependency

```bash
cd /Users/sai/nj-lead-finder
pip3 install -r requirements.txt
```

---

## 4. Set your API key

**macOS / Linux:**
```bash
export GOOGLE_MAPS_API_KEY="paste_your_key_here"
```
**Windows (PowerShell):**
```powershell
$env:GOOGLE_MAPS_API_KEY="paste_your_key_here"
```

---

## 5. Run it

```bash
python3 find_leads.py
```

Because a nationwide run makes **a lot** of API calls, two guards protect you:
a hard ceiling (`MAX_API_CALLS`, default **2000** — the run stops there no matter
what), and a confirm prompt before spending if the run would exceed
`CONFIRM_THRESHOLD` (default 400 calls). To skip the prompt, add `-y`:

```bash
python3 find_leads.py -y
```

**Pick scope and budget from the command line** (no need to edit the file):

```bash
# Only these states (full names OR 2-letter codes both work):
python3 find_leads.py --states "New Jersey,New York"
python3 find_leads.py --states "NJ,NY,PA"

# Cap spending at 300 API calls, then stop:
python3 find_leads.py --states "NJ,NY" --max-calls 300

# 0 = unlimited (ignore the cap):
python3 find_leads.py --states "Texas" --max-calls 0

# Preview every search a real run would make -- no key, no API calls, no cost:
python3 find_leads.py --dry-run --states "NJ,NY"
```

Results are written to **`us_website_leads.csv`** (demo writes to a separate
`us_website_leads_demo.csv`, so a demo never overwrites real leads).

### CSV columns
| Column | Meaning |
|---|---|
| business_name | The business name |
| niche | Which search term found it |
| phone | Phone number |
| address | Full address |
| rating | Average star rating |
| review_count | Number of Google reviews |
| google_maps_url | Link to the business on Google Maps |
| website_status | Always “No website listed” (that’s the point) |
| lead_score | 1–10 priority score (higher = better lead) |
| place_id | Google’s unique ID |
| search_area | The “City, State” we searched — **filter by state with this** |

---

## 6. How the lead score works (1–10)

Points are added up, then squeezed into 1–10:

- **No website listed:** +4 (the main signal — they need what you sell)
- **Has a phone number:** +1
- **Target service niche:** +1
- **Reviews:** +0.5 to +3 (more reviews = more established)
- **Rating:** +0.1 to +1 (better reputation = more serious business)

---

## 7. Customize it

Edit the **CONFIGURATION** section near the top of `find_leads.py`:

- `NICHE_SEARCHES` — the niches and their search phrasings (add synonyms for more leads).
- `STATES_TO_SEARCH` — `"ALL"` or a list of specific states.
- `MAX_CITIES_PER_STATE` — more cities = more leads **and** more cost.
- `STATE_CITIES` — add more cities to any state for deeper coverage.
- `MAX_API_CALLS` — **your budget cap**: the run stops after this many calls (or `None` for unlimited).
- `MIN_REVIEWS` — raise for more established businesses only.
- `MAX_PAGES_PER_QUERY` — 1, 2, or 3. Higher = more results and more cost.

---

## 8. Cost note (read this — nationwide can get big)

Each search request is billed by Google. The script prints the **maximum**
number of API calls before it starts:

```
full-scope calls ≈ (search terms) × (states × MAX_CITIES_PER_STATE) × MAX_PAGES_PER_QUERY
```

With the defaults the *full* scope is tens of thousands of calls, but
**`MAX_API_CALLS` (default 2000) caps every run** — so a default run makes at
most 2000 calls. That 2000-call run still typically yields hundreds to ~1,000+
real leads after filtering. Raise `MAX_API_CALLS` for a bigger list, lower it to
spend less.

**Smart, cheap way to actually land clients:** you don't need all 50 states. Pick
a focused region you can realistically work (e.g. your state + neighbors), set
`STATES_TO_SEARCH = ["Your State", ...]`, and run deep there. You'll get plenty
of leads for far less money — and you can only call/text so many people anyway.

**Other cost levers:**
- Lower `MAX_CITIES_PER_STATE` (e.g. 1–2).
- Set `MAX_PAGES_PER_QUERY = 1`.

### Before you contact anyone
Cold **calls and especially texts** to these numbers are regulated (TCPA, state
"mini-TCPA" laws, Do-Not-Call). Automated/bulk texting is the highest-risk path,
and many of these are personal cell numbers. Manual, one-at-a-time B2B calls are
lower risk. This isn't legal advice — confirm your method is compliant for your
target states before sending at scale.

Free limits and per-call prices change over time — check the current pricing
before big runs: <https://mapsplatform.google.com/pricing/>

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `No Google Maps API key found` | Set `GOOGLE_MAPS_API_KEY` in this terminal (step 4). |
| `status 403` | Enable **Places API (New)**, enable **billing**, check key restrictions. |
| `ModuleNotFoundError: requests` | Run `pip3 install -r requirements.txt`. |
| Run feels huge / costly | Lower `MAX_CITIES_PER_STATE`, trim `STATES_TO_SEARCH`, or set `MAX_PAGES_PER_QUERY = 1`. |
| 0 leads in an area | Many businesses there already have websites — that's normal. |

---

## Data sources & license

- **Google Places API** — used by `find_leads.py` (official API, not scraping).
- **OpenStreetMap** — used by `find_leads_osm.py`. OSM business data is © OpenStreetMap
  contributors, licensed under the [ODbL](https://opendatacommons.org/licenses/odbl/).
  Any published output (including the GitHub Pages dashboard) credits OpenStreetMap.

*This tool uses the official Google Places API and obeys Google’s terms. It does
not scrape Google Search or Google Maps web pages.*
