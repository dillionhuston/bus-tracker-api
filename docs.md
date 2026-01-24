# Technical Documentation

## System Overview

This is a FastAPI-based journey tracking system for public transit. Users submit their actual journey experiences, which feed into a prediction engine that gets smarter over time. Think of it as crowdsourced transit reliability data.

## Architecture

### Three-Layer Design

1. **API Layer** (`routes/`): FastAPI endpoints handling HTTP requests
2. **Service Layer** (`Services/`): Business logic and data processing
3. **Data Layer** (`models/`): SQLAlchemy ORM models and database interactions

This separation keeps concerns isolated and makes testing way easier.

## Database Schema

### Core Tables

#### routes
```sql
- id (String, PK): Public route identifier (e.g., "16", "2a")
- name (String): Human-readable route name
- direction (String): Route direction if applicable
- official_timetable (JSON): Stored timetable data
- timetable_last_updated (DateTime): When timetable was last refreshed
```

#### stops
```sql
- id (String, PK): Public stop identifier (ATCO code)
- name (String): Stop name
- latitude (Float): GPS latitude
- longitude (Float): GPS longitude
```

#### route_stops
Junction table linking routes to stops in sequence.

```sql
- route_id (String, PK, FK)
- stop_id (String, PK, FK)
- sequence (Integer): Order of stop on route
- direction (String): Which direction this applies to
```

**Why composite primary key?** A stop can appear multiple times on a route (different directions or loop routes).

#### journeys
The heart of the system. Stores both user-submitted and official journey data.

```sql
- id (String, PK): UUID for internal tracking
- route_id (String, FK): Which route
- start_stop_id (String, FK): Where journey started
- end_stop_id (String, FK): Intended destination
- planned_start_time (DateTime): When user expected to start
- start_time (DateTime): Actual start (when bus arrived)
- end_time (DateTime): When journey completed
- status (String): Current state (STARTED, ARRIVED, etc.)
- created_at (DateTime): Record creation timestamp
- official_start_time (String): Timetable scheduled start
- official_end_time (String): Timetable scheduled end
- predicted_status (String): Engine prediction (on_time, delayed, early)
- predicted_arrival (String): Predicted arrival time
- data_source (String): "user" or "official"
- is_synthetic (Boolean): True for seeded test data
```

**Why String for times in some fields?** Official times come from external APIs as strings. We store them as-is to avoid timezone conversion issues. DateTimes are used where we control the data.

## API Endpoints

### Route Discovery

#### GET /route/routes
Returns all available routes. Used to populate frontend dropdowns.

**Response:**
```json
[
  {
    "id": "9B-0",
    "name": "City Center - Airport"
  }
]
```

**Error cases:**
- 404: No routes in database

#### GET /route/routes/{route_id}/stops
Returns stops for a route, ordered by sequence.

**Query params:** None

**Response:**
```json
[
  {
    "id": "490000001",
    "name": "Main Street",
    "sequence": 1,
    "direction": "outbound"
  }
]
```

**Implementation notes:**
- Filters out stops with missing/invalid names
- Warns about duplicate sequences (data quality issue)
- Uses SQLAlchemy joinedload to avoid N+1 queries

### Journey Management

#### POST /journeys/start
Create a new journey. This is step 1 of the user flow.

**Request:**
```json
{
  "route_id": "16",
  "start_stop_id": "490000001",
  "end_stop_id": "490000050",
  "planned_start_time": "2026-01-24T09:00:00Z"  // optional
}
```

**Response:**
```json
{
  "journey_id": "550e8400-e29b-41d4-a716-446655440000",
  "route_id": "16",
  "start_stop_id": "490000001",
  "predicted_status": "on_time",
  "predicted_arrival": "2026-01-24 09:23:00",
  "status": "STARTED"
}
```

**What happens internally:**
1. Validates route and stops exist in database
2. Calls PredictionService to get initial ETA
3. Creates journey record with status=STARTED
4. Returns journey UUID for subsequent event submissions

**Error cases:**
- 400: Missing start or end stop
- 404: Route or stop not found

#### POST /journeys/{journey_id}/event
Update journey status. Users call this when events happen (bus arrives, they reach their stop, etc.)

**Path params:**
- journey_id: UUID returned from /start

**Request:**
```json
{
  "event": "ARRIVED"  // or DELAYED, STOP_REACHED
}
```

**Response:**
```json
{
  "journey_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ARRIVED",
  "predicted_arrival": "2026-01-24 09:23:00",
  "updated_at": "2026-01-24T09:05:00Z"
}
```

**Valid state transitions:**
- STARTED → DELAYED
- STARTED → ARRIVED
- DELAYED → ARRIVED
- ARRIVED → STOP_REACHED

Invalid transitions throw 400 errors.

## Service Layer Deep Dive

### JourneyService

Main orchestrator for journey lifecycle.

#### start_journey()
```python
def start_journey(data: StartJourney, db: Session) -> Journey
```

**Responsibilities:**
1. Validate route and stops exist
2. Extract official timetable times (if available)
3. Call prediction service for initial ETA
4. Create journey record with all fields populated
5. Return journey object

