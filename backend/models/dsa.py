"""DSA round models — questions and submissions."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class DSAQuestion(Base):
    __tablename__ = "dsa_questions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    difficulty = Column(String(20), default="medium")  # easy, medium, hard
    topic = Column(String(100), nullable=False)  # arrays, trees, dp, etc.
    hints = Column(Text, nullable=True)
    expected_complexity = Column(String(100), nullable=True)
    question_order = Column(Integer, nullable=False, default=0)

    submission = relationship("DSASubmission", back_populates="question", uselist=False)


class DSASubmission(Base):
    __tablename__ = "dsa_submissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("dsa_questions.id"), nullable=False, unique=True)

    approach_text = Column(Text, nullable=False)

    # Individual scores (0-100)
    score_correctness = Column(Float, default=0.0)
    score_time_complexity = Column(Float, default=0.0)
    score_space_complexity = Column(Float, default=0.0)
    score_edge_cases = Column(Float, default=0.0)
    score_clarity = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)

    # LLM feedback
    feedback = Column(Text, nullable=True)
    optimal_approach = Column(Text, nullable=True)
    time_complexity_analysis = Column(String(200), nullable=True)

    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    question = relationship("DSAQuestion", back_populates="submission")
