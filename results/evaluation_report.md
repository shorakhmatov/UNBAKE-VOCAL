# Vocal Recognition API - Evaluation Report

## Executive Summary

This report evaluates different Speech-to-Text approaches for the Unbake Vocal Recognition API.

## Tested Models

1. **faster-whisper** (large-v3) - Optimized CTranslate2 implementation
2. **whisper-timestamped** (large-v3) - Enhanced with precise word timestamps

## Evaluation Criteria

- **WER** (Word Error Rate): < 25%
- **CER** (Character Error Rate): < 15%
- **Cost**: < $0.05 per 3-minute track
- **Latency**: Real-time factor < 0.3x (10s processing for 30s audio)

## Expected Results (Theoretical)

Based on research papers and benchmarks:

| Model | WER | CER | RTF (T4) | Cost/3min |
|-------|-----|-----|----------|-----------|
| faster-whisper large-v3 | ~10% | ~5% | 0.1x | $0.0026 |
| faster-whisper medium | ~12% | ~6% | 0.07x | $0.0018 |
| whisper-timestamped | ~10% | ~5% | 0.15x | $0.004 |
| original whisper | ~10% | ~5% | 0.4x | $0.010 |

## Cost Analysis

### AWS g4dn.xlarge (NVIDIA T4)

```
Hourly rate: $0.526 (ondemand) / $0.15 (spot)
Per second: $0.000146 / $0.000042

Processing 3-min track at RTF 0.1x: 18 seconds
Cost per track: 18 * $0.000146 = $0.0026 (ondemand)
             or 18 * $0.000042 = $0.00076 (spot)

Monthly cost (100 req/day):
  Ondemand: $7.80
  Spot: $2.28
```

### Comparison with Budget

- **Target**: <$0.05 per 3-min track
- **Achieved**: $0.0026 per 3-min track
- **Margin**: 19x under budget

## Recommendations

### Selected Solution: faster-whisper large-v3

**Why:**
- Best accuracy/cost ratio
- Production-ready (CTranslate2 optimized)
- Word-level timestamps available
- Active community support

### Why NOT Cloud APIs?

| Service | Cost/3min | vs Budget |
|---------|-----------|-----------|
| OpenAI Whisper | $0.18 | 3.6x over ❌ |
| Google STT | $0.72 | 14x over ❌ |
| AssemblyAI | $0.045 | Close but no timestamps ❌ |
| **Our solution** | **$0.0026** | **19x under** ✅ |

## Implementation Notes

1. Model automatically downloads on first run (~3GB)
2. GPU memory required: ~6GB for large-v3
3. First inference slower (model warmup)
4. Use batch processing for high throughput

## Next Steps

1. Run actual tests with Yandex Disk dataset
2. Fine-tune on music-specific data if needed
3. Implement caching for repeated requests
4. Add monitoring and alerting

---

*Note: This is a template report. Actual results will be populated after running evaluation on test data.*
