"""
models.py
=========
Pydantic models = the "shapes" of data moving in and out of the API.

FastAPI uses these classes to:
  - Validate incoming JSON (reject a request missing a field or with a bad type).
  - Auto-generate the interactive API docs at /docs.
  - Serialise outgoing responses to clean JSON.

Think of each class as a contract: "a request/response of this kind MUST
look exactly like this."
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
#  Outlet models                                                              #
# --------------------------------------------------------------------------- #
class OutletCreate(BaseModel):
    """Shape of the JSON a client sends to CREATE an outlet (no id yet)."""
    name: str = Field(..., examples=["Koramangala Hub"])
    address: str = Field("", examples=["80 Feet Rd, Koramangala"])
    # Latitude is between -90 and 90; longitude between -180 and 180.
    # Pydantic enforces these bounds for us and returns a 422 if violated.
    latitude: float = Field(..., ge=-90, le=90, examples=[12.9352])
    longitude: float = Field(..., ge=-180, le=180, examples=[77.6245])
    is_depot: bool = Field(False, description="True if this is the warehouse/start point")


class Outlet(OutletCreate):
    """An outlet as stored/returned: everything in OutletCreate PLUS the id."""
    id: int


# --------------------------------------------------------------------------- #
#  Optimise request / response models                                         #
# --------------------------------------------------------------------------- #
class OptimizeRequest(BaseModel):
    """Options the client can send when asking for an optimised route."""
    start_id: Optional[int] = Field(
        None, description="Outlet id to start from. Defaults to the depot, else the first outlet."
    )
    round_trip: bool = Field(
        True, description="If True the route returns to the start (a loop)."
    )
    avg_speed_kmph: float = Field(
        30.0, gt=0, description="Average driving speed used to estimate time."
    )


class Leg(BaseModel):
    """One hop of the journey, from one outlet to the next."""
    from_: str = Field(..., alias="from")  # 'from' is a Python keyword, so we alias it
    to: str
    distance_km: float
    time_minutes: float

    class Config:
        populate_by_name = True  # allow building with either 'from_' or 'from'


class OptimizeResponse(BaseModel):
    """The full answer the API returns after solving the TSP."""
    ordered_outlets: List[Outlet]
    total_distance_km: float
    total_time_minutes: float
    leg_details: List[Leg]
