# Unbake Vocal Recognition API - Design Document

**Team Lead Proposal** | Version 1.0 | 2024

---

## TL;DR

**Выбранное решение:** Self-hosted Faster-Whisper (large-v3) на AWS g4dn.xlarge
- **Cost:** $0.008 за 3 минуты трека (6x ниже бюджета)
- **Accuracy:** WER ~8-12% на чистом вокале, CER ~4-6%
- **Latency:** 20-40 секунд на 3-минутный трек
- **Word-level timestamps:** Да, ±200ms

---

## 1. Постановка задачи

API принимает S3 presigned URL на вокал (m4a, 256kbps, вырезанный Demucs v4) и возвращает текст песни с таймстемпами по словам.

### Входные данные
- Формат: m4a (AAC 256kbps)
- Источник: Demucs v4 (htdemucs_ft не используется)
- Длина: 1-5 минут (в среднем 3 минуты)
- Языки: FR, IT, RU, EN, PT, ES, JP, PL
- Артефакты: Нет (Demucs оставляет артефакты на границах слов)

### Выходные данные
Формат lrclib.net - JSON с word-level timestamps:
```json
{
  "syncedLyrics": "[00:12.34] Hello\\n[00:13.45] darkness\\n[00:14.56] my",
  "plainLyrics": "Hello darkness my old friend",
  "language": "en",
  "words": [
    {"word": "Hello", "start": 12.34, "end": 13.45},
    {"word": "darkness", "start": 13.45, "end": 14.56}
  ]
}
```

---

## 2. Alternatives Considered

### 2.1 OpenAI Whisper API (Cloud)

**Плюсы:**
- Zero infrastructure
- Мгновенный запуск
- Не нужно думать о железе

**Минусы:**
- **Цена:** $0.006/min = $0.18 за 3 минуты (3.6x OVER BUDGET)
- Нет word-level timestamps (только segment-level)
- Privacy: данные уходят на сервера OpenAI
- Rate limits: 100 req/min на начальном тарифе
- Dependency: внешний сервис

**Verdict:** ❌ Не подходит по цене

---

### 2.2 Google Speech-to-Text API

**Плюсы:**
- Word timestamps есть
- Мультиязычность

**Минусы:**
- **Цена:** $0.024/min = $0.72 за 3 минуты (14x OVER BUDGET)
- Плохо с музыкой (обучен на речь, не пение)
- Нет поддержки некоторых языков

**Verdict:** ❌ Слишком дорого + плохая точность на музыке

---

### 2.3 AssemblyAI / Deepgram

**Плюсы:**
- Хорошие word timestamps
- Специализированные модели

**Минусы:**
- **Цена:** $0.012-0.043/min = $0.36-1.29 за 3 минуты
- AssemblyAI: $0.00025/sec = $0.045 за 3 минуты (почти в бюджет)
- Но: нет free tier для тестирования, vendor lock-in

**Verdict:** ⚠️ AssemblyAI близко по цене, но self-hosted дешевле

---

### 2.4 Self-Hosted Whisper (OpenAI)

**Плюсы:**
- Контроль
- Privacy
- Цена только на железо

**Минусы:**
- Медленнее (RTF ~0.5x на CPU)
- Нужно GPU для production speed

**Verdict:** ✅ Базовый вариант

---

### 2.5 Faster-Whisper (CTranslate2)

**Плюсы:**
- **4x быстрее** чем оригинальный Whisper
- Та же точность
- Меньше памяти
- Поддержка quantization (int8/float16)

**Минусы:**
- Немного сложнее в настройке

**Verdict:** ✅ **ВЫБРАННОЕ РЕШЕНИЕ**

---

### 2.6 WhisperX (Forced Alignment)

**Плюсы:**
- **Очень точные timestamps** (forced alignment с wav2vec2)
- Word-level точность ±50ms

**Минусы:**
- Двухэтапный процесс (Whisper + Alignment) = медленнее
- Больше памяти (две модели)
- Alignment model per language

**Verdict:** ⚠️ Хорошо для максимальной точности timestamps, но медленнее

---

### 2.7 Whisper-Timestamped

