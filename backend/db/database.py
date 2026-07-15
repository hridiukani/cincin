import os
import uuid

from dotenv import load_dotenv
from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Venue(Base):
    __tablename__ = "venues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_place_id = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    address = Column(Text, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    location = Column(Geography("POINT", srid=4326), nullable=False)
    website = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    google_rating = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    happy_hours = relationship("HappyHour", back_populates="venue", cascade="all, delete-orphan")
    scrape_logs = relationship("ScrapeLog", back_populates="venue", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_venues_location", "location", postgresql_using="gist"),
    )


class HappyHour(Base):
    __tablename__ = "happy_hours"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    days = Column(ARRAY(Text), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    deals = Column(ARRAY(Text), nullable=False)
    confidence = Column(String, nullable=False)
    source = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    last_verified = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    venue = relationship("Venue", back_populates="happy_hours")

    __table_args__ = (
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="happy_hours_confidence_check"),
        CheckConstraint("source IN ('website', 'reviews', 'both')", name="happy_hours_source_check"),
        Index("idx_happy_hours_venue_id", "venue_id"),
    )


class ScrapeLog(Base):
    __tablename__ = "scrape_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    scraped_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    success = Column(Boolean, nullable=False)
    pattern_detected = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    venue = relationship("Venue", back_populates="scrape_logs")

    __table_args__ = (
        CheckConstraint(
            "pattern_detected IN ('link', 'location_selector', 'pdf', 'none')",
            name="scrape_log_pattern_detected_check",
        ),
        Index("idx_scrape_log_venue_id", "venue_id"),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
