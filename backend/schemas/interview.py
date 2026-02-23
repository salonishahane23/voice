"""Interview-related Pydantic schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class InterviewStart(BaseModel):
    interview_type: str  # hr, technical, exam
    total_questions: int = 5


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    difficulty: str
    text: str
    tips: Optional[str] = None
    question_number: int = 0
    total_questions: int = 0


class InterviewSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    interview_type: str
    status: str
    current_question_index: int
    total_questions: int
    start_time: datetime
    end_time: Optional[datetime] = None


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question_text: str
    transcript: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: datetime


class InterviewHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    interview_type: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    overall_score: Optional[float] = None
    total_questions: int
