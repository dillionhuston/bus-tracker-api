import requests
from datetime import datetime
import time

BASE_URL = "http://127.0.0.1:8000/journeys"

def start_journey(route_id, start_stop, end_stop):
    payload = {
        "route_id": route_id,
        "start_stop_id": start_stop,
        "end_stop_id": end_stop,
        "planned_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    resp = requests.post(f"{BASE_URL}/start", json=payload)
    if resp.status_code not in (200, 201):
        print("Failed to start journey:", resp.text)
        return None
    return resp.json()

def post_event(journey_id, event):
    payload = {"event": event}
    resp = requests.post(f"{BASE_URL}/{journey_id}/event", json=payload)
    if resp.status_code not in (200, 201):
        print(f"Failed to mark {event}:", resp.text)
    else:
        print(f"Journey {event.lower()} successfully:", resp.json())

def simulate_journey(route_id, start_stop, end_stop, delay_between_events=1):
    journey = start_journey(route_id, start_stop, end_stop)
    if not journey:
        return

    journey_id = journey.get("id")
    print("Journey started successfully")
    print(f"Journey ID: {journey_id}")
    print(f"Official timetable start: {journey.get('official_start_time')}")
    print(f"Predicted arrival: {journey.get('predicted_arrival')}\n")

    time.sleep(delay_between_events)
    post_event(journey_id, "DELAYED")
    time.sleep(delay_between_events)
    post_event(journey_id, "ARRIVED")
    time.sleep(delay_between_events)
    post_event(journey_id, "STOP_REACHED")

if __name__ == "__main__":
    simulate_journey("94B", "CITY_CENTRE", "HOLYWOOD_EXCHANGE")
