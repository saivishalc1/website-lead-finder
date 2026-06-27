#!/usr/bin/env python3
"""
Better leads via Outscraper (real Google Maps data, no Google Cloud account)
============================================================================

Outscraper (https://outscraper.com) is a paid API that returns Google Maps
business data. Versus our free OpenStreetMap path, this gives:
  - WAY more businesses (Google Maps has nearly all of them; OSM has a fraction)
  - RATINGS + REVIEW COUNTS, so the ">=5 reviews" quality filter works again
  - authoritative "no website" via the `site` field

It writes the SAME CSV format as the other scripts, so dashboard.py works on it.

HONEST CAVEATS (read before spending):
  - Outscraper is PAY-PER-RECORD. The Google Maps search returns ALL matching
    businesses; we keep only the no-website ones, so you pay for some records
    you discard. Keep LIMIT_PER_QUERY modest and use a few target states.
  - For businesses with NO website there is usually NO email to find (email
    tools scrape a site; these have none), so the email column is mostly blank
    here -- same as every other tool for this segment.
  - Our own find_leads.py (official Google Places API) returns the same data,
    ToS-clean, and is free within Google's monthly tier -- consider it too.

SETUP
-----
  1. Make a free account at https://outscraper.com and copy your API key
     (Profile -> API/Integrations). New accounts include free trial credits.
  2. export OUTSCRAPER_API_KEY="your_key_here"
  3. pip3 install requests        (only this script needs it)
  4. python3 find_leads_outscraper.py --states "NJ,NY" --limit 20
  5. View:  python3 dashboard.py --csv us_website_leads_outscraper.csv
"""

import argparse
import os
import sys
import time

import find_leads as f  # reuse build_row, passes_filters, scoring, save_and_summarize

OUTSCRAPER_URL = "https://api.outscraper.com/maps/search-v3"
OUTPUT_CSV = "us_website_leads_outscraper.csv"

API_KEY = os.environ.get("OUTSCRAPER_API_KEY", "")

# How many Google Maps results to pull per (niche, city) query. Higher = more
# coverage but more cost (you pay per record, incl. ones we filter out).
LIMIT_PER_QUERY = 20

# Ask before a run that could pull more than this many billable records.
CONFIRM_RECORDS = 1000


def search(query, limit):
    """Call Outscraper's Google Maps search (sync) and return a list of businesses."""
    import requests  # lazy import so --help etc. work without it installed
    headers = {"X-API-KEY": API_KEY}
    params = {"query": query, "limit": limit, "async": "false", "region": "US"}
    try:
        response = requests.get(OUTSCRAPER_URL, params=params, headers=headers, timeout=300)
    except requests.RequestException as error:
        print(f"    ! network error: {error}")
        return []
    if response.status_code == 401:
        print("    ! 401 Unauthorized -- check OUTSCRAPER_API_KEY.")
        return []
    if response.status_code not in (200, 202):
        print(f"    ! API {response.status_code}: {response.text[:200]}")
        return []
    try:
        payload = response.json()
    except ValueError:
        print("    ! could not parse response JSON")
        return []
    # Outscraper returns {"status": "Success", "data": [[ {biz}, ... ]]} for one query.
    blocks = payload.get("data") or []
    return blocks[0] if blocks and isinstance(blocks[0], list) else []


def to_place(business):
    """Map an Outscraper business record into the place-dict shape build_row expects."""
    reviews = business.get("reviews") or 0
    try:
        reviews = int(reviews)
    except (TypeError, ValueError):
        reviews = 0

    status = business.get("business_status") or "OPERATIONAL"

    name = business.get("name", "")
    maps_url = business.get("location_link")
    if not maps_url:
        import urllib.parse
        maps_url = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(
            f"{name}, {business.get('full_address', '')}")

    return {
        "id": business.get("place_id") or business.get("google_id") or name,
        "displayName": {"text": name},
        "formattedAddress": business.get("full_address", ""),
        "nationalPhoneNumber": business.get("phone", "") or "",
        "email": business.get("email_1", "") or "",   # usually blank for no-website biz
        "rating": business.get("rating", "") or "",
        "userRatingCount": reviews,
        "businessStatus": status,
        "googleMapsUri": maps_url,
        # 'site' present => has a website => passes_filters() will drop it
        "websiteUri": business.get("site") or None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pull better leads from Outscraper (Google Maps data, paid API).")
    parser.add_argument("--states", help='States to search, e.g. "NJ,NY". Default: all.')
    parser.add_argument("--limit", type=int, default=LIMIT_PER_QUERY,
                        help=f"Results per niche+city query (default {LIMIT_PER_QUERY}). Higher = more cost.")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip the cost confirmation.")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: no Outscraper API key found.")
        print('Set it first:  export OUTSCRAPER_API_KEY="your_key_here"')
        print("Get a key (with free trial credits) at https://outscraper.com")
        sys.exit(1)

    # Resolve states (reuse the shared helpers).
    if args.states:
        states, unknown = f.resolve_states(args.states)
        if unknown:
            print(f"Warning: ignoring unrecognized state(s): {', '.join(unknown)}")
        if not states:
            print('ERROR: no valid states. Example:  --states "NJ,NY"')
            sys.exit(1)
        f.STATES_TO_SEARCH = states

    locations = f.build_locations()
    total_queries = len(f.NICHES) * len(locations)
    est_records = total_queries * args.limit

    print("=" * 60)
    print("Outscraper Lead Finder (Google Maps data)")
    print("=" * 60)
    print(f"Niches:          {len(f.NICHES)}")
    print(f"Cities:          {len(locations)}")
    print(f"Queries:         {total_queries}")
    print(f"Est. records:    ~{est_records}  (you pay per record -- see Outscraper pricing)")
    print("-" * 60)

    if est_records > CONFIRM_RECORDS and not args.yes:
        print(f"!! This could pull up to ~{est_records} billable records.")
        print("   Shrink it with --states and/or --limit. Continue?")
        try:
            if input("   Type 'yes' to continue: ").strip().lower() != "yes":
                print("Aborted. No records pulled, no cost.")
                sys.exit(0)
        except EOFError:
            print("Aborted.")
            sys.exit(0)

    rows, seen_ids, checked, q = [], set(), 0, 0
    for niche in f.NICHES:
        for city, state in locations:
            q += 1
            query = f"{niche}, {city}, {state}, USA"
            print(f"[{q}/{total_queries}] {query}")
            for business in search(query, args.limit):
                checked += 1
                place = to_place(business)
                pid = place["id"]
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                if f.passes_filters(place):   # no website + phone + >=5 reviews + open
                    rows.append(f.build_row(place, niche, f"{city}, {state}"))
            time.sleep(0.3)

    n_states = len({r["search_area"].split(", ")[-1] for r in rows})
    f.save_and_summarize(rows, checked, OUTPUT_CSV, demo=False, n_states=n_states)
    if rows:
        print("\nReal Google Maps leads (with review counts). View them with:")
        print(f"   python3 dashboard.py --csv {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
