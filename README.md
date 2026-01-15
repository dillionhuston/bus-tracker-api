# Belfast Bus Tracker

A community-driven bus arrival time prediction system for Belfast.

The system combines static timetable data from Translink with crowdsourced journey observations submitted by users.  
No continuous GPS tracking is used — privacy is a core priority.

## Purpose

- Provide reasonably accurate bus arrival time predictions
- Require minimal user input and interaction
- Automatically improve predictions as more observations are collected
- Respect user privacy by avoiding live location tracking

## Core Principles

- No continuous/live GPS tracking
- All prediction calculations happen on the backend
- Users only provide very simple input (start + arrived)
- Use segment-based predictions (between consecutive stops) for faster learning
- Start with simple averaging, improve methods incrementally over time

## High-Level Architecture

- **Backend**: FastAPI + PostgreSQL
- **Frontend**: Minimal UI (dropdowns, buttons, simple display)
- **Data sources**:
  - Translink public transport API (static routes, stops, timetables)
  - User-submitted journey observations (dynamic real-world timings)

## Domain Models

| Model         | Purpose                              | Key Fields                                                                 |
|---------------|--------------------------------------|----------------------------------------------------------------------------|
| Route         | Represents a bus service             | route_id, name, direction, operator                                        |
| Stop          | Physical bus stop                    | stop_id, name, latitude, longitude                                         |
| RouteStop     | Ordered stops on a specific route    | route_id, stop_id, stop_order                                              |
| Segment       | Travel between two consecutive stops | segment_id, route_id, from_stop_id, to_stop_id                             |
| Journey       | Single user journey                  | journey_id, route_id, origin_stop_id, destination_stop_id, started_at, completed_at |
| 



## User Interaction Flow

1. **Start Journey**  
   User selects:  
   - Route  
   - Origin stop  
   - Destination stop  
   → Backend creates Journey record, starts prediction and records start timestamp

2. **Complete Journey**  
   User presses "Arrived" button when they reach their destination  
   → Backend:  
     - Calculates total journey duration  
     - Proportionally allocates time across all segments between origin and destination  
     - Stores individual segment Observations

## Prediction Logic

- Predictions are always **segment-based** (never full journey-based)
- ETA for each segment is calculated from historical observation averages (when available)
- All prediction logic lives on the backend
- Frontend only requests and displays the results

## Static Data Ingestion (Translink)

1. Fetch all available routes and store basic metadata
2. For each route: fetch ordered list of stops → store RouteStop entries
3. Automatically generate segments (Stop1→Stop2, Stop2→Stop3, etc.) for every route

## Frontend Responsibilities

**Does:**
- Show available routes and stops
- Allow users to start and complete journeys
- Display predicted arrival times

**Does NOT:**
- Perform any timing calculations
- Store historical data
- Run prediction algorithms

## MVP Scope (End of January 2026)

Must have working:

- Route and stop data ingestion from Translink
- Journey start/completion flow
- Observation storage
- Basic segment-based ETA prediction
- Simple UI for beta testing

**Out of scope for MVP:**

- Live GPS tracking
- Advanced machine learning models
- User accounts / authentication
- Complex API key system

## Installation

```bash
git clone https://github.com/dillionhuston/bus-tracker-api.git
cd bus-tracker-api

python3 -m venv venv
source venv/bin/activate          

pip install -r requirements.txt

python initdb.py                 

uvicorn main:app --reload