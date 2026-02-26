# Bookaboo — Restaurant Reservation System for Israel

Bookaboo is a production-ready restaurant reservation assistant that talks directly to the **Ontopo API** — no browser automation required. It supports a natural-language CLI, a FastAPI REST server, Google Calendar integration, and is ready to plug into automation workflows like BruBot.

---

## Features

- **Natural-language parsing** — "book 2 tonight 8pm at Prozdor" just works
- **Ontopo API integration** — anonymous auth, venue search, availability check, checkout URL
- **Smart slot selection** — picks the available slot closest to your requested time
- **Google Calendar deep links** — one-click "Add to Calendar"
- **Local event store** — `~/.config/restaurant-reservations/calendar_events.json`
- **Phone-call mode** — generates a ready-to-read script when a call is required
- **Waiting-list support** — gracefully handles full restaurants
- **FastAPI REST server** — expose Bookaboo as a microservice
- **Docker-ready** — single `docker run` command to start the server
- **Optional API key auth** — secure the REST API via `BOOKABOO_API_KEY`

---

## Quick start

### Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### CLI usage

```bash
# Basic reservation
python3 reserve.py "book 2 tonight 8pm at Prozdor"

# With explicit date and party size
python3 reserve.py "reservation for 4 tomorrow 7:30pm at Machneyuda"

# Next Friday
python3 reserve.py "dinner next Friday 9pm, 3 people, Taizu"

# Make it executable (already done in the repo)
chmod +x reserve.py
./reserve.py "book 2 tonight 8pm at Prozdor"
```

#### Output examples

**Success:**
```
────────────────────────────────────────────────────────────
🎉  Reservation Ready!
────────────────────────────────────────────────────────────

  Restaurant:                    Prozdor
  Address:                       Ibn Gabirol 71, Tel Aviv
  Date:                          Thursday, March 7
  Time:                          20:00
  Party size:                    2

  Checkout URL:                  https://ontopo.co.il/reservation/checkout?...
  Add to Calendar:               https://calendar.google.com/calendar/render?...

  Complete your booking at the checkout URL above.
────────────────────────────────────────────────────────────
```

**Phone required:**
```
────────────────────────────────────────────────────────────
📞  Phone Call Required
────────────────────────────────────────────────────────────

  Restaurant:                    Machneyuda
  Restaurant phone:              +972-2-555-0000

  ── Call Script ──────────────────────────────────

  "Hi, this is Devin Pillemer, I'd like to make a reservation
   for 4 people on Friday, March 8 at 19:30.
   My phone number is +972-50-724-2120."
────────────────────────────────────────────────────────────
```

---

## REST API server

### Start the server

```bash
# Default port 8000
python3 api_server.py

# Or with uvicorn directly
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# With optional API key auth
BOOKABOO_API_KEY=mysecret uvicorn api_server:app --port 8000
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/reserve` | Full reservation from natural-language text |
| `POST` | `/search` | Search restaurants by name |
| `POST` | `/availability` | Check availability for a venue |
| `GET` | `/reservations` | List locally saved reservations |

Interactive docs: `http://localhost:8000/docs`

### Example requests

```bash
# Reserve
curl -X POST http://localhost:8000/reserve \
  -H "Content-Type: application/json" \
  -d '{"text": "book 2 tonight 8pm at Prozdor"}'

# Search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Prozdor", "limit": 5}'

# Availability
curl -X POST http://localhost:8000/availability \
  -H "Content-Type: application/json" \
  -d '{"venue_id": "12345", "date": "20250307", "time": "2000", "party_size": 2}'

# With API key auth
curl -X GET http://localhost:8000/reservations \
  -H "X-API-Key: mysecret"
```

### Response schema (`/reserve`)

```json
{
  "success": true,
  "restaurant_name": "Prozdor",
  "restaurant_address": "Ibn Gabirol 71, Tel Aviv",
  "date": "20250307",
  "display_date": "Thursday, March 7",
  "time": "20:00",
  "party_size": 2,
  "checkout_url": "https://ontopo.co.il/reservation/checkout?...",
  "area": "Tel Aviv",
  "available_slots": [...],
  "waiting_list": false,
  "phone_needed": false,
  "phone_number": "",
  "calendar_url": "https://calendar.google.com/calendar/render?...",
  "error": ""
}
```

---

## Docker

```bash
# Build
docker build -t bookaboo .

# Run
docker run -p 8000:8000 bookaboo

# With API key
docker run -p 8000:8000 -e BOOKABOO_API_KEY=mysecret bookaboo

# With custom port
docker run -p 9000:9000 -e BOOKABOO_PORT=9000 bookaboo
```

---

## Configuration

### Environment variables (`.env`)

```bash
cp .env.example .env
# Edit .env with your values
```

| Variable | Default | Description |
|----------|---------|-------------|
| `BOOKABOO_API_KEY` | (empty) | API key for REST auth; disabled if empty |
| `BOOKABOO_PORT` | `8000` | Port for the FastAPI server |

### User profile

The default profile is in `config/user_profile.json` and is also written to `~/.config/restaurant-reservations/user_profile.json` on first save. Edit either file to change your details.

```json
{
  "first_name": "Devin",
  "last_name": "Pillemer",
  "email": "devin.pillemer@gmail.com",
  "phone": "+972-50-724-2120",
  "party_size": 2,
  "preferred_time": "20:00"
}
```

### Local event store

Saved reservations are stored at:
```
~/.config/restaurant-reservations/calendar_events.json
```
File permissions are automatically set to `0600` (owner read/write only).

---

## Running tests

```bash
pip install -r requirements.txt
pytest test_bookaboo.py -v
```

---

## BruBot integration

Bookaboo exposes a clean REST API that BruBot (or any automation layer) can call directly:

```python
import httpx

async def book_restaurant(text: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/reserve",
            json={"text": text},
            headers={"X-API-Key": "your-key"},
        )
        return resp.json()
```

Alternatively, import the orchestrator directly:

```python
from bookaboo import reserve

result = await reserve("book 2 tonight 8pm at Prozdor")
if result.success:
    print(result.checkout_url)
```

---

## Architecture

```
reserve.py / api_server.py
       │
       ▼
  bookaboo.py  (orchestrator)
  ┌────────────┬─────────────────┬──────────────────┐
  │            │                 │                  │
nlp_parser  ontopo_client  calendar_integration  notifications
                │
          Ontopo REST API
          (ontopo.co.il)
```

---

## Ontopo API notes

- **Anonymous auth**: `POST /api/loginAnonymously` with `distributor: "15171493"`, `version: "7738"`
- **Venue search**: `GET /api/venue_search?query=...`
- **Availability**: `POST /api/availability_search` — date in `YYYYMMDD`, time in `HHMM` format
- **Checkout**: Deep-link URL built client-side from venue ID + slot parameters
