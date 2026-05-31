#!/usr/bin/env python3
# ============================================
# RUN - Start the FastAPI Application
# ============================================
# Simple script to run the server
# Just execute: python run.py
# ============================================

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    """
    Run the FastAPI application using uvicorn
    
    This starts the development server with:
    - Auto-reload on code changes
    - Host and port from .env file
    """
    print("=" * 50)
    print(f"🚀 Starting {settings.APP_NAME}")
    print(f"🌍 Environment: {settings.APP_ENV}")
    print(f"📡 Server: http://{settings.HOST}:{settings.PORT}")
    print(f"📚 API Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print("=" * 50)
    
    uvicorn.run(
        "app.main:app",  # Application location
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD  # Auto-reload on code changes (dev only)
    )
