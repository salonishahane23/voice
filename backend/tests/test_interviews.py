"""Tests for interview session endpoints."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import Base, engine

client = TestClient(app)


def _register_and_get_token(email="itest@example.com"):
    """Helper: register a user and return the JWT token."""
    resp = client.post("/api/auth/register", json={
        "name": "Interview Tester",
        "email": email,
        "password": "testpass",
    })
    return resp.json()["access_token"]


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    # Seed questions
    client.post("/api/questions/seed")
    yield
    Base.metadata.drop_all(bind=engine)


class TestInterviews:
    def test_start_interview(self):
        token = _register_and_get_token("start@ex.com")
        resp = client.post("/api/interviews/start", json={
            "interview_type": "hr",
            "total_questions": 3,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert "question" in data
        assert data["question"]["question_number"] == 1

    def test_start_invalid_type(self):
        token = _register_and_get_token("invalid@ex.com")
        resp = client.post("/api/interviews/start", json={
            "interview_type": "music",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_submit_response(self):
        token = _register_and_get_token("respond@ex.com")
        start = client.post("/api/interviews/start", json={
            "interview_type": "technical",
            "total_questions": 2,
        }, headers={"Authorization": f"Bearer {token}"})
        session_id = start.json()["session"]["id"]
        question = start.json()["question"]

        resp = client.post(
            f"/api/interviews/{session_id}/respond",
            data={
                "question_id": question["id"],
                "question_text": question["text"],
                "transcript": "My answer to this question is...",
                "duration_seconds": 30,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_get_next_question(self):
        token = _register_and_get_token("next@ex.com")
        start = client.post("/api/interviews/start", json={
            "interview_type": "hr",
            "total_questions": 3,
        }, headers={"Authorization": f"Bearer {token}"})
        session_id = start.json()["session"]["id"]
        question = start.json()["question"]

        # Submit first response
        client.post(
            f"/api/interviews/{session_id}/respond",
            data={
                "question_id": question["id"],
                "question_text": question["text"],
                "transcript": "Answer",
                "duration_seconds": 15,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Get next question
        resp = client.get(
            f"/api/interviews/{session_id}/next",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "next"
        assert resp.json()["question"]["question_number"] == 2

    def test_end_interview_and_report(self):
        token = _register_and_get_token("end@ex.com")
        start = client.post("/api/interviews/start", json={
            "interview_type": "exam",
            "total_questions": 1,
        }, headers={"Authorization": f"Bearer {token}"})
        session_id = start.json()["session"]["id"]
        question = start.json()["question"]

        # Submit response
        client.post(
            f"/api/interviews/{session_id}/respond",
            data={
                "question_id": question["id"],
                "question_text": question["text"],
                "transcript": "OOP has 4 pillars: encapsulation, inheritance, polymorphism, abstraction.",
                "duration_seconds": 20,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # End session
        end_resp = client.post(
            f"/api/interviews/{session_id}/end",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert end_resp.status_code == 200
        assert end_resp.json()["status"] == "completed"
        assert "feedback" in end_resp.json()

        # Get report
        report = client.get(
            f"/api/interviews/{session_id}/report",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert report.status_code == 200
        assert report.json()["feedback"] is not None

    def test_interview_history(self):
        token = _register_and_get_token("history@ex.com")
        # Start and end a session
        start = client.post("/api/interviews/start", json={
            "interview_type": "hr",
            "total_questions": 1,
        }, headers={"Authorization": f"Bearer {token}"})
        session_id = start.json()["session"]["id"]
        question = start.json()["question"]
        client.post(
            f"/api/interviews/{session_id}/respond",
            data={
                "question_id": question["id"],
                "question_text": question["text"],
                "transcript": "Answer",
                "duration_seconds": 10,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            f"/api/interviews/{session_id}/end",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Check history
        resp = client.get(
            "/api/interviews/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestQuestions:
    def test_list_categories(self):
        resp = client.get("/api/questions/categories")
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        assert "hr" in cats
        assert "technical" in cats
        assert "exam" in cats

    def test_list_questions(self):
        resp = client.get("/api/questions/?category=hr")
        assert resp.status_code == 200
        assert resp.json()["count"] > 0

    def test_seed_idempotent(self):
        resp = client.post("/api/questions/seed")
        assert resp.status_code == 200
        assert resp.json()["added"] == 0  # Already seeded
