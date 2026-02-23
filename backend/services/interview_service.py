"""Interview management service."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from models.interview import InterviewSession, Response
from models.analysis import AnalysisResult, FeedbackReport


def create_session(
    db: Session,
    user_id: str,
    interview_type: str,
    total_questions: int = 5,
) -> InterviewSession:
    """Create a new interview session."""
    session = InterviewSession(
        user_id=user_id,
        interview_type=interview_type,
        total_questions=total_questions,
        status="in_progress",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> Optional[InterviewSession]:
    """Get an interview session by ID."""
    return db.query(InterviewSession).filter(InterviewSession.id == session_id).first()


def get_user_sessions(db: Session, user_id: str) -> List[InterviewSession]:
    """Get all sessions for a user, most recent first."""
    return (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.start_time.desc())
        .all()
    )


def add_response(
    db: Session,
    session_id: str,
    question_id: str,
    question_text: str,
    audio_path: Optional[str] = None,
    video_path: Optional[str] = None,
    transcript: Optional[str] = None,
    duration_seconds: Optional[int] = None,
) -> Response:
    """Add a response to an interview session."""
    response = Response(
        session_id=session_id,
        question_id=question_id,
        question_text=question_text,
        audio_path=audio_path,
        video_path=video_path,
        transcript=transcript,
        duration_seconds=duration_seconds,
    )
    db.add(response)

    # Advance the question index
    session = get_session(db, session_id)
    if session:
        session.current_question_index += 1

    db.commit()
    db.refresh(response)
    return response


def end_session(db: Session, session_id: str) -> Optional[InterviewSession]:
    """Mark a session as completed."""
    session = get_session(db, session_id)
    if session:
        session.status = "completed"
        session.end_time = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session)
    return session


def save_analysis_result(db: Session, response_id: str, analysis_data: dict) -> AnalysisResult:
    """Save analysis results for a response. Filters to valid model columns only."""
    # Only pass keys that are actual columns on AnalysisResult
    valid_columns = {c.key for c in AnalysisResult.__table__.columns}
    filtered = {k: v for k, v in analysis_data.items() if k in valid_columns and k != "id"}
    filtered["response_id"] = response_id

    result = AnalysisResult(**filtered)
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def save_feedback_report(db: Session, session_id: str, report_data: dict) -> FeedbackReport:
    """Save a feedback report for a session."""
    report = FeedbackReport(session_id=session_id, **report_data)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_session_responses(db: Session, session_id: str) -> List[Response]:
    """Get all responses for a session."""
    return (
        db.query(Response)
        .filter(Response.session_id == session_id)
        .order_by(Response.created_at)
        .all()
    )


def get_feedback_report(db: Session, session_id: str) -> Optional[FeedbackReport]:
    """Get the feedback report for a session."""
    return db.query(FeedbackReport).filter(FeedbackReport.session_id == session_id).first()
