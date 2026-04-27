"""Audio processing utilities for vocal tracks."""

from pathlib import Path
from typing import Tuple

import librosa
import numpy as np
import soundfile as sf
from pydub import AudioSegment
import requests

from config import AUDIO_SAMPLE_RATE, SUPPORTED_FORMATS


class AudioProcessor:
    """Process audio files for STT models."""
    
    def __init__(self, target_sample_rate: int = AUDIO_SAMPLE_RATE):
        self.target_sample_rate = target_sample_rate
    
    def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        """
        Load audio file and convert to target sample rate.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (audio_array, sample_rate)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        # Convert m4a to wav if needed
        if file_path.suffix.lower() == ".m4a":
            file_path = self._convert_m4a_to_wav(file_path)
        
        # Load audio with librosa
        audio, sr = librosa.load(
            str(file_path),
            sr=self.target_sample_rate,
            mono=True
        )
        
        return audio, sr
    
    def _convert_m4a_to_wav(self, m4a_path: Path) -> Path:
        """Convert m4a to wav format."""
        wav_path = m4a_path.with_suffix(".wav")
        
        if wav_path.exists():
            return wav_path
        
        audio = AudioSegment.from_file(str(m4a_path), format="m4a")
        audio.export(str(wav_path), format="wav")
        
        return wav_path
    
    def get_duration(self, file_path: str) -> float:
        """Get audio duration in seconds."""
        audio, sr = self.load_audio(file_path)
        return len(audio) / sr
    
    def preprocess_for_stt(self, audio: np.ndarray) -> np.ndarray:
        """
        Preprocess audio for STT models.
        Normalizes audio and applies light noise reduction.
        """
        # Normalize
        audio = audio / (np.max(np.abs(audio)) + 1e-8)
        
        # Trim silence
        audio, _ = librosa.effects.trim(audio, top_db=20)
        
        return audio
    
    def chunk_audio(self, audio: np.ndarray, chunk_duration: float = 30.0) -> list:
        """
        Split audio into chunks for processing.
        
        Args:
            audio: Audio array
            chunk_duration: Chunk duration in seconds
            
        Returns:
            List of audio chunks
        """
        chunk_samples = int(chunk_duration * self.target_sample_rate)
        chunks = []
        
        for i in range(0, len(audio), chunk_samples):
            chunk = audio[i:i + chunk_samples]
            if len(chunk) > self.target_sample_rate:  # At least 1 second
                chunks.append(chunk)
        
        return chunks


def download_from_s3_url(presigned_url: str, output_path: str) -> bool:
    """Download file from S3 presigned URL."""
    try:
        response = requests.get(presigned_url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"Error downloading from S3: {e}")
        return False
