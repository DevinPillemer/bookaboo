"""
Bookaboo FastAPI server.

Endpoints:
  POST /reserve          - Full reservation flow from natural language text
  POST /search           - Search restaurants by name
  POST /availability     - Check availability for a specific venue/date/time
  GET  /health           - Health check
  GET  /reservations     - List saved local reservation events

Optional API key authentication via BOOKABOO_API_KEY environment variable.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

import bookaboo
from calendar_integration import load_events
from ontopo_client import BookingResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Bookaboo Restaurant Reservation API",
    description="Restaurant reservation system for Israel powered by the Ontopo API.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Optional API key auth
# ---------------------------------------------------------------------------

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_BOOKABOO_API_KEY: Optional[str] = os.getenv("BOOKABOO_API_KEY")


async def _check_api_key(api_key: Optional[str] = Security(_API_KEY_HEADER)) -> None:
    """Validate API key if BOOKABOO_API_KEY is set in the environment."""
    if _BOOKABOO_API_KEY and api_key != _BOOKABOO_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ReserveRequest(BaseModel):
    text: str

    class Config:
        json_schema_extra = {
            "example": {"text": "book 2 tonight 8pm at Prozdor"}
        }


class SearchRequest(BaseModel):
    query: str
    area: Optional[str] = None
    limit: int = 10

    class Config:
        json_schema_extra = {
            "example": {"query": "Prozdor", "limit": 5}
        }


class AvailabilityRequest(BaseModel):
    venue_id: str
    date: str          # YYYYMMDD
    time: str          # HHMM or HH:MM
    party_size: int = 2

    class Config:
        json_schema_extra = {
            "example": {
                "venue_id": "12345",
                "date": "20250307",
                "time": "2000",
                "party_size": 2,
            }
        }


class BookingResultResponse(BaseModel):
    success: bool
    restaurant_name: str = ""
    restaurant_address: str = ""
    date: str = ""
    display_date: str = ""
    time: str = ""
    party_size: int = 2
    checkout_url: str = ""
    area: str = ""
    available_slots: list[dict] = []
    waiting_list: bool = False
    phone_needed: bool = False
    phone_number: str = ""
    calendar_url: str = ""
    error: str = ""

    @classmethod
    def from_booking_result(cls, result: BookingResult) -> "BookingResultResponse":
        return cls(
            success=result.success,
            restaurant_name=result.restaurant_name,
            restaurant_address=result.restaurant_address,
            date=result.date,
            display_date=result.display_date,
            time=result.time,
            party_size=result.party_size,
            checkout_url=result.checkout_url,
            area=result.area,
            available_slots=result.available_slots,
            waiting_list=result.waiting_list,
            phone_needed=result.phone_needed,
            phone_number=result.phone_number,
            calendar_url=result.calendar_url,
            error=result.error,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "bookaboo"}


@app.post(
    "/reserve",
    response_model=BookingResultResponse,
    tags=["Reservations"],
    dependencies=[Depends(_check_api_key)],
)
async def reserve(body: ReserveRequest) -> BookingResultResponse:
    """
    Full end-to-end reservation from a natural-language request.

    Example body: `{"text": "book 2 tonight 8pm at Prozdor"}`
    """
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Request text cannot be empty.")
    result = await bookaboo.reserve(body.text)
    return BookingResultResponse.from_booking_result(result)


@app.post(
    "/search",
    response_model=list[dict],
    tags=["Venues"],
    dependencies=[Depends(_check_api_key)],
)
async def search(body: SearchRequest) -> list[dict[str, Any]]:
    """Search for restaurants by name."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    return await bookaboo.search_restaurants(body.query)


@app.post(
    "/availability",
    response_model=dict,
    tags=["Venues"],
    dependencies=[Depends(_check_api_key)],
)
async def availability(body: AvailabilityRequest) -> dict[str, Any]:
    """Check table availability for a specific venue, date, time, and party size."""
    time_normalised = body.time.replace(":", "")
    return await bookaboo.check_availability(
        venue_id=body.venue_id,
        date_yyyymmdd=body.date,
        time_hhmm=time_normalised,
        party_size=body.party_size,
    )


@app.get(
    "/reservations",
    response_model=list[dict],
    tags=["Reservations"],
    dependencies=[Depends(_check_api_key)],
)
async def list_reservations() -> list[dict[str, Any]]:
    """Return all locally saved reservation events."""
    return load_events()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BOOKABOO_PORT", "8000"))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False)
