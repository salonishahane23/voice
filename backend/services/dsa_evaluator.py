"""DSA approach evaluator — uses a dedicated API key to evaluate user approaches via LLM."""
import json
import os
from pathlib import Path
from typing import Dict

import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DSA_API_KEY = os.getenv("DSA_API_KEY", "")
DSA_MODEL = os.getenv("DSA_MODEL", "openai/gpt-oss-120b")
DSA_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Score weights
WEIGHTS = {
    "correctness": 0.30,
    "time_complexity": 0.25,
    "space_complexity": 0.15,
    "edge_cases": 0.15,
    "clarity": 0.15,
}


def evaluate_approach(
    problem_title: str,
    problem_description: str,
    user_approach: str,
    expected_complexity: str = "",
) -> Dict:
    """
    Evaluate the user's approach + pseudocode for a DSA problem.
    Returns a dict with individual scores, overall score, and feedback.
    Raises RuntimeError if API is unavailable.
    """
    if not DSA_API_KEY:
        raise RuntimeError(
            "DSA_API_KEY is not set. Cannot evaluate approach."
        )

    if not user_approach or not user_approach.strip():
        return {
            "score_correctness": 0.0,
            "score_time_complexity": 0.0,
            "score_space_complexity": 0.0,
            "score_edge_cases": 0.0,
            "score_clarity": 0.0,
            "overall_score": 0.0,
            "feedback": "No approach was submitted.",
            "optimal_approach": "",
            "time_complexity_analysis": "",
        }

    prompt = f"""You are an expert DSA interviewer evaluating a candidate's approach to a coding problem.

## Problem
**Title:** {problem_title}
**Description:**
{problem_description}

**Expected optimal complexity:** {expected_complexity}

## Candidate's Approach & Pseudocode
{user_approach}

## Evaluation Instructions
Evaluate the candidate's approach (NOT code — they are writing their thought process and pseudocode). Score each dimension from 0 to 100:

1. **correctness** (weight: 30%) — Does this approach correctly solve the problem? Would it produce the right output for all valid inputs?
2. **time_complexity** (weight: 25%) — Is the time complexity optimal or near-optimal? Compare to the expected complexity.
3. **space_complexity** (weight: 15%) — Is the space usage reasonable? Does it avoid unnecessary extra space?
4. **edge_cases** (weight: 15%) — Does the candidate mention or handle edge cases (empty input, single element, large input, duplicates, negatives, etc.)?
5. **clarity** (weight: 15%) — Is the approach clearly explained? Is the pseudocode understandable and well-structured?

Also provide:
- **feedback**: A detailed paragraph explaining what the candidate did well and what they missed. Be constructive and specific.
- **optimal_approach**: A brief (2-4 sentence) description of the ideal/optimal approach for this problem.
- **time_complexity_analysis**: What you think the time and space complexity of the candidate's approach is (e.g. "Time: O(n), Space: O(1)").

Respond ONLY with a JSON object:
{{
  "correctness": <0-100>,
  "time_complexity": <0-100>,
  "space_complexity": <0-100>,
  "edge_cases": <0-100>,
  "clarity": <0-100>,
  "feedback": "<detailed feedback string>",
  "optimal_approach": "<brief optimal approach>",
  "time_complexity_analysis": "<e.g. Time: O(n), Space: O(n)>"
}}

JSON only, no other text:"""

    headers = {
        "Authorization": f"Bearer {DSA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DSA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior software engineer and DSA expert. "
                    "Evaluate approaches fairly and provide constructive feedback. "
                    "Respond with valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    try:
        response = httpx.post(DSA_API_URL, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()

        # Clean markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        result = json.loads(text)

        # Extract individual scores
        scores = {
            "score_correctness": float(result.get("correctness", 0)),
            "score_time_complexity": float(result.get("time_complexity", 0)),
            "score_space_complexity": float(result.get("space_complexity", 0)),
            "score_edge_cases": float(result.get("edge_cases", 0)),
            "score_clarity": float(result.get("clarity", 0)),
        }

        # Calculate weighted overall score
        overall = (
            scores["score_correctness"] * WEIGHTS["correctness"]
            + scores["score_time_complexity"] * WEIGHTS["time_complexity"]
            + scores["score_space_complexity"] * WEIGHTS["space_complexity"]
            + scores["score_edge_cases"] * WEIGHTS["edge_cases"]
            + scores["score_clarity"] * WEIGHTS["clarity"]
        )
        scores["overall_score"] = round(overall, 1)

        # Add text feedback
        scores["feedback"] = result.get("feedback", "")
        scores["optimal_approach"] = result.get("optimal_approach", "")
        scores["time_complexity_analysis"] = result.get("time_complexity_analysis", "")

        print(f"[DSA] Evaluated approach for '{problem_title}' — score: {scores['overall_score']}")
        return scores

    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"DSA evaluation API failed (HTTP {e.response.status_code}): {e.response.text}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse evaluation from LLM response: {e}")
    except httpx.RequestError as e:
        raise RuntimeError(f"DSA evaluation API connection error: {e}")
