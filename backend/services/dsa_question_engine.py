"""DSA question generator — uses a dedicated API key to generate DSA problems via LLM."""
import json
import os
import time
from pathlib import Path
from typing import List, Optional

import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DSA_API_KEY = os.getenv("DSA_API_KEY", "")
DSA_MODEL = os.getenv("DSA_MODEL", "openai/gpt-oss-120b")
DSA_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_dsa_questions(
    count: int = 3,
    difficulty: Optional[str] = None,
) -> List[dict]:
    """
    Generate DSA problems dynamically via LLM.
    Raises RuntimeError if API is unavailable — no fallback/seed.
    """
    if not DSA_API_KEY:
        raise RuntimeError(
            "DSA_API_KEY is not set in .env. "
            "Please add your API key to use the DSA round."
        )

    difficulty_instruction = ""
    if difficulty and difficulty in ("easy", "medium", "hard"):
        difficulty_instruction = f"All questions should be {difficulty} difficulty."
    else:
        difficulty_instruction = (
            f"Include a mix of difficulties: "
            f"1 easy, {max(1, count - 2)} medium, and 1 hard question."
        )

    prompt = f"""Generate exactly {count} unique Data Structures & Algorithms (DSA) problems.

Cover DIFFERENT topics from this list (do not repeat topics): arrays, linked lists, trees, graphs, dynamic programming, string manipulation, hash maps, stacks/queues, sorting/searching, greedy algorithms, binary search, two pointers, sliding window, recursion/backtracking.

{difficulty_instruction}

Each problem should be a realistic interview-level DSA question. Include:
- A clear problem statement with input/output format
- 1-2 examples with input and expected output
- Constraints (e.g., array size, value ranges)
- The expected optimal time complexity

Respond ONLY with a JSON array. Each item must have:
- "title": short problem title (e.g. "Two Sum", "Merge Intervals")
- "description": full problem statement including examples and constraints (use newlines for formatting)
- "difficulty": "easy", "medium", or "hard"
- "topic": the main DSA topic (e.g. "arrays", "dynamic programming")
- "hints": one brief hint for the approach (max 20 words)
- "expected_complexity": expected optimal time complexity (e.g. "O(n)", "O(n log n)")

JSON array only, no other text:"""

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
                    "You are an expert DSA interview question designer. "
                    "Generate challenging, well-formatted coding problems. "
                    "Respond with valid JSON arrays only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.85,
        "max_tokens": 4096,
    }

    max_retries = 3
    base_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            response = httpx.post(DSA_API_URL, json=payload, headers=headers, timeout=45)
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"].strip()

            # Clean markdown fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            questions = json.loads(text)
            if not isinstance(questions, list) or len(questions) == 0:
                raise RuntimeError("LLM returned an empty or invalid question list.")

            print(f"[DSA] Generated {len(questions)} DSA questions via LLM")
            return [
                {
                    "title": q.get("title", "Untitled"),
                    "description": q.get("description", ""),
                    "difficulty": q.get("difficulty", "medium"),
                    "topic": q.get("topic", "general"),
                    "hints": q.get("hints", ""),
                    "expected_complexity": q.get("expected_complexity", ""),
                }
                for q in questions
                if q.get("title") and q.get("description")
            ]

        except httpx.HTTPStatusError as e:
            retryable = e.response.status_code in (429, 502, 503, 504)
            if retryable and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[DSA] API returned {e.response.status_code}, retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            raise RuntimeError(f"DSA API request failed (HTTP {e.response.status_code}): {e.response.text}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse DSA questions from LLM response: {e}")
        except httpx.RequestError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[DSA] Connection error, retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            raise RuntimeError(f"DSA API connection error: {e}")
