"""
Voice Analysis FastAPI Service.

Standalone microservice that accepts audio files and returns voice analysis results.
Runs on port 8001.
"""
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analyzer import full_analysis

app = FastAPI(
    title="Voice Analysis Service",
    description="AI-powered voice analysis for the Interview Coach platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "Voice Analysis", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_audio(audio: UploadFile = File(...)):
    """
    Analyze an uploaded audio file.

    Accepts: audio file (wav, webm, mp3, m4a, ogg)
    Returns: Full voice analysis including transcript, confidence,
             speaking rate, filler words, and per-segment details.
    """
    # Validate file type
    allowed_extensions = {".wav", ".webm", ".mp3", ".m4a", ".ogg", ".flac"}
    ext = os.path.splitext(audio.filename or "audio.wav")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {ext}. Allowed: {allowed_extensions}",
        )

    # Save to temp file
    suffix = ext if ext else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Run full analysis
        result = full_analysis(tmp_path)
        return {
            "status": "success",
            "analysis": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
