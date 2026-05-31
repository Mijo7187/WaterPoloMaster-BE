# ============================================
# DATABASE - Database Connection & Session
# ============================================
# This file handles database connection and session management
# Uses SQLAlchemy for ORM (Object-Relational Mapping)
#
# KEY CONCEPTS:
# - Engine: Manages connection to database
# - SessionLocal: Creates database sessions
# - get_db(): Dependency that provides database session to routes
# ============================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings


# ============================================
# CREATE DATABASE ENGINE
# ============================================
# Engine manages the connection pool to the database
# connect_args is specific to SQLite (required for SQLite only)
engine = create_engine(settings.DATABASE_URL)

# ============================================
# CREATE SESSION FACTORY
# ============================================
# SessionLocal is a factory that creates database sessions
# Sessions are used to query and modify the database
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit changes
    autoflush=False,   # Don't auto-flush changes
    bind=engine        # Bind to our database engine
)


# ============================================
# DATABASE SESSION DEPENDENCY
# ============================================
def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session
    
    This is used in FastAPI routes with Depends(get_db)
    
    HOW IT WORKS:
    1. Creates a new database session
    2. Provides it to the route function
    3. Automatically closes the session when done
    4. Even if there's an error, session is closed (try/finally)
    
    USAGE IN ROUTES:
    @router.get("/users/")
    def get_users(db: Session = Depends(get_db)):
        users = db.query(User).all()
        return users
    """
    # Create a new database session
    db = SessionLocal()

    try:
        # Provide the session to the route
        yield db
    finally:
        # Always close the session (even if error occurs)
        db.close()


# ============================================
# CREATE TABLES
# ============================================
def create_tables():
    """
    Create all database tables
    
    This reads all models that inherit from Base
    and creates their tables in the database
    
    NOTE: In production, use Alembic migrations instead!
    This is useful for development/testing
    """
    from app.core.db.base import Base

    # Import all models here so they are registered with Base
    # Import other models as you create them
    # from app.features.teams.teams.models import Team

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


# ============================================
# USAGE EXAMPLE:
# ============================================
# In main.py:
# from app.core.db.database import create_tables
# create_tables()  # Creates all tables on startup
#
# In routes:
# from app.core.db.database import get_db
#
# @router.get("/")
# def my_route(db: Session = Depends(get_db)):
#     # db is your database session
#     users = db.query(User).all()
#     return users
# ============================================
