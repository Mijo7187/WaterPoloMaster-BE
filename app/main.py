# ============================================
# MAIN - FastAPI Application Entry Point
# ============================================
# This is the HEART of your application
# Everything starts here!
#
# WHAT THIS FILE DOES:
# 1. Creates FastAPI application
# 2. Registers all feature routers (endpoints)
# 3. Creates database tables
# ============================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db.database import create_tables
from app.core.api.exception_handlers import register_exception_handlers
from app.features.users.users_router import router as users_router
from app.features.auth.auth_router import router as auth_router
from app.features.sifarnici.country.country_router import router as country_router
from app.features.sifarnici.city.city_router import router as city_router
from app.features.company.company_router import router as company_router
from app.features.training.training_router import router as training_router
from app.features.wallet.wallet_router import router as wallet_router
from app.features.payment.payment_router import router as payment_router
from app.features.sifarnici.expense_category.expense_category_router import router as expense_category_router
from app.features.sifarnici.income_category.income_category_router import router as income_category_router
from app.features.training_users.training_users_router import router as training_users_router
from app.features.training_segments.training_segments_router import router as training_segments_router
from app.features.sifarnici.exercise_option.exercise_option_router import router as exercise_option_router
from app.features.quarter.quarter_router import router as quarter_router
from app.features.quarter_users.quarter_users_router import router as quarter_users_router
from app.features.tournament.tournament_router import router as tournament_router
from app.features.tournament_users.tournament_users_router import router as tournament_users_router
from app.scheduler.scheduler import init_scheduler, scheduler



# ============================================
# CREATE FASTAPI APPLICATION
# ============================================
app = FastAPI(
    title=settings.APP_NAME,  # Application name (from .env)
    version=settings.API_VERSION,  # API version (from .env)
    description="Water Polo Master Backend API - Built with FastAPI",
    # Swagger UI will be at: http://localhost:8000/docs
    # ReDoc will be at: http://localhost:8000/redoc
)

# Register global exception handlers (standardized error responses)
register_exception_handlers(app)


# ============================================
# CORS MIDDLEWARE (Cross-Origin Resource Sharing)
# ============================================
# This allows your frontend (React, Vue, etc.) to call your API
# IMPORTANT: In production, restrict origins to your actual frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # React/Vue (Vite)
        "http://localhost:3000",   # React (CRA) / Next.js
        "http://localhost:4200",   # Angular
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)


# ============================================
# STARTUP EVENT - Runs when application starts
# ============================================
@app.on_event("startup")
def on_startup():
    """
    This runs ONCE when the application starts
    
    Good place to:
    - Create database tables
    - Initialize connections
    - Load data
    """
    print("🚀 Starting WaterPoloMaster Backend...")
    print(f"📝 Environment: {settings.APP_ENV}")
    print(f"🗄️  Database: {settings.DATABASE_URL}")
    
    # Create all database tables
    create_tables()

    # Start background scheduler (nightly training job at 23:59)
    init_scheduler()

    print("✅ Application started successfully!")
    print(f"📚 API Documentation: http://{settings.HOST}:{settings.PORT}/docs")


# ============================================
# SHUTDOWN EVENT - Runs when application stops
# ============================================
@app.on_event("shutdown")
def on_shutdown():
    """
    This runs ONCE when the application stops
    
    Good place to:
    - Close connections
    - Clean up resources
    """
    scheduler.shutdown()
    print("👋 Shutting down WaterPoloMaster Backend...")


# ============================================

# ============================================
# REGISTER FEATURE ROUTERS
# ============================================
# This is where you add all your feature routers
# Each feature gets its own prefix

# Authentication feature
app.include_router(
    auth_router,
    prefix="/api"  # All auth routes will start with /api/auth
)

# Users feature
app.include_router(
    users_router,
    prefix="/api"  # All routes will start with /api
    # Tags are defined in the router itself (users_router.py)
)

# Sifarnici - Country
app.include_router(
    country_router,
    prefix="/api"
)

# Sifarnici - City
app.include_router(
    city_router,
    prefix="/api"
)

# Companies
app.include_router(
    company_router,
    prefix="/api"
)

# Trainings
app.include_router(
    training_router,
    prefix="/api"
)

# Wallet
app.include_router(
    wallet_router,
    prefix="/api"
)

# Payment
app.include_router(
    payment_router,
    prefix="/api"
)

# Sifarnici - ExpenseCategory
app.include_router(
    expense_category_router,
    prefix="/api"
)

# Sifarnici - IncomeCategory
app.include_router(
    income_category_router,
    prefix="/api"
)

# Training Users
app.include_router(
    training_users_router,
    prefix="/api"
)

# Training Segments
app.include_router(
    training_segments_router,
    prefix="/api"
)

# Sifarnici - ExerciseOption
app.include_router(
    exercise_option_router,
    prefix="/api"
)

# Quarter
app.include_router(
    quarter_router,
    prefix="/api"
)

# Quarter Users
app.include_router(
    quarter_users_router,
    prefix="/api"
)

# Tournament
app.include_router(
    tournament_router,
    prefix="/api"
)

# Tournament Users
app.include_router(
    tournament_users_router,
    prefix="/api"
)

# Add more features here as you create them:
# app.include_router(
#     teams_router,
#     prefix="/api",
#     tags=["Teams"]
# )
# 
# app.include_router(
#     matches_router,
#     prefix="/api",
#     tags=["Matches"]
# )


# ============================================
# HOW TO RUN THIS APPLICATION:
# ============================================
# In terminal, run:
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#
# Or use our script (we'll create this):
# python run.py
#
# Then visit:
# - API Documentation: http://localhost:8000/docs
# - Alternative Docs: http://localhost:8000/redoc
# - Health Check: http://localhost:8000/health
# ============================================


# ============================================
# API STRUCTURE:
# ============================================
# /                        → Root endpoint
# /health                  → Health check
# /docs                    → Swagger UI (interactive API docs)
# /redoc                   → ReDoc (alternative API docs)
# 
# /api/users/           → User endpoints
#   ├── POST   /           → Create user
#   ├── GET    /           → Get all users
#   ├── GET    /{id}       → Get specific user
#   ├── PUT    /{id}       → Update user
#   └── DELETE /{id}       → Delete user
#
# Add more features:
# /api/teams/           → Team endpoints
# /api/matches/         → Match endpoints
# /api/players/         → Player endpoints
# ============================================
