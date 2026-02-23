"""Analysis-related Pydantic schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any


class AnalysisResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    response_id: str

    # Voice scores
    voice_clarity_score: float
    voice_fluency_score: float
    voice_confidence_score: float
    speaking_speed_wps: float
    filler_word_count: float
    pause_count: float

    # NLP scores
    nlp_relevance_score: float
    nlp_completeness_score: float
    nlp_communication_score: float
    nlp_technical_score: float

    # Facial scores
    face_confidence_score: float
    face_engagement_score: float
    face_emotion_state: str

    # Combined
    voice_overall: float
    nlp_overall: float
    facial_overall: float
    overall_score: float


class FeedbackReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    score_breakdown: Dict[str, float]
    created_at: datetime


class FullReportOut(BaseModel):
    session: Dict[str, Any]
    feedback: Optional[FeedbackReportOut] = None
    responses: List[Dict[str, Any]]
