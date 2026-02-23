"""Interview session, question, and response models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    interview_type = Column(String(50), nullable=False)  # hr, technical, exam
    status = Column(String(20), default="in_progress")   # in_progress, completed, cancelled
    current_question_index = Column(Integer, default=0)
    total_questions = Column(Integer, default=5)
    start_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_time = Column(DateTime, nullable=True)

    responses = relationship("Response", back_populates="session", cascade="all, delete-orphan")
    feedback_report = relationship("FeedbackReport", back_populates="session", uselist=False)


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String(50), nullable=False, index=True)   # hr, technical, exam
    difficulty = Column(String(20), default="medium")            # easy, medium, hard
    text = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True)
    tips = Column(Text, nullable=True)


class Response(Base):
    __tablename__ = "responses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    audio_path = Column(String(500), nullable=True)
    video_path = Column(String(500), nullable=True)
    transcript = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("InterviewSession", back_populates="responses")
    analysis = relationship("AnalysisResult", back_populates="response", uselist=False)