**Design decision:** We get predictions at journey creation, not on-demand. This lets us track prediction accuracy over time.

### JourneyEventHandler

Handles state transitions. Each event type has its own method.

#### arrived()
Marks that the bus has arrived at the starting stop. Journey is now active.

**Allowed from:** STARTED, DELAYED

**Side effects:**
- Sets start_time to current UTC
- Updates status to ARRIVED

#### delayed()
User reports the bus is delayed.

**Allowed from:** STARTED only

**Side effects:**
- Updates status to DELAYED
- Does NOT change predicted times (that happens in background)

#### stop_reached()
Journey is complete. User has reached their destination.

**Allowed from:** STARTED, DELAYED, ARRIVED

**Side effects:**
- Sets end_time to current UTC
- Updates status to STOP_REACHED
- Marks journey as complete (used in predictions)

**Why allow from STARTED?** User might start journey tracking late, after they've already boarded.

#### add_event()
Router method that dispatches to specific handlers.

```python
handlers = {
    "ARRIVED": self.arrived,
    "DELAYED": self.delayed,
    "STOP_REACHED": self.stop_reached,
}
```

Returns 400 for unsupported event types.

## Prediction Engine

This is where the magic happens.

### Design Philosophy

Real-world transit is messy. Official timetables often don't reflect reality (traffic, driver behavior, time of day). User data is noisy but accurate in aggregate. The engine balances both.

### Data Quality Thresholds

```python
MIN_FOR_STATS = 5           # Minimum to use median
MIN_TO_TRUST_USERS_ONLY = 20  # Ignore official data
FALLBACK_MINUTES = 30       # When we have nothing
HIGH_THRESHOLD_MINUTES = 45 # Flag as delayed
```

These are tuneable based on your transit system's characteristics.

### predict_journey()

```python
def predict_journey(
    db: Session,
    route_id: str,
    start_time: datetime
) -> Tuple[datetime, str]
```

**Returns:** (predicted_arrival_time, status)

**Algorithm:**

1. **Sanity check:** If start_time is >24 hours in future, use fallback (probably bad data)

2. **Fetch user journeys:** Get last 100 completed user journeys for this route
   - Filters: status=STOP_REACHED, data_source=user
   - Validates: start_time and end_time exist and are logical
   - Computes: duration = end_time - start_time
   - Orders by recency (recent journeys more relevant)

3. **Decision tree:**
   ```
   if user_count >= 20:
       use_only_user_data()
   else:
       fetch_official_journeys()
       blend_user_and_official()
   ```

4. **Statistical computation:**
   - Calculate average and median duration
   - If we have 5+ journeys, prefer median (robust to outliers)
   - Otherwise use average

5. **Status determination:**
   - With enough data: Compare to 75th percentile
     - If predicted > p75 * 1.25: "delayed"
     - If predicted < avg * 0.75: "early"
     - Otherwise: "on_time"
   - With sparse data: Compare to threshold
     - If predicted > 45 min: "delayed"

6. **Return:** start_time + predicted_duration

### Why Median Over Average?

Example: Route has 10 journeys
- 9 journeys: ~20 minutes
- 1 journey: 90 minutes (accident on route)

Average: 27 minutes (too pessimistic)
Median: 20 minutes (typical experience)

Median better represents "what will probably happen."

### Data Source Blending

```python
if user_count >= 20:
    source = "user_only"
    durations = user_durations
else:
    source = "blended"
    durations = user_durations + official_durations
```

**Rationale:** Official timetables are optimistic. With enough real data, we don't need them. With sparse data, they provide a baseline.

### Logging Strategy

Every prediction logs:
```
[PREDICTION] {source} | {count} journeys | ETA +{minutes} min | status: {status}
```

This makes debugging easy and lets us monitor prediction quality in production.

## Data Model Design Decisions

### String IDs vs UUIDs

- **Routes/Stops:** Use public identifiers (route "16", ATCO codes)
  - Users recognize these
  - External APIs use these
  - Frontend can construct URLs
  
- **Journeys:** Use UUIDs
  - Internal tracking only
  - Prevents enumeration attacks
  - Globally unique across databases

### Nullable Fields Strategy

- `end_stop_id`: Nullable (user might not know final stop)
- `start_time`: Nullable until bus arrives
- `end_time`: Nullable until journey completes
- `planned_start_time`: Nullable (might start journey spontaneously)

This allows partial data entry and progressive enhancement.

### Timezone Handling

All DateTimes stored in UTC. Frontend handles local timezone conversion.

**Why?** Daylight saving time is a nightmare. UTC is unambiguous. Transit systems cross timezones.

### JSON for Timetables

`official_timetable` is JSON because:
- Schema varies by transit agency API
- We don't query it (just display)
- Flexibility for future data sources

Downside: Can't index or query efficiently. If we need to, we'd normalize it later.

## Error Handling Strategy

### HTTP Status Codes

