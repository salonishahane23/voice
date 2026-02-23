"""DSA round API routes — question generation, approach submission, evaluation."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user
from models.interview import InterviewSession
from models.dsa import DSAQuestion, DSASubmission
from schemas.dsa import (
    DSASessionStart,
    DSAQuestionOut,
    DSAApproachSubmit,
    DSAEvaluationOut,
    DSAReportOut,
    DSAQuestionReport,
)
from services.dsa_question_engine import generate_dsa_questions
from services.dsa_evaluator import evaluate_approach
from services.interview_service import create_session, get_session, end_session

router = APIRouter(prefix="/api/dsa", tags=["DSA Round"])

# In-memory cache for DSA session questions (session_id → list of DSAQuestion ids)
_dsa_session_questions: dict = {}


@router.post("/start", response_model=dict)
def start_dsa_session(
    data: DSASessionStart,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new DSA interview session. Generates questions via LLM."""
    try:
        generated = generate_dsa_questions(
            count=data.num_questions,
            difficulty=data.difficulty_preference,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    if not generated:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to generate DSA questions. Please try again.",
        )

    # Create an interview session with type "dsa"
    session = create_session(
        db,
        user_id=current_user.id,
        interview_type="dsa",
        total_questions=len(generated),
    )

    # Save questions to DB
    question_ids = []
    for idx, q in enumerate(generated):
        dsa_q = DSAQuestion(
            session_id=session.id,
            title=q["title"],
            description=q["description"],
            difficulty=q["difficulty"],
            topic=q["topic"],
            hints=q.get("hints", ""),
            expected_complexity=q.get("expected_complexity", ""),
            question_order=idx,
        )
        db.add(dsa_q)
        db.flush()
        question_ids.append(dsa_q.id)

    db.commit()

    # Cache question order
    _dsa_session_questions[session.id] = question_ids

    # Return session info + first question
    first_q = db.query(DSAQuestion).filter(DSAQuestion.id == question_ids[0]).first()

    return {
        "session": {
            "id": session.id,
            "interview_type": session.interview_type,
            "status": session.status,
            "total_questions": session.total_questions,
        },
        "question": {
            "id": first_q.id,
            "title": first_q.title,
            "description": first_q.description,
            "difficulty": first_q.difficulty,
            "topic": first_q.topic,
            "hints": first_q.hints,
            "question_order": 0,
            "total_questions": len(question_ids),
        },
    }


@router.get("/{session_id}/question")
def get_current_dsa_question(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current DSA question."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is already completed")

    question_ids = _dsa_session_questions.get(session_id)
    if not question_ids:
        # Rebuild from DB
        questions = (
            db.query(DSAQuestion)
            .filter(DSAQuestion.session_id == session_id)
            .order_by(DSAQuestion.question_order)
            .all()
        )
        question_ids = [q.id for q in questions]
        _dsa_session_questions[session_id] = question_ids

    idx = session.current_question_index
    if idx >= len(question_ids):
        return {"status": "completed", "message": "All questions answered"}

    q = db.query(DSAQuestion).filter(DSAQuestion.id == question_ids[idx]).first()
    return {
        "status": "next",
        "question": {
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "difficulty": q.difficulty,
            "topic": q.topic,
            "hints": q.hints,
            "question_order": idx,
            "total_questions": len(question_ids),
        },
    }


@router.post("/{session_id}/submit")
def submit_dsa_approach(
    session_id: str,
    data: DSAApproachSubmit,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit approach + pseudocode for a DSA question and get LLM evaluation."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is already completed")

    # Get the question
    question = db.query(DSAQuestion).filter(DSAQuestion.id == data.question_id).first()
    if not question or question.session_id != session_id:
        raise HTTPException(status_code=404, detail="Question not found in this session")

    # Check if already submitted
    existing = db.query(DSASubmission).filter(DSASubmission.question_id == data.question_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already submitted an approach for this question")

    # Evaluate via LLM
    try:
        evaluation = evaluate_approach(
            problem_title=question.title,
            problem_description=question.description,
            user_approach=data.approach_text,
            expected_complexity=question.expected_complexity or "",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    # Save submission
    submission = DSASubmission(
        session_id=session_id,
        question_id=data.question_id,
        approach_text=data.approach_text,
        score_correctness=evaluation["score_correctness"],
        score_time_complexity=evaluation["score_time_complexity"],
        score_space_complexity=evaluation["score_space_complexity"],
        score_edge_cases=evaluation["score_edge_cases"],
        score_clarity=evaluation["score_clarity"],
        overall_score=evaluation["overall_score"],
        feedback=evaluation.get("feedback", ""),
        optimal_approach=evaluation.get("optimal_approach", ""),
        time_complexity_analysis=evaluation.get("time_complexity_analysis", ""),
    )
    db.add(submission)

    # Advance question index
    session.current_question_index += 1
    db.commit()

    return {
        "status": "evaluated",
        "question_id": data.question_id,
        "overall_score": evaluation["overall_score"],
        "score_correctness": evaluation["score_correctness"],
        "score_time_complexity": evaluation["score_time_complexity"],
        "score_space_complexity": evaluation["score_space_complexity"],
        "score_edge_cases": evaluation["score_edge_cases"],
        "score_clarity": evaluation["score_clarity"],
        "feedback": evaluation.get("feedback", ""),
        "optimal_approach": evaluation.get("optimal_approach", ""),
        "time_complexity_analysis": evaluation.get("time_complexity_analysis", ""),
    }


@router.get("/{session_id}/next")
def get_next_dsa_question(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the next DSA question after submitting the current one."""
    return get_current_dsa_question(session_id, current_user, db)


@router.post("/{session_id}/end")
def end_dsa_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End the DSA session and return aggregate results."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    end_session(db, session_id)

    # Cleanup cache
    _dsa_session_questions.pop(session_id, None)

    # Build report
    return _build_dsa_report(db, session_id)


@router.get("/{session_id}/report")
def get_dsa_report(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the full DSA session report with all evaluations."""
    session = get_session(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    return _build_dsa_report(db, session_id)


def _build_dsa_report(db: Session, session_id: str) -> dict:
    """Build the aggregate DSA report."""
    questions = (
        db.query(DSAQuestion)
        .filter(DSAQuestion.session_id == session_id)
        .order_by(DSAQuestion.question_order)
        .all()
    )

    question_reports = []
    scores = []
    for q in questions:
        sub = db.query(DSASubmission).filter(DSASubmission.question_id == q.id).first()
        report_item = {
            "question_id": q.id,
            "title": q.title,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "approach_text": sub.approach_text if sub else None,
            "evaluation": None,
        }
        if sub:
            report_item["evaluation"] = {
                "question_id": q.id,
                "overall_score": sub.overall_score,
                "score_correctness": sub.score_correctness,
                "score_time_complexity": sub.score_time_complexity,
                "score_space_complexity": sub.score_space_complexity,
                "score_edge_cases": sub.score_edge_cases,
                "score_clarity": sub.score_clarity,
                "feedback": sub.feedback,
                "optimal_approach": sub.optimal_approach,
                "time_complexity_analysis": sub.time_complexity_analysis,
            }
            scores.append(sub.overall_score)
        question_reports.append(report_item)

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return {
        "session_id": session_id,
        "total_questions": len(questions),
        "questions_answered": len(scores),
        "average_score": avg_score,
        "questions": question_reports,
    }
