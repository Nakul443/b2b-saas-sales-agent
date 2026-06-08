import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# default fallback create a local SQLite database in project folder
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sales_agent.db")

# SQLite prevents multiple threads from sharing the same connection to prevent state corruption
# FastAPI uses multiple threads
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    echo=True # for seeing the SQL logs in terminal
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# declarative base class that models will inherit from to map Python classes to tables
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()