- **400:** Client error (bad request, invalid state transition)
- **404:** Resource not found (route, stop, journey)
- **500:** Server error (database issues, etc.)

### Validation Layers

1. **Pydantic schemas:** Type validation at API boundary
2. **Business logic:** State machine validation in services
3. **Database constraints:** Foreign keys, not null constraints

### Example: State Transition Validation

```python
allowed = {"STARTED", "DELAYED"}
if journey.status not in allowed:
    raise HTTPException(
        status_code=400,
        detail=f"Cannot mark as ARRIVED from status: {journey.status}"
    )
```

Explicit is better than implicit. Tell users exactly why their request failed.

## Performance Considerations

### N+1 Query Prevention

```python
# BAD: Triggers query for each route_stop
for rs in route_stops:
    print(rs.stop.name)  # Loads stop separately

# GOOD: Single query with join
route_stops = (
    db.query(RouteStop)
    .options(joinedload(RouteStop.stop))
    .filter(...)
    .all()
)
```

### Query Limits

Prediction queries limited to recent data:
- User journeys: Last 100
- Official journeys: Last 50

Prevents scanning entire table as data grows.

### Index Strategy

Should have indexes on:
- `journeys.route_id` (frequently filtered)
- `journeys.status` (state queries)
- `journeys.data_source` (prediction filtering)
- `journeys.start_time` (ordering for recency)

### Future Optimization

When dataset grows:
- Add pagination to /routes and /stops
- Cache prediction results (Redis)
- Archive old completed journeys
- Pre-compute route statistics

## Testing Strategy

### What Should Be Tested

1. **API endpoints:** Request/response validation
2. **State machine:** All valid and invalid transitions
3. **Prediction engine:** Different data volumes and edge cases
4. **Data validation:** Malformed inputs

### Test Data Setup

Need seed data for:
- Routes with various stop counts
- User journeys (completed and in-progress)
- Official journey data
- Edge cases (very short/long journeys)

### Example Test Cases

```python
def test_cannot_arrive_when_already_completed():
    # Journey with status=STOP_REACHED
    # POST /journeys/{id}/event with event=ARRIVED
    # Should return 400

def test_prediction_with_no_data():
    # New route with no journey history
    # Should return 30min fallback

def test_prediction_prefers_recent_data():
    # 50 old journeys: 30min average
    # 10 recent journeys: 45min average
    # Should weight recent data more heavily
```

## Security Considerations

### Current State (MVP)

- No authentication
- No rate limiting
- No input sanitization beyond Pydantic validation

  Got to add these before prod

### Before Production

1. **Add authentication:** JWT tokens or API keys
2. **Rate limiting:** Prevent abuse of prediction endpoint
3. **Input validation:** Sanitize all string inputs
4. **CORS configuration:** Restrict to known frontends
5. **SQL injection:** SQLAlchemy parameterization handles this, but audit raw queries
6. **Journey ownership:** Users should only modify their own journeys

## Deployment Considerations

### Environment Variables

Required:
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

Optional:
```
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

### Database Migrations

Use Alembic for schema changes:
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Scaling Strategy

Current bottleneck will be prediction queries. Solutions:
1. Cache predictions by route (5min TTL)
2. Pre-compute statistics nightly
3. Read replicas for prediction queries
4. Horizontal scaling (stateless API)

## Monitoring and Observability

### What to Monitor

- **Prediction accuracy:** Compare predicted vs actual journey times
- **API latency:** P50, P95, P99 response times
- **Database query times:** Slow query log
- **Error rates:** 4xx and 5xx by endpoint
- **User journey completion rate:** % of STARTED that reach STOP_REACHED

### Logging

Current logging:
- Prediction decisions (source, count, duration)
- Data quality warnings (duplicate sequences, missing stops)
- Journey state transitions

Add in production:
- User IDs (when auth added)
- Request IDs for tracing
- Performance metrics

## Known Issues and Limitations

1. **No time-of-day patterns:** 8am journey and 8pm journey treated the same
2. **No day-of-week patterns:** Monday commute vs Sunday treated the same  
3. **No outlier filtering:** Single 3-hour journey due to accident affects predictions
4. **No confidence intervals:** We say "20 minutes" but not "18-22 minutes"
5. **No live tracking:** Can't update predictions as journey progresses
6. **Direction not fully utilized:** Stored but not factored into predictions

## Future Enhancements

### Phase 2: Time-Based Patterns
Segment journeys by:
- Hour of day (rush hour vs off-peak)
- Day of week (weekday vs weekend)
- Season (summer vs winter schedules)

### Phase 3: Real-Time Updates
- WebSocket connections for live journey updates
- Recalculate ETA as journey progresses
- Show other users' active journeys on same route

### Phase 4: Advanced Analytics
- Route reliability scores
- Weather impact correlation
- Special event detection (concerts, sports)

### Phase 5: Machine Learning
Replace statistical predictions with ML:
- Feature engineering (time, weather, traffic)
- Train on historical journeys
- Continuous model retraining
- A/B test against statistical baseline

---

This documentation reflects the current implementation. Update as the system evolves.