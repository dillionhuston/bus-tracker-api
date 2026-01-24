import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    echo=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind= engine
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

