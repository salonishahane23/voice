"""
Voice Analysis Module — Real AI-powered analysis using Whisper.

Uses OpenAI Whisper for transcription with word-level timestamps,
then analyzes the actual transcript for filler words, fluency,
speaking rate, pauses, and confidence. No hardcoded scores.
"""
import numpy as np
import whisper
import librosa
from pathlib import Path
from typing import Dict, List, Any

# Filler words to detect (with timestamps)
FILLER_WORDS = {
    "uh", "um", "erm", "like", "you know", "actually",
    "basically", "so", "well", "hmm", "right", "okay",
    "i mean", "sort of", "kind of", "you see", "literally",
}

# Cache
_whisper_model = None


def get_whisper_model(model_size: str = "base"):
    """Load and cache the Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        print(f"[VOICE] Loading Whisper model: {model_size}")
        _whisper_model = whisper.load_model(model_size)
    return _whisper_model


def transcribe_audio(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio using Whisper with word-level timestamps.
    Returns the full Whisper result with segments and word timestamps.
    """
    model = get_whisper_model()
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        temperature=0,
    )
    return result


def detect_filler_words_with_timestamps(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect filler words in the transcript with exact timestamps.
    Uses Whisper's word-level timestamps for precision.
    """
    fillers_found = []

    for segment in result.get("segments", []):
        words = segment.get("words", [])
        for i, word_info in enumerate(words):
            word_text = word_info.get("word", "").strip().lower().rstrip(".,!?;:")

            # Single-word fillers
            if word_text in FILLER_WORDS:
                fillers_found.append({
                    "word": word_text,
                    "start": round(word_info["start"], 2),
                    "end": round(word_info["end"], 2),
                    "segment_text": segment["text"].strip(),
                })

            # Two-word fillers (e.g., "you know", "sort of")
            if i < len(words) - 1:
                next_word = words[i + 1].get("word", "").strip().lower().rstrip(".,!?;:")
                two_word = f"{word_text} {next_word}"
                if two_word in FILLER_WORDS:
                    fillers_found.append({
                        "word": two_word,
                        "start": round(word_info["start"], 2),
                        "end": round(words[i + 1]["end"], 2),
                        "segment_text": segment["text"].strip(),
                    })

    return fillers_found


def detect_repetitions(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect word repetitions (stuttering) with timestamps."""
    repetitions = []

    for segment in result.get("segments", []):
        words = segment.get("words", [])
        for i in range(len(words) - 1):
            w1 = words[i].get("word", "").strip().lower().rstrip(".,!?;:")
            w2 = words[i + 1].get("word", "").strip().lower().rstrip(".,!?;:")
            if w1 == w2 and len(w1) > 1:
                repetitions.append({
                    "word": w1,
                    "start": round(words[i]["start"], 2),
                    "end": round(words[i + 1]["end"], 2),
                    "segment_text": segment["text"].strip(),
                })

    return repetitions


def analyze_speaking_rate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate actual speaking rate from Whisper segments."""
    segs = result.get("segments", [])
    if not segs:
        return {"words_per_second": 0.0, "words_per_minute": 0.0,
                "total_words": 0, "total_duration": 0.0, "rating": "no_speech"}

    total_dur = segs[-1]["end"] - segs[0]["start"]
    total_words = sum(len(s["text"].split()) for s in segs)

    if total_dur <= 0:
        return {"words_per_second": 0.0, "words_per_minute": 0.0,
                "total_words": total_words, "total_duration": 0.0, "rating": "no_speech"}

    wps = total_words / total_dur
    wpm = wps * 60

    # Rate natural speech: 120-160 WPM is ideal for interviews
    if wpm < 80:
        rating = "too_slow"
    elif wpm < 120:
        rating = "slightly_slow"
    elif wpm <= 160:
        rating = "ideal"
    elif wpm <= 200:
        rating = "slightly_fast"
    else:
        rating = "too_fast"

    return {
        "words_per_second": round(wps, 2),
        "words_per_minute": round(wpm, 1),
        "total_words": total_words,
        "total_duration": round(total_dur, 2),
        "rating": rating,
    }


def analyze_pauses(result: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze pauses between segments — detects awkward silences."""
    segs = result.get("segments", [])
    if len(segs) < 2:
        return {"pause_count": 0, "avg_pause": 0.0, "max_pause": 0.0,
                "long_pauses": [], "awkward_silence_count": 0}

    pauses = []
    long_pauses = []
    for prev, cur in zip(segs, segs[1:]):
        gap = max(0.0, cur["start"] - prev["end"])
        pauses.append(gap)
        if gap > 2.0:  # pauses > 2 seconds are awkward
            long_pauses.append({
                "start": round(prev["end"], 2),
                "end": round(cur["start"], 2),
                "duration": round(gap, 2),
                "after_text": prev["text"].strip()[-50:],
            })

    return {
        "pause_count": len(pauses),
        "avg_pause": round(float(np.mean(pauses)), 3) if pauses else 0.0,
        "max_pause": round(float(max(pauses)), 3) if pauses else 0.0,
        "long_pauses": long_pauses,
        "awkward_silence_count": len(long_pauses),
    }


def analyze_audio_features(audio_path: str) -> Dict[str, Any]:
    """Analyze raw audio features: pitch variation, energy, volume consistency."""
    y, sr = librosa.load(audio_path, sr=None)

    if len(y) == 0:
        return {"pitch_mean": 0, "pitch_std": 0, "energy_mean": 0,
                "energy_std": 0, "volume_consistency": 0}

    # Pitch analysis
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    pitch_vals = pitches[pitches > 0]
    if len(pitch_vals) > 1000:
        pitch_vals = pitch_vals[:1000]

    pitch_mean = float(pitch_vals.mean()) if len(pitch_vals) > 0 else 0
    pitch_std = float(pitch_vals.std()) if len(pitch_vals) > 0 else 0

    # Energy/volume analysis
    energy = librosa.feature.rms(y=y)[0]
    energy_mean = float(energy.mean())
    energy_std = float(energy.std())

    # Volume consistency: low std relative to mean = more consistent
    volume_consistency = 1.0 - min(energy_std / (energy_mean + 0.001), 1.0)

    return {
        "pitch_mean": round(pitch_mean, 1),
        "pitch_std": round(pitch_std, 1),
        "energy_mean": round(energy_mean, 4),
        "energy_std": round(energy_std, 4),
        "volume_consistency": round(volume_consistency, 3),
    }


def compute_scores(
    result: Dict[str, Any],
    fillers: List[Dict],
    repetitions: List[Dict],
    rate: Dict[str, Any],
    pauses: Dict[str, Any],
    audio_features: Dict[str, Any],
) -> Dict[str, float]:
    """
    Compute voice scores from ACTUAL analysis data. No hardcoding.

    Scores are 0.0 to 1.0 where:
    - 1.0 = perfect delivery
    - 0.0 = very poor delivery
    """
    total_words = rate.get("total_words", 0)
    duration = rate.get("total_duration", 0)

    if total_words == 0 or duration == 0:
        return {
            "fluency_score": 0.0,
            "clarity_score": 0.0,
            "confidence_score": 0.0,
            "note": "No speech detected in audio",
        }

    # --- FLUENCY SCORE ---
    # Based on: filler word ratio, repetition ratio, speaking rate
    filler_ratio = len(fillers) / max(total_words, 1)
    repetition_ratio = len(repetitions) / max(total_words, 1)

    fluency = 1.0
    fluency -= min(filler_ratio * 5.0, 0.5)     # each filler penalizes ~5% of words
    fluency -= min(repetition_ratio * 8.0, 0.3)  # repetitions penalize more
    fluency -= min(pauses["awkward_silence_count"] * 0.08, 0.3)  # penalize long silences

    # Speaking rate penalty
    rate_rating = rate.get("rating", "ideal")
    rate_penalties = {
        "too_slow": 0.15, "slightly_slow": 0.05, "ideal": 0.0,
        "slightly_fast": 0.05, "too_fast": 0.15, "no_speech": 0.5,
    }
    fluency -= rate_penalties.get(rate_rating, 0.0)
    fluency = max(0.0, fluency)

    # --- CLARITY SCORE ---
    # Based on: Whisper confidence (avg_logprob), volume consistency, pitch variety
    segs = result.get("segments", [])
    if segs:
        avg_logprobs = [s.get("avg_logprob", -1.0) for s in segs]
        whisper_conf = np.exp(np.mean(avg_logprobs))  # 0 to 1
    else:
        whisper_conf = 0.0

    volume_consistency = audio_features.get("volume_consistency", 0.5)

    # Good pitch variation (not monotone) — std between 20-80 is good
    pitch_std = audio_features.get("pitch_std", 0)
    if pitch_std < 10:
        pitch_variety = 0.3  # monotone
    elif pitch_std > 150:
        pitch_variety = 0.5  # too erratic
    else:
        pitch_variety = min(pitch_std / 80.0, 1.0)

    clarity = (whisper_conf * 0.4) + (volume_consistency * 0.3) + (pitch_variety * 0.3)
    clarity = max(0.0, min(1.0, clarity))

    # --- CONFIDENCE SCORE ---
    # Based on: speaking rate consistency, few pauses, few fillers, good energy
    avg_pause = pauses.get("avg_pause", 0)
    pause_penalty = min(avg_pause * 0.5, 0.3)

    confidence = 1.0
    confidence -= min(filler_ratio * 4.0, 0.35)
    confidence -= pause_penalty
    confidence -= rate_penalties.get(rate_rating, 0.0)

    # Low energy = low confidence
    if audio_features.get("energy_mean", 0) < 0.01:
        confidence -= 0.2

    confidence = max(0.0, min(1.0, confidence))

    return {
        "fluency_score": round(fluency, 3),
        "clarity_score": round(clarity, 3),
        "confidence_score": round(confidence, 3),
    }


def full_analysis(audio_path: str) -> Dict[str, Any]:
    """
    Complete voice analysis pipeline. All scores derived from actual
    Whisper transcription and librosa audio analysis — nothing hardcoded.

    Returns transcript, filler words with timestamps, and real scores.
    """
    # Step 1: Transcribe with Whisper
    result = transcribe_audio(audio_path)
    transcript = result.get("text", "").strip()

    # Step 2: Detect filler words with timestamps
    fillers = detect_filler_words_with_timestamps(result)

    # Step 3: Detect repetitions/stuttering
    repetitions = detect_repetitions(result)

    # Step 4: Analyze speaking rate
    rate = analyze_speaking_rate(result)

    # Step 5: Analyze pauses
    pauses = analyze_pauses(result)

    # Step 6: Analyze raw audio features
    audio_features = analyze_audio_features(audio_path)

    # Step 7: Compute scores from real data
    scores = compute_scores(result, fillers, repetitions, rate, pauses, audio_features)

    return {
        "transcript": transcript,
        "language": result.get("language", "unknown"),

        # Scores (computed from actual analysis)
        "fluency_score": scores["fluency_score"],
        "clarity_score": scores["clarity_score"],
        "voice_confidence_score": scores["confidence_score"],

        # Detailed analysis with timestamps
        "filler_words": {
            "count": len(fillers),
            "instances": fillers,  # each has word, start, end, segment_text
        },
        "repetitions": {
            "count": len(repetitions),
            "instances": repetitions,
        },
        "speaking_rate": rate,
        "pauses": pauses,
        "audio_features": audio_features,
    }
