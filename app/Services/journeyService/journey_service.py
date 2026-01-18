from uuid import UUID, uuid4
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.Journey import Journey
from app.schemas.journey import StartJourney, JourneyEventType

from app.Services.Prediction.prediction import PredictionService

from datetime import datetime, timezone


class JourneyService:
    @staticmethod
    def start_journey(data: StartJourney, db: Session) -> Journey:
        """Create journey and add it to database. Returns journey data"""
        start_time = datetime.now(timezone.utc)
        
        predicted_arrival, predicted_status = PredictionService.predict_journey(
            db=db,
            route_id=data.route_id,
            start_time=start_time
        )

        journey = Journey(
            id=str(uuid4()),
            route_id=data.route_id,
            start_stop_id=data.start_stop_id,
            end_stop_id=data.end_stop_id,
            start_time=None,  # We change once bus arrives
            status=JourneyEventType.EVENT_TYPE_STARTED,
            created_at=datetime.now(timezone.utc),
            predicted_status=predicted_status,
            predicted_arrival=predicted_arrival.strftime("%Y-%m-%d %H:%M:%S")
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