**Плюсы:**
- Встроенные word timestamps
- Проще чем WhisperX

**Минусы:**
- Чуть менее точные timestamps чем WhisperX
- Медленнее faster-whisper

**Verdict:** ⚠️ Fallback если faster-whisper timestamps недостаточно точные

---

## 3. Выбранная архитектура

### Core: Faster-Whisper (large-v3)

**Почему large-v3, а не small/medium?**
- Accuracy критичнее скорости (по требованиям)
- Large-v3: WER 8-10% vs Small: WER 15-20%
- Разница в скорости: 0.1x RTF vs 0.05x RTF
- Для 3-минутного трека: 18 сек vs 9 сек — приемлемо

### Fallback: Whisper-Timestamped
Если faster-whisper дает плохие timestamps — добавляем fallback.

### Language Detection
Автоопределение языка через faster-whisper (встроено).

---

## 4. Стоимость за запрос

### Предположения
- Средняя длина трека: 3 минуты (180 сек)
- RTF (Real-Time Factor) faster-whisper large-v3 на T4: ~0.1x
- Время обработки: 180 * 0.1 = 18 секунд

### Расчет для AWS g4dn.xlarge (T4 GPU)

**Характеристики:**
- GPU: NVIDIA T4 (16GB)
- CPU: 4 vCPU
- RAM: 16GB
- Цена: $0.526/час (ondemand) или ~$0.15/час (spot)

**Расчет:**
```
Цена за секунду GPU: $0.526 / 3600 = $0.000146
Время обработки 3-мин трека: 18 сек
Стоимость за трек: 18 * $0.000146 = $0.0026
```

**Итог: $0.0026 за 3-минутный трек**

### Сравнение с бюджетом

| Метод | Стоимость/3min | vs Бюджет ($0.05) |
|-------|----------------|-------------------|
| **Наше решение** | **$0.0026** | **19x ниже** ✅ |
| AssemblyAI | $0.045 | 1.1x ниже |
| Whisper API | $0.18 | 3.6x выше ❌ |
| Google STT | $0.72 | 14x выше ❌ |

### Масштабирование

**100 запросов/день:**
- Общее время GPU: 100 * 18 sec = 1800 sec = 0.5 часов
- Стоимость/день: 0.5 * $0.526 = $0.26
- Стоимость/месяц: $0.26 * 30 = **$7.80**

**10,000 запросов/день:**
- Общее время GPU: 10,000 * 18 sec = 180,000 sec = 50 часов
- Нужно: 3-4 GPU instances
- Стоимость/месяц: ~$800-1000 (вне текущего бюджета, но scale готов)

---

## 5. Что может пойти не так + Mitigations

### 5.1 Demucs артефакты

**Проблема:** Вокал после Demucs имеет артефакты на границах слов, особенно когда backing vocals.

**Влияние:** 
- WER может вырасти на 5-10%
- Timestamps на границах фраз менее точные

**Mitigation:**
- Pre-processing: light denoising (RNNoise)
- Post-processing: adjust timestamps based on audio energy
- Fallback к Whisper-Timestamped если CER > 15%

---

### 5.2 Мультивокал (leading + backing)

**Проблема:** Несколько голосов одновременно — STT путается.

**Влияние:**
- Hallucinated words (STT пытается сложить два голоса)
- Пропущенные слова

**Mitigation:**
- **Out of scope по ТЗ**, но если нужно:
- Demucs 4-stem (vocals + other) - отдельно обработать
- Или pyannote.audio для diarization (speaker separation)

---

### 5.3 Языковые смешения

**Проблема:** Песни с код-свичингом (например, K-pop: корейский + английский).

**Влияние:**
- Language detection может ошибиться
- Точность падает на втором языке

**Mitigation:**
- Force language parameter в API
- Multi-pass: detect primary language first

---

### 5.4 Каверы с другим текстом

**Проблема:** Музыканты делают каверы с измененным текстом.

**Влияние:**
- ShazamKit не найдет оригинал
- Нет ground truth для сравнения

**Mitigation:**
- Это **feature, not bug** — система должна работать с любым вокалом
- Нет ground truth = нет возможности проверить accuracy внешне
- Релизим результат как есть

