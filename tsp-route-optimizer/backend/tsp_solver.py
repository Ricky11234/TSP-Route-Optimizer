"""
tsp_solver.py
=============
The algorithmic heart of the project: solving the Travelling Salesman Problem.

THE PROBLEM (say this in an interview):
    Given a set of outlets and the distances between every pair, find the
    shortest possible route that starts at a depot, visits every outlet
    exactly once, and (optionally) returns to the depot.

WHY IT'S HARD:
    TSP is NP-hard. The number of possible routes for n stops is (n-1)!/2.
    - 10 stops  -> ~181,000 routes      (brute force is fine)
    - 15 stops  -> ~43 billion routes   (brute force dies)
    - 50 stops  -> more routes than atoms in the galaxy
    So for anything realistic we cannot check every route. We use HEURISTICS:
    algorithms that find a very good (not always perfect) route, fast.

OUR TWO-STEP STRATEGY:
    1. Nearest Neighbour (NN) -- builds a decent starting route quickly.
    2. 2-opt                  -- repeatedly improves that route by untangling it.
    Together they typically land within ~5% of the true optimum in milliseconds.
"""

from typing import List, Dict, Any, Optional
from distance import build_distance_matrix, travel_time_minutes


# --------------------------------------------------------------------------- #
#  Helper: total length of a route                                            #
# --------------------------------------------------------------------------- #
def route_distance(route: List[int], matrix: List[List[float]], round_trip: bool) -> float:
    """
    Sum the distances of consecutive stops in `route`.

    `route` is a list of indices, e.g. [0, 3, 1, 2] means visit outlet 0,
    then 3, then 1, then 2. If `round_trip` is True we also add the leg
    from the last stop back to the first (the depot).
    """
    total = 0.0
    for i in range(len(route) - 1):
        total += matrix[route[i]][route[i + 1]]
    if round_trip and len(route) > 1:
        total += matrix[route[-1]][route[0]]  # return to start
    return total


# --------------------------------------------------------------------------- #
#  Step 1: Nearest Neighbour construction heuristic                           #
# --------------------------------------------------------------------------- #
def nearest_neighbour(matrix: List[List[float]], start: int) -> List[int]:
    """
    Build an initial route with a greedy rule: "always drive to the closest
    outlet you haven't visited yet."

    Walkthrough:
      - Begin at `start`, mark it visited.
      - Look at every unvisited outlet, pick the nearest one, go there.
      - Repeat until all outlets are visited.

    Greedy = makes the locally-best choice each step. It's fast (O(n^2)) and
    usually gives a reasonable route, but it can make short-sighted choices
    (that's exactly what 2-opt fixes next).
    """
    n = len(matrix)
    visited = [False] * n
    route = [start]
    visited[start] = True

    current = start
    for _ in range(n - 1):            # we still need to add n-1 more stops
        nearest = -1
        nearest_dist = float("inf")
        for candidate in range(n):
            if not visited[candidate] and matrix[current][candidate] < nearest_dist:
                nearest = candidate
                nearest_dist = matrix[current][candidate]
        route.append(nearest)
        visited[nearest] = True
        current = nearest

    return route


# --------------------------------------------------------------------------- #
#  Step 2: 2-opt improvement heuristic                                        #
# --------------------------------------------------------------------------- #
def two_opt(route: List[int], matrix: List[List[float]], round_trip: bool) -> List[int]:
    """
    Improve a route by removing "crossings".

    The idea of 2-opt:
      Take any two edges in the route. If uncrossing them (reversing the
      segment between them) makes the route shorter, do it. Keep sweeping
      over all pairs until no single swap helps anymore (a "local optimum").

    Intuition: a route that crosses itself is never optimal -- you can always
    shorten it by swapping the crossed edges. 2-opt mechanically finds and
    fixes those crossings.

    We keep the first stop fixed (index 0) because that is the depot /
    chosen start point and we don't want to move it.

    Complexity: each full sweep is O(n^2); we repeat until no improvement.
    """
    best = route[:]                 # work on a copy
    improved = True

    while improved:
        improved = False
        # i and k define the segment best[i..k] that we try to reverse.
        # Start i at 1 so the depot (index 0) stays first.
        for i in range(1, len(best) - 1):
            for k in range(i + 1, len(best)):
                # Build a candidate route: reverse the segment between i and k.
                new_route = best[:i] + best[i:k + 1][::-1] + best[k + 1:]
                # Accept it only if it is strictly shorter.
                if route_distance(new_route, matrix, round_trip) < route_distance(best, matrix, round_trip):
                    best = new_route
                    improved = True
        # If a whole sweep made no improvement, `improved` stays False and we stop.

    return best


