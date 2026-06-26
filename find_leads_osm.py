#!/usr/bin/env python3
"""
REAL, FREE leads from OpenStreetMap (no API key, no billing, no card)
=====================================================================

Pulls REAL local businesses from OpenStreetMap via the free Overpass API, keeps
the ones with a phone and NO website, and writes the same CSV format as
find_leads.py (so the dashboard works on it too).

Reliability features:
  - Rotates across several public Overpass MIRRORS and AUTO-RETRIES on failure
    (the free servers often return 504 when busy).
  - Saves progress to the CSV after EVERY state, so a long run never loses work.
  - Does a second retry pass over any states that still failed.

Honest limitations vs. the Google version:
  - OpenStreetMap has NO review counts/ratings (leads all score ~6).
  - Best coverage is TRADES: painters, plumbers, electricians, roofers, HVAC,
    landscapers, handymen. Mobile niches (junk removal, towing, pressure washing,
    detailing) are barely mapped -- use Google for those.
  - "No website" = "no website tag in OSM", which is less reliable than Google.
    VERIFY each lead really has no site before pitching.

USAGE
-----
  python3 find_leads_osm.py                       # all states (slow; uses retries)
  python3 find_leads_osm.py --states "NJ,NY"      # specific states
Then view them:
  python3 dashboard.py --csv us_website_leads_osm.csv
"""

import argparse
import csv
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Reuse the shared helpers (build_row, lead_score, save_and_summarize, states).
import find_leads as f

# Several public Overpass servers -- we rotate through them on failure.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# CSV columns (must match find_leads.py's output so the dashboard works).
FIELDNAMES = [
    "business_name", "niche", "phone", "address", "rating", "review_count",
    "google_maps_url", "website_status", "lead_score", "place_id", "search_area",
]

# Map our niches -> OpenStreetMap tags. These trade tags are the best-populated
# business tags in US OpenStreetMap data.
OSM_NICHE_TAGS = {
    "painting contractors": [("craft", "painter")],
    "plumbing": [("craft", "plumber")],
    "electrician": [("craft", "electrician")],
    "roofing": [("craft", "roofer")],
    "hvac": [("craft", "hvac")],
    "landscaping": [("craft", "gardener"), ("shop", "garden_centre")],
    "handyman services": [("craft", "handyman")],
    "tree service": [("craft", "tree_service")],
    "fencing": [("craft", "fencing")],
}

# Reverse lookup: (tag_key, tag_value) -> niche name.
TAG_TO_NICHE = {tag: niche for niche, tags in OSM_NICHE_TAGS.items() for tag in tags}


def build_query(state):
    """Build one Overpass query for all our trade tags inside a US state."""
    selectors, seen = [], set()
    for tags in OSM_NICHE_TAGS.values():
        for key, value in tags:
            if (key, value) in seen:
                continue
            seen.add((key, value))
            selectors.append(f'  nwr["{key}"="{value}"](area.a);')
    return ('[out:json][timeout:120];\n'
            f'area["name"="{state}"]["admin_level"="4"]->.a;\n'
            '(\n' + "\n".join(selectors) + '\n);\n'
            'out center tags;')


def _ssl_context(insecure=False):
    """SSL context that actually finds CA certs on macOS (uses certifi if present)."""
    if insecure:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch(endpoint, payload, headers):
    """One HTTPS POST to an Overpass endpoint (verified, then unverified fallback)."""
    for insecure in (False, True):
        request = urllib.request.Request(endpoint, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=150, context=_ssl_context(insecure)) as response:
                return json.load(response)
        except urllib.error.URLError as error:
            is_ssl = isinstance(getattr(error, "reason", None), ssl.SSLError) or "CERTIFICATE" in str(error)
            if is_ssl and not insecure:
                continue  # retry the same endpoint without verification
            raise


def overpass(query, attempts=4):
    """POST to Overpass with retries across several public mirrors."""
    payload = urllib.parse.urlencode({"data": query}).encode()
    headers = {"User-Agent": "lead-finder-osm/1.0 (personal lead research)"}
    last_error = None
    for attempt in range(attempts):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        if attempt > 0:
            print(f"(retry {attempt} via {endpoint.split('/')[2]})", end=" ", flush=True)
        try:
            return _fetch(endpoint, payload, headers)
        except urllib.error.HTTPError as error:
            last_error = f"HTTP {error.code}"
        except Exception as error:
            last_error = type(error).__name__
        time.sleep(min(3 + attempt * 3, 12))  # back off, then try the next mirror
    raise RuntimeError(last_error or "all Overpass mirrors failed")


