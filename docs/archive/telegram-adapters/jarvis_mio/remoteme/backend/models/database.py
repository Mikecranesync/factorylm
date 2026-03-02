"""
RemoteMe Database Models
========================
SQLite database with SQLAlchemy ORM.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from backend.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite specific
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class User(Base):
    """User account"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String(50), unique=True, index=True, nullable=False)
    telegram_username = Column(String(100), nullable=True)
    
    # Subscription
    subscription_status = Column(String(20), default="trial")  # trial, active, cancelled, expired
    trial_started_at = Column(DateTime, nullable=True)
    subscription_started_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    
    # Usage
    commands_this_month = Column(Integer, default=0)
    total_commands = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, nullable=True)
    
    # Relationships
    commands = relationship("Command", back_populates="user")
    nodes = relationship("Node", back_populates="user")


class Node(Base):
    """Registered computer node"""
    __tablename__ = "nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String(100), nullable=False)
    tailscale_ip = Column(String(50), nullable=False)
    port = Column(Integer, default=8765)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="nodes")
    commands = relationship("Command", back_populates="node")


class Command(Base):
    """Command execution record"""
    __tablename__ = "commands"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    
    # Command details
    raw_text = Column(Text, nullable=False)  # Original user message
    parsed_intent = Column(String(50), nullable=True)  # screenshot, shell, interpret, etc.
    parsed_args = Column(Text, nullable=True)  # JSON of parsed arguments
    
    # Execution
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    recording_path = Column(String(500), nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    
    # Metrics
    execution_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="commands")
    node = relationship("Node", back_populates="commands")


class UsageLog(Base):
    """Daily usage tracking"""
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    
    commands_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    api_cost_usd = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
