#!/usr/bin/env python3
"""
US Website Lead Finder  (all 50 states + DC)
============================================

Finds local SERVICE businesses that have **no website listed** on Google.
A business that gets real customers and reviews but has no website is a great
lead if you sell web design / online presence services.

How it works (high level):
  1. For each niche (junk removal, pressure washing, ...) and each city
     (across every state you enable), we ask the Google Places API "Text
     Search" for matching businesses.
  2. The Places API (New) returns the website + phone + rating fields directly
     in the search response, so we usually do NOT need a separate "Place
     Details" call.
  3. We keep only businesses that: have NO website, HAVE a phone number,
     have at least 5 reviews, and are not permanently closed.
  4. We score each lead from 1-10 and save everything to a CSV file.

IMPORTANT: Live mode uses the official Google Places API (it does NOT scrape
Google). Searching the whole country is a LOT of API calls, so the script
estimates the cost up front and asks you to confirm before spending anything.

-------------------------------------------------------------------------------
TRY IT FREE FIRST (no key, no internet, no cost):
        python3 find_leads.py --demo
    Writes a national SAMPLE CSV so you can see the output before paying.
-------------------------------------------------------------------------------
RUN FOR REAL (needs a Google Maps API key -- see README.md):
  1. pip3 install -r requirements.txt
  2. export GOOGLE_MAPS_API_KEY="your_key_here"      (macOS/Linux)
  3. python3 find_leads.py
-------------------------------------------------------------------------------
"""

import argparse
import csv
import os
import random
import sys
import time
import urllib.parse
# NOTE: 'requests' is imported lazily inside text_search() so that demo mode,
# dry runs, and the dashboard all work with zero third-party installs.


# =============================================================================
# CONFIGURATION  --  edit anything in this section to change what gets searched
# =============================================================================

# Your Google Maps API key is read from an environment variable (not needed for --demo).
API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# The service-business niches to search for, each with several search phrasings.
# Different phrasings surface DIFFERENT businesses (e.g. "junk removal" vs
# "junk hauling"), and duplicates are merged automatically -- so synonyms = more
# leads per city. The dict KEY is the clean niche name saved to the CSV; the LIST
# is the phrasings we actually search. Add/remove niches or phrasings freely.
NICHE_SEARCHES = {
    "junk removal": ["junk removal", "junk hauling", "debris removal"],
    "pressure washing": ["pressure washing", "power washing", "exterior soft washing"],
    "mobile car detailing": ["mobile car detailing", "auto detailing", "car detailing"],
    "cleaning services": ["house cleaning service", "maid service", "janitorial cleaning service"],
    "handyman services": ["handyman", "handyman services", "home repair service"],
    "landscaping": ["landscaping", "lawn care service", "lawn maintenance"],
    "painting contractors": ["painting contractor", "house painters", "residential painting"],
    "towing companies": ["towing service", "tow truck service", "roadside assistance"],
    "roofing": ["roofing contractor", "roof repair", "roofer"],
    "plumbing": ["plumber", "plumbing service"],
    "electrician": ["electrician", "electrical contractor"],
    "hvac": ["hvac contractor", "air conditioning repair", "heating and cooling service"],
    "tree service": ["tree service", "tree removal", "tree trimming"],
    "fencing": ["fence contractor", "fence installation"],
    "pest control": ["pest control", "exterminator"],
    "moving services": ["moving company", "local movers"],
}

# Clean niche names (the dict keys) -- used for the CSV and scoring.
NICHES = list(NICHE_SEARCHES)

