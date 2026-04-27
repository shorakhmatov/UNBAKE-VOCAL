"""Speech-to-Text recognizers comparison."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import torch

from src.config import DEFAULT_WHISPER_MODEL, SUPPORTED_LANGUAGES


@dataclass
class WordTimestamp:
    """Single word with timestamp."""
    word: str
    start: float  # seconds
    end: float    # seconds
    confidence: Optional[float] = None


@dataclass
class RecognitionResult:
    """Result of speech recognition."""
    text: str
    words: List[WordTimestamp]
    language: str
    duration: float
    processing_time: float
    model_name: str
    raw_output: Any = None


class BaseRecognizer(ABC):
    """Base class for STT recognizers."""
    
    def __init__(self, model_name: str, device: str = "auto"):
        self.model_name = model_name
        self.device = self._get_device(device)
        self.model = None
    
    def _get_device(self, device: str) -> str:
        """Determine compute device."""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device
    
    @abstractmethod
    def load_model(self):
        """Load the model."""
        pass
    
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> RecognitionResult:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en', 'ru')
            
        Returns:
            RecognitionResult with text and timestamps
        """
        pass
    
    def format_lrclib(self, result: RecognitionResult) -> List[Dict]:
        """
        Format result in lrclib.net format.
        
        Returns list of lines with timestamps:
        [mm:ss.xx] Text line
        """
        lines = []
        current_line = []
        current_line_start = None
        
        for word in result.words:
            if current_line_start is None:
                current_line_start = word.start
            
            current_line.append(word.word)
            
            # Check if we should end this line (rough heuristic)
            if word.word.endswith((".", "!", "?", ",")) or len(current_line) > 8:
                line_text = " ".join(current_line)
                minutes = int(current_line_start // 60)
                seconds = current_line_start % 60
                timestamp = f"[{minutes:02d}:{seconds:05.2f}]"
                lines.append({
                    "timestamp": timestamp,
                    "start": current_line_start,
                    "text": line_text,
                    "words": current_line
                })
                current_line = []
                current_line_start = None
        
        # Add remaining words
        if current_line:
            line_text = " ".join(current_line)
            minutes = int(current_line_start // 60)
            seconds = current_line_start % 60
            timestamp = f"[{minutes:02d}:{seconds:05.2f}]"
            lines.append({
                "timestamp": timestamp,
                "start": current_line_start,
                "text": line_text,
                "words": current_line
            })
        
        return lines


class WhisperRecognizer(BaseRecognizer):
    """OpenAI Whisper implementation."""
    
    def __init__(self, model_size: str = DEFAULT_WHISPER_MODEL, device: str = "auto"):
        super().__init__(f"whisper-{model_size}", device)
        self.model_size = model_size
    
    def load_model(self):
        """Load Whisper model."""
        import whisper
        
        print(f"Loading Whisper model: {self.model_size} on {self.device}")
        self.model = whisper.load_model(self.model_size).to(self.device)
    
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> RecognitionResult:
        """Transcribe with Whisper."""
        import whisper
        
        if self.model is None:
            self.load_model()
        
        start_time = time.time()
        
        # Load audio
        audio = whisper.load_audio(audio_path)
        duration = len(audio) / 16000
        
        # Transcribe
        options = {
            "language": language,
            "task": "transcribe",
            "word_timestamps": True,
        }
        
        result = self.model.transcribe(audio, **options)
        
        # Extract word timestamps
        words = []
        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                words.append(WordTimestamp(
                    word=word_info["word"].strip(),
                    start=word_info["start"],
                    end=word_info["end"],
                    confidence=None  # Whisper doesn't provide word confidence
                ))
        
        processing_time = time.time() - start_time
        
        return RecognitionResult(
            text=result["text"].strip(),
            words=words,
            language=result.get("language", language or "unknown"),
            duration=duration,
            processing_time=processing_time,
            model_name=self.model_name,
            raw_output=result
        )


class FasterWhisperRecognizer(BaseRecognizer):
    """Faster Whisper implementation (CTranslate2)."""
    
    def __init__(self, model_size: str = "large-v3", device: str = "auto", 
                 compute_type: str = "float16"):
        super().__init__(f"faster-whisper-{model_size}", device)
        self.model_size = model_size
        self.compute_type = compute_type if device != "cpu" else "int8"
    
    def load_model(self):
        """Load Faster Whisper model."""
        from faster_whisper import WhisperModel
        
        print(f"Loading Faster Whisper: {self.model_size} on {self.device}")
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type
        )
    
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> RecognitionResult:
        """Transcribe with Faster Whisper."""
        from faster_whisper import WhisperModel
        
        if self.model is None:
            self.load_model()
        
        start_time = time.time()
        
        # Transcribe
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            beam_size=5,
            best_of=5,
            condition_on_previous_text=True
        )
        
        # Collect results
        words = []
        full_text_parts = []
        
        for segment in segments:
            full_text_parts.append(segment.text)
            if segment.words:
                for word in segment.words:
                    words.append(WordTimestamp(
                        word=word.word.strip(),
                        start=word.start,
                        end=word.end,
                        confidence=getattr(word, 'probability', None)
                    ))
        
        # Get duration
        import librosa
        duration = librosa.get_duration(path=audio_path)
        
        processing_time = time.time() - start_time
        
        return RecognitionResult(
            text=" ".join(full_text_parts).strip(),
            words=words,
            language=info.language,
            duration=duration,
            processing_time=processing_time,
            model_name=self.model_name,
            raw_output=None
        )


