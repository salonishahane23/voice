"""DSA-related Pydantic schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class DSASessionStart(BaseModel):
    num_questions: int = 3
    difficulty_preference: Optional[str] = None  # easy, medium, hard, or None for mixed


class DSAQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    difficulty: str
    topic: str
    hints: Optional[str] = None
    question_order: int
    total_questions: int = 0


class DSAApproachSubmit(BaseModel):
    question_id: str
    approach_text: str


class DSAEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    overall_score: float
    score_correctness: float
    score_time_complexity: float
    score_space_complexity: float
    score_edge_cases: float
    score_clarity: float
    feedback: Optional[str] = None
    optimal_approach: Optional[str] = None
    time_complexity_analysis: Optional[str] = None


class DSAQuestionReport(BaseModel):
    question_id: str
    title: str
    topic: str
    difficulty: str
    approach_text: Optional[str] = None
    evaluation: Optional[DSAEvaluationOut] = None


class DSAReportOut(BaseModel):
    session_id: str
    total_questions: int
    questions_answered: int
    average_score: float
    questions: List[DSAQuestionReport]
