# ============================================
# BASE - Base Model Class
# ============================================
# This file contains the base class for all SQLAlchemy models
# All database models inherit from this
#
# WHY THIS FILE?
# - Creates the declarative base for SQLAlchemy
# - All models extend this base class
# - Provides common functionality to all models
# ============================================

from sqlalchemy.ext.declarative import declarative_base

# ============================================
# CREATE BASE CLASS
# ============================================
# This is the base class that all database models inherit from
# It's created by SQLAlchemy's declarative_base()
Base = declarative_base()

# ============================================
# USAGE EXAMPLE:
# ============================================
# In your models file:
# 
# from app.core.db.base import Base
# 
# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True)
#     ...
# ============================================
