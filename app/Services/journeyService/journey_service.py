from uuid import UUID, uuid4
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.Route import Route

from app.models.Journey import Journey
from app.schemas.journey import StartJourney, JourneyEventType

from app.Services.Prediction.prediction import PredictionService
from app.utils.fetch_timetable_cif import get_official_timetable_for_route


from datetime import datetime, timezone


class JourneyService:
    @staticmethod
    def start_journey(data: StartJourney, db: Session) -> Journey:
        """Create journey and add it to database. Returns journey data"""
        route = db.query(Route).filter(Route.id == data.route_id).first()
        if not route:
                raise HTTPException(
                     status_code=404,
                     detail=f"Route {data.route_id} Not found")
        
        planned = data.planned_start_time or datetime.now(timezone.utc)

        cif_path = "data/Metro.cif"  # local CIF file. Change to config.py 
        official_times = get_official_timetable_for_route(cif_path, data.route_id, planned)

        if official_times:
            route.official_timetable = official_times
            route.timetable_last_updated = datetime.now(timezone.utc)
            db.commit()
            db.refresh(route)  

        official_time = route.official_timetable

        official_start = None
        official_end   = None
        if official_time:
            official_start = official_time.get('start_time')
            official_end   = official_time.get('end_time')
            
        predicted_arrival, predicted_status = PredictionService.predict_journey(
            self=PredictionService,
            db=db,
            route_id=data.route_id,
            start_time=datetime.now(timezone.utc)
        )

        offical_time = route.official_timetable
        journey = Journey(
            id=str(uuid4()),
            route_id=data.route_id,
            start_stop_id=data.start_stop_id,
            planned_start_time=planned,
            end_stop_id=data.end_stop_id,
            start_time=None,  # We change once bus arrives
            status=JourneyEventType.EVENT_TYPE_STARTED,
            created_at=datetime.now(timezone.utc),
            predicted_status=predicted_status,
            predicted_arrival=predicted_arrival.strftime("%Y-%m-%d %H:%M:%S"),
            official_start_time=official_start,
            official_end_time=official_end            
            
        )
        db.add(journey)
        db.commit()
        db.refresh(journey)

        return journey

    @staticmethod
    def get_active_journey(journey_id: UUID, db: Session) -> Journey:
        """Get a specific active journey by ID"""

        journey = (
            db.query(Journey)
            .filter(
                Journey.id == str(journey_id),
                Journey.status.in_([
                    JourneyEventType.EVENT_TYPE_STARTED,
                    JourneyEventType.EVENT_TYPE_DELAYED,
                    JourneyEventType.EVENT_TYPE_ARRIVED
                ]),
                Journey.end_time.is_(None)
            )
            .one_or_none()
        )

        if journey is None:
            raise HTTPException(
                status_code=404,
                detail=f"Active journey not found for id: {journey_id}"
            )
        
        # Return the journey object directly
        return journey