# The biggest cities in every US state (+ DC). We search city-by-city because a
# single "in <State>" search only returns ~60 results -- far too few for a whole
# state. More cities = more leads, but also more API calls (see cost note below).
STATE_CITIES = {
    "Alabama": ["Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa"],
    "Alaska": ["Anchorage", "Fairbanks", "Juneau", "Wasilla", "Sitka"],
    "Arizona": ["Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale", "Gilbert"],
    "Arkansas": ["Little Rock", "Fayetteville", "Fort Smith", "Springdale", "Jonesboro"],
    "California": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno", "Sacramento"],
    "Colorado": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood"],
    "Connecticut": ["Bridgeport", "New Haven", "Hartford", "Stamford", "Waterbury"],
    "Delaware": ["Wilmington", "Dover", "Newark", "Middletown", "Smyrna"],
    "Florida": ["Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah"],
    "Georgia": ["Atlanta", "Augusta", "Columbus", "Savannah", "Athens", "Macon"],
    "Hawaii": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Pearl City"],
    "Idaho": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Caldwell"],
    "Illinois": ["Chicago", "Aurora", "Naperville", "Joliet", "Rockford", "Springfield"],
    "Indiana": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel"],
    "Iowa": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City"],
    "Kansas": ["Wichita", "Overland Park", "Kansas City", "Olathe", "Topeka"],
    "Kentucky": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington"],
    "Louisiana": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles"],
    "Maine": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn"],
    "Maryland": ["Baltimore", "Columbia", "Germantown", "Silver Spring", "Rockville", "Frederick"],
    "Massachusetts": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell", "Quincy"],
    "Michigan": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", "Lansing"],
    "Minnesota": ["Minneapolis", "Saint Paul", "Rochester", "Duluth", "Bloomington"],
    "Mississippi": ["Jackson", "Gulfport", "Southaven", "Hattiesburg", "Biloxi"],
    "Missouri": ["Kansas City", "St. Louis", "Springfield", "Columbia", "Independence"],
    "Montana": ["Billings", "Missoula", "Great Falls", "Bozeman", "Helena"],
    "Nebraska": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney"],
    "Nevada": ["Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks"],
    "New Hampshire": ["Manchester", "Nashua", "Concord", "Dover", "Rochester"],
    "New Jersey": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Edison", "Trenton"],
    "New Mexico": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell"],
    "New York": ["New York", "Buffalo", "Rochester", "Yonkers", "Syracuse", "Albany"],
    "North Carolina": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", "Fayetteville"],
    "North Dakota": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo"],
    "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton"],
    "Oklahoma": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond"],
    "Oregon": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro", "Bend"],
    "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", "Scranton"],
    "Rhode Island": ["Providence", "Cranston", "Warwick", "Pawtucket", "East Providence"],
    "South Carolina": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant", "Greenville"],
    "South Dakota": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown"],
    "Tennessee": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville"],
    "Texas": ["Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso"],
    "Utah": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem"],
    "Vermont": ["Burlington", "South Burlington", "Rutland", "Barre", "Montpelier"],
    "Virginia": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Arlington", "Alexandria"],
    "Washington": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Everett"],
    "West Virginia": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling"],
    "Wisconsin": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine", "Appleton"],
    "Wyoming": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs"],
    "District of Columbia": ["Washington"],
    # --- US territories (expand coverage even further) ---
    "Puerto Rico": ["San Juan", "Bayamón", "Carolina", "Ponce", "Caguas"],
    "Guam": ["Hagåtña", "Dededo", "Tamuning", "Mangilao"],
    "United States Virgin Islands": ["Charlotte Amalie", "Christiansted", "Frederiksted"],
    "Northern Mariana Islands": ["Saipan", "Garapan"],
    "American Samoa": ["Pago Pago", "Tafuna"],
}

# Two-letter abbreviations -> full state names, so --states "NJ,NY" works too.
STATE_ABBREVIATIONS = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "United States Virgin Islands",
    "MP": "Northern Mariana Islands", "AS": "American Samoa",
}

# Which states to search.
#   "ALL"  -> every state above (the whole country).
#   Or give a list, e.g.  ["New Jersey", "New York", "Pennsylvania"]
STATES_TO_SEARCH = "ALL"

# How many cities to use from EACH state (caps cost + size). Raise for deeper
# coverage, lower to save money. Each state lists its biggest cities first.
MAX_CITIES_PER_STATE = 4

# A business must have at least this many reviews to count as a lead.
MIN_REVIEWS = 5

