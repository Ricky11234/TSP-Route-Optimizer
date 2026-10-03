"""
distance.py
===========
Everything about MEASURING distance between two delivery outlets.

We use the **Haversine formula**: the great-circle distance between two
points on a sphere (the Earth), given their latitude/longitude in degrees.

Why Haversine and not "real road distance"?
-------------------------------------------
- It needs NO API key and NO internet -> the project always runs.
- It is pure, explainable math -> perfect for an interview whiteboard.
- For comparing routes it is a very good proxy: a route that is shorter
  in straight-line distance is almost always shorter on the road too.

In a production system you would swap `haversine_km` for a call to a
routing engine (OSRM, Google Distance Matrix) to get true driving
distance/time. The rest of the code would not change -- that is the
whole point of isolating distance in its own module.
"""

import math
from typing import List, Tuple

# Mean radius of the Earth in kilometres. Used by the Haversine formula.
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two points.

    Steps (this is the whole formula, nothing hidden):
      1. Convert all degrees to radians (trig functions work in radians).
      2. Compute the differences in latitude and longitude.
      3. Apply the Haversine formula to get the central angle.
      4. Multiply the angle by Earth's radius to get distance.
    """
    # 1. degrees -> radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)      # difference in latitude
    d_lambda = math.radians(lon2 - lon1)   # difference in longitude

    # 2 & 3. The Haversine formula.
    # 'a' is the square of half the chord length between the points.
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    # 'c' is the angular distance in radians (central angle).
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # 4. arc length = radius * angle
    return EARTH_RADIUS_KM * c


def build_distance_matrix(points: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Pre-compute a 2D matrix where matrix[i][j] = distance from point i to point j.

    Why build a matrix up front?
      The TSP solver asks for the same distances thousands of times (2-opt
      checks many pairs repeatedly). Computing Haversine once per pair and
      caching it in a matrix is a classic space-for-speed trade-off.

    `points` is a list of (latitude, longitude) tuples. The returned matrix
    is symmetric (dist i->j == dist j->i) with zeros on the diagonal.

    Complexity: O(n^2) time and space, where n = number of outlets.
    """
    n = len(points)
    # Start with an n x n grid of zeros.
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):  # only compute the upper triangle...
            d = haversine_km(points[i][0], points[i][1], points[j][0], points[j][1])
            matrix[i][j] = d
            matrix[j][i] = d       # ...and mirror it, since distance is symmetric
    return matrix


def travel_time_minutes(distance_km: float, avg_speed_kmph: float = 30.0) -> float:
    """
    Convert a distance into an estimated travel time in minutes.

    time (hours) = distance / speed  ->  then * 60 for minutes.

    Default speed is 30 km/h, a reasonable average for urban delivery
    driving (stop-and-go traffic, traffic lights). Expose it as a parameter
    so the business can tune it per city.
    """
    if avg_speed_kmph <= 0:
        raise ValueError("Average speed must be positive.")
    hours = distance_km / avg_speed_kmph
    return hours * 60.0