# --------------------------------------------------------------------------- #
#  Public entry point: solve the whole thing                                  #
# --------------------------------------------------------------------------- #
def solve_tsp(
    outlets: List[Dict[str, Any]],
    start_index: int = 0,
    round_trip: bool = True,
    avg_speed_kmph: float = 30.0,
    distance_matrix: Optional[List[List[float]]] = None,
    duration_matrix: Optional[List[List[float]]] = None,
    distance_source: str = "haversine",
) -> Dict[str, Any]:
    """
    Orchestrate the full solve and return a tidy result.

    `outlets` is a list of dicts, each with at least 'id', 'name',
    'latitude', 'longitude'. `start_index` is the position in that list to
    start from (the depot). Set `round_trip=False` for an open route that
    ends at the last delivery instead of returning to the depot.

    Distance/time sources (this is the new "real road" wiring):
      - `distance_matrix`  : if provided (e.g. real road km from OSRM), we
                             optimise on it. If None, we compute Haversine here.
      - `duration_matrix`  : if provided (real drive-time in minutes from OSRM),
                             each leg's time is read from it. If None, we
                             ESTIMATE time as distance / avg_speed_kmph.
      - `distance_source`  : a label passed straight through to the response so
                             the UI can show whether numbers are road or
                             straight-line.

    Returns a dictionary the API can hand straight back as JSON.
    """
    n = len(outlets)

    # Edge cases: 0 or 1 outlet has nothing to optimise.
    if n == 0:
        return {"ordered_outlets": [], "total_distance_km": 0.0,
                "total_time_minutes": 0.0, "leg_details": [], "route_index": [],
                "distance_source": distance_source}
    if n == 1:
        return {"ordered_outlets": outlets, "total_distance_km": 0.0,
                "total_time_minutes": 0.0, "leg_details": [],
                "route_index": [{"order": 1, "name": outlets[0]["name"],
                                 "is_depot": bool(outlets[0].get("is_depot", False)),
                                 "cumulative_distance_km": 0.0,
                                 "cumulative_time_minutes": 0.0}],
                "distance_source": distance_source}

    # 1. Use the supplied distance matrix, or build a Haversine one if none given.
    if distance_matrix is None:
        points = [(o["latitude"], o["longitude"]) for o in outlets]
        distance_matrix = build_distance_matrix(points)

    # 2. Construct an initial route, then improve it (optimise on DISTANCE).
    initial = nearest_neighbour(distance_matrix, start_index)
    optimised = two_opt(initial, distance_matrix, round_trip)

    # 3. Translate the index route back into actual outlet objects and
    #    compute per-leg stats for display.
    ordered = [outlets[i] for i in optimised]
    legs = []
    total_km = 0.0
    total_min = 0.0

    # Cumulative "index": for each stop in visit order, how far (and how long)
    # it takes to REACH it from the depot along the optimal route. The depot
    # itself is 0 km / 0 min; each later stop adds the leg that reaches it.
    route_index = []
    cum_km = 0.0
    cum_min = 0.0
    for position, idx in enumerate(optimised):
        if position > 0:
            prev = optimised[position - 1]
            leg_km = distance_matrix[prev][idx]
            leg_min = (duration_matrix[prev][idx] if duration_matrix is not None
                       else travel_time_minutes(leg_km, avg_speed_kmph))
            cum_km += leg_km
            cum_min += leg_min
        route_index.append({
            "order": position + 1,
            "name": outlets[idx]["name"],
            "is_depot": bool(outlets[idx].get("is_depot", False)),
            "cumulative_distance_km": round(cum_km, 2),
            "cumulative_time_minutes": round(cum_min, 1),
        })

    # Build the list of hops. If round_trip, append the return hop at the end.
    hop_indices = list(optimised)
    if round_trip:
        hop_indices = hop_indices + [optimised[0]]  # ...back to the depot

    for step in range(len(hop_indices) - 1):
        a = hop_indices[step]
        b = hop_indices[step + 1]
        d = distance_matrix[a][b]
        # Real drive-time if we have it, otherwise estimate from speed.
        if duration_matrix is not None:
            t = duration_matrix[a][b]
        else:
            t = travel_time_minutes(d, avg_speed_kmph)
        total_km += d
        total_min += t
        legs.append({
            "from": outlets[a]["name"],
            "to": outlets[b]["name"],
            "distance_km": round(d, 2),
            "time_minutes": round(t, 1),
        })

    return {
        "ordered_outlets": ordered,
        "total_distance_km": round(total_km, 2),
        "total_time_minutes": round(total_min, 1),
        "leg_details": legs,
        "route_index": route_index,
        "distance_source": distance_source,
    }