# Each Text Search returns up to 20 results/page, up to 3 pages (~60) per query.
MAX_PAGES_PER_QUERY = 3

# If a live run would make more than this many API calls, ask before spending.
CONFIRM_THRESHOLD = 400

# Hard ceiling on API calls per live run -- the run STOPS once it hits this, no
# matter how big your niche/city/page settings are. This is your budget guard:
# set it to how many calls you're willing to pay for, or None for "no limit".
MAX_API_CALLS = 2000

# Small pauses so we are polite to the API and the "next page" token is ready.
PAGE_DELAY_SECONDS = 2.0
QUERY_DELAY_SECONDS = 0.2

# Output files (live vs demo are separate so a demo never overwrites real leads).
OUTPUT_CSV = "us_website_leads.csv"
DEMO_CSV = "us_website_leads_demo.csv"


# =============================================================================
# GOOGLE PLACES API DETAILS  --  you normally don't need to change these
# =============================================================================

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# A "field mask" tells Google EXACTLY which fields to return (controls cost).
FIELD_MASK = ",".join([
    "nextPageToken",
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.businessStatus",
    "places.googleMapsUri",
])


# =============================================================================
# LOCATIONS
# =============================================================================

def resolve_states(raw):
    """
    Turn a user string like "NJ, New York, florida" into clean state names.
    Accepts full names (any capitalization) and 2-letter codes. Returns
    (matched_state_names, unrecognized_tokens).
    """
    by_lower = {name.lower(): name for name in STATE_CITIES}
    matched, unknown = [], []
    for token in raw.split(","):
        name = token.strip()
        if not name:
            continue
        if name.lower() in by_lower:                  # full name, any case
            matched.append(by_lower[name.lower()])
        elif name.upper() in STATE_ABBREVIATIONS:     # 2-letter code
            matched.append(STATE_ABBREVIATIONS[name.upper()])
        else:
            unknown.append(name)                      # typo / not found
    return matched, unknown


def build_locations():
    """
    Turn STATE_CITIES + STATES_TO_SEARCH + MAX_CITIES_PER_STATE into a flat list
    of (city, state) pairs to search.
    """
    states = list(STATE_CITIES) if STATES_TO_SEARCH == "ALL" else STATES_TO_SEARCH
    locations = []
    for state in states:
        for city in STATE_CITIES.get(state, [])[:MAX_CITIES_PER_STATE]:
            locations.append((city, state))
    return locations


# =============================================================================
# FILTERING + SCORING  --  shared by BOTH live mode and demo mode
# =============================================================================

def passes_filters(place):
    """Keep a business only if: no website, has phone, >=MIN_REVIEWS, not closed."""
    if place.get("websiteUri"):
        return False
    if not place.get("nationalPhoneNumber"):
        return False
    if (place.get("userRatingCount") or 0) < MIN_REVIEWS:
        return False
    if place.get("businessStatus") == "CLOSED_PERMANENTLY":
        return False
    return True


def lead_score(place, niche):
    """
    Simple 1-10 "how good is this lead" score. We add up points for the signals
    that make a business worth contacting, then clamp the total to 1-10.
    """
    score = 0.0

    # No website = the core opportunity (they need exactly what you sell).
    if not place.get("websiteUri"):
        score += 4
    # Has a phone number = you can actually reach them.
    if place.get("nationalPhoneNumber"):
        score += 1
    # It's one of our target service niches = good fit.
    if niche in NICHES:
        score += 1
    # Review count = how established / busy the business is.
    reviews = place.get("userRatingCount") or 0
    if reviews >= 50:
        score += 3
    elif reviews >= 25:
        score += 2
    elif reviews >= 10:
        score += 1
    elif reviews >= 5:
        score += 0.5
    # Rating = reputation.
    rating = place.get("rating") or 0
    if rating >= 4.5:
        score += 1
    elif rating >= 4.0:
        score += 0.7
    elif rating >= 3.0:
        score += 0.4
    else:
        score += 0.1

    return int(max(1, min(10, round(score))))