---

### 5.5 Длинные треки (>5 мин)

**Проблема:** Memory usage растет, возможен OOM.

**Mitigation:**
- Chunk processing: 30-sec segments
- Оверлап 1 секунда для continuity
- Merge timestamps после обработки

---

### 5.6 Rate limiting на S3

**Проблема:** Presigned URL может истечь или иметь rate limits.

**Mitigation:**
- Проверить валидность URL перед скачиванием
- Retry с exponential backoff
- Если URL expired — вернуть 400 с понятной ошибкой

---

## 6. Железо и Infrastructure

### 6.1 Выбор железа

**AWS g4dn.xlarge (RECOMMENDED)**
- GPU: NVIDIA T4 (16GB) — достаточно для large-v3
- CPU: 4 vCPU — хватает для I/O
- RAM: 16GB — достаточно
- Цена: $0.526/hour on-demand, $0.15/hour spot
- **Why:** Лучший баланс цена/производительность для inference

**Альтернативы:**

| Инстанс | GPU | Цена/час | Почему нет |
|---------|-----|----------|------------|
| g4dn.2xlarge | T4 | $0.75 | Дороже, не нужен 2x GPU |
| p3.2xlarge | V100 | $3.06 | Слишком дорого |
| g5.xlarge | A10G | $1.006 | Быстрее, но дороже |

### 6.2 Self-hosted vs Cloud GPU

**RunPod / Vast.ai:**
- Цена: $0.20-0.30/hour для RTX 3090/4090
- Можно дешевле, но reliability ниже
- Подходит для стартапа

**AWS vs RunPod:**
- AWS: надежнее, но дороже
- RunPod: дешевле, но может не быть GPU

**Decision:** Начинаем с AWS spot instances для stability.

### 6.3 CPU fallback

Если GPU недоступна:
- faster-whisper работает на CPU
- RTF ~0.5-1.0x (3 мин трека обрабатывается 1.5-3 минуты)
- Приемлемо для low-traffic periods

---

## 7. Автоматическая оценка точности

### 7.1 Метрики

**Primary:**
- **CER** (Character Error Rate): Целевой < 15%
- **WER** (Word Error Rate): Целевой < 25%

**Secondary:**
- **Timestamp MAE** (Mean Absolute Error): Целевой < 200ms
- **Precision/Recall** на словах

### 7.2 Как оценивать без ground truth?

**Проблема:** Для каверов нет ground truth текстов.

**Решения:**

#### A. Для песен с известным текстом (есть ground truth)
```python
# Levenshtein distance
from jiwer import cer, wer

accuracy = 1 - cer(ground_truth, predicted)  # Чем ближе к 1, тем лучше
```

#### B. Для каверов без ground truth (self-consistency)
1. **Language model perplexity:** Проверяем, насколько текст похож на настоящий язык
   ```python
   from transformers import GPT2LMHeadModel
   # Низкая perplexity = хороший текст
   ```

2. **Cross-model consensus:** Сравниваем результаты 2-3 моделей
   - Если все модели согласны — высокая уверенность
   - Если различаются — flag for review

3. **Audio-text alignment:** Проверяем, что длина аудио соответствует длине текста
   - Средняя скорость речи: 2-3 слова/сек
   - Если получилось 10 слов/сек — явная ошибка

### 7.3 Автоматический пайплайн оценки

```python
def evaluate_quality(result, ground_truth=None):
    """Оценка качества распознавания."""
    
    if ground_truth:
        # Есть ground truth — честная оценка
        return calculate_cer_wer(result.text, ground_truth)
    else:
        # Нет ground truth — heuristics
        scores = {
            'perplexity': check_language_model_score(result.text),
            'speed_check': verify_speech_rate(result),
            'timestamp_continuity': check_timestamp_gaps(result.words),
            'confidence_mean': np.mean([w.confidence for w in result.words])
        }
        return aggregate_scores(scores)
```

### 7.4 Monitoring

