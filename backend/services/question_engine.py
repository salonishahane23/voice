"""Question engine — selects, serves, and dynamically generates interview questions."""
import json
import os
import random
from pathlib import Path
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from models.interview import Question

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

SEED_FILE = Path(__file__).resolve().parent.parent / "seed_data" / "questions.json"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "gpt-oss")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def seed_questions(db: Session) -> int:
    """Load questions from seed file into the database. Returns count of new questions added."""
    existing_count = db.query(Question).count()
    if existing_count > 0:
        return 0  # Already seeded

    if not SEED_FILE.exists():
        return 0

    with open(SEED_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    count = 0
    for q in questions:
        question = Question(
            category=q["category"],
            difficulty=q.get("difficulty", "medium"),
            text=q["text"],
            expected_answer=q.get("expected_answer"),
            tips=q.get("tips"),
        )
        db.add(question)
        count += 1

    db.commit()
    return count


def generate_questions_llm(category: str, count: int = 5) -> List[dict]:
    """
    Generate fresh interview questions using Groq/gpt-oss.
    Falls back to empty list if API key not set or API fails.
    """
    if not GROQ_API_KEY:
        return []

    category_descriptions = {
        "hr": "behavioral HR interview questions about teamwork, leadership, strengths, weaknesses, career goals, conflict resolution, and work experience",
        "viva": "technical viva questions about programming concepts, data structures, algorithms, system design, databases, APIs, and software engineering principles",
        "technical": "technical interview questions about programming concepts, data structures, algorithms, system design, databases, APIs, and software engineering principles",
        "exam": "academic viva/exam questions about computer science fundamentals including OS, DBMS, networking, data structures, algorithms, and OOP concepts",
    }
    desc = category_descriptions.get(category, f"{category} interview questions")

    prompt = f"""Generate exactly {count} unique {desc}.

Each question should be challenging and test the candidate's depth of knowledge.
Vary the difficulty: include 1 easy, {count-2} medium, and 1 hard question.

Respond ONLY with a JSON array. Each item must have:
- "text": the question text
- "difficulty": "easy", "medium", or "hard"
- "tips": one brief tip for answering well (max 15 words)

JSON array only, no other text:"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert interview question designer. Respond with valid JSON arrays only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 2048,
    }

    try:
        response = httpx.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()

        # Clean markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        questions = json.loads(text)
        if isinstance(questions, list):
            print(f"[QUESTIONS] Generated {len(questions)} questions via Groq for category: {category}")
            return [
                {
                    "text": q.get("text", ""),
                    "difficulty": q.get("difficulty", "medium"),
                    "category": category,
                    "tips": q.get("tips", ""),
                }
                for q in questions
                if q.get("text")
            ]
    except Exception as e:
        print(f"[QUESTIONS] Groq generation failed: {e}")

    return []


def get_questions_for_session(
    db: Session,
    category: str,
    count: int = 5,
) -> List[Question]:
    """
    Select questions for an interview session.
    Tries dynamic generation via Groq first, falls back to database seed questions.
    """
    # Try LLM-generated questions first
    generated = generate_questions_llm(category, count)
    if generated:
        # Save generated questions to DB and return them
        questions = []
        for q in generated[:count]:
            question = Question(
                category=q["category"],
                difficulty=q["difficulty"],
                text=q["text"],
                tips=q.get("tips"),
            )
            db.add(question)
            db.flush()
            questions.append(question)
        db.commit()
        return questions

    # Fallback to seed questions from database
    questions = (
        db.query(Question)
        .filter(Question.category == category)
        .all()
    )

    if len(questions) <= count:
        selected = questions
    else:
        selected = random.sample(questions, count)

    return selected


def get_question_by_id(db: Session, question_id: str) -> Optional[Question]:
    """Get a single question by ID."""
    return db.query(Question).filter(Question.id == question_id).first()


def get_all_categories(db: Session) -> List[str]:
    """Get distinct question categories."""
    results = db.query(Question.category).distinct().all()
    return [r[0] for r in results]