def build_row(place, niche, search_area):
    """Turn one raw result (live OR demo) into a clean CSV row dictionary."""
    display_name = place.get("displayName", {}).get("text", "")
    return {
        "business_name": display_name,
        "niche": niche,
        "phone": place.get("nationalPhoneNumber", ""),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating", ""),
        "review_count": place.get("userRatingCount", 0),
        "google_maps_url": place.get("googleMapsUri", ""),
        "website_status": "No website listed",
        "lead_score": lead_score(place, niche),
        "place_id": place.get("id", ""),       # bonus: handy for future lookups
        "search_area": search_area,            # bonus: "City, State" -> filter by state
    }


def collect_leads_from_places(triples):
    """
    Take (place, niche, search_area) triples, drop duplicates (a business can
    appear under several cities/niches), keep the ones that pass the filters,
    and build CSV rows. Returns (lead_rows, unique_businesses_checked).
    """
    seen_place_ids = set()
    leads = []
    for place, niche, search_area in triples:
        place_id = place.get("id")
        if place_id in seen_place_ids:
            continue
        seen_place_ids.add(place_id)
        if passes_filters(place):
            leads.append(build_row(place, niche, search_area))
    return leads, len(seen_place_ids)


def save_and_summarize(leads, unique_checked, output_path, demo=False, n_states=0):
    """Sort leads best-first, write the CSV, and print a friendly summary."""
    leads.sort(key=lambda row: (row["lead_score"], row["review_count"]), reverse=True)

    fieldnames = [
        "business_name", "niche", "phone", "address", "rating",
        "review_count", "google_maps_url", "website_status",
        "lead_score", "place_id", "search_area",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)

    filtered_out = unique_checked - len(leads)
    print("-" * 60)
    if demo:
        print("DEMO RESULTS  (sample data -- these are NOT real businesses)")
    print(f"States covered:     {n_states}")
    print(f"Businesses checked: {unique_checked}")
    print(f"Filtered out:       {filtered_out}  (had a website / <{MIN_REVIEWS} reviews / closed / no phone)")
    print(f"Leads saved:        {len(leads)}")
    print(f"CSV file:           {os.path.abspath(output_path)}")

    if leads:
        print("\nTop leads (highest score first):")
        for row in leads[:5]:
            print(f"  [{row['lead_score']}/10] {row['business_name']} "
                  f"-- {row['phone']} ({row['search_area']}, {row['review_count']} reviews)")

    if demo:
        print("\nThat used invented sample data so you could see the output for free.")
        print("For REAL leads, run without --demo (needs a Google Maps API key).")


# =============================================================================
# LIVE MODE  --  calls the real Google Places API
# =============================================================================

def text_search(query, page_token=None):
    """Run ONE Text Search request and return parsed JSON (or None on error)."""
    try:
        import requests
    except ImportError:
        print("ERROR: live mode needs the 'requests' library.  pip3 install requests")
        sys.exit(1)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {"textQuery": query, "pageSize": 20}
    if page_token:
        body["pageToken"] = page_token

    try:
        response = requests.post(SEARCH_URL, headers=headers, json=body, timeout=30)
    except requests.RequestException as error:
        print(f"    ! Network error: {error}")
        return None

    if response.status_code != 200:
        print(f"    ! API returned status {response.status_code}")
        if response.status_code == 403:
            print("      Check that 'Places API (New)' is ENABLED, billing is ON,")
            print("      and the API key isn't restricted away from Places.")
        print(f"      Details: {response.text[:300]}")
        return None

    try:
        return response.json()
    except ValueError:
        print("    ! Could not read the API response as JSON.")
        return None