class WhisperTimestampedRecognizer(BaseRecognizer):
    """Whisper with precise word-level timestamps."""
    
    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        super().__init__(f"whisper-timestamped-{model_size}", device)
        self.model_size = model_size
    
    def load_model(self):
        """Load whisper-timestamped model."""
        import whisper_timestamped
        
        print(f"Loading whisper-timestamped: {self.model_size}")
        self.model = whisper_timestamped.load_model(self.model_size, device=self.device)
    
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> RecognitionResult:
        """Transcribe with precise timestamps."""
        import whisper_timestamped
        
        if self.model is None:
            self.load_model()
        
        start_time = time.time()
        
        # Transcribe with word timestamps
        result = whisper_timestamped.transcribe_timestamped(
            self.model,
            audio_path,
            language=language,
            verbose=False
        )
        
        # Extract word timestamps
        words = []
        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                words.append(WordTimestamp(
                    word=word_info["text"].strip(),
                    start=word_info["start"],
                    end=word_info["end"],
                    confidence=word_info.get("confidence")
                ))
        
        # Get duration
        import librosa
        duration = librosa.get_duration(path=audio_path)
        
        processing_time = time.time() - start_time
        
        return RecognitionResult(
            text=result["text"].strip(),
            words=words,
            language=result.get("language", language or "unknown"),
            duration=duration,
            processing_time=processing_time,
            model_name=self.model_name,
            raw_output=result
        )


class WhisperXRecognizer(BaseRecognizer):
    """WhisperX with forced alignment for precise timestamps."""
    
    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        super().__init__(f"whisperx-{model_size}", device)
        self.model_size = model_size
        self.align_model = None
    
    def load_model(self):
        """Load WhisperX model."""
        import whisperx
        
        print(f"Loading WhisperX: {self.model_size} on {self.device}")
        self.model = whisperx.load_model(
            self.model_size,
            self.device,
            compute_type="float16" if self.device == "cuda" else "int8"
        )
    
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> RecognitionResult:
        """Transcribe with WhisperX forced alignment."""
        import whisperx
        import torch
        
        if self.model is None:
            self.load_model()
        
        start_time = time.time()
        
        # Load audio
        audio = whisperx.load_audio(audio_path)
        duration = len(audio) / 16000
        
        # 1. Transcribe with Whisper
        result = self.model.transcribe(audio, language=language)
        detected_language = result.get("language", language or "en")
        
        # 2. Load alignment model
        if self.align_model is None:
            self.align_model, self.align_metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=self.device
            )
        
        # 3. Align for word-level timestamps
        result_aligned = whisperx.align(
            result["segments"],
            self.align_model,
            self.align_metadata,
            audio,
            self.device
        )
        
        # Extract word timestamps
        words = []
        for segment in result_aligned.get("segments", []):
            for word_info in segment.get("words", []):
                words.append(WordTimestamp(
                    word=word_info.get("word", "").strip(),
                    start=word_info.get("start", 0),
                    end=word_info.get("end", 0),
                    confidence=word_info.get("score")
                ))
        
        processing_time = time.time() - start_time
        
        return RecognitionResult(
            text=" ".join([s["text"] for s in result_aligned["segments"]]).strip(),
            words=words,
            language=detected_language,
            duration=duration,
            processing_time=processing_time,
            model_name=self.model_name,
            raw_output=result_aligned
        )


def get_recognizer(recognizer_type: str, model_size: str = "large-v3", 
                   device: str = "auto") -> BaseRecognizer:
    """
    Factory function to get recognizer by type.
    
    Args:
        recognizer_type: One of "whisper", "faster-whisper", "whisper-timestamped", "whisperx"
        model_size: Model size (tiny, base, small, medium, large-v3)
        device: Device to use (cuda, cpu, auto)
        
    Returns:
        BaseRecognizer instance
    """
    recognizers = {
        "whisper": WhisperRecognizer,
        "faster-whisper": FasterWhisperRecognizer,
        "whisper-timestamped": WhisperTimestampedRecognizer,
        "whisperx": WhisperXRecognizer,
    }
    
    if recognizer_type not in recognizers:
        raise ValueError(f"Unknown recognizer: {recognizer_type}. Available: {list(recognizers.keys())}")
    
    return recognizers[recognizer_type](model_size=model_size, device=device)
