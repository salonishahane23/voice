"""
Facial & Gesture Analysis FastAPI Service.

Standalone microservice that accepts video files and returns facial analysis
results including emotions, engagement, and confidence. Runs on port 8003.
"""
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analyzer import full_analysis

app = FastAPI(
    title="Facial Analysis Service",
    description="AI-powered facial expression and gesture analysis",
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
    return {"service": "Facial Analysis", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_video(video: UploadFile = File(...)):
    """
    Analyze facial expressions and gestures in an uploaded video.

    Accepts: video file (webm, mp4, avi, mkv)
    Returns: Confidence, engagement, emotion, and stability scores.
    """
    allowed_extensions = {".webm", ".mp4", ".avi", ".mkv", ".mov"}
    ext = os.path.splitext(video.filename or "video.webm")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: {ext}. Allowed: {allowed_extensions}",
        )

    suffix = ext if ext else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await video.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = full_analysis(tmp_path)
        return {"status": "success", "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
