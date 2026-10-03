"""
seed_data.py
============
Sample delivery outlets so the demo has something to show immediately.

The scenario: a fictional company, "QuickDrop Logistics", runs a central
warehouse in Bengaluru plus several delivery outlets across the city.
These are real-ish coordinates spread around the city so the optimised
route looks meaningful on the map.

You can import and call `seed()` from anywhere, or hit the POST /seed
endpoint from the frontend's "Load sample data" button.
"""

from database import clear_all_outlets, add_outlet

# (name, address, latitude, longitude, is_depot)
SAMPLE_OUTLETS = [
    ("Central Warehouse", "Majestic, Bengaluru", 12.9767, 77.5713, True),   # the depot
    ("Koramangala Hub",   "Koramangala",         12.9352, 77.6245, False),
    ("Indiranagar Store", "Indiranagar",         12.9719, 77.6412, False),
    ("Whitefield Point",  "Whitefield",          12.9698, 77.7500, False),
    ("Electronic City",   "Electronic City",     12.8452, 77.6602, False),
    ("Jayanagar Outlet",  "Jayanagar",           12.9250, 77.5938, False),
    ("Hebbal Depot",      "Hebbal",              13.0358, 77.5970, False),
    ("Marathahalli Spot", "Marathahalli",        12.9560, 77.7010, False),
    ("Yelahanka Branch",  "Yelahanka",           13.1007, 77.5963, False),
    ("BTM Layout Store",  "BTM Layout",          12.9166, 77.6101, False),
]


def seed() -> int:
    """Wipe existing outlets and load the sample set. Returns the count added."""
    clear_all_outlets()
    for name, address, lat, lon, is_depot in SAMPLE_OUTLETS:
        add_outlet(name, address, lat, lon, is_depot)
    return len(SAMPLE_OUTLETS)


# Allow running `python seed_data.py` directly to (re)seed the database.
if __name__ == "__main__":
    from database import init_db
    init_db()
    n = seed()
    print(f"Seeded {n} sample outlets into the database.")
