"""Application configuration using Pydantic BaseSettings."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'interview_coach.db'}")

# JWT Settings
JWT_SECRET = os.getenv("JWT_SECRET", "interview-coach-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60 * 24  # 24 hours

# AI Service URLs
VOICE_SERVICE_URL = os.getenv("VOICE_SERVICE_URL", "http://localhost:8001")
NLP_SERVICE_URL = os.getenv("NLP_SERVICE_URL", "http://localhost:8002")
FACIAL_SERVICE_URL = os.getenv("FACIAL_SERVICE_URL", "http://localhost:8003")

# DSA Round API (separate key from main Groq key)
DSA_API_KEY = os.getenv("DSA_API_KEY", "")
DSA_MODEL = os.getenv("DSA_MODEL", "openai/gpt-oss-120b")

# Upload directory
UPLOAD_DIR = BASE_DIR.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# CORS
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Scoring Weights
SCORING_WEIGHTS = {
    "voice": 0.30,
    "nlp": 0.40,
    "facial": 0.30,
}
