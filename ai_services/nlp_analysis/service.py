"""
NLP Answer Analysis FastAPI Service.

Standalone microservice that evaluates interview answer quality using
Groq API with the gpt-oss model. Runs on port 8002.
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from analyzer import analyze_answer

app = FastAPI(
    title="NLP Answer Analysis Service",
    description="AI-powered interview answer evaluation using Groq/gpt-oss",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    question: str
    answer: str
    category: str = "general"


@app.get("/")
def root():
    return {"service": "NLP Answer Analysis", "status": "running", "model": os.getenv("GROQ_MODEL", "gpt-oss")}


@app.get("/health")
def health():
    has_key = bool(os.getenv("GROQ_API_KEY"))
    return {"status": "healthy", "groq_configured": has_key}


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """
    Analyze an interview answer.

    Accepts: question text, answer text, category
    Returns: Scores for relevance, completeness, communication, technical quality.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = analyze_answer(request.question, request.answer, request.category)
    return {
        "status": "success",
        "analysis": result,
    }
