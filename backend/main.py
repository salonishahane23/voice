"""FastAPI application entry point for the Interview Coach backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from database import create_tables

# Import routers
from routers.auth import router as auth_router
from routers.interviews import router as interviews_router
from routers.questions import router as questions_router
from routers.dsa import router as dsa_router

# Create FastAPI app
app = FastAPI(
    title="AI Interview Coach API",
    description="Backend API for the AI-powered Interview Coach platform",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(interviews_router)
app.include_router(questions_router)
app.include_router(dsa_router)


@app.on_event("startup")
def on_startup():
    """Initialize database tables on startup."""
    create_tables()

    # Auto-seed questions
    from database import SessionLocal
    from services.question_engine import seed_questions

    db = SessionLocal()
    try:
        count = seed_questions(db)
        if count > 0:
            print(f"[OK] Seeded {count} questions into the database")
        else:
            print("[INFO] Questions already seeded")
    finally:
        db.close()


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "message": "AI Interview Coach API is running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}
