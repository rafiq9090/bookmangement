import difflib
import json
import math
import urllib.parse
import urllib.request
from django.core.cache import cache
from django.conf import settings

OSM_USER_AGENT = "eB-BookMarketplace/1.0 (local-p2p-book-marketplace; https://www.openstreetmap.org/)"

# Strict Bangladesh Geographic Bounding Box (min_lon, max_lat, max_lon, min_lat for Nominatim)
BANGLADESH_BBOX = "88.01,26.63,92.68,20.57"

# Curated catalog of granular Bangladesh micro-neighborhoods, postal hubs, and pickup centers
BANGLADESH_LOCATIONS = [
    # Dhaka Central & Tejgaon / Nakhalpara / Mohakhali (High engagement micro-areas)
    {"name": "East Nakhalpara, Dhaka 1215", "district": "Dhaka", "area": "East Nakhalpara", "lat": 23.7720, "lon": 90.3984},
    {"name": "West Nakhalpara, Dhaka 1215", "district": "Dhaka", "area": "West Nakhalpara", "lat": 23.7715, "lon": 90.3920},
    {"name": "Tejgaon, Dhaka 1215", "district": "Dhaka", "area": "Tejgaon", "lat": 23.7598, "lon": 90.3916},
    {"name": "Tejgaon Industrial Area, Dhaka", "district": "Dhaka", "area": "Tejgaon I/A", "lat": 23.7680, "lon": 90.4040},
    {"name": "Mohakhali, Dhaka 1212", "district": "Dhaka", "area": "Mohakhali", "lat": 23.7776, "lon": 90.4054},
    {"name": "Mohakhali DOHS, Dhaka", "district": "Dhaka", "area": "Mohakhali DOHS", "lat": 23.7788, "lon": 90.3942},
    {"name": "Wireless Gate, Mohakhali, Dhaka", "district": "Dhaka", "area": "Mohakhali Wireless", "lat": 23.7795, "lon": 90.4020},
    {"name": "Farmgate, Dhaka 1215", "district": "Dhaka", "area": "Farmgate", "lat": 23.7570, "lon": 90.3888},
    {"name": "Indira Road, Farmgate, Dhaka", "district": "Dhaka", "area": "Indira Road", "lat": 23.7585, "lon": 90.3845},
    {"name": "Green Road, Dhaka", "district": "Dhaka", "area": "Green Road", "lat": 23.7510, "lon": 90.3870},
    {"name": "Panthapath, Dhaka 1205", "district": "Dhaka", "area": "Panthapath", "lat": 23.7515, "lon": 90.3850},
    {"name": "Karwan Bazar, Dhaka 1215", "district": "Dhaka", "area": "Karwan Bazar", "lat": 23.7500, "lon": 90.3930},
    {"name": "Agargaon, Dhaka 1207", "district": "Dhaka", "area": "Agargaon", "lat": 23.7780, "lon": 90.3770},

    # Dhaka - Banani, Gulshan, Baridhara, Bashundhara
    {"name": "Banani, Dhaka 1213", "district": "Dhaka", "area": "Banani", "lat": 23.7937, "lon": 90.4033},
    {"name": "Banani Road 11, Dhaka", "district": "Dhaka", "area": "Banani Road 11", "lat": 23.7942, "lon": 90.4050},
    {"name": "Banani DOHS, Dhaka", "district": "Dhaka", "area": "Banani DOHS", "lat": 23.7972, "lon": 90.3989},
    {"name": "Gulshan 1, Dhaka 1212", "district": "Dhaka", "area": "Gulshan 1", "lat": 23.7780, "lon": 90.4162},
    {"name": "Gulshan 2, Dhaka 1212", "district": "Dhaka", "area": "Gulshan 2", "lat": 23.7930, "lon": 90.4140},
    {"name": "Baridhara, Dhaka 1212", "district": "Dhaka", "area": "Baridhara", "lat": 23.7997, "lon": 90.4227},
    {"name": "Baridhara DOHS, Dhaka", "district": "Dhaka", "area": "Baridhara DOHS", "lat": 23.8115, "lon": 90.4150},
    {"name": "Bashundhara R/A, Dhaka 1229", "district": "Dhaka", "area": "Bashundhara R/A", "lat": 23.8191, "lon": 90.4348},
    {"name": "Kuril, Dhaka", "district": "Dhaka", "area": "Kuril", "lat": 23.8180, "lon": 90.4200},
    {"name": "Badda, Dhaka 1212", "district": "Dhaka", "area": "Badda", "lat": 23.7805, "lon": 90.4267},
    {"name": "Middle Badda, Dhaka", "district": "Dhaka", "area": "Middle Badda", "lat": 23.7780, "lon": 90.4250},
    {"name": "Rampura, Dhaka 1219", "district": "Dhaka", "area": "Rampura", "lat": 23.7612, "lon": 90.4194},
    {"name": "Banasree, Dhaka 1219", "district": "Dhaka", "area": "Banasree", "lat": 23.7630, "lon": 90.4310},
    {"name": "Khilgaon, Dhaka 1219", "district": "Dhaka", "area": "Khilgaon", "lat": 23.7516, "lon": 90.4243},
    {"name": "Malibagh, Dhaka 1217", "district": "Dhaka", "area": "Malibagh", "lat": 23.7470, "lon": 90.4160},
    {"name": "Shantinagar, Dhaka 1217", "district": "Dhaka", "area": "Shantinagar", "lat": 23.7430, "lon": 90.4140},
    {"name": "Mouchak, Dhaka", "district": "Dhaka", "area": "Mouchak", "lat": 23.7460, "lon": 90.4130},
    {"name": "Kakrail, Dhaka", "district": "Dhaka", "area": "Kakrail", "lat": 23.7400, "lon": 90.4070},

    # Dhaka - Dhanmondi, Lalmatia, Mohammadpur
    {"name": "Dhanmondi, Dhaka 1205", "district": "Dhaka", "area": "Dhanmondi", "lat": 23.7465, "lon": 90.3760},
    {"name": "Dhanmondi 27, Dhaka", "district": "Dhaka", "area": "Dhanmondi 27", "lat": 23.7530, "lon": 90.3720},
    {"name": "Dhanmondi 32, Dhaka", "district": "Dhaka", "area": "Dhanmondi 32", "lat": 23.7510, "lon": 90.3775},
    {"name": "Shankar, Dhanmondi, Dhaka", "district": "Dhaka", "area": "Shankar", "lat": 23.7470, "lon": 90.3670},
    {"name": "Rayerbazar, Dhaka", "district": "Dhaka", "area": "Rayerbazar", "lat": 23.7430, "lon": 90.3630},
    {"name": "Lalmatia, Dhaka 1207", "district": "Dhaka", "area": "Lalmatia", "lat": 23.7548, "lon": 90.3712},
    {"name": "Mohammadpur, Dhaka 1207", "district": "Dhaka", "area": "Mohammadpur", "lat": 23.7658, "lon": 90.3584},
    {"name": "Town Hall, Mohammadpur, Dhaka", "district": "Dhaka", "area": "Mohammadpur Town Hall", "lat": 23.7610, "lon": 90.3640},
    {"name": "Adabor, Dhaka 1207", "district": "Dhaka", "area": "Adabor", "lat": 23.7710, "lon": 90.3550},
    {"name": "Shyamoli, Dhaka 1207", "district": "Dhaka", "area": "Shyamoli", "lat": 23.7715, "lon": 90.3650},
    {"name": "Kalyanpur, Dhaka 1207", "district": "Dhaka", "area": "Kalyanpur", "lat": 23.7790, "lon": 90.3580},

    # Dhaka - Mirpur Sections
    {"name": "Mirpur 10, Dhaka 1216", "district": "Dhaka", "area": "Mirpur 10", "lat": 23.8069, "lon": 90.3687},
    {"name": "Mirpur 1, Dhaka 1216", "district": "Dhaka", "area": "Mirpur 1", "lat": 23.7956, "lon": 90.3537},
    {"name": "Mirpur 2, Dhaka 1216", "district": "Dhaka", "area": "Mirpur 2", "lat": 23.8042, "lon": 90.3615},
    {"name": "Mirpur 6, Dhaka 1216", "district": "Dhaka", "area": "Mirpur 6", "lat": 23.8080, "lon": 90.3620},
    {"name": "Mirpur 11, Dhaka 1216", "district": "Dhaka", "area": "Mirpur 11", "lat": 23.8223, "lon": 90.3654},
    {"name": "Mirpur 12, Dhaka 1216", "district": "Dhaka", "area": "Mirpur 12", "lat": 23.8284, "lon": 90.3644},
    {"name": "Mirpur 14, Dhaka 1206", "district": "Dhaka", "area": "Mirpur 14", "lat": 23.8120, "lon": 90.3800},
    {"name": "Pallabi, Mirpur, Dhaka", "district": "Dhaka", "area": "Pallabi", "lat": 23.8240, "lon": 90.3620},
    {"name": "Mirpur DOHS, Dhaka", "district": "Dhaka", "area": "Mirpur DOHS", "lat": 23.8340, "lon": 90.3680},
    {"name": "Kazipara, Dhaka", "district": "Dhaka", "area": "Kazipara", "lat": 23.7970, "lon": 90.3730},
    {"name": "Shewrapara, Dhaka", "district": "Dhaka", "area": "Shewrapara", "lat": 23.7890, "lon": 90.3735},

    # Dhaka - Uttara Sectors
    {"name": "Uttara Sector 1, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 1", "lat": 23.8610, "lon": 90.3980},
    {"name": "Uttara Sector 3, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 3", "lat": 23.8680, "lon": 90.3970},
    {"name": "Uttara Sector 4, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 4", "lat": 23.8720, "lon": 90.4010},
    {"name": "Uttara Sector 7, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 7", "lat": 23.8730, "lon": 90.3960},
    {"name": "Uttara Sector 10, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 10", "lat": 23.8820, "lon": 90.3880},
    {"name": "Uttara Sector 11, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 11", "lat": 23.8790, "lon": 90.3830},
    {"name": "Uttara Sector 13, Dhaka 1230", "district": "Dhaka", "area": "Uttara Sector 13", "lat": 23.8710, "lon": 90.3850},
    {"name": "Azampur, Uttara, Dhaka", "district": "Dhaka", "area": "Azampur", "lat": 23.8685, "lon": 90.4005},
    {"name": "House Building, Uttara, Dhaka", "district": "Dhaka", "area": "House Building Uttara", "lat": 23.8735, "lon": 90.3995},

    # Dhaka - Shahbagh, Nilkhet, Motijheel, Old Dhaka
    {"name": "Nilkhet Book Market, Dhaka 1205", "district": "Dhaka", "area": "Nilkhet", "lat": 23.7320, "lon": 90.3880},
    {"name": "New Market, Dhaka 1205", "district": "Dhaka", "area": "New Market", "lat": 23.7335, "lon": 90.3840},
    {"name": "Shahbagh, Dhaka 1000", "district": "Dhaka", "area": "Shahbagh", "lat": 23.7388, "lon": 90.3957},
    {"name": "Dhaka University Campus, Dhaka", "district": "Dhaka", "area": "Dhaka University", "lat": 23.7300, "lon": 90.3940},
    {"name": "Elephant Road, Dhaka 1205", "district": "Dhaka", "area": "Elephant Road", "lat": 23.7400, "lon": 90.3850},
    {"name": "Motijheel C/A, Dhaka 1000", "district": "Dhaka", "area": "Motijheel", "lat": 23.7330, "lon": 90.4172},
    {"name": "Paltan, Dhaka 1000", "district": "Dhaka", "area": "Paltan", "lat": 23.7360, "lon": 90.4130},
    {"name": "Wari, Dhaka 1203", "district": "Dhaka", "area": "Wari", "lat": 23.7180, "lon": 90.4200},
    {"name": "Lalbagh, Dhaka 1211", "district": "Dhaka", "area": "Lalbagh", "lat": 23.7190, "lon": 90.3880},
    {"name": "Chawkbazar, Dhaka 1211", "district": "Dhaka", "area": "Chawkbazar", "lat": 23.7170, "lon": 90.3960},
    {"name": "Sadarghat, Dhaka 1100", "district": "Dhaka", "area": "Sadarghat", "lat": 23.7080, "lon": 90.4110},
    {"name": "Gandaria, Dhaka 1204", "district": "Dhaka", "area": "Gandaria", "lat": 23.7070, "lon": 90.4280},
    {"name": "Jatrabari, Dhaka 1204", "district": "Dhaka", "area": "Jatrabari", "lat": 23.7110, "lon": 90.4340},

    # Greater Dhaka
    {"name": "Savar, Dhaka 1340", "district": "Dhaka", "area": "Savar", "lat": 23.8583, "lon": 90.2667},
    {"name": "Ashulia, Dhaka", "district": "Dhaka", "area": "Ashulia", "lat": 23.9050, "lon": 90.3200},
    {"name": "Keraniganj, Dhaka", "district": "Dhaka", "area": "Keraniganj", "lat": 23.6840, "lon": 90.3400},
    {"name": "Tongi, Gazipur 1710", "district": "Gazipur", "area": "Tongi", "lat": 23.8960, "lon": 90.4030},
    {"name": "Board Bazar, Gazipur", "district": "Gazipur", "area": "Board Bazar", "lat": 23.9480, "lon": 90.3820},
    {"name": "Gazipur Sadar, Gazipur", "district": "Gazipur", "area": "Gazipur Sadar", "lat": 23.9999, "lon": 90.4203},
    {"name": "Chashara, Narayanganj 1400", "district": "Narayanganj", "area": "Chashara", "lat": 23.6210, "lon": 90.4980},
    {"name": "Narayanganj Sadar", "district": "Narayanganj", "area": "Narayanganj Sadar", "lat": 23.6238, "lon": 90.5000},

    # Chattogram (Chittagong) Granular Hubs
    {"name": "Agrabad C/A, Chattogram", "district": "Chattogram", "area": "Agrabad", "lat": 22.3255, "lon": 91.8133},
    {"name": "GEC Circle, Chattogram", "district": "Chattogram", "area": "GEC Circle", "lat": 22.3587, "lon": 91.8214},
    {"name": "Nasirabad, Chattogram", "district": "Chattogram", "area": "Nasirabad", "lat": 22.3680, "lon": 91.8242},
    {"name": "Khulshi, Chattogram", "district": "Chattogram", "area": "Khulshi", "lat": 22.3640, "lon": 91.8050},
    {"name": "Chawkbazar, Chattogram", "district": "Chattogram", "area": "Chawkbazar", "lat": 22.3570, "lon": 91.8390},
    {"name": "Halishahar, Chattogram", "district": "Chattogram", "area": "Halishahar", "lat": 22.3217, "lon": 91.7770},
    {"name": "Muradpur, Chattogram", "district": "Chattogram", "area": "Muradpur", "lat": 22.3690, "lon": 91.8350},
    {"name": "Bahaddarhat, Chattogram", "district": "Chattogram", "area": "Bahaddarhat", "lat": 22.3730, "lon": 91.8470},
    {"name": "Anderkilla, Chattogram", "district": "Chattogram", "area": "Anderkilla", "lat": 22.3380, "lon": 91.8370},

    # Sylhet Granular Hubs
    {"name": "Zindabazar, Sylhet 3100", "district": "Sylhet", "area": "Zindabazar", "lat": 24.8967, "lon": 91.8703},
    {"name": "Amberkhana, Sylhet 3100", "district": "Sylhet", "area": "Amberkhana", "lat": 24.9080, "lon": 91.8708},
    {"name": "Shibganj, Sylhet", "district": "Sylhet", "area": "Shibganj", "lat": 24.8930, "lon": 91.8900},
    {"name": "Subidbazar, Sylhet", "district": "Sylhet", "area": "Subidbazar", "lat": 24.9030, "lon": 91.8590},
    {"name": "Shahjalal Upashahar, Sylhet", "district": "Sylhet", "area": "Shahjalal Upashahar", "lat": 24.8850, "lon": 91.8800},

    # Other Major Divisions & Cities
    {"name": "Shaheb Bazar, Rajshahi 6000", "district": "Rajshahi", "area": "Shaheb Bazar", "lat": 24.3667, "lon": 88.6000},
    {"name": "Motihar, Rajshahi", "district": "Rajshahi", "area": "Motihar", "lat": 24.3700, "lon": 88.6300},
    {"name": "Shibbari, Khulna 9100", "district": "Khulna", "area": "Shibbari", "lat": 22.8250, "lon": 89.5530},
    {"name": "Daulatpur, Khulna", "district": "Khulna", "area": "Daulatpur", "lat": 22.8750, "lon": 89.5250},
    {"name": "Sadar Road, Barishal 8200", "district": "Barishal", "area": "Sadar Road", "lat": 22.7020, "lon": 90.3700},
    {"name": "Jahaj Company More, Rangpur", "district": "Rangpur", "area": "Jahaj Company More", "lat": 25.7480, "lon": 89.2450},
    {"name": "Ganginar Par, Mymensingh 2200", "district": "Mymensingh", "area": "Ganginar Par", "lat": 24.7570, "lon": 90.4070},
    {"name": "Kandirpar, Cumilla 3500", "district": "Cumilla", "area": "Kandirpar", "lat": 23.4610, "lon": 91.1810},
    {"name": "Satmatha, Bogura 5800", "district": "Bogura", "area": "Satmatha", "lat": 24.8510, "lon": 89.3720},
    {"name": "Laboni Beach, Cox's Bazar", "district": "Cox's Bazar", "area": "Laboni Beach", "lat": 21.4310, "lon": 91.9790},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in kilometers.
    """
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
        return 0.0

    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 1)


def find_bd_location_matches(
    query: str,
    limit: int = 5,
    user_lat: float | None = None,
    user_lon: float | None = None,
) -> list[dict]:
    """
    Matches query against curated Bangladesh micro-neighborhoods using prefix,
    sub-area match, and typo-tolerant fuzzy matching (e.g. 'dhka' -> 'Dhaka').
    Optionally sorts by proximity to user coordinates (closest first).
    """
    q_clean = query.strip().lower()
    if len(q_clean) < 2:
        return []

    results = []
    seen = set()

    # 1. Exact or prefix matches (e.g. 'nakh' -> 'East Nakhalpara', 'West Nakhalpara')
    for loc in BANGLADESH_LOCATIONS:
        name_l = loc["name"].lower()
        district_l = loc["district"].lower()
        area_l = loc["area"].lower()

        is_match = (
            name_l.startswith(q_clean)
            or district_l.startswith(q_clean)
            or area_l.startswith(q_clean)
            or any(w.startswith(q_clean) for w in name_l.replace(",", " ").split())
        )
        if is_match and name_l not in seen:
            seen.add(name_l)
            results.append({
                "name": loc["name"],
                "full_name": f"{loc['name']}, Bangladesh",
                "district": loc["district"],
                "area": loc["area"],
                "lat": loc["lat"],
                "lon": loc["lon"],
            })

    # 2. Substring matches
    if len(results) < limit:
        for loc in BANGLADESH_LOCATIONS:
            name_l = loc["name"].lower()
            if q_clean in name_l and name_l not in seen:
                seen.add(name_l)
                results.append({
                    "name": loc["name"],
                    "full_name": f"{loc['name']}, Bangladesh",
                    "district": loc["district"],
                    "area": loc["area"],
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                })

    # 3. Typo-tolerant fuzzy matches (only for close misspellings like 'dhka' -> 'Dhaka')
    if len(results) < limit:
        name_map = {loc["name"].lower(): loc for loc in BANGLADESH_LOCATIONS}
        area_map = {loc["area"].lower(): loc for loc in BANGLADESH_LOCATIONS}
        district_map = {loc["district"].lower(): loc for loc in BANGLADESH_LOCATIONS}
        all_keys = list(set(list(name_map.keys()) + list(area_map.keys()) + list(district_map.keys())))

        close_matches = difflib.get_close_matches(q_clean, all_keys, n=limit, cutoff=0.70)
        for match_key in close_matches:
            matched_loc = name_map.get(match_key) or area_map.get(match_key) or district_map.get(match_key)
            if matched_loc and matched_loc["name"].lower() not in seen:
                seen.add(matched_loc["name"].lower())
                results.append({
                    "name": matched_loc["name"],
                    "full_name": f"{matched_loc['name']}, Bangladesh",
                    "district": matched_loc["district"],
                    "area": matched_loc["area"],
                    "lat": matched_loc["lat"],
                    "lon": matched_loc["lon"],
                })

    # 4. Proximity ranking if user coordinates are provided
    if user_lat is not None and user_lon is not None and results:
        results.sort(
            key=lambda item: haversine_km(user_lat, user_lon, item["lat"], item["lon"])
        )

    return results[:limit]


def search_osm_locations(
    query: str,
    limit: int = 6,
    user_lat: float | None = None,
    user_lon: float | None = None,
) -> list[dict]:
    """
    Queries OpenStreetMap Nominatim API strictly bounded to Bangladesh (viewbox + bounded=1).
    Dynamically finds any Upazila, Town, Thana, Village, or Micro-Neighborhood in Bangladesh (e.g. Burichang, Cumilla).
    Optionally biases by user GPS proximity.
    """
    if not getattr(settings, "GEOCODING_ENABLED", False):
        return []
    clean_q = query.strip()
    if len(clean_q) < 2:
        return []

    cache_key = f"osm_bbox_v3_{clean_q.lower()}_{limit}_{round(user_lat or 0, 2)}_{round(user_lon or 0, 2)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if not cache.add("geocoding:outbound", 1, timeout=2):
        return []

    # Query Nominatim strictly locked to Bangladesh bounding box
    params = {
        "q": clean_q,
        "format": "json",
        "addressdetails": "1",
        "countrycodes": "bd",
        "viewbox": BANGLADESH_BBOX,
        "bounded": "1",
        "limit": str(limit * 2),
        "accept-language": "en",
    }

    url = settings.GEOCODING_URL.rstrip("/") + "/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": settings.GEOCODING_USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en",
        },
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data:
                addr = item.get("address", {})
                country_code = addr.get("country_code", "").lower()
                # Strictly Bangladesh
                if country_code and country_code != "bd":
                    continue

                addresstype = item.get("addresstype", "")
                place_name = item.get("name", "").strip()

                # Filter out ONLY whole-division state polygons (e.g. 'Dhaka Division')
                if addresstype == "state" and "division" not in clean_q.lower():
                    continue

                # Comprehensive geographic hierarchy for Bangladesh
                area = (
                    addr.get("suburb")
                    or addr.get("neighbourhood")
                    or addr.get("residential")
                    or addr.get("quarter")
                    or addr.get("road")
                    or addr.get("village")
                    or addr.get("hamlet")
                    or addr.get("town")
                    or addr.get("city_district")
                    or addr.get("municipality")
                    or addr.get("county")  # In Bangladesh OSM, Upazilas are mapped under county
                    or place_name
                )
                district = (
                    addr.get("state_district")  # In Bangladesh OSM, Districts are state_district (e.g. Cumilla District)
                    or addr.get("city")
                    or addr.get("district")
                    or addr.get("county")
                    or ""
                )
                postcode = addr.get("postcode", "").strip()

                if area and district and area.lower() != district.lower():
                    display_title = f"{area}, {district}"
                else:
                    display_title = area or district or place_name

                if postcode and postcode not in display_title:
                    display_title = f"{display_title} {postcode}"

                lat_val = float(item.get("lat", 0))
                lon_val = float(item.get("lon", 0))

                results.append({
                    "name": display_title,
                    "full_name": item.get("display_name", ""),
                    "district": district,
                    "area": area,
                    "lat": lat_val,
                    "lon": lon_val,
                })

        # Rank by proximity if user coordinates available
        if user_lat is not None and user_lon is not None and results:
            results.sort(
                key=lambda x: haversine_km(user_lat, user_lon, x["lat"], x["lon"])
            )

        results = results[:limit]
        cache.set(cache_key, results, timeout=3600)
    except Exception:
        results = []

    return results


def reverse_osm_location(lat: float, lon: float) -> dict | None:
    """
    Reverse geocodes GPS coordinates to a friendly place name using OpenStreetMap Nominatim.
    """
    if not getattr(settings, "GEOCODING_ENABLED", False):
        return None
    try:
        lat = round(float(lat), 4)
        lon = round(float(lon), 4)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None

    cache_key = f"osm_rev_{lat}_{lon}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if not cache.add("geocoding:outbound", 1, timeout=2):
        return None
    url = (
        settings.GEOCODING_URL.rstrip("/") + "/reverse?"
        + urllib.parse.urlencode({
            "lat": str(lat),
            "lon": str(lon),
            "format": "json",
            "addressdetails": "1",
            "accept-language": "en",
        })
    )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": settings.GEOCODING_USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            addr = data.get("address", {})
            district = (
                addr.get("city")
                or addr.get("county")
                or addr.get("state_district")
                or addr.get("town")
                or addr.get("state")
                or ""
            )
            area = (
                addr.get("suburb")
                or addr.get("neighbourhood")
                or addr.get("residential")
                or addr.get("road")
                or addr.get("quarter")
                or addr.get("village")
                or ""
            )

            parts = []
            if area:
                parts.append(area)
            if district and district != area:
                parts.append(district)

            display_title = ", ".join(parts) if parts else data.get("display_name", "").split(",")[0]

            result = {
                "name": display_title,
                "full_name": data.get("display_name", ""),
                "district": district,
                "area": area,
                "lat": lat,
                "lon": lon,
            }
            cache.set(cache_key, result, timeout=86400)
            return result
    except Exception:
        return None
