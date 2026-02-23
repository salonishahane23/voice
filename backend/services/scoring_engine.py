"""Scoring engine — combines AI analysis outputs into final scores and feedback."""
from typing import List, Dict, Any, Optional

from config import SCORING_WEIGHTS


def calculate_voice_overall(voice_data: dict) -> float:
    """Calculate overall voice score from individual voice metrics."""
    clarity = voice_data.get("voice_clarity_score", 0.0)
    fluency = voice_data.get("voice_fluency_score", 0.0)
    confidence = voice_data.get("voice_confidence_score", 0.0)
    return round((clarity * 0.3 + fluency * 0.4 + confidence * 0.3), 2)


def calculate_nlp_overall(nlp_data: dict) -> float:
    """Calculate overall NLP score from individual NLP metrics."""
    relevance = nlp_data.get("nlp_relevance_score", 0.0)
    completeness = nlp_data.get("nlp_completeness_score", 0.0)
    communication = nlp_data.get("nlp_communication_score", 0.0)
    technical = nlp_data.get("nlp_technical_score", 0.0)
    return round((relevance * 0.3 + completeness * 0.25 + communication * 0.25 + technical * 0.2), 2)


def calculate_facial_overall(facial_data: dict) -> float:
    """Calculate overall facial score from individual facial metrics."""
    confidence = facial_data.get("face_confidence_score", 0.0)
    engagement = facial_data.get("face_engagement_score", 0.0)
    return round((confidence * 0.5 + engagement * 0.5), 2)


def calculate_overall_score(voice_overall: float, nlp_overall: float, facial_overall: float) -> float:
    """Weighted combination of all three analysis dimensions."""
    score = (
        voice_overall * SCORING_WEIGHTS["voice"]
        + nlp_overall * SCORING_WEIGHTS["nlp"]
        + facial_overall * SCORING_WEIGHTS["facial"]
    )
    return round(score, 2)


def generate_feedback(
    responses_analyses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate a feedback report from all response analyses in a session.

    Args:
        responses_analyses: List of analysis result dicts, one per response.

    Returns:
        Dict with overall_score, strengths, weaknesses, suggestions, score_breakdown.
    """
    if not responses_analyses:
        return {
            "overall_score": 0.0,
            "strengths": [],
            "weaknesses": [],
            "suggestions": ["Complete at least one question to receive feedback."],
            "score_breakdown": {"voice": 0, "nlp": 0, "facial": 0},
        }

    # Average scores across all responses
    voice_avg = _avg(responses_analyses, "voice_overall")
    nlp_avg = _avg(responses_analyses, "nlp_overall")
    facial_avg = _avg(responses_analyses, "facial_overall")
    overall = calculate_overall_score(voice_avg, nlp_avg, facial_avg)

    strengths = []
    weaknesses = []
    suggestions = []

    # Voice feedback
    if voice_avg >= 0.7:
        strengths.append("Strong vocal clarity and confident delivery")
    elif voice_avg >= 0.4:
        suggestions.append("Practice speaking more steadily — reduce filler words and long pauses")
    else:
        weaknesses.append("Voice confidence needs significant improvement")
        suggestions.append("Record yourself speaking and practice eliminating 'um', 'uh', and hesitations")

    # Speaking speed feedback
    speed_avg = _avg(responses_analyses, "speaking_speed_wps")
    if speed_avg > 3.5:
        suggestions.append("Slow down slightly — you're speaking quite fast, which can reduce clarity")
    elif speed_avg < 1.5 and speed_avg > 0:
        suggestions.append("Try to speak a bit more naturally and at a consistent pace")

    # Filler words
    filler_avg = _avg(responses_analyses, "filler_word_count")
    if filler_avg > 3:
        weaknesses.append("Frequent use of filler words detected")
        suggestions.append("Practice pausing silently instead of using 'um', 'like', 'you know'")
    elif filler_avg <= 1:
        strengths.append("Minimal use of filler words — very clean speech")

    # NLP feedback
    if nlp_avg >= 0.7:
        strengths.append("Excellent answer content — relevant and well-structured responses")
    elif nlp_avg >= 0.4:
        suggestions.append("Structure your answers using the STAR method (Situation, Task, Action, Result)")
    else:
        weaknesses.append("Answer content needs improvement — focus on relevance and completeness")
        suggestions.append("Before answering, take a moment to organize your thoughts")

    # Facial feedback
    if facial_avg >= 0.7:
        strengths.append("Confident body language and strong engagement")
    elif facial_avg >= 0.4:
        suggestions.append("Practice maintaining eye contact with the camera during responses")
    else:
        weaknesses.append("Low engagement or confidence detected from facial expressions")
        suggestions.append("Sit upright, look at the camera, and try to appear relaxed yet attentive")

    # General improvement
    if overall < 0.5:
        suggestions.append("Consider practicing with a friend or recording yourself regularly to build comfort")

    return {
        "overall_score": round(overall * 100, 1),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "score_breakdown": {
            "voice": round(voice_avg * 100, 1),
            "nlp": round(nlp_avg * 100, 1),
            "facial": round(facial_avg * 100, 1),
        },
    }


def _avg(items: List[Dict], key: str) -> float:
    """Compute average of a key across a list of dicts."""
    values = [item.get(key, 0.0) for item in items]
    return sum(values) / len(values) if values else 0.0
