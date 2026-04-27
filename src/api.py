"""FastAPI implementation for Vocal Recognition API."""

import os
import tempfile
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn

from src.config import SUPPORTED_LANGUAGES
from src.audio_processor import download_from_s3_url
from src.recognizers import get_recognizer, RecognitionResult


app = FastAPI(
    title="Unbake Vocal Recognition API",
    description="API для распознавания текста песни с таймстемпами",
    version="1.0.0"
)

# Initialize components
recognizer = None  # Lazy load


def get_recognizer_instance():
    """Lazy initialization of recognizer."""
    global recognizer
    if recognizer is None:
        recognizer = get_recognizer("faster-whisper", "large-v3", "auto")
        recognizer.load_model()
    return recognizer


# Request/Response models
class TranscribeRequest(BaseModel):
    audio_url: str = Field(..., description="S3 presigned URL to vocal audio file")
    language: str = Field(default="auto", description="Language code or 'auto' for detection")
    options: Optional[dict] = Field(default=None, description="Additional options")


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    confidence: Optional[float] = None


class TranscribeResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool


def format_lrclib(result: RecognitionResult) -> str:
    """Format result in lrclib.net format."""
    lines = []
    current_line = []
    current_start = None
    
    for word in result.words:
        if current_start is None:
            current_start = word.start
        
        current_line.append(word.word)
        
        # End line on punctuation or length
        if word.word.endswith((".", "!", "?", ",")) or len(current_line) > 8:
            minutes = int(current_start // 60)
            seconds = current_start % 60
            timestamp = f"[{minutes:02d}:{seconds:05.2f}]"
            lines.append(f"{timestamp} {' '.join(current_line)}")
            current_line = []
            current_start = None
    
    # Remaining words
    if current_line:
        minutes = int(current_start // 60)
        seconds = current_start % 60
        timestamp = f"[{minutes:02d}:{seconds:05.2f}]"
        lines.append(f"{timestamp} {' '.join(current_line)}")
    
    return "\n".join(lines)


def validate_language(language: str) -> Optional[str]:
    """Validate language code."""
    if language == "auto":
        return None
    if language in SUPPORTED_LANGUAGES:
        return language
    return None


@app.post("/api/v1/transcribe", response_model=TranscribeResponse)
async def transcribe(request: TranscribeRequest, background_tasks: BackgroundTasks):
    """
    Transcribe vocal audio and return lyrics with timestamps.
    
    - **audio_url**: S3 presigned URL to m4a vocal file (Demucs v4 output)
    - **language**: Language code (en, ru, fr, etc.) or 'auto'
    - **options**: Additional options (word_timestamps, format)
    
    Returns synced lyrics in lrclib.net format with word-level timestamps.
    """
    start_time = time.time()
    temp_file = None
    
    try:
        # Validate language
        lang = validate_language(request.language)
        if request.language != "auto" and lang is None:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    code="LANGUAGE_NOT_SUPPORTED",
                    message=f"Language '{request.language}' not supported. Use: {', '.join(SUPPORTED_LANGUAGES)}",
                    retryable=False
                ).dict()
            )
        
        # Download audio
        temp_file = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        success = download_from_s3_url(request.audio_url, temp_path)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    code="DOWNLOAD_FAILED",
                    message="Failed to download audio from provided URL. Check if URL is valid and not expired.",
                    retryable=True
                ).dict()
            )
        
        # Get recognizer
        rec = get_recognizer_instance()
        
        # Transcribe
        result = rec.transcribe(temp_path, language=lang)
        
        # Format output
        synced_lyrics = format_lrclib(result)
        
        # Calculate quality score (simplified)
        quality_score = 0.95  # TODO: implement actual calculation
        
        processing_time = time.time() - start_time
        
        response_data = {
            "text": result.text,
            "language": result.language,
            "duration": result.duration,
            "synced_lyrics": synced_lyrics,
            "words": [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "confidence": w.confidence
                }
                for w in result.words
            ],
            "processing_time": processing_time,
            "quality_score": quality_score
        }
        
        # Cleanup
        background_tasks.add_task(os.unlink, temp_path)
        
        return TranscribeResponse(success=True, data=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on error
        if temp_file:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code="INTERNAL_ERROR",
                message=f"Processing failed: {str(e)}",
                retryable=True
            ).dict()
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": recognizer is not None,
        "supported_languages": SUPPORTED_LANGUAGES
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Unbake Vocal Recognition API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "transcribe": "/api/v1/transcribe",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
