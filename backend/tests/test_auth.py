"""Tests for authentication endpoints."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestAuth:
    def test_register_success(self):
        response = client.post("/api/auth/register", json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["name"] == "Test User"

    def test_register_duplicate_email(self):
        client.post("/api/auth/register", json={
            "name": "User 1",
            "email": "dup@example.com",
            "password": "pass123",
        })
        response = client.post("/api/auth/register", json={
            "name": "User 2",
            "email": "dup@example.com",
            "password": "pass456",
        })
        assert response.status_code == 409

    def test_login_success(self):
        client.post("/api/auth/register", json={
            "name": "Login User",
            "email": "login@example.com",
            "password": "mypassword",
        })
        response = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "mypassword",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password(self):
        client.post("/api/auth/register", json={
            "name": "User",
            "email": "wrong@example.com",
            "password": "correct",
        })
        response = client.post("/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "incorrect",
        })
        assert response.status_code == 401

    def test_get_me(self):
        reg = client.post("/api/auth/register", json={
            "name": "Me User",
            "email": "me@example.com",
            "password": "pass123",
        })
        token = reg.json()["access_token"]
        response = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"

    def test_get_me_invalid_token(self):
        response = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-token"
        })
        assert response.status_code == 401
