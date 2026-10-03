"""
main.py
=======
The FastAPI application: the public face of the system.

It wires together the three layers you've already seen:
    HTTP request  ->  main.py (routing/validation)
                  ->  database.py (storage)
                  ->  tsp_solver.py (the algorithm)
                  ->  JSON response

Run it with:   uvicorn main:app --reload   (from inside the backend/ folder)
Then open:     http://127.0.0.1:8000        (the map UI)
And:           http://127.0.0.1:8000/docs    (auto-generated Swagger API docs)
"""

import os
import csv
import io
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Our own modules.
import database
import seed_data
import distance
from models import Outlet, OutletCreate, OptimizeRequest, OptimizeResponse
from tsp_solver import solve_tsp

# --------------------------------------------------------------------------- #
#  App setup                                                                   #
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="TSP Route Optimizer",
    description="Suggests optimal delivery routes using the Travelling Salesman Problem.",
    version="1.0.0",
)

# CORS lets a browser page fetch this API even if it's served from a different
# origin. We allow everything here for simplicity. In production you would list
# only your real frontend domain(s). (Good interview talking point: what CORS
# is and why browsers enforce it.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Make sure the database + table exist before serving any request."""
    database.init_db()


# --------------------------------------------------------------------------- #
#  Outlet CRUD endpoints                                                       #
# --------------------------------------------------------------------------- #
@app.get("/outlets", response_model=list[Outlet], tags=["Outlets"])
def list_outlets():
    """Return every outlet currently in the database."""
    return database.get_all_outlets()


@app.post("/outlets", response_model=Outlet, tags=["Outlets"])
def create_outlet(outlet: OutletCreate):
    """
    Add a new outlet. FastAPI has already validated the body against
    OutletCreate (correct types, lat/lon in range) before we get here.
    """
    return database.add_outlet(
        name=outlet.name,
        address=outlet.address,
        latitude=outlet.latitude,
        longitude=outlet.longitude,
        is_depot=outlet.is_depot,
    )


@app.delete("/outlets/{outlet_id}", tags=["Outlets"])
def remove_outlet(outlet_id: int):
    """Delete one outlet by id, or return 404 if it doesn't exist."""
    if not database.delete_outlet(outlet_id):
        raise HTTPException(status_code=404, detail=f"No outlet with id {outlet_id}")
    return {"deleted": outlet_id}


@app.post("/seed", tags=["Outlets"])
def seed_sample_data():
    """Reset the database to the built-in sample outlets. Great for demos."""
    count = seed_data.seed()
    return {"seeded": count}


@app.post("/outlets/upload", tags=["Outlets"])
async def upload_outlets(request: Request):
    """
    Replace all outlets with ones from an uploaded CSV.

    The CSV is sent as the raw request body (the frontend reads the file and
    posts its text), so this needs no file-upload dependency. Expected columns
    (header row required, order doesn't matter):

        name, latitude, longitude, is_depot

    `is_depot` is optional; values like 1/true/yes/depot mean True.

    Returns how many rows were added, how many were skipped, and any errors —
    so the user gets clear feedback on a malformed file.
    """
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload. Send a CSV file.")

    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig also strips a BOM if present
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV has no header row.")

    # Normalise headers to lowercase so 'Name'/'name'/'LATITUDE' all work.
    headers = {h.lower().strip() for h in reader.fieldnames}
    required = {"name", "latitude", "longitude"}
    missing = required - headers
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required column(s): {', '.join(sorted(missing))}",
        )

    truthy = {"1", "true", "yes", "y", "depot"}
    parsed = []   # rows that are valid
    errors = []   # human-readable problems, by row number

    for i, row in enumerate(reader, start=2):  # start=2: row 1 is the header
        # Access case-insensitively.
        low = {(k.lower().strip() if k else k): v for k, v in row.items()}
        name = (low.get("name") or "").strip()
        lat_s = (low.get("latitude") or "").strip()
        lon_s = (low.get("longitude") or "").strip()
        depot_s = (low.get("is_depot") or "").strip().lower()

        if not name:
            errors.append(f"Row {i}: missing name")
            continue
        try:
            lat = float(lat_s)
            lon = float(lon_s)
        except ValueError:
            errors.append(f"Row {i} ({name}): latitude/longitude must be numbers")
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            errors.append(f"Row {i} ({name}): latitude/longitude out of range")
            continue

        parsed.append((name, lat, lon, depot_s in truthy))

    if not parsed:
        raise HTTPException(
            status_code=400,
            detail="No valid rows found. " + (" ".join(errors) if errors else ""),
        )

    # Everything checks out -> replace the dataset.
    database.clear_all_outlets()
    for name, lat, lon, is_depot in parsed:
        database.add_outlet(name, "", lat, lon, is_depot)

    return {"added": len(parsed), "skipped": len(errors), "errors": errors}


