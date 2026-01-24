from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from app.models.Database import SessionLocal, engine, get_db

from app.models.Route import Route
from app.models.Route import Stop
from app.models.Route import RouteStop

from app.schemas.route import StopsPerRoute
from app.schemas.route import RouteOut

from app.utils.logger import logger

logger = logger.get_logger()


router = APIRouter(prefix="/route", tags=["Route"])


# This is used for populating the drop down menu for the frontend
@router.get("/routes", response_model=List[RouteOut])
def get_routes(db: Session = Depends(get_db)):
    """Return a list of available routes"""

    routes = db.query(Route).all()  
    if not routes:
        raise HTTPException(
            status_code=404,
            detail="Could not return a list of routes"
        )
    
    return [
        {
            "id": route.id,
            "name": route.name
        }
        for route in routes
    ]

@router.get("/routes/{route_id}/stops", response_model=List[StopsPerRoute])
def get_stops_per_route(route_id: str, db: Session = Depends(get_db)):
    route_stops = (
        db.query(RouteStop)
        .options(joinedload(RouteStop.stop))
        .filter(RouteStop.route_id == route_id)
        .order_by(RouteStop.sequence)
        .all()
    )

    if not route_stops:
        raise HTTPException(404, detail=f"No stops found for route '{route_id}'")

    result = []
    seen_sequences = set()  # Track duplicates
    
    for rs in route_stops:
        # Check if stop exists and has a name
        if rs.stop and rs.stop.name and rs.stop.name != "Unknown Stop":
            stop_data = {
                "id": rs.stop_id,
                "name": rs.stop.name,
                "sequence": rs.sequence,
                "direction": rs.direction
            }
    
            # Warn about duplicates
            if rs.sequence in seen_sequences:
                logger.warning(f"[WARNING] Duplicate sequence {rs.sequence} for route {route_id}")
            seen_sequences.add(rs.sequence)
            
            result.append(stop_data)
        else:
            logger.warning(f"[WARNING] Missing or invalid stop data for stop_id: {rs.stop_id}")

    logger.warning(f"[DEBUG] Valid stops for {route_id}: {len(result)}")
    return result