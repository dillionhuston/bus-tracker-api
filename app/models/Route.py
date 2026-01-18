from sqlalchemy import Column, String, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship

from app.models.Database import Base

class Route(Base):
    __tablename__ = "routes"

    id = Column(String, nullable=False, primary_key=True)  # e.g., 12a, 10J
    name = Column(String, nullable=False)
    direction = Column(String, nullable=True)

    route_stops = relationship('RouteStop', back_populates='route')


class RouteStop(Base):
    __tablename__ = "route_stops"  

    route_id = Column(String, ForeignKey("routes.id"), primary_key=True)  
    stop_id = Column(String, ForeignKey("stops.id"), primary_key=True)    
    sequence = Column(Integer, nullable=False)
    direction = Column(String)  # outbound/inbound

    route = relationship('Route', back_populates='route_stops')
    stop = relationship('Stop', back_populates='route_stops')




class Stop(Base):
    __tablename__ = "stops"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)

    route_stops = relationship('RouteStop', back_populates='stop')