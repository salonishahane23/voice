"""Question bank API routes."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user
from services.question_engine import seed_questions, get_all_categories, get_questions_for_session

router = APIRouter(prefix="/api/questions", tags=["Questions"])


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """Get all available interview question categories."""
    categories = get_all_categories(db)
    return {"categories": categories}


@router.get("/")
def list_questions(
    category: str = None,
    db: Session = Depends(get_db),
):
    """List questions, optionally filtered by category."""
    if category:
        questions = get_questions_for_session(db, category, count=50)
    else:
        from models.interview import Question
        questions = db.query(Question).limit(50).all()

    return {
        "count": len(questions),
        "questions": [
            {
                "id": q.id,
                "category": q.category,
                "difficulty": q.difficulty,
                "text": q.text,
            }
            for q in questions
        ],
    }


@router.post("/seed")
def seed_question_bank(db: Session = Depends(get_db)):
    """Seed the question bank from the JSON file."""
    count = seed_questions(db)
    if count == 0:
        return {"message": "Questions already seeded or no seed file found", "added": 0}
    return {"message": f"Successfully seeded {count} questions", "added": count}