# --------------------------------------------------------------------------- #
#  The main event: optimise a route                                           #
# --------------------------------------------------------------------------- #
@app.post("/optimize", response_model=OptimizeResponse, tags=["Routing"])
def optimize_route(options: OptimizeRequest):
    """
    Compute the optimal delivery route over ALL outlets in the database.

    Flow:
      1. Load outlets from the DB.
      2. Figure out which one is the start (explicit start_id, else the depot,
         else the first outlet).
      3. Hand them to the TSP solver (nearest-neighbour + 2-opt).
      4. Return the ordered route plus distance/time stats.
    """
    outlets = database.get_all_outlets()
    if len(outlets) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 outlets to build a route. Add more or POST /seed.",
        )

    # Decide the starting index within the outlets list.
    start_index = 0
    if options.start_id is not None:
        # Client explicitly chose a start outlet.
        match = [i for i, o in enumerate(outlets) if o["id"] == options.start_id]
        if not match:
            raise HTTPException(status_code=404,
                                detail=f"start_id {options.start_id} not found")
        start_index = match[0]
    else:
        # No explicit start: prefer the depot if one is flagged.
        depot = [i for i, o in enumerate(outlets) if o["is_depot"]]
        if depot:
            start_index = depot[0]

    # Build the distance/time matrices for the requested mode. In "road" mode
    # this calls OSRM; if OSRM is unreachable it transparently falls back to
    # Haversine and says so in `source`.
    points = [(o["latitude"], o["longitude"]) for o in outlets]
    matrices = distance.build_matrices(points, mode=options.mode)

    result = solve_tsp(
        outlets=outlets,
        start_index=start_index,
        round_trip=options.round_trip,
        avg_speed_kmph=options.avg_speed_kmph,
        distance_matrix=matrices["distance_matrix"],
        duration_matrix=matrices["duration_matrix"],
        distance_source=matrices["source"],
    )

    # If we got real road data, also fetch the actual road geometry for the
    # optimised order so the frontend can draw the true driving path. This is
    # best-effort: if it fails we just skip it (the UI draws straight lines).
    if matrices["source"] == "road":
        ordered_points = [(o["latitude"], o["longitude"])
                          for o in result["ordered_outlets"]]
        if options.round_trip and ordered_points:
            ordered_points = ordered_points + [ordered_points[0]]
        try:
            result["route_geometry"] = distance.osrm_route_geometry(ordered_points)
        except Exception as exc:  # noqa: BLE001 - geometry is optional
            print(f"[optimize] Could not fetch road geometry: {exc}")
            result["route_geometry"] = None

    return result


# --------------------------------------------------------------------------- #
#  Serve the frontend                                                         #
# --------------------------------------------------------------------------- #
# We serve the single-page UI directly from FastAPI so the whole project runs
# with ONE command and there is no CORS hassle in the demo. The HTML lives in
# ../frontend/index.html.
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Return the map UI at the root URL."""
    return FileResponse(FRONTEND)
