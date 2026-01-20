from sqlalchemy import Column, String, ForeignKey, Integer, Float, DateTime, Boolean
from app.models.Database import Base


class Journey(Base):

    __tablename__ = "journeys"

    id = Column(String, primary_key=True, index=True)
    route_id = Column(String, ForeignKey("routes.id"), nullable=False)
    start_stop_id = Column(String, ForeignKey("stops.id"), nullable=False)
    planned_start_time = Column(DateTime, nullable=True)
    end_stop_id = Column(String, ForeignKey("stops.id"))
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)  # completed, delayed etc
    created_at = Column(DateTime, nullable=False)
    official_start_time = Column(String, nullable=False)
    official_end_time = Column(String, nullable=False)
    
    predicted_status = Column(String, nullable=False)
    predicted_arrival = Column(String, nullable=False) 


    # Track data source
    data_source = Column(String, nullable=False, default="user")  # "official" or "user"
    is_synthetic = Column(Boolean, default=False)  # True for seeded data