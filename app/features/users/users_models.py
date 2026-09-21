# ============================================
# USERS MODELS - Database Tables
# ============================================
# This file defines the DATABASE STRUCTURE for users
# SQLAlchemy models represent tables in your database
#
# Think of it as: "What columns does my users table have?"
# ============================================

import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, JSON, ForeignKey, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db.base import Base  # Base class for all models


# ============================================
# USER ROLE ENUM
# ============================================
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    USER = "USER"
    PLAYER = "PLAYER"
    COACH = "COACH"


# ============================================
# PLAYER POSITION ENUM (water polo positions)
# ============================================
class PlayerPosition(str, enum.Enum):
    GK = "GK"   # Goalkeeper
    LW = "LW"   # Left Wing
    LB = "LB"   # Left Back
    CB = "CB"   # Center Back
    RB = "RB"   # Right Back
    RW = "RW"   # Right Wing
    C = "C"     # Center


# ============================================
# DEFAULT TEAM ENUM
# ============================================
class DefaultTeam(str, enum.Enum):
    HOME = "HOME"
    AWAY = "AWAY"


# ============================================
# USER MODEL - Represents the "users" table
# ============================================
class User(Base):
    """
    User model - represents a user in the database
    
    Each attribute becomes a column in the database table
    """
    
    # This tells SQLAlchemy what the table name is in the database
    __tablename__ = "users"
    
    # ============================================
    # COLUMNS (fields in the database)
    # ============================================
    
    # Primary key - unique identifier for each user
    # autoincrement means database generates this automatically
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # User's email - must be unique (no two users can have same email)
    # index=True makes searches faster
    email = Column(String(200), unique=True, index=True, nullable=False)
    
    # User's username - also unique
    username = Column(String(100), unique=True, index=True, nullable=True)
    
    # Hashed password (NEVER store plain text passwords!)
    # This will be encrypted using bcrypt
    hashed_password = Column(String(1000), nullable=False)
    
    # User's full name (optional, can be null)
    first_name = Column(String(200), nullable=False)
    last_name = Column(String(200), nullable=False)
    phone_number = Column(String(20), nullable=False)
    address = Column(String(500), nullable=True)
    address_number = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=False)
    
    # Is the user active? (for soft delete or account suspension)
    is_active = Column(Boolean, default=True)

    # Company - every user except SUPER_ADMIN must belong to a company
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    company = relationship("Company", back_populates="users")

    w_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=True)
    wallet = relationship("Wallet", foreign_keys=[w_id], uselist=False)

    # User roles - array of role strings e.g. ["USER"] or ["ADMIN", "USER"]
    roles = Column(JSON, default=lambda: [UserRole.USER.value])

    # Player positions - array of position strings e.g. ["GK"] or ["LW", "C"]
    # Required (in the schema) when the user holds the PLAYER role.
    position = Column(JSON, nullable=True)

    # Default team side the player lines up on (HOME / AWAY).
    # Required (in the schema) when the user holds the PLAYER role.
    default_team = Column(String(10), nullable=True)
    
    # Timestamps - automatically track when user was created/updated
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ============================================
    # STRING REPRESENTATION (for debugging)
    # ============================================
    def __repr__(self):
        """
        How the user object looks when printed
        Useful for debugging
        """
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