def element_to_lead(element, state):
    """Convert one OSM element into a lead row, or None if it doesn't qualify."""
    tags = element.get("tags", {})

    name = tags.get("name")
    if not name:
        return None

    phone = tags.get("phone") or tags.get("contact:phone") or tags.get("phone:mobile")
    if not phone:
        return None

    # Skip anyone who already has a website (a Facebook page is still a lead).
    if tags.get("website") or tags.get("contact:website") or tags.get("url"):
        return None

    niche = None
    for key in ("craft", "shop", "amenity", "office"):
        value = tags.get(key)
        if value and (key, value) in TAG_TO_NICHE:
            niche = TAG_TO_NICHE[(key, value)]
            break
    if not niche:
        return None

    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")
    if lat and lon:
        maps = f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"
    else:
        maps = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(f"{name} {state}")

    city = tags.get("addr:city", "")
    street_line = " ".join(b for b in [tags.get("addr:housenumber", ""), tags.get("addr:street", "")] if b)
    address = ", ".join(b for b in [street_line, city, state, tags.get("addr:postcode", "")] if b)

    place = {
        "id": f"osm-{element.get('type')}-{element.get('id')}",
        "displayName": {"text": name},
        "formattedAddress": address or f"{city}, {state}".strip(", "),
        "nationalPhoneNumber": phone,
        "rating": "",            # OSM has no ratings
        "userRatingCount": 0,    # OSM has no review counts
        "businessStatus": "OPERATIONAL",
        "googleMapsUri": maps,
    }
    search_area = f"{city}, {state}" if city else state
    return f.build_row(place, niche, search_area)


def write_csv(rows, path):
    """Save the rows to CSV (called after every state so progress is never lost)."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def fetch_state(state, rows, seen_ids, seen_name_phone):
    """Query one state and append its qualifying leads to `rows`."""
    data = overpass(build_query(state))
    elements = data.get("elements", [])
    added = 0
    for element in elements:
        osm_id = f"osm-{element.get('type')}-{element.get('id')}"
        if osm_id in seen_ids:
            continue
        lead = element_to_lead(element, state)
        if not lead:
            continue
        digits = "".join(ch for ch in lead["phone"] if ch.isdigit())
        name_phone = (lead["business_name"].lower(), digits)
        if name_phone in seen_name_phone:
            continue
        seen_ids.add(osm_id)
        seen_name_phone.add(name_phone)
        rows.append(lead)
        added += 1
    return len(elements), added


def main():
    parser = argparse.ArgumentParser(
        description="Pull REAL, free leads from OpenStreetMap (no API key needed).")
    parser.add_argument("--states", help='States to search, e.g. "NJ,NY". Default: all states.')
    parser.add_argument("--out", default="us_website_leads_osm.csv", help="Output CSV file.")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Seconds between states (be kind to the free servers).")
    args = parser.parse_args()

    if args.states:
        states, unknown = f.resolve_states(args.states)
        if unknown:
            print(f"Warning: ignoring unrecognized state(s): {', '.join(unknown)}")
        if not states:
            print('ERROR: no valid states. Example:  --states "NJ,NY"')
            sys.exit(1)
    else:
        states = list(f.STATE_CITIES)

    print(f"Searching OpenStreetMap (free, no key) across {len(states)} state(s)...")
    print("Real businesses + phones, but NO review counts. Best for trades.")
    print("Using mirrors + auto-retry; large states can take a while.")
    print("-" * 60)

    rows, seen_ids, seen_name_phone = [], set(), set()
    checked_total = 0

    def run_pass(state_list, tag=""):
        nonlocal checked_total
        failed = []
        for index, state in enumerate(state_list, 1):
            print(f"[{tag}{index}/{len(state_list)}] {state} ...", end=" ", flush=True)
            try:
                n_elements, added = fetch_state(state, rows, seen_ids, seen_name_phone)
            except Exception as error:
                print(f"FAILED ({error})")
                failed.append(state)
                continue
            checked_total += n_elements
            print(f"{n_elements} places, +{added} leads")
            write_csv(rows, args.out)  # save progress after every state
            if index < len(state_list):
                time.sleep(args.delay)
        return failed

    failed = run_pass(states)
    if failed:
        print(f"\nRetrying {len(failed)} state(s) that failed: {', '.join(failed)}")
        time.sleep(5)
        failed = run_pass(failed, tag="retry ")
    if failed:
        print(f"\nStill failed (busy servers): {', '.join(failed)}")
        print(f'Re-run just these later:  python3 find_leads_osm.py --states "{",".join(failed)}"')

    n_states = len({r["search_area"].split(", ")[-1] for r in rows})
    f.save_and_summarize(rows, checked_total, args.out, demo=False, n_states=n_states)
    if rows:
        print("\nThese are REAL businesses from OpenStreetMap. Verify each one still")
        print("has no website before contacting. View them in the dashboard with:")
        print(f"   python3 dashboard.py --csv {args.out}")


if __name__ == "__main__":
    main()
