import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Webhook(Base):
    __tablename__ = "webhooks"
    curr_webhook_url = Column(String, primary_key=True)
    prev_webhook_url = Column(String)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