def run_live_search(locations, dry_run=False):
    """
    Loop over every niche phrasing x city, page through results, and collect
    (place, niche, area) triples. Stops early if MAX_API_CALLS is reached.

    If dry_run=True, print every search it WOULD make but call no API (no cost) --
    great for previewing scope/cost and for watching the run flow for free.
    """
    triples = []
    api_calls = 0
    total_terms = sum(len(p) for p in NICHE_SEARCHES.values())
    total_queries = total_terms * len(locations)
    query_number = 0
    stop = False

    for niche, phrasings in NICHE_SEARCHES.items():
        if stop:
            break
        for phrasing in phrasings:
            if stop:
                break
            for city, state in locations:
                query_number += 1
                query = f"{phrasing} in {city}, {state}"
                search_area = f"{city}, {state}"
                print(f"[{query_number}/{total_queries}] {query}")

                page_token = None
                for _ in range(MAX_PAGES_PER_QUERY):
                    # Budget guard: stop the whole run at the hard cap.
                    if MAX_API_CALLS and api_calls >= MAX_API_CALLS:
                        print(f"    -- reached MAX_API_CALLS ({MAX_API_CALLS}); stopping here.")
                        stop = True
                        break
                    if dry_run:
                        api_calls += 1   # count a would-be call, but don't call/paginate
                        continue
                    if page_token:
                        time.sleep(PAGE_DELAY_SECONDS)
                    data = text_search(query, page_token)
                    api_calls += 1
                    if not data:
                        break
                    for place in data.get("places", []):
                        triples.append((place, niche, search_area))
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                if stop:
                    break
                if not dry_run:
                    time.sleep(QUERY_DELAY_SECONDS)

    print(f"\n{'Would make' if dry_run else 'Made'} {api_calls} API call(s).")
    return triples


# =============================================================================
# DEMO MODE  --  invented sample data, no API key / internet / cost
# =============================================================================

# Name patterns per niche. {city} and {prefix} get filled in, so the sample
# scales to any number of cities and still looks realistic.
DEMO_PATTERNS = {
    "junk removal": ["{city} Junk Removal", "{prefix} Junk Hauling LLC", "{city} Cleanout Pros", "Junk Kings of {city}"],
    "pressure washing": ["{city} Pressure Washing", "{prefix} Power Wash LLC", "{city} SoftWash Pros", "Pristine Pressure Washing of {city}"],
    "mobile car detailing": ["{city} Mobile Detailing", "{prefix} Auto Detailing LLC", "{city} Car Spa", "Showroom Detailing of {city}"],
    "cleaning services": ["{city} Home Cleaning", "{prefix} Maid Service LLC", "Spotless {city} Cleaning", "Sparkle Cleaners of {city}"],
    "handyman services": ["{city} Handyman Services", "{prefix} Home Repairs LLC", "Mr. Fix-It of {city}", "{city} Handyman & Repair"],
    "landscaping": ["{city} Landscaping", "{prefix} Lawn & Landscape LLC", "Green Acres of {city}", "{city} Landscape Design"],
    "painting contractors": ["{city} Painting", "{prefix} Painters LLC", "Fresh Coat of {city}", "{city} Pro Painting"],
    "towing companies": ["{city} Towing", "{prefix} Towing & Recovery LLC", "24/7 {city} Tow", "{city} Roadside Recovery"],
    "roofing": ["{city} Roofing", "{prefix} Roofing LLC", "{city} Roof Repair", "Top Notch Roofing of {city}"],
    "plumbing": ["{city} Plumbing", "{prefix} Plumbing LLC", "{city} Plumbers", "Rapid Plumbing of {city}"],
    "electrician": ["{city} Electric", "{prefix} Electrical LLC", "{city} Electricians", "Bright Spark Electric of {city}"],
    "hvac": ["{city} Heating & Cooling", "{prefix} HVAC LLC", "{city} Air Conditioning", "Comfort Pros HVAC of {city}"],
    "tree service": ["{city} Tree Service", "{prefix} Tree Care LLC", "{city} Tree Removal", "Timberline Tree of {city}"],
    "fencing": ["{city} Fence Co.", "{prefix} Fencing LLC", "{city} Fence Installation", "Sturdy Fence of {city}"],
    "pest control": ["{city} Pest Control", "{prefix} Pest Solutions LLC", "{city} Exterminators", "Bug Free of {city}"],
    "moving services": ["{city} Movers", "{prefix} Moving Co. LLC", "{city} Moving Services", "Smooth Move of {city}"],
}
DEMO_PREFIXES = ["A-1", "Pro", "Five Star", "Reliable", "Elite", "Premier",
                 "Quick", "All-Star", "Top Notch", "Quality", "Apex", "Summit"]


