# 🚚 TSP Route Optimizer

> Optimal delivery-route suggestions powered by the **Travelling Salesman Problem (TSP)**.

Give the app the delivery outlets of a business and it computes the shortest
route to visit them all — complete with total distance and estimated travel
time — and draws it live on an interactive map.

Built as a full-stack SDE project with a deliberately simple, transparent
stack: every component is a choice you can read, understand, and explain
end-to-end.

<!-- Add a screenshot once you've run it:  ![screenshot](docs/screenshot.png) -->

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)
![uv](https://img.shields.io/badge/packaging-uv-purple)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

---

## ✨ What it does

- **Store delivery outlets** (name + latitude/longitude) in a database.
- **Mark one outlet as the depot** — the warehouse you start and end at.
- **Compute the optimal visit order** using a TSP heuristic (Nearest-Neighbour + 2-opt).
- **Use real road distances & drive times** via the OSRM routing engine — or switch to straight-line (Haversine) mode with a toggle.
- **Visualize the route** on an interactive Leaflet map, drawn along the actual roads, with numbered stops.
- **See the numbers that matter:** total kilometres and total minutes (real drive time in road mode).
- **Route index:** a table of the cumulative distance & time to reach each stop from the depot along the optimal route.
- **Start instantly, then bring your own data:** the sample dataset loads on first open; after your first run, upload a CSV of your own depot + outlets (a template is one click away).
- **Manage data easily:** add outlets by clicking the map, delete them, or reload the sample dataset.

---

## 🧰 Tech stack

| Layer | Technology | Why it was chosen |
|-------|------------|-------------------|
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) | Modern, fast, and auto-generates interactive API docs at `/docs`. |
| **Algorithm** | Pure Python (Nearest-Neighbour + 2-opt) | No black-box solver library — the TSP logic is fully readable. |
| **Distance model** | OSRM road network + Haversine fallback | Real driving distance/time from [OSRM](http://project-osrm.org/) (no API key), with straight-line Haversine as an automatic offline fallback. |
| **Database** | SQLite (via built-in `sqlite3`) | A real SQL database in a single file; raw SQL, no ORM. |
| **Frontend** | HTML + vanilla JS + [Leaflet.js](https://leafletjs.com/) | A real interactive map with **zero build step**. |
| **Packaging** | [uv](https://docs.astral.sh/uv/) | Fast, reproducible dependency management (`pyproject.toml` + `uv.lock`). |

---

## 📁 Project structure

```
tsp-route-optimizer/
├── backend/
│   ├── main.py         # FastAPI app: routes, validation, serves the frontend
│   ├── tsp_solver.py   # The TSP algorithm: Nearest-Neighbour + 2-opt
│   ├── distance.py     # OSRM road distance/time + geometry, Haversine fallback
│   ├── models.py       # Pydantic models (request/response contracts)
│   ├── database.py     # SQLite storage (raw SQL)
│   └── seed_data.py    # Sample outlets for the demo
├── frontend/
│   └── index.html      # Leaflet map UI (vanilla JS)
├── data/               # SQLite file is created here at runtime
├── pyproject.toml      # Project metadata + dependencies (uv's source of truth)
├── uv.lock             # Exact pinned dependency versions
├── requirements.txt    # Fallback for non-uv environments
└── README.md
```

---

## 🚀 Getting started — step by step

Follow these steps to run the project from scratch. They work on
**Windows, macOS, and Linux**.

### Step 1 — Install Python 3.10 or newer

Check whether you already have it:

```bash
python --version
```

If it prints `3.10` or higher, you're set. Otherwise download it from
[python.org/downloads](https://www.python.org/downloads/) (on Windows, tick
**"Add Python to PATH"** during install).

### Step 2 — Install uv (the package manager)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen your terminal, then confirm it works:

```bash
uv --version
```

### Step 3 — Get the code

```bash
git clone https://github.com/<your-username>/tsp-route-optimizer.git
cd tsp-route-optimizer
```

### Step 4 — Install the dependencies

`uv sync` reads `pyproject.toml` + `uv.lock` and sets up an isolated
environment with the exact pinned versions. (The first run builds a cache and
can take a minute or two; later runs are instant.)

```bash
uv sync
```

### Step 5 — Run the server

```bash
uv run uvicorn main:app --app-dir backend --reload
```

`uv run` executes the command inside the project's environment automatically —
there's no separate "activate" step. When you see
`Uvicorn running on http://127.0.0.1:8000`, it's ready.

### Step 6 — Open the app

Open your browser to:

| URL | What it is |
|-----|------------|
| **http://127.0.0.1:8000** | The interactive map UI |
| **http://127.0.0.1:8000/docs** | Auto-generated Swagger API docs |

### Step 7 — Try it out

1. Click **"Load sample data"** to add 10 example outlets in Bengaluru.
2. Click **"Optimise route"** — the optimal path is drawn on the map with
   numbered stops, and the total distance and time appear in the sidebar.
3. Add your own outlets by clicking anywhere on the map (it fills in the
   coordinates) and pressing **"Add outlet"**.

To stop the server, press **Ctrl + C** in the terminal.

### Using your own data

The sample dataset loads automatically on first open. **After you optimise
once**, a "Use your own data" panel appears where you can upload a CSV of your
own depot and outlets. Click **Download CSV template** for the exact format:

```csv
name,latitude,longitude,is_depot
Central Warehouse,12.9767,77.5713,true
Outlet A,12.9352,77.6245,false
Outlet B,12.9719,77.6412,false
```

- `is_depot` marks your start/end point (`true` for one row; the rest `false`).
- Invalid rows are skipped and reported, so a small typo won't break the upload.

> **No uv?** You can fall back to pip instead of steps 2, 4, and 5:
> ```bash
> pip install -r requirements.txt
> uvicorn main:app --app-dir backend --reload
> ```

---

## 🔌 API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/outlets` | List all outlets |
| `POST` | `/outlets` | Add a new outlet |
| `DELETE` | `/outlets/{id}` | Delete an outlet |
| `POST` | `/seed` | Reset to the sample dataset |
| `POST` | `/outlets/upload` | Replace outlets from an uploaded CSV |
| `POST` | `/optimize` | Compute the optimal route (returns a cumulative route index) |
| `GET` | `/` | Serves the map UI |

**Example — optimise a route:**

```bash
curl -X POST http://127.0.0.1:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"round_trip": true, "avg_speed_kmph": 30}'
```

Returns the outlets in optimal visit order, total distance, total time, and
a per-leg breakdown.

---

## 🧠 How the optimization works

**The problem:** visit every outlet exactly once, starting from the depot,
with the shortest total distance. TSP is **NP-hard** — the number of possible
routes grows factorially:

| Outlets | Possible routes |
|--------:|-----------------|
| 10 | ~181,000 |
| 15 | ~43 billion |
| 50 | more than atoms in the galaxy |

So checking every route is impossible at scale. This project uses a classic
two-phase **heuristic**:

1. **Nearest-Neighbour** builds an initial route fast — from each stop, go to
   the closest unvisited outlet. Simple and quick (`O(n²)`), but it can make
   short-sighted choices.
2. **2-opt** then improves that route by repeatedly reversing segments to
   remove "crossings," until no single swap helps anymore (a local optimum).

Together they land within a few percent of optimal in milliseconds. On the
sample data, 2-opt improves the route from **88.0 km → 82.9 km (~6%)**
(straight-line); in road mode the solver optimizes on real driving distances
instead.

### Distance: road vs straight-line

The `/optimize` endpoint accepts a `mode`:

- **`"road"` (default)** — calls the **OSRM** `/table` service, which returns the
  full road-distance *and* drive-time matrix in a single request. The route is
  then drawn along the actual roads using OSRM's `/route` geometry. No API key
  required (uses the public demo server).
- **`"haversine"`** — pure straight-line math, fully offline.

If a road request can't reach OSRM, it **automatically falls back to Haversine**
and labels the result accordingly, so the app never breaks. All of this lives in
`distance.py` — the solver and API don't care how a distance was obtained, which
is a clean example of separation of concerns.

---

## 📦 The business case

Delivery businesses lose money to inefficient routes — wasted fuel, longer
driver hours, missed SLAs. This tool turns a raw list of stops into the
shortest route automatically and reports the distance and time it saves. Even
a ~6% reduction compounds across every driver, every day. That's the value
proposition for any logistics or last-mile delivery operation.

---

## 🔭 Possible extensions

- **Multiple vehicles** → the Vehicle Routing Problem (VRP).
- **Delivery time windows** and per-outlet priorities.
- **Self-hosted OSRM** (Docker) for no rate limits and full offline road routing.
- **Stronger optimization** — Or-opt / 3-opt, simulated annealing, or Google OR-Tools.
- **Export routes** to Google Maps navigation links.

---

## ⚠️ Design notes & limitations

- The solver finds a **near-optimal** route (heuristic), not a provably
  optimal one — an honest and standard trade-off for realistic sizes.
- Road distances come from the **public OSRM demo server**, which is
  rate-limited and "best effort" — great for a demo, but for production you'd
  self-host OSRM (Docker) or use a paid routing API. The straight-line fallback
  keeps the app usable regardless.
- Storage uses **SQLite** for zero-setup simplicity; the storage layer is
  isolated in `database.py`, so moving to PostgreSQL later wouldn't affect the
  API or the solver.

---

## 📄 License

Released under the [MIT License](LICENSE) — free to use, modify, and learn from.
