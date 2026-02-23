"""Analysis result and feedback report models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    response_id = Column(String, ForeignKey("responses.id"), nullable=False, unique=True)

    # Voice analysis scores
    voice_clarity_score = Column(Float, default=0.0)
    voice_fluency_score = Column(Float, default=0.0)
    voice_confidence_score = Column(Float, default=0.0)
    speaking_speed_wps = Column(Float, default=0.0)
    filler_word_count = Column(Float, default=0.0)
    pause_count = Column(Float, default=0.0)

    # NLP analysis scores
    nlp_relevance_score = Column(Float, default=0.0)
    nlp_completeness_score = Column(Float, default=0.0)
    nlp_communication_score = Column(Float, default=0.0)
    nlp_technical_score = Column(Float, default=0.0)

    # Facial analysis scores
    face_confidence_score = Column(Float, default=0.0)
    face_engagement_score = Column(Float, default=0.0)
    face_emotion_state = Column(String(50), default="neutral")

    # Combined scores
    voice_overall = Column(Float, default=0.0)
    nlp_overall = Column(Float, default=0.0)
    facial_overall = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)

    # Raw data from AI services
    voice_raw = Column(JSON, nullable=True)
    nlp_raw = Column(JSON, nullable=True)
    facial_raw = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    response = relationship("Response", back_populates="analysis")


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, unique=True)

    overall_score = Column(Float, default=0.0)
    strengths = Column(JSON, default=list)        # List of strength strings
    weaknesses = Column(JSON, default=list)       # List of weakness strings
    suggestions = Column(JSON, default=list)      # List of improvement tips
    score_breakdown = Column(JSON, default=dict)  # {voice: X, nlp: Y, face: Z}

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("InterviewSession", back_populates="feedback_report")
