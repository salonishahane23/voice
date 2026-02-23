"""Interview session API routes."""
import os
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from config import UPLOAD_DIR
from database import get_db
from routers.auth import get_current_user
from schemas.interview import (
    InterviewStart,
    InterviewSessionOut,
    QuestionOut,
    InterviewHistoryItem,
)
from schemas.analysis import FullReportOut, FeedbackReportOut
from services.interview_service import (
    create_session,
    get_session,
    get_user_sessions,
    add_response,
    end_session,
    get_session_responses,
    get_feedback_report,
    save_analysis_result,
    save_feedback_report,
)
from services.question_engine import get_questions_for_session
from services.scoring_engine import (
    calculate_voice_overall,
    calculate_nlp_overall,
    calculate_facial_overall,
    calculate_overall_score,
    generate_feedback,
)

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])

# In-memory session question cache (maps session_id → list of question dicts)
_session_questions: dict = {}


@router.post("/start", response_model=dict)
def start_interview(
    data: InterviewStart,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new interview session. Returns session info and the first question."""
    # Validate interview type
    valid_types = ["hr", "technical", "viva", "exam", "dsa"]
    if data.interview_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interview type. Must be one of: {valid_types}",
        )

    # Get questions for this category
    questions = get_questions_for_session(db, data.interview_type, data.total_questions)
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No questions found for category: {data.interview_type}. Run seed first.",
        )

    # Create session
    session = create_session(
        db,
        user_id=current_user.id,
        interview_type=data.interview_type,
        total_questions=len(questions),
    )

    # Cache the question order for this session
    question_list = [
        {
            "id": q.id,
            "category": q.category,
            "difficulty": q.difficulty,
            "text": q.text,
            "tips": q.tips,
        }
        for q in questions
    ]
    _session_questions[session.id] = question_list

    first_q = question_list[0]
    return {
        "session": InterviewSessionOut.model_validate(session).model_dump(),
        "question": {
            **first_q,
            "question_number": 1,
            "total_questions": len(questions),
        },
    }


@router.post("/{session_id}/respond")
async def submit_response(
    session_id: str,
    question_id: str = Form(...),
    question_text: str = Form(...),
    transcript: str = Form(default=""),
    duration_seconds: int = Form(default=0),
    audio: UploadFile = File(default=None),
    video: UploadFile = File(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a response (audio/video + transcript) for the current question."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is already completed")

    # Save uploaded files
    audio_path = None
    video_path = None
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    if audio:
        audio_filename = f"q{session.current_question_index}_{uuid.uuid4().hex[:8]}.webm"
        audio_path = str(session_dir / audio_filename)
        with open(audio_path, "wb") as f:
            f.write(audio.file.read())

    if video:
        video_filename = f"v{session.current_question_index}_{uuid.uuid4().hex[:8]}.webm"
        video_path = str(session_dir / video_filename)
        with open(video_path, "wb") as f:
            f.write(video.file.read())

    # Save response
    response = add_response(
        db,
        session_id=session_id,
        question_id=question_id,
        question_text=question_text,
        audio_path=audio_path,
        video_path=video_path,
        transcript=transcript,
        duration_seconds=duration_seconds,
    )

    # Run real AI analysis — no mock/fake scores
    try:
        from services.analysis_orchestrator import orchestrate_analysis
        analysis_data = await orchestrate_analysis(
            audio_path=audio_path,
            video_path=video_path,
            question_text=question_text,
            transcript=transcript,
            category=session.interview_type,
        )
    except Exception as e:
        print(f"[INTERVIEW] Orchestrator error: {e}")
        analysis_data = {
            "overall_score": 0.0,
            "voice_overall": 0.0,
            "nlp_overall": 0.0,
            "facial_overall": 0.0,
            "note": f"Analysis failed: {str(e)}",
        }

    save_analysis_result(db, response.id, analysis_data)

    return {"status": "ok", "response_id": response.id}


@router.get("/{session_id}/next")
def get_next_question(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the next question in the interview session."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is already completed")

    question_list = _session_questions.get(session_id, [])
    idx = session.current_question_index

    if idx >= len(question_list):
        return {"status": "completed", "message": "All questions answered"}

    q = question_list[idx]
    return {
        "status": "next",
        "question": {
            **q,
            "question_number": idx + 1,
            "total_questions": len(question_list),
        },
    }


@router.post("/{session_id}/end")
def finish_interview(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End an interview session and generate the feedback report."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Mark session complete
    end_session(db, session_id)

    # Gather all analyses
    responses = get_session_responses(db, session_id)
    analyses = []
    for resp in responses:
        if resp.analysis:
            analyses.append({
                "voice_overall": resp.analysis.voice_overall,
                "nlp_overall": resp.analysis.nlp_overall,
                "facial_overall": resp.analysis.facial_overall,
                "speaking_speed_wps": resp.analysis.speaking_speed_wps,
                "filler_word_count": resp.analysis.filler_word_count,
            })

    # Generate feedback
    feedback_data = generate_feedback(analyses)
    save_feedback_report(db, session_id, feedback_data)

    # Cleanup cached questions
    _session_questions.pop(session_id, None)

    return {"status": "completed", "feedback": feedback_data}


@router.get("/{session_id}/report", response_model=FullReportOut)
def get_report(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the full interview report with feedback and per-question analysis."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    feedback = get_feedback_report(db, session_id)
    responses = get_session_responses(db, session_id)

    response_data = []
    for resp in responses:
        entry = {
            "id": resp.id,
            "question_text": resp.question_text,
            "transcript": resp.transcript,
            "duration_seconds": resp.duration_seconds,
        }
        if resp.analysis:
            entry["analysis"] = {
                "voice_overall": resp.analysis.voice_overall,
                "nlp_overall": resp.analysis.nlp_overall,
                "facial_overall": resp.analysis.facial_overall,
                "overall_score": resp.analysis.overall_score,
                "voice_confidence": resp.analysis.voice_confidence_score,
                "filler_word_count": resp.analysis.filler_word_count,
                "voice_raw": resp.analysis.voice_raw,
                "nlp_raw": resp.analysis.nlp_raw,
                "facial_raw": resp.analysis.facial_raw,
            }
        response_data.append(entry)

    return FullReportOut(
        session={
            "id": session.id,
            "interview_type": session.interview_type,
            "status": session.status,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "total_questions": session.total_questions,
        },
        feedback=FeedbackReportOut.model_validate(feedback) if feedback else None,
        responses=response_data,
    )


@router.get("/history", response_model=List[InterviewHistoryItem])
def get_history(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's interview history."""
    sessions = get_user_sessions(db, current_user.id)
    history = []
    for s in sessions:
        report = get_feedback_report(db, s.id)
        history.append(
            InterviewHistoryItem(
                id=s.id,
                interview_type=s.interview_type,
                status=s.status,
                start_time=s.start_time,
                end_time=s.end_time,
                overall_score=report.overall_score if report else None,
                total_questions=s.total_questions,
            )
        )
    return history


# Mock score generation removed — all analysis is real.
