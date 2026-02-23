"""
Scoring & Feedback Engine — Standalone service.

Combines outputs from Voice, NLP, and Facial analysis services
to generate final scores, strengths, weaknesses, and coaching feedback.
Runs on port 8004.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from engine import combine_scores, generate_session_feedback

app = FastAPI(
    title="Scoring & Feedback Engine",
    description="Combines multi-modal analysis into final interview scores and coaching feedback",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SingleResponseScores(BaseModel):
    voice_analysis: Dict[str, Any] = {}
    nlp_analysis: Dict[str, Any] = {}
    facial_analysis: Dict[str, Any] = {}


class SessionScoreRequest(BaseModel):
    responses: List[SingleResponseScores]


@app.get("/")
def root():
    return {"service": "Scoring Engine", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/score")
async def score_response(data: SingleResponseScores):
    """Score a single response by combining voice, NLP, and facial analysis."""
    result = combine_scores(
        voice=data.voice_analysis,
        nlp=data.nlp_analysis,
        facial=data.facial_analysis,
    )
    return {"status": "success", "scores": result}


@app.post("/feedback")
async def generate_feedback(data: SessionScoreRequest):
    """Generate complete session feedback from all response analyses."""
    feedback = generate_session_feedback(
        [r.model_dump() for r in data.responses]
    )
    return {"status": "success", "feedback": feedback}