def generate_demo_places(locations):
    """
    Build (fake_place, niche, area) triples shaped EXACTLY like real Google
    results, so they flow through the same filter + scoring code. Data is
    invented (phones use the 555-01xx 'fiction' range). A fixed seed => the same
    output every time. Some entries deliberately FAIL the filters so you can see
    the filtering work.
    """
    random.seed(42)
    streets = ["Main St", "Broad St", "Washington Ave", "Park Ave", "Oak St",
               "Market St", "1st St", "Union Ave", "Central Ave", "Maple Ave"]
    area_codes = ["212", "312", "305", "415", "702", "404", "617", "206",
                  "303", "512", "602", "214", "713", "404", "917", "480"]

    triples = []
    idx = 0
    for niche in NICHES:
        patterns = DEMO_PATTERNS[niche]
        for city, state in locations:
            name = patterns[idx % len(patterns)].format(
                city=city, prefix=DEMO_PREFIXES[idx % len(DEMO_PREFIXES)])
            phone = f"({area_codes[idx % len(area_codes)]}) 555-{100 + (idx % 100):04d}"

            place = {
                "id": f"demo-{idx}",
                "displayName": {"text": name},
                "formattedAddress": f"{random.randint(12, 1990)} {random.choice(streets)}, {city}, {state} {random.randint(10001, 99950)}",
                "nationalPhoneNumber": phone,
                "rating": round(random.uniform(3.7, 5.0), 1),
                "userRatingCount": random.choice([6, 8, 11, 15, 22, 29, 38, 54, 73, 96, 128]),
                "businessStatus": "OPERATIONAL",
                "googleMapsUri": "https://www.google.com/maps/search/?api=1&query="
                                 + urllib.parse.quote(f"{name} {city} {state}"),
                # no 'websiteUri' on purpose => NO website
            }

            # --- sprinkle in entries the filters SHOULD reject ---
            if idx % 7 == 3:
                slug = name.lower().replace(" ", "").replace(".", "").replace("&", "and").replace("/", "")
                place["websiteUri"] = f"https://{slug}.com"   # has a website
            if idx % 11 == 6:
                place["userRatingCount"] = 3                  # too few reviews
            if idx % 37 == 5:
                place["businessStatus"] = "CLOSED_PERMANENTLY"  # closed
            if idx % 41 == 9:
                place.pop("nationalPhoneNumber", None)        # no phone

            triples.append((place, niche, f"{city}, {state}"))
            idx += 1

    return triples


# =============================================================================
# ENTRY POINT
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Find US service businesses with no website (Google Places API). "
                    "Use --demo for a free, offline sample."
    )
    parser.add_argument("--demo", action="store_true",
                        help="Run offline with realistic SAMPLE data (no key, no internet, no cost).")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip the 'this may cost money' confirmation in live mode.")
    parser.add_argument("--states", metavar='"NJ,NY"', default=None,
                        help='Only search these states (comma-separated). Full names or '
                             '2-letter codes, e.g. --states "New Jersey,New York" or "NJ,NY". '
                             'Overrides STATES_TO_SEARCH.')
    parser.add_argument("--max-calls", metavar="N", type=int, default=None,
                        help="Hard cap on API calls for this run (0 = unlimited). "
                             "Overrides MAX_API_CALLS.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview every search a live run would make, WITHOUT calling "
                             "the API (no key, no cost).")
    return parser.parse_args()


