# Unbake Vocal Recognition API

## Тестовое задание - Team Lead

Решение для API распознавания текста песни с синхронизацией по времени (таймстемпами) из вокала.

## TL;DR / Резюме

**Выбранное решение:** Self-hosted Faster-Whisper (large-v3) на AWS g4dn.xlarge
- **Cost:** $0.0026 за 3 минуты трека (6x ниже бюджета $0.05)
- **Accuracy:** WER ~8-12% на чистом вокале, CER ~4-6%
- **Latency:** 20-40 секунд на 3-минутный трек
- **Word-level timestamps:** Да, ±200ms
- **Языки:** FR, IT, RU, EN, PT, ES, JP, PL

## Структура проекта

```
unbake-vocal-recognition/
├── src/
│   ├── api.py                    # FastAPI implementation
│   ├── config.py                 # Configuration
│   ├── audio_processor.py        # Audio loading & preprocessing
│   ├── recognizers.py            # STT models (Whisper variants)
│   ├── evaluator.py              # Evaluation metrics (WER/CER)
│   ├── evaluate.py               # Main evaluation script
│   └── download_test_data.py     # Test data downloader
├── docs/
│   └── API_DESIGN.md             # Full design document
├── data/                         # Runtime data
├── test_data/                    # Test dataset
├── results/                      # Evaluation results
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image
├── docker-compose.yml            # Docker Compose setup
└── README.md                     # This file
```

## Быстрый старт

### 1. Установка зависимостей

```bash
# Clone/navigate to project
cd unbake-vocal-recognition

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Скачать тестовые данные

```bash
python src/download_test_data.py
```

Или вручную скачать с [Yandex Disk](https://disk.yandex.com/d/aGtcKCVEnii2bw) в папку `test_data/`.

### 3. Запустить тестирование

```bash
# Сравнить все модели
python src/evaluate.py --compare

# Или протестировать конкретную модель
python src/evaluate.py --recognizer faster-whisper --model large-v3
```

### 4. Запустить API сервер

```bash
# Development
python src/api.py

# Production (with Docker)
docker-compose up -d
```

API будет доступно на `http://localhost:8000`

## Использование API

### Request

```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://bucket.s3.amazonaws.com/vocals/song.m4a?X-Amz-Signature=...",
    "language": "auto",
    "options": {"word_timestamps": true}
  }'
```

### Response

```json
{
  "success": true,
  "data": {
    "text": "Hello darkness my old friend",
    "language": "en",
    "duration": 180.5,
    "synced_lyrics": "[00:12.34] Hello\\n[00:13.45] darkness...",
    "words": [
      {"word": "Hello", "start": 12.34, "end": 13.45, "confidence": 0.95}
    ],
    "processing_time": 18.2,
    "quality_score": 0.92
  }
}
```

## Основные документы

| Документ | Описание |
|----------|----------|
| `docs/API_DESIGN.md` | Полный design document с альтернативами, расчетами стоимости, рисками |
| `src/evaluate.py` | Код для оценки разных STT моделей |
| `src/recognizers.py` | Реализация различных recognizers (faster-whisper, whisper-timestamped) |
| `src/evaluator.py` | Метрики оценки: WER, CER, timestamp accuracy |

## Архитектура решения

### STT Models (рассмотренные и выбранные)

| Model | WER | RTF | Cost/3min | Verdict |
|-------|-----|-----|-----------|---------|
| **faster-whisper** | ~10% | 0.1x | $0.0026 | ✅ **ВЫБРАН** |
| whisper-timestamped | ~10% | 0.15x | $0.004 | ⚠️ Fallback |
| Whisper API (OpenAI) | ~9% | - | $0.18 | ❌ Дорого |
| Google STT | ~15% | - | $0.72 | ❌ Дорого + плохо с музыкой |

### Железо

**AWS g4dn.xlarge** (рекомендуется):
- GPU: NVIDIA T4 (16GB)
- Цена: $0.526/час (ondemand) / $0.15/час (spot)
- Стоимость за 3-мин трек: $0.0026
- Месячная стоимость (100 req/day): ~$8

**Alternative:** RunPod/Vast.ai RTX 3090 ~$0.20-0.30/час

## Метрики качества

### Текстовые метрики
- **CER** (Character Error Rate): < 15%
- **WER** (Word Error Rate): < 25%
- **Precision/Recall**: на уровне слов

### Timestamp метрики
- **MAE** (Mean Absolute Error): < 200ms
- **% within threshold**: 80% слов в ±200ms

## Автоматическая оценка

```python
from src.evaluator import RecognitionEvaluator
from src.recognizers import RecognitionResult

evaluator = RecognitionEvaluator()
metrics = evaluator.evaluate(
    result=recognition_result,
    ground_truth_text="actual lyrics here"
)

print(f"WER: {metrics.wer:.2%}")
print(f"CER: {metrics.cer:.2%}")
print(f"Passed: {metrics.overall_passed}")
```

## Требования

### Minimum
- Python 3.9+
- 8GB RAM
- 10GB disk space
- CPU (slower, RTF ~0.5x)

### Recommended
- Python 3.10+
- NVIDIA GPU (T4/RTX 3090/4090)
- 16GB RAM
- CUDA 11.8+
- 20GB disk space (models)

## Troubleshooting

### GPU not detected
```bash
# Check CUDA
nvidia-smi

# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Model download fails
```bash
# Pre-download models
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3')"
```

### Audio loading errors
```bash
# Ensure ffmpeg is installed
ffmpeg -version

# On Ubuntu/Debian
sudo apt-get install ffmpeg

# On macOS
brew install ffmpeg
```

## Оценка результатов

После запуска `evaluate.py` результаты сохраняются в `results/`:

```
results/
├── comparison_results.json       # Сравнение всех моделей
├── faster-whisper_large-v3_results.json  # Детали по модели
└── evaluation_report.md          # Summary report
```

## Вклад решения

### Ключевые trade-offs

1. **Accuracy vs Cost**: Выбрали large-v3 вместо small/base — точность критичнее
2. **Speed vs Precision**: faster-whisper дает 4x скорость без потери точности
3. **Self-hosted vs API**: Self-hosted дешевле в 19x чем Whisper API
4. **GPU vs CPU**: GPU необходим для production latency

### Что учтено из рисков

- Demucs артефакты: pre-processing + fallback модели
- Мультивокал: out of scope (demucs 4-stem как будущее решение)
- Языковые смешения: auto-detection + force language parameter
- Длинные треки: chunk processing с оверлапом



