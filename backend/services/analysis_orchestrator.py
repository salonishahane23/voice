"""
Analysis Orchestrator — Coordinates AI microservice calls.

Pipeline:
1. Voice service receives audio → transcribes via Whisper → returns transcript + voice scores
2. NLP service receives transcript (from voice) + question → returns content scores
3. Facial service receives video → returns posture/eye/engagement scores

Voice runs FIRST so its transcript feeds into NLP. Facial runs in parallel with voice.
No mock/fake scores — if a service is down, that category gets 0.
"""
import asyncio
import httpx
from typing import Dict, Any, Optional

from config import VOICE_SERVICE_URL, NLP_SERVICE_URL, FACIAL_SERVICE_URL

SERVICE_TIMEOUT = 120  # longer timeout for Whisper transcription


async def call_voice_service(audio_path: str) -> Dict[str, Any]:
    """Call Voice Analysis service — returns transcript + voice scores."""
    try:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{VOICE_SERVICE_URL}/analyze",
                    files={"audio": ("audio.webm", f, "audio/webm")},
                )
            if response.status_code == 200:
                return response.json().get("analysis", {})
            else:
                print(f"[ORCHESTRATOR] Voice service returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[ORCHESTRATOR] Voice service error: {e}")
    return {}


async def call_nlp_service(question: str, answer: str, category: str = "general") -> Dict[str, Any]:
    """Call NLP Analysis service — evaluates answer content quality."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{NLP_SERVICE_URL}/analyze",
                json={"question": question, "answer": answer, "category": category},
            )
            if response.status_code == 200:
                return response.json().get("analysis", {})
            else:
                print(f"[ORCHESTRATOR] NLP service returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[ORCHESTRATOR] NLP service error: {e}")
    return {}


async def call_facial_service(video_path: str) -> Dict[str, Any]:
    """Call Facial Analysis service — returns posture/eye/engagement scores."""
    try:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            with open(video_path, "rb") as f:
                response = await client.post(
                    f"{FACIAL_SERVICE_URL}/analyze",
                    files={"video": ("video.webm", f, "video/webm")},
                )
            if response.status_code == 200:
                return response.json().get("analysis", {})
            else:
                print(f"[ORCHESTRATOR] Facial service returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[ORCHESTRATOR] Facial service error: {e}")
    return {}


async def orchestrate_analysis(
    audio_path: Optional[str],
    video_path: Optional[str],
    question_text: str,
    transcript: str = "",
    category: str = "general",
) -> Dict[str, Any]:
    """
    Orchestrate AI analysis with proper pipeline:

    1. Voice + Facial run in parallel
    2. Voice returns transcript → fed into NLP
    3. Results combined into final scores

    NO mock scores. If a service is down, those scores are 0.
    """
    voice = {}
    nlp = {}
    facial = {}

    # Step 1: Run Voice and Facial in parallel
    parallel_tasks = {}
    if audio_path:
        parallel_tasks["voice"] = call_voice_service(audio_path)
    if video_path:
        parallel_tasks["facial"] = call_facial_service(video_path)

    if parallel_tasks:
        keys = list(parallel_tasks.keys())
        values = await asyncio.gather(*parallel_tasks.values(), return_exceptions=True)
        for k, v in zip(keys, values):
            if isinstance(v, Exception):
                print(f"[ORCHESTRATOR] {k} error: {v}")
            elif k == "voice":
                voice = v
            elif k == "facial":
                facial = v

    # Step 2: Get transcript from voice service (NOT from frontend)
    actual_transcript = voice.get("transcript", "") or transcript
    print(f"[ORCHESTRATOR] Transcript length: {len(actual_transcript)} chars")

    # Step 3: Run NLP with the ACTUAL transcript from whisper
    if actual_transcript and len(actual_transcript.strip()) > 5:
        nlp = await call_nlp_service(question_text, actual_transcript, category)
    else:
        print("[ORCHESTRATOR] No transcript available — NLP scores will be 0")

    # Extract scores — 0.0 when service didn't return data
    voice_clarity = voice.get("clarity_score", 0.0)
    voice_fluency = voice.get("fluency_score", 0.0)
    voice_confidence = voice.get("voice_confidence_score", 0.0)
    speaking_speed = voice.get("speaking_rate", {}).get("words_per_second", 0.0)
    filler_count = voice.get("filler_words", {}).get("count", 0)
    pause_count = voice.get("pauses", {}).get("pause_count", 0)

    nlp_relevance = nlp.get("relevance_score", 0.0)
    nlp_completeness = nlp.get("completeness_score", 0.0)
    nlp_communication = nlp.get("communication_score", 0.0)
    nlp_technical = nlp.get("technical_score", 0.0)

    face_confidence = facial.get("face_confidence_score", 0.0)
    face_engagement = facial.get("face_engagement_score", 0.0)
    face_emotion = facial.get("face_emotion_state", "unknown")

    # Calculate per-category overall scores
    voice_overall = round(voice_clarity * 0.3 + voice_fluency * 0.4 + voice_confidence * 0.3, 3)
    nlp_overall = round(
        nlp_relevance * 0.30 + nlp_completeness * 0.25
        + nlp_communication * 0.25 + nlp_technical * 0.20, 3
    )
    facial_overall = round(face_confidence * 0.5 + face_engagement * 0.5, 3)

    # Overall: voice 30%, NLP 40%, facial 30%
    overall = round(voice_overall * 0.3 + nlp_overall * 0.4 + facial_overall * 0.3, 3)

    return {
        # Transcript from Whisper
        "transcript": actual_transcript,

        # Voice scores
        "voice_clarity_score": voice_clarity,
        "voice_fluency_score": voice_fluency,
        "voice_confidence_score": voice_confidence,
        "speaking_speed_wps": speaking_speed,
        "filler_word_count": filler_count,
        "pause_count": pause_count,

        # NLP scores
        "nlp_relevance_score": nlp_relevance,
        "nlp_completeness_score": nlp_completeness,
        "nlp_communication_score": nlp_communication,
        "nlp_technical_score": nlp_technical,

        # Facial scores
        "face_confidence_score": face_confidence,
        "face_engagement_score": face_engagement,
        "face_emotion_state": face_emotion,

        # Overalls
        "voice_overall": voice_overall,
        "nlp_overall": nlp_overall,
        "facial_overall": facial_overall,
        "overall_score": overall,

        # Raw details (filler timestamps, posture data, etc.)
        "voice_raw": voice,
        "nlp_raw": nlp,
        "facial_raw": facial,
    }
