# Journey Tracking System

A real-time public transit journey tracking and prediction system that learns from user-submitted journey data to improve arrival time predictions.

## What It Does

This system tracks bus journeys and predicts arrival times by combining official timetable data with real user journey submissions. The more users submit their actual journey data, the more accurate the predictions become for everyone.

**Key Features:**
- Start and track active bus journeys
- Submit journey events (arrived, delayed, stop reached)
- Smart predictions that improve with more data
- Blend official timetables with real-world user data
- RESTful API built with FastAPI

## How Predictions Work

The prediction engine uses a tiered approach based on data availability:

- **20+ user journeys**: Uses only real user data (most accurate)
- **5-19 user journeys**: Blends user data with official timetables
- **< 5 user journeys**: Falls back to official timetable data
- **No data**: Safe 30-minute fallback estimate

Predictions use median journey duration when enough data exists (more robust to outliers) and average duration for smaller datasets.

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL
- pip or poetry for dependency management

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd journey-tracking-system

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your DATABASE_URL
```

### Database Setup

```bash
# Create database
createdb journey_tracking

# Run migrations (if using Alembic)
alembic upgrade head
```

### Running the Server

```bash
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`

Interactive docs at `http://localhost:8000/docs`

## API Usage

### Get Available Routes

```bash
GET /route/routes
```

Returns list of all available routes with IDs and names.

### Get Stops for a Route

```bash
GET /route/routes/{route_id}/stops
```

Returns ordered list of stops for the specified route.

### Start a Journey

```bash
POST /journeys/start
Content-Type: application/json

{
  "route_id": "16",
  "start_stop_id": "490000001",
  "end_stop_id": "490000050",
  "planned_start_time": "2026-01-24T09:00:00Z"  // optional
}
```

Returns journey ID and initial predictions.

### Submit Journey Event

```bash
POST /journeys/{journey_id}/event
Content-Type: application/json

{
  "event": "ARRIVED"  // or "DELAYED", "STOP_REACHED"
}
```

Updates journey status and returns updated predictions.

## Project Structure

```
app/
├── models/              # SQLAlchemy models
│   ├── Database.py      # Database connection setup
│   ├── Journey.py       # Journey model
│   └── Route.py         # Route, Stop, RouteStop models
├── schemas/             # Pydantic schemas for validation
│   ├── journey.py       # Journey request/response schemas
│   ├── route.py         # Route schemas
│   └── stop.py          # Stop schemas
├── Services/
│   ├── journeyService/  # Journey business logic
│   │   ├── journey_service.py
│   │   └── eventHandler.py
│   └── Prediction/      # Prediction engine
│       └── prediction.py
└── routes/              # API route handlers
    ├── Journey.py
    ├── Route.py
    └── test.py
```

## Journey State Machine

```
STARTED → DELAYED → ARRIVED → STOP_REACHED
   ↓         ↓         ↓
   └─────────┴─────────┘
```

- **STARTED**: Journey created, waiting for bus
- **DELAYED**: User reports delay
- **ARRIVED**: Bus has arrived, journey active
- **STOP_REACHED**: Journey completed at destination

## Contributing

We welcome contributions! Here's how you can help:

### Areas for Improvement

1. **Prediction Engine**: Improve algorithms, add time-of-day patterns, weather integration
2. **Real-time Updates**: WebSocket support for live journey updates
3. **Data Validation**: Better validation for journey data quality
4. **Analytics**: Dashboard for route performance metrics
5. **Testing**: Expand test coverage (currently minimal)
6. **Documentation**: API examples, architecture diagrams

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Write or update tests
5. Submit a pull request

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings to public methods
- Keep functions focused and single-purpose

### Running Tests

```bash
pytest tests/
```

## Technical Decisions

### Why SQLAlchemy?
Provides database abstraction and works well with FastAPI's dependency injection.

### Why String IDs?
Routes and stops use public identifiers (route numbers, ATCO codes) that users recognize. Internal journey IDs use UUIDs.

### Why Median over Average?
With 5+ data points, median is more robust to outliers (one unusually delayed journey won't skew predictions).

### Data Source Tracking
Journeys track whether they come from official timetables or user submissions, allowing the prediction engine to trust user data more as it accumulates.

## Configuration

Key environment variables in `.env`:

```
DATABASE_URL=postgresql://user:password@localhost/journey_tracking
```

## Known Limitations

- No authentication/authorization yet
- No data cleanup for old journeys
- Limited error handling for edge cases
- No rate limiting on API endpoints
- Predictions don't account for time of day or day of week patterns yet

## Roadmap

- [ ] User authentication and personal journey history
- [ ] Time-based prediction patterns (rush hour vs off-peak)
- [ ] Mobile app integration
- [ ] Real-time journey sharing between users
- [ ] Integration with official transit APIs
- [ ] Data export and analytics dashboard

## License

MIT License
Copyright (c) 2026 Dillon Huston

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Built with FastAPI, SQLAlchemy, and PostgreSQL. Contributions welcome!