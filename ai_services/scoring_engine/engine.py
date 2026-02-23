"""
Scoring & Feedback Engine — Core logic.

Combines voice, NLP, and facial analysis results into final scores
and generates actionable coaching feedback.
"""
from typing import List, Dict, Any

# Scoring weights
WEIGHTS = {
    "voice": 0.30,
    "nlp": 0.40,
    "facial": 0.30,
}


def combine_scores(
    voice: Dict[str, Any],
    nlp: Dict[str, Any],
    facial: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine scores from all three analysis modules into a single result.

    Args:
        voice: Voice analysis output with fluency_score, clarity_score, voice_confidence_score
        nlp: NLP analysis output with relevance, completeness, communication, technical scores
        facial: Facial analysis output with face_confidence_score, face_engagement_score

    Returns:
        Dict with voice_overall, nlp_overall, facial_overall, and overall_score.
    """
    # Voice overall
    v_fluency = voice.get("fluency_score", 0.5)
    v_clarity = voice.get("clarity_score", 0.5)
    v_confidence = voice.get("voice_confidence_score", 0.5)
    voice_overall = round(v_fluency * 0.4 + v_clarity * 0.3 + v_confidence * 0.3, 3)

    # NLP overall
    n_relevance = nlp.get("relevance_score", 0.5)
    n_completeness = nlp.get("completeness_score", 0.5)
    n_communication = nlp.get("communication_score", 0.5)
    n_technical = nlp.get("technical_score", 0.5)
    nlp_overall = round(
        n_relevance * 0.30 + n_completeness * 0.25 + n_communication * 0.25 + n_technical * 0.20, 3
    )

    # Facial overall
    f_confidence = facial.get("face_confidence_score", 0.5)
    f_engagement = facial.get("face_engagement_score", 0.5)
    facial_overall = round(f_confidence * 0.5 + f_engagement * 0.5, 3)

    # Combined overall
    overall = round(
        voice_overall * WEIGHTS["voice"]
        + nlp_overall * WEIGHTS["nlp"]
        + facial_overall * WEIGHTS["facial"],
        3,
    )

    return {
        "voice_overall": voice_overall,
        "nlp_overall": nlp_overall,
        "facial_overall": facial_overall,
        "overall_score": overall,
        "voice_details": {
            "fluency": v_fluency,
            "clarity": v_clarity,
            "confidence": v_confidence,
        },
        "nlp_details": {
            "relevance": n_relevance,
            "completeness": n_completeness,
            "communication": n_communication,
            "technical": n_technical,
        },
        "facial_details": {
            "confidence": f_confidence,
            "engagement": f_engagement,
        },
    }


def generate_session_feedback(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate comprehensive session feedback from all responses.

    Each response dict should have voice_analysis, nlp_analysis, facial_analysis keys.
    """
    if not responses:
        return {
            "overall_score": 0.0,
            "strengths": [],
            "weaknesses": [],
            "suggestions": ["Complete at least one question to receive feedback."],
            "score_breakdown": {"voice": 0, "nlp": 0, "facial": 0},
        }

    # Compute scores for each response
    all_scores = []
    for resp in responses:
        scores = combine_scores(
            voice=resp.get("voice_analysis", {}),
            nlp=resp.get("nlp_analysis", {}),
            facial=resp.get("facial_analysis", {}),
        )
        all_scores.append(scores)

    # Average
    voice_avg = _avg([s["voice_overall"] for s in all_scores])
    nlp_avg = _avg([s["nlp_overall"] for s in all_scores])
    facial_avg = _avg([s["facial_overall"] for s in all_scores])
    overall_avg = _avg([s["overall_score"] for s in all_scores])

    strengths = []
    weaknesses = []
    suggestions = []

    # Voice feedback
    if voice_avg >= 0.7:
        strengths.append("Strong vocal delivery with good clarity and confidence")
    elif voice_avg >= 0.4:
        suggestions.append("Practice speaking more steadily and reduce filler words")
    else:
        weaknesses.append("Voice confidence needs significant improvement")
        suggestions.append("Record yourself daily and practice eliminating hesitations")

    # NLP feedback
    if nlp_avg >= 0.7:
        strengths.append("Excellent answer content with relevant and well-structured responses")
    elif nlp_avg >= 0.4:
        suggestions.append("Use the STAR method (Situation, Task, Action, Result) for behavioral questions")
    else:
        weaknesses.append("Answer content needs improvement in relevance and completeness")
        suggestions.append("Before answering, pause briefly to organize your thoughts")

    # Facial feedback
    if facial_avg >= 0.7:
        strengths.append("Confident body language and strong visual engagement")
    elif facial_avg >= 0.4:
        suggestions.append("Practice maintaining natural eye contact with the camera")
    else:
        weaknesses.append("Low visual engagement or confidence detected")
        suggestions.append("Sit upright, look at the camera, and project a calm, attentive demeanor")

    # General
    if overall_avg < 0.5:
        suggestions.append("Regular mock interview practice will help build overall confidence")

    return {
        "overall_score": round(overall_avg * 100, 1),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "score_breakdown": {
            "voice": round(voice_avg * 100, 1),
            "nlp": round(nlp_avg * 100, 1),
            "facial": round(facial_avg * 100, 1),
        },
    }


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0
