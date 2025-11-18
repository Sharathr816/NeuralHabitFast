from sqlalchemy import (
    Column, Integer, BigInteger, Text, DateTime, JSON, Numeric, String, 
    ForeignKey, Boolean, SmallInteger, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import sqlalchemy.orm

Base = sqlalchemy.orm.declarative_base()


class User(Base):
    """User accounts table."""
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    signup_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Journal(Base):
    """Journal entries table."""
    __tablename__ = "journals"
    
    journal_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    text = Column(Text, nullable=True)
    screen_minutes = Column(Integer, nullable=True)
    unlock_count = Column(Integer, nullable=True)
    sleep_hours = Column(Numeric(4, 2), nullable=True)
    steps = Column(Integer, nullable=True)
    dominant_emotion = Column(Text, nullable=True)
    dominant_emotion_score = Column(Numeric(4, 3), nullable=True)
    #meta = Column(JSONB, nullable=True)  # PostgreSQL JSONB for better performance
    
    # Index for efficient queries
    __table_args__ = (
        Index('idx_journals_user_time', 'user_id', 'created_at'),
    )


class HabitAnalysis(Base):
    """Habit analysis results table."""
    __tablename__ = "habit_analysis"
    
    analysis_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    journal_id = Column(BigInteger, ForeignKey("journals.journal_id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    risk_score = Column(Numeric(4, 3), nullable=True)
    prediction_label = Column(Text, nullable=True)
    top_features = Column(JSONB, nullable=True)  # PostgreSQL JSONB
    # raw_shap = Column(JSONB, nullable=True)  # PostgreSQL JSONB
    

    # Index for efficient queries
    __table_args__ = (
        Index('idx_analysis_user_time', 'user_id', 'created_at'),
    )