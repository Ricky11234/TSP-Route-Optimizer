"""
distance.py
===========
Everything about MEASURING distance/time between delivery outlets.

This module now supports TWO modes:

1. "road"  -> real driving distance & time from the road network, via OSRM
              (Open Source Routing Machine). This is the accurate option.
2. "haversine" -> great-circle (straight-line) distance, pure math, no network.
              Used on its own, OR automatically as a FALLBACK if OSRM is
              unreachable so the app never breaks.

WHY KEEP BOTH?
  Isolating distance behind this module means the solver and API don't care
  HOW a distance was obtained. Swapping or falling back between providers
  happens here and nowhere else -- a clean example of separation of concerns
  you can point to in an interview.

OSRM NOTES:
  - We use the free public demo server (router.project-osrm.org). No API key.
  - Its /table service returns the FULL distance+duration matrix in ONE request
    (far better than calling a point-to-point API n^2 times).
  - Its /route service returns the actual road geometry so we can draw the real
    path on the map instead of straight lines.
  - The public server is rate-limited and "best effort" -- fine for a demo,
    not for production. For production you'd self-host OSRM or use a paid API.
  - IMPORTANT: OSRM expects coordinates as  lon,lat  (longitude first!).
"""

import json
import math
import urllib.request
import urllib.error
from typing import List, Tuple, Optional, Dict, Any

# Mean radius of the Earth in kilometres, used by Haversine.
EARTH_RADIUS_KM = 6371.0

# Public OSRM demo server. Override with your own/self-hosted URL if you like.
OSRM_BASE_URL = "https://router.project-osrm.org"

# How long to wait on OSRM before giving up and falling back to Haversine.
OSRM_TIMEOUT_SECONDS = 15


# =========================================================================== #
#  HAVERSINE (straight-line) -- the offline, zero-dependency option           #
# =========================================================================== #
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points (pure math)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def build_distance_matrix(points: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Haversine distance matrix: matrix[i][j] = straight-line km from i to j.
    Symmetric, zeros on the diagonal. O(n^2).
    `points` is a list of (latitude, longitude) tuples.
    """
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(points[i][0], points[i][1], points[j][0], points[j][1])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def travel_time_minutes(distance_km: float, avg_speed_kmph: float = 30.0) -> float:
    """Estimate travel time (minutes) from distance, when we have no real time."""
    if avg_speed_kmph <= 0:
        raise ValueError("Average speed must be positive.")
    return (distance_km / avg_speed_kmph) * 60.0


# =========================================================================== #
#  OSRM (real road network) -- the accurate, online option                    #
# =========================================================================== #
def _http_get_json(url: str) -> Dict[str, Any]:
    """
    Tiny helper: GET a URL and parse the JSON body.
    Uses only the Python standard library (urllib) -- no extra dependency.
    Raises urllib.error.* on network/HTTP problems, which callers catch.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "tsp-route-optimizer"})
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _coords_param(points: List[Tuple[float, float]]) -> str:
    """
    Build the coordinate string OSRM expects: 'lon,lat;lon,lat;...'
    NOTE the lon,lat order -- the opposite of how we store (lat, lon).
    """
    return ";".join(f"{lon},{lat}" for (lat, lon) in points)


def osrm_matrix(points: List[Tuple[float, float]],
                base_url: str = OSRM_BASE_URL
                ) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Ask OSRM for the full road distance + duration matrix in ONE request.

    Returns a tuple: (distance_km_matrix, duration_min_matrix).
      - distances come back from OSRM in metres  -> we convert to km.
      - durations come back from OSRM in seconds  -> we convert to minutes.

    Raises on any failure (network error, bad response) so the caller can
    decide to fall back to Haversine.
    """
    coords = _coords_param(points)
    # annotations=distance,duration asks OSRM to include BOTH matrices.
    url = f"{base_url}/table/v1/driving/{coords}?annotations=distance,duration"
    data = _http_get_json(url)

    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table error: {data.get('code')}")

    # Convert units. 'distances' and 'durations' are n x n lists.
    dist_km = [[(d / 1000.0) if d is not None else 0.0 for d in row]
               for row in data["distances"]]
    dur_min = [[(t / 60.0) if t is not None else 0.0 for t in row]
               for row in data["durations"]]
    return dist_km, dur_min


def osrm_route_geometry(points: List[Tuple[float, float]],
                        base_url: str = OSRM_BASE_URL
                        ) -> List[List[float]]:
    """
    Ask OSRM for the actual road geometry connecting `points` IN ORDER.
    Used to draw the real driving path on the map (not straight lines).

    Returns a list of [latitude, longitude] pairs ready for Leaflet.
    OSRM returns GeoJSON coordinates as [lon, lat], so we flip them.
    Raises on failure (caller can skip drawing the road path).
    """
    coords = _coords_param(points)
    url = (f"{base_url}/route/v1/driving/{coords}"
           f"?overview=full&geometries=geojson")
    data = _http_get_json(url)

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"OSRM route error: {data.get('code')}")

    geojson_coords = data["routes"][0]["geometry"]["coordinates"]
    return [[lat, lon] for (lon, lat) in geojson_coords]  # flip to lat,lon


# =========================================================================== #
#  The one function the rest of the app calls                                 #
# =========================================================================== #
def build_matrices(points: List[Tuple[float, float]],
                   mode: str = "road"
                   ) -> Dict[str, Any]:
    """
    Produce the distance (and, if available, duration) matrices for a set of
    points, honouring the requested `mode` and falling back gracefully.

    Returns a dict:
      {
        "distance_matrix": [[km, ...], ...],
        "duration_matrix": [[min, ...], ...] or None,  # None => estimate time
        "source": "road" | "haversine" | "haversine (OSRM unavailable)",
      }

    Behaviour:
      - mode="haversine": straight-line only, no network call.
      - mode="road": try OSRM; if it fails for ANY reason, fall back to
        Haversine and say so in "source". The app keeps working either way.
    """
    if mode == "haversine":
        return {
            "distance_matrix": build_distance_matrix(points),
            "duration_matrix": None,
            "source": "haversine",
        }

    # mode == "road": try OSRM, fall back on failure.
    try:
        dist_km, dur_min = osrm_matrix(points)
        return {
            "distance_matrix": dist_km,
            "duration_matrix": dur_min,
            "source": "road",
        }
    except (urllib.error.URLError, urllib.error.HTTPError,
            RuntimeError, ValueError, TimeoutError, OSError) as exc:
        # Any problem reaching/parsing OSRM -> graceful fallback.
        print(f"[distance] OSRM unavailable ({exc}); falling back to Haversine.")
        return {
            "distance_matrix": build_distance_matrix(points),
            "duration_matrix": None,
            "source": "haversine (OSRM unavailable)",
        }