def main():
    args = parse_args()

    # Apply command-line overrides (these win over the CONFIG section above).
    global STATES_TO_SEARCH, MAX_API_CALLS
    if args.states:
        matched, unknown = resolve_states(args.states)
        if unknown:
            print(f"Warning: ignoring unrecognized state(s): {', '.join(unknown)}")
        if not matched:
            print("ERROR: --states matched no known states.")
            print('Examples:  --states "New Jersey,New York"   or   --states "NJ,NY"')
            sys.exit(1)
        STATES_TO_SEARCH = matched
    if args.max_calls is not None:
        if args.max_calls < 0:
            print("ERROR: --max-calls cannot be negative.")
            sys.exit(1)
        MAX_API_CALLS = None if args.max_calls == 0 else args.max_calls

    locations = build_locations()
    n_states = len({state for _, state in locations})

    # ---------- DEMO MODE: free, offline, instant ----------
    if args.demo:
        print("=" * 60)
        print("US Website Lead Finder  --  DEMO MODE (free sample, no API key)")
        print("=" * 60)
        print(f"Simulating {len(NICHES)} niches across {len(locations)} cities in {n_states} states/territories.")
        triples = generate_demo_places(locations)
        leads, unique_checked = collect_leads_from_places(triples)
        save_and_summarize(leads, unique_checked, DEMO_CSV, demo=True, n_states=n_states)
        return

    # ---------- LIVE MODE (and --dry-run preview) ----------
    total_terms = sum(len(p) for p in NICHE_SEARCHES.values())
    total_queries = total_terms * len(locations)
    full_scope_calls = total_queries * MAX_PAGES_PER_QUERY
    effective_max = min(full_scope_calls, MAX_API_CALLS) if MAX_API_CALLS else full_scope_calls

    print("=" * 60)
    print("US Website Lead Finder  --  " + ("DRY RUN (no API calls)" if args.dry_run else "LIVE MODE"))
    print("=" * 60)
    print(f"States:           {n_states}")
    print(f"Cities:           {len(locations)}  ({MAX_CITIES_PER_STATE} per state)")
    print(f"Niches:           {len(NICHE_SEARCHES)}  ({total_terms} search terms)")
    print(f"Pages per search: {MAX_PAGES_PER_QUERY}")
    print(f"Full-scope calls: ~{full_scope_calls}")
    if MAX_API_CALLS:
        print(f"Hard cap:         {MAX_API_CALLS}  (run stops here; change MAX_API_CALLS to adjust)")
    print(f"This run:         up to {effective_max} API calls (each may cost money -- see README)")
    print("-" * 60)

    # --dry-run: show exactly what WOULD be searched; make zero API calls.
    if args.dry_run:
        run_live_search(locations, dry_run=True)
        print("-" * 60)
        print("DRY RUN complete -- no API calls were made, nothing was charged.")
        print("Remove --dry-run (and set GOOGLE_MAPS_API_KEY) to run it for real.")
        return

    # A real run needs an API key.
    if not API_KEY:
        print("ERROR: No Google Maps API key found.")
        print('Set it first, e.g.:  export GOOGLE_MAPS_API_KEY="your_key_here"')
        print("\nTip: preview the exact searches for free with:  python3 find_leads.py --dry-run")
        print("Tip: see sample output for free with:           python3 find_leads.py --demo")
        sys.exit(1)

    # Cost safety gate: confirm before a big spend.
    if effective_max > CONFIRM_THRESHOLD and not args.yes:
        print(f"!! This run could make up to {effective_max} API calls, which may exceed")
        print("   Google's free tier and cost money. To shrink it: lower MAX_API_CALLS,")
        print("   lower MAX_CITIES_PER_STATE, set STATES_TO_SEARCH to a short list, or")
        print("   set MAX_PAGES_PER_QUERY = 1 in the CONFIG section.")
        try:
            answer = input("   Type 'yes' to continue: ").strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            print("Aborted. Nothing was searched, no cost incurred.")
            sys.exit(0)
        print("-" * 60)

    triples = run_live_search(locations)
    leads, unique_checked = collect_leads_from_places(triples)
    save_and_summarize(leads, unique_checked, OUTPUT_CSV, demo=False, n_states=n_states)


if __name__ == "__main__":
    main()