**Метрики для дашборда:**
- Средний CER/WER по батчам
- % запросов с CER > 15% (error rate)
- Среднее время обработки
- GPU utilization
- Queue depth (если используем очередь)

**Alerts:**
- CER > 20% за последние 10 запросов
- GPU utilization > 95% (bottleneck)
- Queue depth > 10 (need to scale)

---

## 8. API Specification

### Endpoint

```
POST /api/v1/transcribe
Content-Type: application/json
```

### Request

```json
{
  "audio_url": "https://bucket.s3.amazonaws.com/vocals/...?X-Amz-Signature=...",
  "language": "auto",
  "options": {
    "word_timestamps": true,
    "format": "lrclib"
  }
}
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

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "DOWNLOAD_FAILED",
    "message": "Failed to download audio from S3 URL",
    "retryable": true
  }
}
```

### Error Codes

| Code | Description | Retryable |
|------|-------------|-----------|
| `INVALID_URL` | URL expired or invalid | No |
| `DOWNLOAD_FAILED` | Network error | Yes |
| `UNSUPPORTED_FORMAT` | Not m4a/mp3/wav | No |
| `NO_SPEECH_DETECTED` | Empty or instrumental | No |
| `LANGUAGE_NOT_SUPPORTED` | Not in FR/IT/RU/EN/PT/ES/JP/PL | No |
| `PROCESSING_TIMEOUT` > 60s | Yes |
| `INTERNAL_ERROR` | Unknown error | Yes |

---

## 9. Implementation Plan

### Phase 1: MVP (2 недели)
1. Faster-Whisper large-v3 на g4dn.xlarge
2. Поддержка 8 языков
3. Word-level timestamps
4. API endpoint
5. Basic monitoring (logs)

### Phase 2: Optimization (2 недели)
1. Batch processing для очереди
2. Cache frequently requested tracks
3. Optimize for Demucs artifacts
4. Add Whisper-Timestamped fallback

### Phase 3: Quality (2 недели)
1. Fine-tune на music dataset
2. Improve timestamp accuracy
3. Add confidence scores per word
4. Implement quality alerts

---

## 10. Summary

### Trade-offs

| Factor | Choice | Rationale |
|--------|--------|-----------|
| **Accuracy vs Cost** | Large-v3 model | Accuracy критичнее |
| **Speed vs Precision** | faster-whisper | 4x быстрее, та же точность |
| **Self-hosted vs API** | Self-hosted | 19x дешевле |
| **GPU vs CPU** | GPU (T4) | RTF 0.1x vs 0.5x |

### Final Recommendation

**Используем Faster-Whisper large-v3 на AWS g4dn.xlarge (или RunPod для экономии).**

- Стоимость: $0.0026/трек (6x ниже бюджета)
- Точность: WER ~10%, CER ~5%
- Latency: 18 сек на 3-мин трек
- Timestamps: word-level ±200ms
- Масштабирование: до 10000 запросов/день на 3-4 GPU

---

## Appendix A: Test Results

См. `results/comparison_results.json` для фактических замеров.

## Appendix B: Cost Calculator

```python
def calculate_monthly_cost(requests_per_day, avg_duration_sec=180):
    """
    Calculate monthly cost based on traffic.
    
    Args:
        requests_per_day: Daily request volume
        avg_duration_sec: Average track duration (default 180s = 3min)
    
    Returns:
        Monthly cost in USD
    """
    # Constants
    RTF = 0.1  # Real-time factor (faster-whisper on T4)
    GPU_COST_PER_HOUR = 0.526  # AWS g4dn.xlarge on-demand
    
    # Calculate
    daily_gpu_seconds = requests_per_day * avg_duration_sec * RTF
    daily_gpu_hours = daily_gpu_seconds / 3600
    monthly_gpu_hours = daily_gpu_hours * 30
    monthly_cost = monthly_gpu_hours * GPU_COST_PER_HOUR
    
    return monthly_cost

# Examples:
# 100 req/day: $7.80/month
# 1000 req/day: $78/month
# 10000 req/day: $780/month (need 3-4 instances)
```

---

**Document prepared by:** Team Lead Candidate  
**For:** Unbake Engineering Team  
**Date:** 2024
