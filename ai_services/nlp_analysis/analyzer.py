"""
NLP Answer Analysis Module — Core analyzer.

Uses Groq API with the gpt-oss model to evaluate interview answer quality
including relevance, completeness, structure, and communication quality.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "gpt-oss")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_groq_api(messages: list, temperature: float = 0.3) -> Optional[str]:
    """Call the Groq API and return the response text."""
    import httpx

    if not GROQ_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1024,
    }

    try:
        response = httpx.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[NLP] Groq API error: {e}")
        return None


def analyze_answer(question: str, answer: str, category: str = "general") -> Dict[str, Any]:
    """
    Analyze an interview answer using the Groq LLM.

    Args:
        question: The interview question asked.
        answer: The candidate's transcribed answer.
        category: Interview category (hr, technical, exam).

    Returns:
        Dict with relevance_score, completeness_score, communication_score,
        technical_score, keywords, feedback, and overall score.
    """
    if not answer or len(answer.strip()) < 5:
        return _empty_analysis("Answer too short or empty to analyze.")

    # Try LLM-based analysis
    llm_result = _llm_analysis(question, answer, category)
    if llm_result:
        return llm_result

    # Fallback to rule-based analysis
    return _rule_based_analysis(question, answer, category)


def _llm_analysis(question: str, answer: str, category: str) -> Optional[Dict[str, Any]]:
    """Use Groq LLM to analyze the answer."""
    prompt = f"""You are an expert interview coach. Analyze the following interview answer and provide scores.

**Interview Category:** {category}
**Question:** {question}
**Candidate's Answer:** {answer}

Evaluate the answer on these criteria (score each from 0.0 to 1.0):
1. **relevance_score**: How relevant is the answer to the question?
2. **completeness_score**: How complete and thorough is the answer?
3. **communication_score**: How well-structured and clearly communicated is the answer?
4. **technical_score**: How technically accurate is the answer (if applicable)?

Also provide:
- **keywords**: List of important keywords/concepts used (max 5)
- **strengths**: One sentence about what was done well
- **improvement**: One sentence about what could be improved

Respond ONLY in this exact JSON format:
{{
    "relevance_score": 0.0,
    "completeness_score": 0.0,
    "communication_score": 0.0,
    "technical_score": 0.0,
    "keywords": [],
    "strengths": "",
    "improvement": ""
}}"""

    messages = [
        {"role": "system", "content": "You are an expert interview evaluator. Always respond with valid JSON only."},
        {"role": "user", "content": prompt},
    ]

    response_text = _call_groq_api(messages)
    if not response_text:
        return None

    try:
        # Extract JSON from response
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        data = json.loads(text)

        # Validate and clamp scores
        relevance = max(0.0, min(1.0, float(data.get("relevance_score", 0.5))))
        completeness = max(0.0, min(1.0, float(data.get("completeness_score", 0.5))))
        communication = max(0.0, min(1.0, float(data.get("communication_score", 0.5))))
        technical = max(0.0, min(1.0, float(data.get("technical_score", 0.5))))

        overall = round(
            relevance * 0.30 + completeness * 0.25 + communication * 0.25 + technical * 0.20, 3
        )

        return {
            "relevance_score": round(relevance, 3),
            "completeness_score": round(completeness, 3),
            "communication_score": round(communication, 3),
            "technical_score": round(technical, 3),
            "overall_score": overall,
            "keywords": data.get("keywords", [])[:5],
            "strengths": data.get("strengths", ""),
            "improvement": data.get("improvement", ""),
            "analysis_method": "groq_llm",
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"[NLP] Failed to parse LLM response: {e}")
        return None


def _rule_based_analysis(question: str, answer: str, category: str) -> Dict[str, Any]:
    """Fallback rule-based answer analysis when LLM is unavailable."""
    q_words = set(question.lower().split())
    a_words = answer.lower().split()
    a_word_set = set(a_words)

    # Relevance: word overlap between question and answer
    common = q_words.intersection(a_word_set)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
                  "what", "how", "why", "when", "where", "who", "which", "you", "your",
                  "i", "me", "my", "we", "our", "it", "in", "on", "at", "to", "for",
                  "of", "and", "or", "but", "not", "with", "this", "that", "can", "would"}
    meaningful_common = common - stop_words
    meaningful_q = q_words - stop_words
    relevance = min(len(meaningful_common) / max(len(meaningful_q), 1), 1.0)
    relevance = max(0.3, relevance)  # Floor at 0.3

    # Completeness: based on answer length
    word_count = len(a_words)
    if word_count > 80:
        completeness = 0.9
    elif word_count > 50:
        completeness = 0.75
    elif word_count > 25:
        completeness = 0.6
    elif word_count > 10:
        completeness = 0.4
    else:
        completeness = 0.25

    # Communication: sentence structure
    sentences = [s.strip() for s in answer.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if len(sentences) >= 3:
        communication = 0.75
    elif len(sentences) >= 2:
        communication = 0.6
    else:
        communication = 0.4

    # Avg sentence length check
    if sentences:
        avg_sent_len = word_count / len(sentences)
        if 10 <= avg_sent_len <= 25:
            communication = min(communication + 0.1, 1.0)

    # Technical score: presence of technical-sounding words
    technical_indicators = {"algorithm", "data", "system", "process", "method",
                           "function", "class", "object", "database", "api",
                           "server", "client", "framework", "architecture",
                           "performance", "security", "scalable", "design"}
    tech_overlap = a_word_set.intersection(technical_indicators)
    if category == "technical" or category == "exam":
        technical = min(len(tech_overlap) * 0.15 + 0.3, 1.0)
    else:
        technical = min(len(tech_overlap) * 0.1 + 0.5, 1.0)

    overall = round(
        relevance * 0.30 + completeness * 0.25 + communication * 0.25 + technical * 0.20, 3
    )

    # Extract keywords
    keywords = list(meaningful_common | tech_overlap)[:5]

    return {
        "relevance_score": round(relevance, 3),
        "completeness_score": round(completeness, 3),
        "communication_score": round(communication, 3),
        "technical_score": round(technical, 3),
        "overall_score": overall,
        "keywords": keywords,
        "strengths": "Answer provided on topic." if relevance > 0.5 else "Attempted to address the question.",
        "improvement": "Expand your answer with specific examples and the STAR method." if completeness < 0.7 else "Good depth of answer.",
        "analysis_method": "rule_based",
    }


def _empty_analysis(reason: str) -> Dict[str, Any]:
    """Return an empty analysis result."""
    return {
        "relevance_score": 0.0,
        "completeness_score": 0.0,
        "communication_score": 0.0,
        "technical_score": 0.0,
        "overall_score": 0.0,
        "keywords": [],
        "strengths": "",
        "improvement": reason,
        "analysis_method": "none",
    }
