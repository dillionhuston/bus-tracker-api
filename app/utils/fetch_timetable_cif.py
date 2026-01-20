import re
from pathlib import Path
from datetime import datetime, timezone

def parse_cif_for_route(cif_content: str, target_route: str) -> list[dict]:
    """
    Parse CIF timetable content for a specific route.
    Returns a list of trips with start/end times.
    """
    results = []
    current_route = None

    for line in cif_content.splitlines():
        line = line.strip()
        if not line or line.startswith('//'):
            continue

        record_type = line[:2]

        if record_type == "JQ":  # Route header
            parts = re.split(r'\s+', line)
            current_route = parts[1] if len(parts) > 1 else None

        elif record_type == "QP":  # Trip for route
            if current_route == target_route:
                parts = re.split(r'\s+', line)
                if len(parts) >= 6:
                    start_time = parts[4]  # HHMM
                    end_time = parts[5]
                    results.append({
                        "trip_id": parts[1],
                        "start_time": f"{start_time[:2]}:{start_time[2:]}",
                        "end_time": f"{end_time[:2]}:{end_time[2:]}",
                        "operating_days": parts[3],
                    })

    return results



def get_official_timetable_for_route(cif_file_path: str, route_id: str, planned_start_time: datetime | None = None) -> dict | None:
    path = Path(cif_file_path)
    if not path.exists():
        return None

    content = path.read_text()
    trips = parse_cif_for_route(content, route_id)
    if not trips:
        return None

    planned = planned_start_time or datetime.now(timezone.utc)
    planned_minutes = planned.hour * 60 + planned.minute

    def trip_diff(trip):
        h, m = map(int, trip["start_time"].split(":"))
        trip_minutes = h * 60 + m
        return abs(trip_minutes - planned_minutes)

    closest_trip = min(trips, key=trip_diff)

    return {
        "trip_id": closest_trip["trip_id"],
        "start_time": closest_trip["start_time"],
        "end_time": closest_trip["end_time"]
    }
