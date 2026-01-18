from uuid import UUID
from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.models.Route import Route
from app.models.Database import get_db
from app.schemas.journey import StartJourney, JourneyEventType, AddJourneyEvent

from app.Services.journeyService.journey_service import JourneyService
from app.Services.journeyService.eventHandler import JourneyEventHandler


router = APIRouter(prefix="/journeys", tags=['Journeys'])

@router.post("/start")
def startJourney(
    journey: StartJourney,
    db: Session = Depends(get_db)):
    """User starts their journey by submitting their route and start/end stops"""


    if not journey.start_stop_id or not journey.end_stop_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid start or end stop. Cannot create journey"
        )
    
    newJourney = JourneyService.start_journey(db=db, data=journey)

    return {       
        "id": newJourney.id,
        "predicted_status": newJourney.predicted_status,
        "predicted_arrival": newJourney.predicted_arrival
    }
        
    
@router.post("/{journey_id}/event")
def add_journey_event(
    event: AddJourneyEvent,
    journey_id: UUID,
    db: Session = Depends(get_db)):
    """User submits an event. Bus arrived, delayed, stop reached"""


    if not event.event_type:
        raise HTTPException(
            status_code=400,
            detail="You must provide a valid event. Arrived, Delayed, StopReached"
        )


    updated_journey = JourneyEventHandler.add_event(
        event_type=event.event_type,
        db=db,
        journey_id=journey_id
    )
    
    return {
        "journey_id": str(updated_journey.id),
        "status": updated_journey.status
    }