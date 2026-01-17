#  Bus Tracker API Documentation

## Overview

The Bus Tracker API is a backend service built with **FastAPI** that provides structured access to bus routes, stops, and journey tracking.

It is designed to support a frontend application that allows users to:

- View available bus routes  
- Retrieve ordered stops for a selected route  
- Start a journey  
- Track journey events (e.g. delays, stop reached, arrival)

The API focuses on:
- Clean REST API design  
- Performance-efficient database access  
- Clear separation of concerns  
- Predictable, schema-validated responses  

---

## Tech Stack

- Python 3.11  
- FastAPI  
- SQLAlchemy ORM  
- PostgreSQL  
- Pydantic  
- Uvicorn  

---

## Design Principles

- **Routers** → HTTP layer only  
- **Services** → Business logic  
- **Models** → Database schema  
- **Schemas** → API contracts  

This structure ensures the application is maintainable, testable, and scalable.

---

## Project Structure

```
app/
├── routers/
│   ├── Route.py
│   ├── Journey.py
│   └── Stop.py
├── models/
│   ├── BusRoute.py
│   ├── Stop.py
│   ├── RouteStop.py
│   └── Journey.py
├── schemas/
│   ├── route.py
│   ├── journey.py
│   └── stop.py
├── services/
│   └── journeyService/
│       ├── journey_service.py
│       └── eventHandler.py
└── main.py
```

---

## Routes API

### Get All Routes

```
GET /route/routes
```

**Description**  
Returns all available bus routes. This endpoint is used by the frontend to populate the route selection dropdown.

**Response (200)**

```json
[
  {
    "id": "12A",
    "name": "City Centre to Airport"
  }
]
```

**Errors**
- `404` – No routes found

---

### Get Stops for a Route

```
GET /route/routes/{route_id}/stops
```

**Description**  
Returns all stops for a given route, ordered by sequence.

**Response (200)**

```json
[
  {
    "id": "STOP_001",
    "name": "Main Street",
    "sequence": 1
  },
  {
    "id": "STOP_002",
    "name": "City Centre",
    "sequence": 2
  }
]
```

---

## Journey API

### Start a Journey

```
POST /journeys/start
```

**Request Body**

```json
{
  "route_id": "12A",
  "start_stop_id": "STOP_001",
  "end_stop_id": "STOP_010"
}
```

**Response (201)**

```json
{
  "id": "uuid",
  "predicted_status": "ON_TIME",
  "predicted_arrival": "2025-01-20T14:30:00"
}
```

---

### Add Journey Event

```
POST /journeys/{journey_id}/event
```

**Request Body**

```json
{
  "event_type": "DELAYED"
}
```

**Response (200)**

```json
{
  "journey_id": "uuid",
  "status": "DELAYED"
}
```

---

## Error Handling

Errors return structured JSON responses:

```json
{
  "detail": "No stops found for this route"
}
```

---

## Running Locally

```bash
git clone https://github.com/dillionhuston/bus-tracker-api
cd bus-tracker-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger UI:
```
http://localhost:8000/docs
```

---

## Future Improvements

- Translink API integration  
- Caching  
- Authentication  
- Automated testing  
- Rate limiting  
