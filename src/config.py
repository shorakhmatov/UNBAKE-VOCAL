"""Configuration for Vocal Recognition System."""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TEST_DATA_DIR = BASE_DIR / "test_data"
RESULTS_DIR = BASE_DIR / "results"

# Create directories
for dir_path in [DATA_DIR, TEST_DATA_DIR, RESULTS_DIR]:
    dir_path.mkdir(exist_ok=True)

# Audio settings
AUDIO_SAMPLE_RATE = 16000
AUDIO_FORMAT = "wav"
SUPPORTED_FORMATS = [".m4a", ".mp3", ".wav", ".flac", ".ogg"]

# Model settings
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_WHISPER_MODEL = "large-v3"

# Language support
SUPPORTED_LANGUAGES = ["fr", "it", "ru", "en", "pt", "es", "ja", "pl"]

# Evaluation settings
MAX_CER_THRESHOLD = 0.15  # 15% Character Error Rate
MAX_WER_THRESHOLD = 0.25  # 25% Word Error Rate
MAX_TIMESTAMP_ERROR_MS = 500  # 500ms max deviation

# Cost constraints (from requirements)
MAX_COST_PER_3MIN_USD = 0.05
TARGET_COST_PER_3MIN_USD = 0.03

# Performance targets
TARGET_LATENCY_SECONDS = 30  # For 3-minute track
MAX_LATENCY_SECONDS = 60

# Batch processing
BATCH_SIZE = 1  # For now, single file processing
